'use strict';
const $=id=>document.getElementById(id);let savedStudio=null,voiceCatalog=[];
function note(text,error=false){$('feedback').textContent=text;$('feedback').classList.toggle('error',error);}
async function request(path,body){const r=await fetch('/api/local/'+path,body===undefined?{cache:'no-store',signal:AbortSignal.timeout(35000)}:{signal:AbortSignal.timeout(35000),method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('；'):'请求失败');return data;}
function action(id,fn){$(id).onclick=async()=>{const b=$(id);b.disabled=true;try{await fn();}catch(e){note(e.message,true);}finally{b.disabled=false;}};}
function form(id,fn){$(id).onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await fn();}catch(e){note(e.message,true);}finally{b.disabled=false;}};}
for(const button of document.querySelectorAll('[data-tab]'))button.onclick=()=>{for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b===button));for(const p of document.querySelectorAll('[data-panel]'))p.hidden=p.dataset.panel!==button.dataset.tab;note('');history.replaceState(null,'','#'+button.dataset.tab);};
if(location.hash)document.querySelector('[data-tab="'+location.hash.slice(1).replace(/[^a-z]/g,'')+'"]')?.click();
window.addEventListener('hashchange',()=>document.querySelector('[data-tab="'+location.hash.slice(1).replace(/[^a-z]/g,'')+'"]')?.click());
function fields(ids){return Object.fromEntries(ids.map(id=>{const e=$(id);return [id,e.type==='checkbox'?e.checked:e.type==='number'||e.type==='range'?Number(e.value):e.value.trim()];}));}
const characterFields=['name','personality','speaking_style','expression_strength','memory_turns','auto_gestures','remember'];
async function loadCharacter(){const data=await request('character'),p=data.profile;for(const id of characterFields){const e=$(id);if(e.type==='checkbox')e.checked=p[id];else e.value=p[id];}voiceCatalog=data.voices;const groups=new Map();for(const v of voiceCatalog){const group=v.category||'已安装声线';if(!groups.has(group)){const g=document.createElement('optgroup');g.label=group;groups.set(group,g);}const o=document.createElement('option');o.value=v.id;o.textContent=v.label;groups.get(group).append(o);}$('voice').replaceChildren(...groups.values());$('voice').value=p.voice_template;updateVoiceSample();$('memory-info').textContent=p.remember?`已记住 ${data.remembered_turns} 轮私人对话；直播使用独立的临时上下文。`:'私人聊天断开后不保留；当前连接中的上下文仍可用。';}
let voicePreviewURL=null,lastSample='';
function updateVoiceSample(){const voice=voiceCatalog.find(v=>v.id===$('voice').value);if(!voice)return;const sample=voice.preview_text||'你好，很高兴见到你。';if(!$('voice-preview-text').value||$('voice-preview-text').value===lastSample)$('voice-preview-text').value=sample;lastSample=sample;$('voice-language-note').textContent=voice.language==='en'?'英文声线，可自行输入中文试听跨语言效果。':'中文或参考录音声线。试听不会自动改变默认声线，选择后请保存。';}
$('voice').onchange=()=>{const player=$('voice-preview');player.pause();updateVoiceSample();};
action('preview-voice',async()=>{
 note('正在生成试听…');const player=$('voice-preview');player.pause();
 const response=await fetch('/api/tts/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({voice:$('voice').value,text:$('voice-preview-text').value.trim()||lastSample})});
 if(!response.ok){const data=await response.json();throw Error(typeof data.detail==='string'?data.detail:'试听失败');}
 if(voicePreviewURL)URL.revokeObjectURL(voicePreviewURL);voicePreviewURL=URL.createObjectURL(await response.blob());player.src=voicePreviewURL;player.hidden=false;
 await player.play().catch(()=>{});note('试听已生成。点击“保存角色设置”后，将用于后续聊天和直播。');
});
async function loadVoiceEngine(){const r=await fetch('/api/tts/voices',{cache:'no-store'});if(!r.ok)return;const data=await r.json();const clone=data.engine==='hojo'&&data.variant==='80m';$('voice-import-form').hidden=!clone;$('voice-engine').textContent=clone?`本机 CPU 配音 · 已开放 ${data.voices.length} 种声线。Hojo 80M 用于参考录音，Hojo 40M 提供全部15种预置音色。选择后可试听并保存。`:data.engine==='hojo'?'Hojo 40M · 本机 CPU 配音。已开放全部15种预设。':'使用已配置的固定声音服务。';}
form('voice-import-form',async()=>{
 const file=$('voice-recording').files[0];if(!file)throw Error('请选择参考录音');
 if(file.size>10*1024*1024)throw Error('录音文件不能超过10MB');
 note('正在导入录音声线…');
 const audio_base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('录音读取失败'));reader.readAsDataURL(file);});
 const data=await request('voices/import',{label:$('voice-label').value.trim(),transcript:$('voice-transcript').value.trim(),audio_base64});
 const option=document.createElement('option');option.value=data.id;option.textContent=data.label;
 $('voice').append(option);$('voice').value=data.id;
 voiceCatalog.push({id:data.id,label:data.label,language:'zh',category:'参考录音声线 · Hojo 80M'});updateVoiceSample();
 $('voice-recording').value='';note('声线已导入并选中。请点击“试听所选声线”，满意后点击“保存角色设置”。');
 $('voice').scrollIntoView({behavior:'smooth',block:'center'});
});
window.addEventListener('pagehide',()=>{if(voicePreviewURL)URL.revokeObjectURL(voicePreviewURL);});
function flags(data){for(const [key,id] of [['douyin_cookie','cookie-state'],['collector_token','token-state'],['obs_password','obs-password-state'],['stream_key','stream-key-state']])$(id).textContent=data[key+'_set']?'已保存，留空保持原值。':'尚未填写。';}
async function loadStudio(){const data=await request('studio');savedStudio=data.settings;for(const [id,value] of Object.entries(savedStudio)){const e=$(id);if(!e)continue;if(e.type==='checkbox')e.checked=value;else if(id==='blocked_words')e.value=value.join('\n');else e.value=value;}$('stage_url').value=savedStudio.stage_url||location.origin+'/local/broadcast';flags(data.secrets);$('douyin_cookie').disabled=!data.managed_collector;$('collector-info').textContent=data.managed_collector?'本机采集插件与访问令牌已配置，通常只需填写直播间。':'使用外部采集插件；Cookie需在该插件所在机器配置。';$('relay-url').textContent=location.origin+'/api/danmaku';renderStatus(data.runtime);}
form('character-form',async()=>{await request('character',{...fields(characterFields),voice_template:$('voice').value});await loadCharacter();note('角色设置已保存。');});
action('clear-memory',async()=>{await request('memory/clear',{});await loadCharacter();note('私人对话记忆已清除。');});
action('export-character',async()=>{const data=await request('character/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='character-template.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);note('角色模板已导出，不包含聊天或直播凭据。');});
action('import-character',async()=>{$('template-file').click();});
$('template-file').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>32768)throw Error('模板超过32KB');await request('character/import',JSON.parse(await f.text()));await loadCharacter();note('角色模板已导入，私人对话记忆保留。');}catch(e){note(e.message,true);}finally{e.target.value='';}};
async function saveStudio(ids){if(!savedStudio)throw Error('设置尚未加载');const values=fields(ids);if('blocked_words' in values)values.blocked_words=values.blocked_words.split('\n').map(x=>x.trim()).filter(Boolean);await request('studio',{...savedStudio,...values});await loadStudio();note('直播设置已保存；启用中的采集连接已按新设置重连。');}
const liveFields=['room','collector_url','input_mode','answer_chat','read_chat','thank_gifts','reply_gap','max_chars','blocked_words'];
function liveSettings(){if(!savedStudio)throw Error('设置尚未加载');const v=fields(liveFields);v.blocked_words=v.blocked_words.split('\n').map(x=>x.trim()).filter(Boolean);return {...savedStudio,...v};}
let previewOpened=false;
function openPreview(s){if(s.player_connected)return;if(previewOpened)return;previewOpened=true;$('inline-preview').hidden=false;$('studio-preview').src='/local/broadcast';}
function closePreview(){previewOpened=false;$('studio-preview').removeAttribute('src');$('inline-preview').hidden=true;}
async function startStudio(collect){
 note(collect?'正在保存并连接直播间…':'正在准备本地演练…');$('live-state-title').textContent=collect?'正在连接，请稍候…':'正在打开演练画面…';
 const data=await request('studio/start',collect?{settings:liveSettings(),collect:true}:{collect:false});
 if(collect){savedStudio=data.settings;$('room').value=data.settings.room;}
 try{const channel=new BroadcastChannel('local-studio');channel.postMessage('audience-mode');channel.close();}catch{}
 openPreview(data.runtime);renderStatus(data.runtime);$('live-state-title').scrollIntoView({behavior:'smooth',block:'start'});
 note(data.runtime.player_connected?'已使用当前直播画面。请查看下方状态，可发送模拟弹幕验证。':'互动画面正在打开。若提示声音未启用，请点击画面中的按钮，再发送模拟弹幕。');
}
form('live-form',()=>startStudio(true));
action('save-live',()=>saveStudio(liveFields));
action('rehearse',()=>startStudio(false));
action('operator-say',async()=>{
 const text=$('operator-text').value.trim();
 if(!text)throw Error('请输入要口播的文字');
 $('operator-state').textContent='正在插入口播队列…';
 const data=await request('studio/say',{text});
 $('operator-state').textContent=data.interrupted?'已打断当前互动，主播口播已优先安排。':'主播口播已进入最高优先级队列。';
 $('operator-text').value='';
 await refresh();
});
action('operator-clear',()=>{$('operator-text').value='';$('operator-state').textContent='';});
action('close-preview',async()=>{closePreview();note('本页画面已关闭，可以让 OBS 加载直播画面地址。声音就绪后才会处理新消息。');});
$('room').addEventListener('input',()=>{$('room-check-result').hidden=true;});
action('room-check',async()=>{
 $('room-check-result').hidden=false;$('room-check-result').textContent='正在查询抖音房间，请稍候…';
 try{const d=await request('studio/room-check',{room:$('room').value.trim()});$('room-check-result').textContent=[d.anchor?'主播：'+d.anchor:'',d.title?'标题：'+d.title:'',d.detail].filter(Boolean).join(' · ');}
 catch(e){$('room-check-result').textContent=e.message;throw e;}
});
function testResult(data){return data.queued?'模拟弹幕已入队，等待人物回答和播放完成。':({duplicate:'这条模拟消息刚刚发过，请稍等或换一条。',filtered:'这条消息被过滤，请检查自动回答开关、字数上限或过滤词。',no_audio_player:'画面声音尚未就绪，请先启用声音。',disabled:'互动已暂停。'}[data.reason]||'消息没有进入队列，请查看互动状态。');}
form('quick-test-form',async()=>{const data=await request('studio/test',{kind:'chat',text:$('quick-test-text').value});note(testResult(data),!data.queued);await refresh();});
form('obs-form',()=>saveStudio(['orientation','background','subtitles','stage_url','obs_url','obs_scene','stream_server']));
async function saveSecrets(ids){const values=fields(ids);for(const key of Object.keys(values))if(!values[key])delete values[key];if(!Object.keys(values).length){note('没有填写新的凭据，保留原值。');return;}const data=await request('studio/secrets',values);flags(data.secrets);for(const id of ids)$(id).value='';note('凭据已保存，不会在页面回显。');}
form('collector-secrets',()=>saveSecrets(['douyin_cookie','collector_token']));form('obs-secrets',()=>saveSecrets(['obs_password','stream_key']));
action('clear-cookie',async()=>{const data=await request('studio/secrets',{douyin_cookie:''});flags(data.secrets);note('已清除Cookie，采集插件改用匿名访问。');});
action('collector-check',async()=>{note('正在检测采集器…');const data=await request('studio/collector-check',{});note(data.detail);});
for(const id of ['pause','test-stop'])action(id,async()=>{renderStatus(await request('studio/pause',{}));closePreview();note('互动已暂停，当前语音已打断。OBS推流状态不受此按钮控制。');});
action('copy-stage',async()=>{const value=$('stage_url').value;if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(value);else{$('stage_url').focus();$('stage_url').select();if(!document.execCommand('copy'))throw Error('画面地址已选中，请手动复制');}note('画面地址已复制。');});
action('obs-check',async()=>{note('正在连接OBS…');const data=await request('studio/obs/check',{});$('obs-status').textContent=`OBS ${data.version} 已连接，${data.streaming?'正在推流':'当前未推流'}。`;note($('obs-status').textContent);});
action('obs-setup',async()=>{note('正在配置OBS…');const data=await request('studio/obs/setup',{});note(`OBS已配置：${data.scene}，${data.width} × ${data.height}，画面与声音来源已接入。尚未开始推流。`);});
for(const [id,path,label] of [['obs-start','start','开始'],['obs-stop','stop','停止']])action(id,async()=>{const data=await request('studio/obs/'+path,{});const active=!!data.status?.outputActive;$('obs-status').textContent=active?'OBS正在推流。':'OBS当前未推流。';note(`已请求OBS${label}推流。${$('obs-status').textContent}`);});
form('test-form',async()=>{const data=await request('studio/test',{kind:'chat',text:$('test-text').value});note(testResult(data),!data.queued);await refresh();});
action('test-gift',async()=>{const data=await request('studio/test',{kind:'gift'});note(testResult(data),!data.queued);await refresh();});
const collectorLabels={stopped:'未启用',connecting:'连接中',connected:'已连接',reconnecting:'重连中',external_relay:'等待外部转发'};
const roomLabels={unconfigured:'未配置',waiting_status:'等待状态',online:'已开播',offline:'未开播',ended:'已下播',not_found:'房间无效',unknown:'暂未确认',error:'查询异常',account_offline:'未开播',account_no_room:'尚无直播间'};
function renderStatus(s){
 const phaseLabel={thinking:'正在想怎么回答',synthesizing:'正在准备声音',speaking:'正在说话',idle:'等待消息'}[s.reply_phase]||'等待消息';
 const timing=s.last_latency;$('live-latency').textContent=timing?`上次声音送达用时 ${Number(timing.seconds).toFixed(1)} 秒${timing.model_seconds!==undefined?'（生成回答 '+Number(timing.model_seconds).toFixed(1)+' 秒，首段配音 '+Number(timing.first_tts_seconds).toFixed(1)+' 秒）':''}`:'';

 $('quick-room').textContent=roomLabels[s.room]||s.room;$('quick-collector').textContent=collectorLabels[s.collector]||s.collector;$('quick-player').textContent=s.player_connected?'已连接':s.private_chat_connected?'私人聊天中':'未连接';$('quick-audio').textContent=s.player_audio_ready?'已就绪':'待启用';
 $('operator-state').textContent=s.operator_active?`正在优先口播：${s.current_text||''}`:s.operator_queue_size?`已有 ${s.operator_queue_size} 条主播口播等待播放。`:'';
 $('live-state-title').textContent=s.ready?'已就绪 · 等待观众弹幕':s.enabled?'正在准备 / 等待开播':'互动尚未开始';
 $('live-state-summary').textContent=`真实消息 ${s.real_received||0} · 本地模拟 ${s.test_received||0} · 已完成 ${s.counts.answered} · 普通队列 ${s.queue_size} · 主播口播 ${s.operator_queue_size||0} · ${phaseLabel} · 跳过 ${s.counts.dropped}`;
 $('live-blockers').replaceChildren(...(s.issues||[]).map(i=>{const li=document.createElement('li');li.textContent=i.text;return li;}));
 $('live-room-identity').textContent=[s.room_info?.anchor?'主播：'+s.room_info.anchor:'',s.last_error].filter(Boolean).join(' · ');
 $('quick-test').disabled=!s.player_audio_ready;$('operator-say').disabled=!s.player_audio_ready;
$('player-status').textContent=s.player_connected?'已连接':s.private_chat_connected?'私人聊天占用中':'未连接';$('audio-status').textContent=s.player_audio_ready?'已启用':'未就绪';$('collector-status').textContent=collectorLabels[s.collector]||s.collector;$('room-status').textContent=roomLabels[s.room]||s.room;$('runtime-summary').textContent=`${s.enabled?'互动已启用':'互动已暂停'} · ${phaseLabel} · 队列 ${s.queue_size} · 收到 ${s.counts.received} · 已完成 ${s.counts.answered} · 过滤 ${s.counts.filtered} · 去重 ${s.counts.duplicates} · 跳过 ${s.counts.dropped}`;$('runtime-error').hidden=!s.last_error;$('runtime-error').textContent=s.last_error;$('events').replaceChildren(...s.events.slice().reverse().map(e=>{const li=document.createElement('li');li.textContent=new Date(e.at*1000).toLocaleTimeString()+' · '+e.text;return li;}));}
async function refresh(){renderStatus(await request('studio/status'));}
action('refresh-status',refresh);action('check-health',async()=>{const data=await request('health');note(data.ok?'本地形象素材就绪；语音与对话请用本地演练验证。':'本地形象素材未就绪。',!data.ok);});
Promise.all([loadCharacter(),loadStudio(),loadVoiceEngine(),request('appearance').then(a=>{$('avatar-source-note').textContent='鲸鱼娘美术素材仅供非商业使用，许可与署名见聊天页。';})]).catch(e=>note(e.message,true));
setInterval(()=>refresh().catch(()=>{$('live-state-title').textContent='状态连接中断，正在重试…';$('live-state-summary').textContent='暂时无法读取服务器状态，下面显示的是上次结果。';}),3000);
