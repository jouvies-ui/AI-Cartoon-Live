/* Local Xiaoya Live2D player. Model/artwork and runtime credits: ./credits/NOTICE.md.
 * Parameter integration follows Andersen216's MIT-licensed beforeModelUpdate rig.
 * Mouth motion is measured from the audio being played, never a synthetic timer. */
'use strict';
const $=id=>document.getElementById(id), clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const expressionNames=WhaleCharacterRig.names;
const subtitleTrack=SubtitleTrack.create($('speech-caption'));
window.whaleSubtitleTrack=subtitleTrack;
let sid=null,busy=false,connecting=false,pageLeaving=false,request=null,model=null,app=null,core=null,manifest=null,ready=false,ctx=null,analyser=null,gain=null;
let measuredBounds=null,characterProfile=null,avatarView=null,avatarAppearance=null;
let faceState=WhaleCharacterRig.face('neutral',1),heldIntensity=.55,heldText='',heldSegment=-1,autoGesture=null,turnStill=false,phase='listening';
let emotionBeat=null;
let epoch=0,nextAudio=0,cues=[],sources=new Set(),actionQueue=[],activeAction=null,nativeMotion=null;
let lastFrame=performance.now(),mouth=0,lastSpeech=-100,heldExpression='neutral',gaze={x:0,y:0},aim={x:0,y:0};
let nextBlink=performance.now()+2600,blinkStart=-10000,weights={},defaults={},validParams=new Set(),parameterRanges={},lastLabel='';
const actionNames={},diagnostics={frames:0,audioChunks:0,audioSeconds:0,maxMouth:0,expressionSamples:{},actions:[],errors:[],modelReady:false,timeline:[],gestures:[]};
window.whaleDiagnostics=diagnostics;
const status=t=>$('status').textContent=t;
async function api(path,body={}){const r=await fetch('/api/local/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){let e=await r.json().catch(()=>({}));const error=Error(typeof e.detail==='string'?e.detail:e.detail?.message|| (Array.isArray(e.detail)?e.detail.map(x=>x.msg).join('；'):'请求失败'));error.status=r.status;error.code=e.detail?.code;throw error;}return r.json();}
function controls(){$('connect').disabled=!!sid||!ready||connecting;$('takeover').disabled=!!sid||!ready||connecting;$('disconnect').disabled=!sid;$('interrupt').disabled=!sid;$('send').disabled=!sid||busy;document.querySelectorAll('#actions button').forEach(b=>b.disabled=!sid);}
function message(role,text=''){const box=document.createElement('div');box.className='message';const label=document.createElement('b');label.textContent=role;const p=document.createElement('p');p.textContent=text;box.append(label,p);$('messages').append(box);$('messages').scrollTop=$('messages').scrollHeight;return p;}
function setupAudio(){if(!ctx){ctx=new AudioContext();analyser=ctx.createAnalyser();analyser.fftSize=512;gain=ctx.createGain();analyser.connect(gain);gain.connect(ctx.destination);gain.gain.value=+$('volume').value;}return ctx.resume();}
$('volume').oninput=()=>{if(gain)gain.gain.setTargetAtTime(+$('volume').value,ctx.currentTime,.03);};
async function queueAudio(event,myEpoch){
 const bytes=Uint8Array.from(atob(event.wav),c=>c.charCodeAt(0));
 const buffer=await ctx.decodeAudioData(bytes.buffer);if(myEpoch!==epoch||!sid)return;
 const start=Math.max(ctx.currentTime+.07,nextAudio+clamp(Number(event.pause_before_ms)||0,0,500)/1000),end=start+buffer.duration;nextAudio=end;
 const src=ctx.createBufferSource();src.buffer=buffer;src.connect(analyser);sources.add(src);
 src.onended=()=>{sources.delete(src);src.disconnect();if(myEpoch===epoch&&!sources.size&&!busy&&sid)status('已连接，可以提问');};
 const planned=Array.isArray(event.performance_cues)&&event.performance_cues.length?event.performance_cues:[{...event,start_ratio:0,end_ratio:1}];
 for(const cue of planned){
  const cueStart=start+clamp(Number(cue.start_ratio)||0,0,1)*buffer.duration,cueEnd=start+clamp(Number(cue.end_ratio)||1,0,1)*buffer.duration;
  if(cueEnd<=cueStart)continue;
  cues.push({start:cueStart,end:cueEnd,expression:cue.expression||'neutral',intensity:cue.intensity??.55,gesture:cue.gesture||'none',segment:cue.segment??0,text:cue.text||'',actions:cue.actions||[],delivery:event.delivery||null,acted:false});
 }
 src.start(start);diagnostics.audioChunks++;diagnostics.audioSeconds+=buffer.duration;
}

function clearMotion(){if(!model||!nativeMotion)return;model.internalModel.motionManager.stopAllMotions();for(const id of manifest.motions[nativeMotion.group]?.params||[]){if(defaults[id]!==undefined)core.setParameterValueById(id,defaults[id]);}core.saveParameters();nativeMotion=null;}
function stopPlayback(){epoch++;if(request)request.abort();request=null;for(const src of sources){try{src.stop();}catch{}src.disconnect();}sources.clear();cues=[];nextAudio=0;mouth=0;emotionBeat=null;lastSpeech=-100;heldExpression='neutral';heldIntensity=.55;heldText='';heldSegment=-1;autoGesture=null;turnStill=false;actionQueue=[];activeAction=null;clearMotion();busy=false;controls();}
function enqueueActions(names){if(names.includes('neutral')){actionQueue=[];activeAction=null;clearMotion();weights={};return;}actionQueue=names.filter(n=>actionNames[n]);}
function startAction(name,now){const group={selfie:'selfie'}[name];let duration=name==='blink'?.65:2.8;if(group){clearMotion();const meta=manifest.motions[group];duration=meta.duration;nativeMotion={group,until:now+duration*1000};model.motion(group,0,3).catch(e=>{diagnostics.errors.push(String(e));status('动作未能播放');});}activeAction={name,start:now,end:now+duration*1000};diagnostics.actions.push(name);}
function set(id,value){if(validParams.has(id)){const range=parameterRanges[id];core.setParameterValueById(id,range?clamp(value,range.min,range.max):value);}}
function add(id,value){if(validParams.has(id))core.addParameterValueById(id,value);}
const samples=new Float32Array(512);
function rig(){
 const now=performance.now(),dt=clamp((now-lastFrame)/1000,0,.08);lastFrame=now;diagnostics.frames++;
 const at=ctx?.currentTime||0,current=cues.find(c=>at>=c.start&&at<c.end);cues=cues.filter(c=>c.end>at-1);
 if(current){
  lastSpeech=at;heldExpression=current.expression;heldIntensity=current.intensity;heldText=current.text;
  if(!current.acted){
   emotionBeat=WhaleCharacterRig.beginBeat(emotionBeat,current);
   if(current.segment!==heldSegment){autoGesture=null;heldSegment=current.segment;}
   if(current.actions.length)enqueueActions(current.actions);
   if(current.gesture!=='none'&&current.expression!=='still'){
    autoGesture={name:current.gesture,start:at+.12,end:Math.min(current.end,at+1.65),strength:heldIntensity};
    diagnostics.gestures.push({name:current.gesture,text:current.text,at});
   }
   diagnostics.timeline.push({segment:current.segment,text:current.text,expression:current.expression,intensity:current.intensity,start:current.start,end:current.end,playedAt:at,delivery:current.delivery});
   if(diagnostics.timeline.length>100)diagnostics.timeline.shift();
   if(diagnostics.gestures.length>100)diagnostics.gestures.shift();
   current.acted=true;
  }
 }
 const speaking=!!current;
 // Keep the last attitude through synthesis gaps and briefly after speech ends.
 phase=speaking?'speaking':busy?(heldText?'between-segments':'thinking'):(at-lastSpeech<3.6?'settling':'listening');
 let expression=speaking||phase==='between-segments'||phase==='settling'?heldExpression:phase==='thinking'?'thoughtful':'listening';
 if(turnStill)expression='still';
 let intensity=phase==='thinking'?.42:phase==='listening'?.2:heldIntensity;

 if(activeAction&&now>=activeAction.end){activeAction=null;clearMotion();}
 if(!activeAction&&actionQueue.length)startAction(actionQueue.shift(),now);
 const action=activeAction?.name||'neutral';let e=expression;
 if(action==='smile'){e='warm';intensity=.8;}if(action==='frown'){e='concerned';intensity=.8;}if(action==='surprise'){e='surprised';intensity=.85;}
 const still=expression==='still';
 if(!nativeMotion){for(const id of ['bi','pointZ'])add(id,1);}
 const age=activeAction?(now-activeAction.start)/1000:emotionBeat?at-emotionBeat.start:10;
 const recovery=phase==='settling'?at-lastSpeech:0;
 const dynamics=WhaleCharacterRig.sample(e,intensity,age,recovery,activeAction?1:emotionBeat?.accent??1);
 const target=still?faceState:dynamics.face;
 // Fast enough for a readable onset; slow release preserves a mild expression.
 const smoothing=dynamics.stage==='rising'||dynamics.stage==='peak'?11:phase==='listening'?2.6:5;
 for(const key of Object.keys(target))faceState[key]+=(target[key]-faceState[key])*(1-Math.exp(-dt*smoothing));
 if(!nativeMotion)for(const [id,value] of Object.entries(faceState))if(id!=='tilt'&&!id.includes('Eye'))set(id,value);
 let rms=0;if(analyser&&speaking){analyser.getFloatTimeDomainData(samples);for(const s of samples)rms+=s*s;rms=Math.sqrt(rms/samples.length);}
 const targetMouth=speaking?clamp((rms-.009)*7.2,0,.82):0;mouth+=(targetMouth-mouth)*(1-Math.exp(-dt*(targetMouth>mouth?25:19)));
 if(speaking||!nativeMotion)set('ParamMouthOpenY',mouth);
 diagnostics.maxMouth=Math.max(diagnostics.maxMouth,mouth);
 gaze.x+=(aim.x-gaze.x)*dt*3;gaze.y+=(aim.y-gaze.y)*dt*3;
 if(!nativeMotion){
  const t=now/1000,a=activeAction?clamp((now-activeAction.start)/(activeAction.end-activeAction.start),0,1):0,envelope=Math.sin(Math.PI*a);
  const calm=['concerned','sad','firm','angry'].includes(e)?.38:.7;
  let x=still?0:calm*Math.sin(t*.6)+gaze.x*4,y=still?0:.5*Math.sin(t*.8)+gaze.y*2,z=still?0:.6*Math.sin(t*.45)+faceState.tilt;
  if(e==='thoughtful'&&!still){x+=2.2;y-=1.1;}
  if(e==='shy'&&!still)y-=1.8*intensity;
  if(autoGesture&&!activeAction&&!still){
   const g=WhaleCharacterRig.pose(autoGesture.name,(at-autoGesture.start)/(autoGesture.end-autoGesture.start),autoGesture.strength);
   x+=g.x;y+=g.y;z+=g.z;
  }
  if(action==='nod')y+=11*Math.sin(a*Math.PI*4)*envelope;
  if(action==='shake')x+=14*Math.sin(a*Math.PI*4)*envelope;
  if(action==='look_left')x-=16*envelope;if(action==='look_right')x+=16*envelope;
  set('ParamAngleX',x);set('ParamAngleY',y);set('ParamAngleZ',z);set('ParamEyeBallX',clamp(x/30,-.65,.65));set('ParamEyeBallY',clamp(y/30,-.45,.45));
  if(!still&&now>nextBlink){blinkStart=now;nextBlink=now+3100+Math.random()*2400;}
  const blinkPhase=(now-blinkStart)/190;
  let blink=blinkPhase>=0&&blinkPhase<=1?Math.sin(Math.PI*blinkPhase):0;
  if(action==='blink')blink=Math.sin(Math.PI*clamp(a/.65,0,1));
  set('ParamEyeLOpen',faceState.ParamEyeLOpen*(still?1:1-blink));set('ParamEyeROpen',faceState.ParamEyeROpen*(still?1:1-blink));
 }
 const label=action!=='neutral'?(actionNames[action]||action):expressionNames[phase==='thinking'?'thinking':expression]||'认真听你说';
 if(label!==lastLabel){$('action-status').textContent=label;lastLabel=label;}
 subtitleTrack.show(speaking&&heldText?heldText:phase==='thinking'?'让我想一想…':(location.pathname==='/local/broadcast'?'':'眨眼、看向你，也会认真听你说话'),current?(at-current.start)/(current.end-current.start):0);
 if(speaking)diagnostics.expressionSamples[expression]=(diagnostics.expressionSamples[expression]||0)+1;
 window.whaleState={speaking,expression,phase,intensity,emotionStage:still?'held':dynamics.stage,emotionPeak:dynamics.peak,delivery:current?.delivery||null,segment:heldSegment,text:speaking?heldText:'',gesture:autoGesture&&!activeAction&&at>=autoGesture.start&&at<autoGesture.end?autoGesture.name:'none',face:{...faceState},action,mouth,rms,pending:actionQueue.slice(),audioQueue:sources.size,busy,sid,ready};
}

async function fitModel(){
 if(avatarView){avatarView.resize();return;}
 const host=$('canvas-wrap'),w=host.clientWidth,h=host.clientHeight;app.renderer.resize(w,h);
 if(!measuredBounds){
  model.scale.set(1);model.position.set(0);const initial=Math.min(w/model.width,h/model.height);model.scale.set(initial);app.renderer.render(app.stage);
  // WebGL readPixels uses a bottom-left origin. Measure the displayed canvas
  // in top-left coordinates so portrait layouts don't crop the character.
  const probe=document.createElement('canvas');probe.width=app.view.width;probe.height=app.view.height;
  const probeContext=probe.getContext('2d');probeContext.drawImage(app.view,0,0);
  const rw=probe.width,rh=probe.height,pixels=probeContext.getImageData(0,0,rw,rh).data;let x0=rw,y0=rh,x1=0,y1=0;
  for(let y=0;y<rh;y+=2)for(let x=0;x<rw;x+=2)if(pixels[(y*rw+x)*4+3]>25){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}
  if(x1<=x0||y1<=y0)throw Error('模型没有可见画面');const res=app.renderer.resolution;
  measuredBounds={x:x0/res/initial,y:y0/res/initial,w:(x1-x0)/res/initial,h:(y1-y0)/res/initial};diagnostics.bounds=measuredBounds;
 }
 const box=measuredBounds,scale=Math.min(w*.86/box.w,h*.84/box.h);model.scale.set(scale);model.position.set((w-box.w*scale)/2-box.x*scale,(h-box.h*scale)/2-box.y*scale);
}

async function init(){try{
 const appearanceResponse=await fetch('/api/local/appearance');if(!appearanceResponse.ok)throw Error('形象配置未能加载');avatarAppearance=await appearanceResponse.json();
 $('avatar-subtitle').textContent=avatarAppearance.label+' · 本地语音伙伴';document.querySelector('.stage').setAttribute('aria-label',avatarAppearance.label+'动画');document.querySelector('.badge').textContent=avatarAppearance.source;
 $('whale-credits').hidden=false;
 {if(!window.PIXI?.live2d||!window.Live2DCubismCore)throw Error('Live2D运行库未能加载');manifest=await (await fetch('/local-assets/model/manifest.json')).json();app=new PIXI.Application({width:600,height:600,backgroundAlpha:0,antialias:true,preserveDrawingBuffer:true,resolution:Math.min(devicePixelRatio||1,1.5),autoDensity:true,powerPreference:'low-power'});app.ticker.maxFPS=30;$('canvas-wrap').append(app.view);PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);model=await PIXI.live2d.Live2DModel.from('/local-assets/model/c_0120.model3.json',{autoInteract:false,autoUpdate:true,idleMotionGroup:'idle'});app.stage.addChild(model);core=model.internalModel.coreModel;model.internalModel.eyeBlink=undefined;model.internalModel.on('beforeModelUpdate',rig);}
 const p=core._model.parameters;for(let i=0;i<p.ids.length;i++){validParams.add(p.ids[i]);defaults[p.ids[i]]=p.defaultValues[i];parameterRanges[p.ids[i]]={min:p.minimumValues[i],max:p.maximumValues[i]};}await new Promise(r=>setTimeout(r,300));await fitModel();ready=true;diagnostics.modelReady=true;$('loading').style.display='none';status('形象就绪，点击开始聊天');controls();let timer;new ResizeObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>fitModel().catch(console.error),120);}).observe($('canvas-wrap'));
 const catalog=await (await fetch('/api/local/actions')).json();for(const a of catalog.actions){actionNames[a.id]=a.label;const b=document.createElement('button');b.type='button';b.textContent=a.label;b.dataset.action=a.id;b.disabled=!sid;b.onclick=async()=>{try{const r=await api('action',{sessionid:sid,actions:[a.id]});enqueueActions(r.actions);}catch(e){status(e.message);}};$('actions').append(b);}
 }catch(e){diagnostics.errors.push(String(e));$('loading').textContent='形象加载失败';status(e.message);$('retry').style.display='inline-block';}}
