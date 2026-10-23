const {app,BrowserWindow,ipcMain,dialog,clipboard,shell}=require('electron');
const {homedir}=require('node:os');
const {resolveDatabaseLocation,createDatabaseLocationBridge}=require('./database-location.cjs');
const {spawn}=require('node:child_process');
const {join,resolve}=require('node:path');
const {createInterface}=require('node:readline');
const {existsSync}=require('node:fs');
const appIcon=join(__dirname,'..','assets',process.platform==='win32'?'app-icon.ico':'app-icon.png');
if(process.platform==='win32')app.setAppUserModelId('kr.loco.desktop');
let window,worker,databaseLocation,terminalError,sequence=0;
const pending=new Map();
function disconnect(error){terminalError=error;for(const request of pending.values())request.reject(error);pending.clear();}
function startWorker(){
 const entry=join(__dirname,'..','..','ergo','service','json_lines.py');
 const localPython=join(__dirname,'..','..','.venv','Scripts','python.exe');
 const binary=app.isPackaged?join(process.resourcesPath,'backend','loco-service','loco-service.exe'):process.env.LOCO_PYTHON||(existsSync(localPython)?localPython:'python');
 const args=app.isPackaged?[]:['-u',resolve(entry)];
 const model=process.env.LOCO_MOVENET_MODEL||(app.isPackaged?join(process.resourcesPath,'models','movenet_lightning.tflite'):join(__dirname,'..','..','models','movenet_lightning.tflite'));
 const cwd=app.isPackaged?process.resourcesPath:resolve(__dirname,'../..');
 databaseLocation=resolveDatabaseLocation({env:process.env,cwd,home:homedir()});
 worker=spawn(binary,args,{cwd,windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...process.env,LOCO_DB_PATH:databaseLocation.path,LOCO_MODELS_ROOT:app.isPackaged?process.resourcesPath:cwd,LOCO_MOVENET_MODEL:model,PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1'}});
 worker.on('error',error=>{console.error('LOCO worker start failed',error);disconnect(new Error('저장 기능을 시작하지 못했어요. 앱을 다시 실행해 주세요.'));});
 worker.on('exit',code=>{console.error('LOCO worker exited',code);disconnect(new Error('저장 연결이 종료됐어요. 앱을 다시 실행해 주세요.'));});
 worker.stdin.on('error',disconnect);worker.stderr.on('data',chunk=>process.stderr.write(chunk));
 createInterface({input:worker.stdout,crlfDelay:Infinity}).on('line',line=>{
  try{const response=JSON.parse(line),request=pending.get(response.request_id);if(!request)return;pending.delete(response.request_id);request.resolve(response.result);}
  catch{disconnect(new Error('저장한 정보를 불러오지 못했어요. 앱을 다시 실행해 주세요.'));}
 });
}
function callWorker(method,params={}){return new Promise((resolve,reject)=>{
 if(terminalError)return reject(terminalError);
 const request_id=++sequence;pending.set(request_id,{resolve,reject});
 worker.stdin.write(JSON.stringify({request_id,method,params})+'\n','utf8',error=>{if(error){pending.delete(request_id);reject(error);}});
});}
app.whenReady().then(()=>{
 startWorker();
 ipcMain.handle('loco:call',(_event,method,params)=>callWorker(method,params));
 const database=createDatabaseLocationBridge({location:databaseLocation,call:callWorker,clipboard,shell});
 ipcMain.handle('loco:database-info',()=>database.info());
 ipcMain.handle('loco:database-copy',()=>database.copy());
 ipcMain.handle('loco:database-folder',()=>database.openFolder());
 ipcMain.handle('loco:export-pdf',async()=>{const result=await dialog.showSaveDialog(window,{defaultPath:'LOCO_유해요인조사표.pdf',filters:[{name:'PDF',extensions:['pdf']}]});return result.canceled?null:result.filePath;});
 ipcMain.handle('loco:photos',async()=>{const result=await dialog.showOpenDialog(window,{properties:['openFile','multiSelections'],filters:[{name:'사진',extensions:['jpg','jpeg','png']}]});return result.canceled?[]:result.filePaths;});
 ipcMain.handle('loco:export',async()=>{const result=await dialog.showSaveDialog(window,{defaultPath:'LOCO_작업분석.xlsx',filters:[{name:'Excel',extensions:['xlsx']}]});return result.canceled?null:result.filePath;});
 window=new BrowserWindow({title:'LOCO · 현장 자세 분석',icon:appIcon,width:1440,height:1060,minWidth:1100,minHeight:768,backgroundColor:'#F5F6FA',autoHideMenuBar:true,...(process.env.LOCO_HIDDEN==='1'?{x:-12000,y:-12000,skipTaskbar:true,focusable:false}:{}),webPreferences:{preload:join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,plugins:true,backgroundThrottling:process.env.LOCO_HIDDEN!=='1'}});
 window.loadFile(join(__dirname,'..','desktop.html'));
 window.webContents.on('did-finish-load',()=>console.log('LOCO Electron renderer ready'));
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{disconnect(new Error('앱을 종료합니다.'));worker?.kill();});
