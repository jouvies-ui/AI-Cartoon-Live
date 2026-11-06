/* The production view reuses the tested Live2D/audio rig and contains no chat UI. */
if(location.pathname==='/local/broadcast'){
 let socket=null,turn=null,complete=false,pipeline=Promise.resolve(),closing=false,generation=0;
 const gate=document.getElementById('broadcast-audio'),errorBox=document.getElementById('broadcast-error');
 function report(message){window.studioPlayerError=message||null;errorBox.textContent=message||'';errorBox.hidden=!message;}
 function send(value){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(value));}
 function appearance(value){document.documentElement.dataset.background=value.background;document.documentElement.dataset.subtitles=String(value.subtitles);}
 function audioReady(){const active=ctx?.state==='running';gate.style.display=active||!sid?'none':'block';send({event:'ready',audio:active});}
 gate.onclick=async()=>{try{await setupAudio();audioReady();}catch{report('声音未能启用，请再次点击或检查浏览器声音权限。');}};
 function connectPlayer(){
  if(closing)return;if(!ready){setTimeout(connectPlayer,500);return;}
  socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/local/studio/player');
  socket.onmessage=event=>{
   const value=JSON.parse(event.data);
   if(value.event==='released'){closing=true;generation++;turn=null;complete=false;sid=null;stopPlayback();report(value.detail);gate.style.display='none';socket.close();return;}
   if(value.event==='stop'){generation++;turn=null;complete=false;stopPlayback();return;}
   const receivedGeneration=generation;
   pipeline=pipeline.then(async()=>{
    if(receivedGeneration!==generation)return;
    if(value.event==='connected'){report('');sid=value.sessionid;appearance(value.settings);setupAudio().then(audioReady).catch(audioReady);if(ctx)ctx.onstatechange=audioReady;audioReady();}
    if(value.event==='settings')appearance(value.settings);
    if(value.event==='unavailable'){closing=true;report(value.detail);gate.style.display='none';return;}
    if(value.event==='turn'){stopPlayback();turn=value.turn_id;complete=false;busy=true;window.studioPlayerError=null;}
    if(value.turn_id&&value.turn_id!==turn)return;
    if(value.event==='audio')window.whaleLastLatency=value;
    if(value.event==='plan'){window.whaleLastPlan=value;turnStill=value.segments.some(s=>s.expression==='still');}
    if(value.event==='audio_chunk')await queueAudio(value,epoch);
    if(value.event==='action')enqueueActions(value.actions);
    if(value.event==='turn_end'){busy=false;complete=true;}
   }).catch(error=>{report('播放出现异常，正在重新连接。');turn=null;complete=false;stopPlayback();socket.close();});
  };
  socket.onclose=()=>{generation++;turn=null;complete=false;sid=null;stopPlayback();gate.style.display='none';if(!closing)setTimeout(connectPlayer,8000);};
  socket.onerror=()=>{if(!window.studioPlayerError)report('直播画面连接暂不可用，正在重试。');};
 }
 setInterval(()=>{
  if(complete&&turn&&!sources.size&&!busy&&!activeAction&&!actionQueue.length&&ctx?.state==='running'){
   send({event:'played',turn_id:turn});complete=false;turn=null;
  }
 },100);
 setInterval(()=>{send({event:'ping'});if(sid)audioReady();},15000);
 let modeChannel;
 function listenMode(){if(typeof BroadcastChannel==='undefined'||modeChannel)return;modeChannel=new BroadcastChannel('local-studio');modeChannel.onmessage=e=>{if(e.data==='audience-mode'&&closing){closing=false;connectPlayer();}};}
 listenMode();
 window.addEventListener('pagehide',()=>{closing=true;generation++;turn=null;complete=false;sid=null;stopPlayback();socket?.close();modeChannel?.close();modeChannel=null;});
 window.addEventListener('pageshow',e=>{listenMode();if(e.persisted){closing=false;connectPlayer();}});
 connectPlayer();
}
