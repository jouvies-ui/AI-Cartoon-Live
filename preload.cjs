const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('companion',Object.freeze({
 status:()=>ipcRenderer.invoke('state'),saveKey:value=>ipcRenderer.invoke('save-key',value),
 restart:()=>ipcRenderer.invoke('restart'),logs:()=>ipcRenderer.invoke('logs'),
 stage:()=>ipcRenderer.invoke('stage'),copyStage:()=>ipcRenderer.invoke('copy-stage'),
 deepseek:()=>ipcRenderer.invoke('deepseek'),license:()=>ipcRenderer.invoke('license'),
 onState:callback=>{const listener=(_event,value)=>callback(value);ipcRenderer.on('state',listener);return()=>ipcRenderer.removeListener('state',listener);}
}));
