'use strict';
const $=id=>document.getElementById(id);let current={},page='/local',showConnection=false;
function render(state){current=state;$('status').textContent=state.message;$('light').style.background=state.phase==='ready'?'#65ad9a':state.phase==='error'||state.phase==='blocked'?'#ce7979':'#e8b959';
 const setup=(!state.keySet||showConnection)&&state.phase!=='blocked';
 $('welcome').hidden=!setup;$('loading').hidden=setup||state.phase==='ready';$('view').hidden=setup||state.phase!=='ready';
 $('loading-message').textContent=state.message;$('loading-title').textContent=state.phase==='blocked'?'显卡检查未通过':state.phase==='error'?'启动遇到问题':'正在唤醒鲸鱼娘';
 $('retry').hidden=state.phase==='starting'||state.phase==='blocked';$('restart').disabled=state.phase==='starting'||!state.keySet||state.phase==='blocked';
 if(state.phase!=='ready'&&$('view').hasAttribute('src'))$('view').removeAttribute('src');
 $('stage').disabled=state.phase!=='ready';$('copy-stage').disabled=state.phase!=='ready';
 if(state.phase==='ready'&&!setup){const target=state.url+page;if($('view').getAttribute('src')!==target)$('view').src=target;}
}
document.querySelectorAll('[data-page]').forEach(button=>button.onclick=()=>{page=button.dataset.page;showConnection=false;document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('selected',b===button));$('title').textContent=button.textContent;render(current);});
$('key-form').onsubmit=async event=>{event.preventDefault();$('save').disabled=true;$('key-message').textContent='正在验证 DeepSeek 连接…';try{const result=await companion.saveKey($('key').value.trim());$('key-message').textContent=result.message;if(result.ok){$('key').value='';showConnection=false;render(await companion.status());}}catch{$('key-message').textContent='验证失败，请重试。';}finally{$('save').disabled=false;}};
$('connection').onclick=()=>{showConnection=true;render(current);};
$('restart').onclick=$('retry').onclick=()=>companion.restart();
$('logs').onclick=()=>companion.logs();$('license').onclick=()=>companion.license();
$('stage').onclick=()=>companion.stage();$('copy-stage').onclick=async()=>{await companion.copyStage();$('copy-stage').textContent='已复制';setTimeout(()=>$('copy-stage').textContent='复制本机直播画面地址',1600);};
$('get-key').onclick=()=>companion.deepseek();companion.onState(render);companion.status().then(render);