$('retry').onclick=()=>location.reload();
$('canvas-wrap').onpointermove=e=>{const r=e.currentTarget.getBoundingClientRect();aim.x=clamp((e.clientX-r.left)/r.width*2-1,-1,1);aim.y=clamp(1-(e.clientY-r.top)/r.height*2,-1,1);};$('canvas-wrap').onpointerleave=()=>{aim={x:0,y:0};};
async function startChat(takeover=false){
 if(connecting||sid||!ready)return;
 connecting=true;controls();status('正在连接…');
 try{
  await setupAudio();const r=await api('connect',{takeover});
  if(pageLeaving){await api('close',{sessionid:r.sessionid});return;}
  sid=r.sessionid;$('takeover').hidden=true;status('已连接，可以提问');
  if(typeof BroadcastChannel!=='undefined'){const channel=new BroadcastChannel('local-studio');channel.postMessage({type:'private-chat',sessionid:sid});channel.close();}
 }catch(e){
  status(e.message);$('takeover').hidden=!['live_in_use','chat_in_use'].includes(e.code);
  $('takeover').textContent=e.code==='live_in_use'?'结束直播互动并在此聊天':'释放旧连接并在此聊天';
 }finally{connecting=false;controls();}
}
$('connect').onclick=()=>startChat();
$('takeover').onclick=()=>startChat(true);
async function close(){const id=sid;sid=null;stopPlayback();if(id)await api('close',{sessionid:id}).catch(()=>{});status('已断开');controls();}
$('disconnect').onclick=close;
$('interrupt').onclick=async()=>{if(!sid)return;stopPlayback();try{await api('interrupt',{sessionid:sid});status('已打断，可以继续提问');}catch(e){status(e.message);}};
$('form').onsubmit=async e=>{e.preventDefault();const text=$('text').value.trim();if(!sid||!text||busy)return;await setupAudio();stopPlayback();const myEpoch=epoch;message('你',text);const reply=message($('mode').value==='say'?'朗读':characterProfile?.name||'伙伴');$('text').value='';busy=true;controls();status('正在想怎么回答…');const aborter=new AbortController();request=aborter;let turnError='';
 try{const r=await fetch('/api/local/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sessionid:sid,text,mode:$('mode').value}),signal:aborter.signal});if(!r.ok){const err=await r.json();throw Error(err.detail||'请求失败');}const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';while(true){const {value,done}=await reader.read();if(epoch!==myEpoch)break;buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});let cut;while((cut=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,cut);buffer=buffer.slice(cut+1);if(!line)continue;const event=JSON.parse(line);if(event.event==='character_updated'){renderCharacter(event);reply.previousElementSibling.textContent=event.profile.name;$('character-status').textContent+=' 默认角色设置已保存。';}if(event.event==='text'){reply.textContent+=event.delta;$('messages').scrollTop=$('messages').scrollHeight;}if(event.event==='done'&&Number.isInteger(event.remembered_turns)&&characterProfile?.remember){$('character-status').textContent=`保留最近 ${characterProfile.memory_turns} 轮，已记住 ${event.remembered_turns} 轮。`;}if(event.event==='audio')window.whaleLastLatency=event;if(event.event==='plan'){status('回答已就绪，正在准备声音…');window.whaleLastPlan=event;turnStill=event.segments.some(s=>s.expression==='still');}if(event.event==='audio_chunk'){await queueAudio(event,myEpoch);if(epoch!==myEpoch)break;status('正在说话…');}if(event.event==='action'&&!event.scheduled){enqueueActions(event.actions);reply.textContent=event.actions.map(x=>actionNames[x]).join(' → ');}if(event.event==='error')throw Error(event.detail);}if(done)break;}
 }catch(err){if(err.name!=='AbortError'&&epoch===myEpoch){turnError=err.message;status(turnError);reply.textContent+='\n'+turnError;}}
 finally{if(epoch===myEpoch){busy=false;request=null;controls();status(turnError||(sources.size?'语音播放中，可继续提问或打断':'已连接，可以提问'));}}};
