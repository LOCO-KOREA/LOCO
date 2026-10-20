const {contextBridge,ipcRenderer,webUtils}=require('electron');
contextBridge.exposeInMainWorld('loco',{
 call:(method,params={})=>ipcRenderer.invoke('loco:call',method,params),
 choose_photo_paths:()=>ipcRenderer.invoke('loco:photos'),
 path_for_file:file=>webUtils.getPathForFile(file),
 choose_export_destination:()=>ipcRenderer.invoke('loco:export'),
 get_database_info:()=>ipcRenderer.invoke('loco:database-info'),
 copy_database_path:()=>ipcRenderer.invoke('loco:database-copy'),
 open_database_folder:()=>ipcRenderer.invoke('loco:database-folder')
});
