/* Launch only the prepared independent copy; never close another app. */
const path=require('node:path'),fs=require('node:fs'),{spawn:spawnNative}=require('node:child_process');

function createLaunchPlan(config,environment=process.env){
 const root=config.repo_root,directory=config.destination_directory;
 const overrides={LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv','Scripts','python.exe'),LOCO_MODELS_ROOT:root,LOCO_HIDDEN:'0',PYTHONDONTWRITEBYTECODE:'1'};
 const remove=new Set(['ELECTRON_RUN_AS_NODE','LOCO_LIVE_TRACE','PYTHONPATH','LOCO_LIVE_AI','LOCO_EXPECT_PHOTO_VISION',...Object.keys(overrides)]);
 const env={...environment};
 // Windows environment names are case insensitive. Remove empty keys as well.
 for(const key of Object.keys(env))if(remove.has(key.toUpperCase()))delete env[key];
 Object.assign(env,overrides);
 return {file:path.join(root,'frontend','node_modules','electron','dist','electron.exe'),args:[`--user-data-dir=${path.join(directory,'profile')}`,`--remote-debugging-port=${config.remote_debugging_port}`,path.join(root,'frontend')],options:{cwd:root,env,detached:true,windowsHide:false,shell:false},directory};
}

async function startClone(config,{spawn=spawnNative,files=fs,environment=process.env}={}){
 const plan=createLaunchPlan(config,environment);
 const stdout=files.openSync(path.join(plan.directory,'app.stdout.log'),'a');
 const stderr=files.openSync(path.join(plan.directory,'app.stderr.log'),'a');
 let closed=false;
 const close=()=>{if(!closed){closed=true;files.closeSync(stdout);files.closeSync(stderr);}};
 let child;
 try{child=spawn(plan.file,plan.args,{...plan.options,stdio:['ignore',stdout,stderr]});}
 catch(error){close();throw error;}
 return new Promise((resolve,reject)=>{
  child.once('error',error=>{close();reject(error);});
  child.once('spawn',()=>{
   close();child.unref();
   const receipt={pid:child.pid,database:plan.options.env.LOCO_DB_PATH,source_sha:config.source_sha,previous_app_untouched:true,windows_hide:false};
   try{files.writeFileSync(path.join(plan.directory,'app.pid'),String(child.pid),'utf8');files.writeFileSync(path.join(plan.directory,'launch-receipt.json'),JSON.stringify(receipt,null,2),'utf8');resolve(receipt);}
   catch(error){reject(error);}
  });
 });
}
module.exports={createLaunchPlan,startClone};
if(require.main===module){
 const config=JSON.parse(fs.readFileSync(process.argv[2]||path.join(__dirname,'launch-config.json'),'utf8').replace(/^\uFEFF/,''));
 startClone(config).then(receipt=>process.stdout.write(JSON.stringify(receipt)+'\n')).catch(error=>{process.stderr.write('새 앱을 시작하지 못했어요: '+error.message+'\n');process.exitCode=1;});
}