$('text').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('form').requestSubmit();}};
window.addEventListener('pagehide',()=>{pageLeaving=true;if(location.pathname==='/local/broadcast')return;const id=sid;sid=null;stopPlayback();if(id)navigator.sendBeacon('/api/local/close',new Blob([JSON.stringify({sessionid:id})],{type:'application/json'}));});
window.addEventListener('pageshow',()=>{pageLeaving=false;controls();if(location.pathname!=='/local/broadcast'&&!sid&&ready)status('形象就绪，点击开始聊天');});
init();
loadCharacter().catch(e=>{$('character-status').textContent=e.message;});

setInterval(async()=>{const id=sid;if(!id||location.pathname==='/local/broadcast'||pageLeaving)return;try{await api('status',{sessionid:id});}catch(e){if(sid===id&&e.status===404){sid=null;stopPlayback();status('连接已释放或已在其他页面切换，可重新开始聊天');}}},15000);

async function loadCharacter(){
 const r=await fetch('/api/local/character');if(!r.ok)throw Error('角色设置暂不可用');
 renderCharacter(await r.json());
}
function renderCharacter(data){
 characterProfile=data.profile;
 const voices=data.voices||[];$('character-voice').replaceChildren(...voices.map(v=>{const o=document.createElement('option');o.value=v.id;o.textContent=v.label+'（'+v.id+'）';return o;}));
 $('character-voice').value=characterProfile.voice_template;
 $('character-voice-label').textContent=voices.find(v=>v.id===characterProfile.voice_template)?.label||'模板未安装';
 $('character-name').value=characterProfile.name;$('character-personality').value=characterProfile.personality;
 $('character-style').value=characterProfile.speaking_style;$('character-strength').value=characterProfile.expression_strength;
 $('character-gestures').checked=characterProfile.auto_gestures;$('character-remember').checked=characterProfile.remember;
 $('character-turns').value=characterProfile.memory_turns;
 $('character-status').textContent=characterProfile.remember?`保留最近 ${characterProfile.memory_turns} 轮，已记住 ${data.remembered_turns} 轮。`:'断开后不保留对话。';
 $('character-title').textContent=characterProfile.name+' · 本地伙伴';document.title=characterProfile.name+' · 本地伙伴';
}
$('character-save').onclick=async()=>{try{
 const profile={name:$('character-name').value,personality:$('character-personality').value,speaking_style:$('character-style').value,
 voice_template:$('character-voice').value,expression_strength:Number($('character-strength').value),auto_gestures:$('character-gestures').checked,
 remember:$('character-remember').checked,memory_turns:Number($('character-turns').value)};
 await api('character',profile);await loadCharacter();$('character-status').textContent+=' 设置已保存，下一轮生效。';
}catch(e){$('character-status').textContent=typeof e.message==='string'?e.message:'设置保存失败';}};
$('memory-clear').onclick=async()=>{try{await api('memory/clear');await loadCharacter();$('character-status').textContent='对话记忆已清除。';}catch(e){$('character-status').textContent=e.message;}};

