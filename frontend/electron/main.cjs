const {app,BrowserWindow,ipcMain,dialog}=require('electron');
const {spawn}=require('node:child_process');
const {join,resolve}=require('node:path');
const {createInterface}=require('node:readline');
let window,worker,terminalError,sequence=0;
const pending=new Map();
function disconnect(error){terminalError=error;for(const request of pending.values())request.reject(error);pending.clear();}
function startWorker(){
 const entry=process.env.LOCO_SERVICE_ENTRY||join(__dirname,'..','service','survey_service.py');
 worker=spawn(process.env.LOCO_PYTHON||'python',['-u',resolve(entry)],{cwd:resolve(__dirname,'../..'),windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1'}});
 worker.on('error',error=>disconnect(new Error('Python 실행 실패: '+error.message)));
 worker.on('exit',code=>disconnect(new Error(`Python 서비스가 종료되었습니다 (${code}). 실행 경로를 확인하세요.`)));
 worker.stdin.on('error',disconnect);worker.stderr.on('data',chunk=>process.stderr.write(chunk));
 createInterface({input:worker.stdout,crlfDelay:Infinity}).on('line',line=>{
  try{const response=JSON.parse(line),request=pending.get(response.request_id);if(!request)return;pending.delete(response.request_id);request.resolve(response.result);}
  catch{disconnect(new Error('Python 응답을 읽을 수 없습니다.'));}
 });
}
app.whenReady().then(()=>{
 startWorker();
 ipcMain.handle('loco:call',(_event,method,params)=>new Promise((resolve,reject)=>{
  if(terminalError)return reject(terminalError);
  const request_id=++sequence;pending.set(request_id,{resolve,reject});
  worker.stdin.write(JSON.stringify({request_id,method,params})+'\n','utf8',error=>{if(error){pending.delete(request_id);reject(error);}});
 }));
 ipcMain.handle('loco:photos',async()=>{const result=await dialog.showOpenDialog(window,{properties:['openFile','multiSelections'],filters:[{name:'사진',extensions:['jpg','jpeg','png']}]});return result.canceled?[]:result.filePaths;});
 ipcMain.handle('loco:export',async()=>{const result=await dialog.showSaveDialog(window,{defaultPath:'LOCO_작업분석.xlsx',filters:[{name:'Excel',extensions:['xlsx']}]});return result.canceled?null:result.filePath;});
 window=new BrowserWindow({title:'LOCO · 현장 자세 분석',width:1440,height:1060,minWidth:1100,minHeight:768,backgroundColor:'#F5F6FA',autoHideMenuBar:true,webPreferences:{preload:join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false}});
 window.loadFile(join(__dirname,'..','desktop.html'));
 window.webContents.on('did-finish-load',()=>console.log('LOCO Electron renderer ready'));
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{disconnect(new Error('앱을 종료합니다.'));worker?.kill();});
