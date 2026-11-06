'use strict';
const {app,BrowserWindow,ipcMain,safeStorage,shell,clipboard}=require('electron');
const fs=require('node:fs'),path=require('node:path'),{spawn,execFile}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const root=__dirname,entry=pathToFileURL(path.join(root,'shell.html')).href;
const icon=path.join(root,'assets','whale.ico');
app.setName('WhaleCompanion');
if(process.platform==='win32')app.setAppUserModelId('WhaleCompanion.Desktop');
app.setPath('userData',path.join(app.getPath('appData'),'WhaleCompanion'));
app.commandLine.appendSwitch('autoplay-policy','no-user-gesture-required');
let window,stage,worker,key='',poller,stopping=false,quitting=false,launching=false;
const data=app.getPath('userData'),keyPath=path.join(data,'deepseek-key.dpapi');
let state={phase:'starting',message:'正在检查运行环境…',keySet:false,url:null};
const python=path.join(root,'runtime','python.exe');
function notify(){if(window&&!window.isDestroyed())window.webContents.send('state',state);}
function update(value){state={...state,...value,keySet:!!key};notify();}
function readStatus(){try{
 const s=JSON.parse(fs.readFileSync(path.join(data,'runtime.json'),'utf8'));
 if(s.pid!==worker?.pid)return;
 if(s.url&&!/^http:\/\/127\.0\.0\.1:\d+$/.test(s.url))return;
 if(JSON.stringify({...state,...s,keySet:!!key})!==JSON.stringify(state))update(s);
}catch{}}
function trusted(event){return event.sender===window?.webContents&&event.senderFrame===window.webContents.mainFrame&&event.senderFrame.url===entry;}
function handle(name,callback){ipcMain.handle(name,async(event,...args)=>{if(!trusted(event))throw Error('无效窗口');return callback(...args);});}
function safeEnv(){
 const env={...process.env};
 for(const k of Object.keys(env))if(/^(CYBER_|HOJO_|VIDU_|DEEPSEEK_|PYTHON|OPENAI_)/.test(k))delete env[k];
 return {...env,DEEPSEEK_API_KEY:key,PYTHONUTF8:'1'};
}
function gpuCheck(){return new Promise(resolve=>{
 const ps=path.join(process.env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe');
 execFile(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'check-gpu.ps1')],{windowsHide:true,timeout:25000},error=>resolve(!error));
});}
async function stop(){
 stopping=true;clearInterval(poller);poller=null;
 if(stage&&!stage.isDestroyed())stage.close();stage=null;
 if(worker&&worker.exitCode===null){
  fs.writeFileSync(path.join(data,'stop.request'),'stop');
  const child=worker;
  await new Promise(resolve=>{let settled=false;const finish=()=>{if(!settled){settled=true;clearTimeout(timer);resolve();}};const timer=setTimeout(()=>{execFile('taskkill.exe',['/pid',String(child.pid),'/t','/f'],{windowsHide:true},finish);},25000);child.once('exit',finish);});
 }
 worker=null;stopping=false;
}
async function start(){
 if(launching)return;
 launching=true;
 try{
 await stop();
 fs.mkdirSync(data,{recursive:true});
 fs.rmSync(path.join(data,'runtime.json'),{force:true});
 update({phase:'starting',message:'正在启动本机语音和数字人…',url:null});
 const log=fs.openSync(path.join(data,'launcher.log'),'a');
 worker=spawn(python,[path.join(root,'python_entry.py'),'supervisor','--data',data,'--parent',String(process.pid)],{cwd:data,env:safeEnv(),windowsHide:true,stdio:['ignore',log,log]});
 fs.closeSync(log);
 worker.once('error',()=>{clearInterval(poller);update({phase:'error',message:'无法启动内置运行环境，请打开日志或重新安装。'});});
 worker.once('exit',()=>{clearInterval(poller);if(!stopping&&!quitting){readStatus();update({phase:'error',message:state.phase==='error'?state.message:'本机服务已停止，请重启服务并查看日志。'});}});
 poller=setInterval(readStatus,500);
 }finally{launching=false;}
}
function lockNavigation(view,local){
 view.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 view.webContents.on('will-navigate',(event,url)=>{if(!local(url))event.preventDefault();});
 view.webContents.on('will-frame-navigate',(event)=>{if(!local(event.url))event.preventDefault();});
 view.webContents.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
}
function showStage(){
 if(state.phase!=='ready')return;
 if(stage&&!stage.isDestroyed()){stage.focus();return;}
 stage=new BrowserWindow({icon,title:'AI-Cartoon-Live · 直播画面',width:620,height:980,backgroundColor:'#eef8ff',webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false}});
 stage.setMenuBarVisibility(false);
 lockNavigation(stage,url=>url.startsWith(state.url+'/'));
 stage.loadURL(state.url+'/local/broadcast');
}
let saving=false;
handle('state',()=>state);
handle('save-key',async value=>{
 if(saving)return{ok:false,message:'正在验证，请稍候。'};
 if(typeof value!=='string'||value.length<12||value.length>512||/[\s\x00-\x1f]/.test(value))return{ok:false,message:'请输入完整的 DeepSeek API Key，不要包含空格或换行。'};
 saving=true;
 try{
  const response=await fetch('https://api.deepseek.com/chat/completions',{method:'POST',signal:AbortSignal.timeout(30000),headers:{Authorization:'Bearer '+value,'Content-Type':'application/json'},body:JSON.stringify({model:'deepseek-flash',messages:[{role:'user',content:'请回答好。'}],thinking:{type:'disabled'},max_tokens:4,stream:false})});
  if(!response.ok)return{ok:false,message:response.status===401?'密钥未通过验证，请检查是否为 DeepSeek 官方密钥。':response.status===402?'账户余额不足，请在 DeepSeek 平台充值后重试。':response.status===429?'接口暂时限流，请稍后重试。':`DeepSeek 暂时不可用（${response.status}），请稍后重试。`};
  const answer=await response.json();if(!answer.choices?.[0]?.message)return{ok:false,message:'接口返回异常，请稍后重试。'};
  if(!safeStorage.isEncryptionAvailable())return{ok:false,message:'Windows 密钥保护不可用，未保存密钥。'};
  fs.mkdirSync(data,{recursive:true});fs.writeFileSync(keyPath+'.tmp',safeStorage.encryptString(value));fs.renameSync(keyPath+'.tmp',keyPath);key=value;
  await start();return{ok:true,message:'密钥已加密保存，正在启动你的数字伙伴。'};
 }catch{return{ok:false,message:'无法连接 DeepSeek，请检查网络后重试。'};}
 finally{saving=false;}
});
handle('restart',async()=>{await start();return true;});
handle('logs',async()=>{fs.mkdirSync(path.join(data,'logs'),{recursive:true});await shell.openPath(data);});
handle('stage',()=>showStage());
handle('copy-stage',()=>{if(state.url)clipboard.writeText(state.url+'/local/broadcast');});
handle('deepseek',()=>shell.openExternal('https://platform.deepseek.com/api_keys'));
handle('license',()=>shell.openPath(path.join(root,'THIRD-PARTY-NOTICES.txt')));
if(!app.requestSingleInstanceLock())app.quit();
else {
 app.on('second-instance',()=>{if(window){window.show();window.focus();}});
 app.whenReady().then(async()=>{
  fs.mkdirSync(data,{recursive:true});
  try{if(fs.existsSync(keyPath)&&safeStorage.isEncryptionAvailable())key=safeStorage.decryptString(fs.readFileSync(keyPath));}catch{key='';}
  window=new BrowserWindow({icon,width:1280,height:920,minWidth:920,minHeight:680,title:'AI-Cartoon-Live',backgroundColor:'#edf5ff',webPreferences:{preload:path.join(root,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true}});
  window.on('closed',()=>{if(!quitting)app.quit();});
  window.setMenuBarVisibility(false);lockNavigation(window,url=>url===entry||url==='about:blank'||!!state.url&&url.startsWith(state.url+'/'));
  await window.loadURL(entry);notify();
  if(process.platform!=='win32'||!(await gpuCheck())){update({phase:'blocked',message:'需要安装正常驱动的 NVIDIA GTX 10 系列或更新显卡。请更新驱动后重新打开应用。'});return;}
  if(key)await start();else update({phase:'setup',message:'首次使用：填写 DeepSeek API Key 即可开始。'});
 });
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',event=>{if(quitting)return;event.preventDefault();quitting=true;stop().finally(()=>app.quit());});
}