$('character-export').onclick=async()=>{try{
 const r=await fetch('/api/local/character/export');if(!r.ok)throw Error('模板导出失败，请检查声线设置');
 const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download='character-template.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 $('character-status').textContent='角色模板已导出，不包含聊天记录或连接密钥。';
}catch(e){$('character-status').textContent=e.message;}};
$('character-import').onclick=()=>$('character-file').click();
$('character-file').onchange=async e=>{try{
 const file=e.target.files[0];if(!file)return;if(file.size>32768)throw Error('角色模板超过32KB');
 const data=await api('character/import',JSON.parse(await file.text()));renderCharacter(data);
 $('character-status').textContent+=' 模板已导入，当前对话记忆保留。';
}catch(e){$('character-status').textContent=e.message;}finally{e.target.value='';}};

// A deliberate switch in the settings page also stops audio in other chat tabs.
if(location.pathname!=='/local/broadcast' && typeof BroadcastChannel!=='undefined'){
 let studioModeChannel;
 function listenMode(){if(studioModeChannel)return;studioModeChannel=new BroadcastChannel('local-studio');studioModeChannel.onmessage=async e=>{
  if(e.data==='audience-mode'){await close();status('已切换到直播互动，私人聊天记忆保留。');}
  if(e.data?.type==='private-chat'&&sid&&e.data.sessionid!==sid){await close();status('已切换到另一个聊天页面，记忆保留。');}
 };}
 listenMode();window.addEventListener('pageshow',listenMode);
 window.addEventListener('pagehide',()=>{studioModeChannel?.close();studioModeChannel=null;});
}
