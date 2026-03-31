const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gexApi', {
  pickDirectory: () => ipcRenderer.invoke('dialog:pickDirectory'),
  readFile: (filePath) => ipcRenderer.invoke('fs:readFile', filePath),
  ensureModule: () => ipcRenderer.invoke('gex:ensureModule'),
  runScan: (payload) => ipcRenderer.invoke('gex:runScan', payload),
});
