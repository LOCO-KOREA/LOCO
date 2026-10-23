const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const load=file=>import(pathToFileURL(path.resolve(__dirname,'../frontend',file)).href);
 const {rectFromPoints,pointOnImage,moveRect,validRect}=await load('photo-crop.js');
 const {QuickFlow}=await load('quick-flow.js');
 assert.deepEqual(pointOnImage(110,70,{left:10,top:20,width:200,height:100},1000,500),{x:500,y:250});
 assert.deepEqual(rectFromPoints({x:900.8,y:480.9},{x:-20,y:20.1},1000,500),{x:0,y:20,width:901,height:461});
 assert.deepEqual(moveRect({x:10,y:20,width:100,height:50},-100,900,200,100),{x:0,y:50,width:100,height:50});
 assert.equal(validRect({x:0,y:0,width:200,height:100},200,100),true);
 for(const r of [{x:0,y:0,width:0,height:1},{x:0,y:0,width:1.5,height:1},{x:199,y:0,width:2,height:1}])assert.equal(validRect(r,200,100),false);
 const source={data_url:'data:image/png;base64,AA==',width_px:100,height_px:100,source_sha256:'a'.repeat(64)};
 const task={task_id:7,created_at:'original'},photo={photo_id:42},rect={x:10,y:20,width:50,height:60};
 function flow(choice){
  const calls=[],errors=[],value=Object.create(QuickFlow.prototype);
  Object.assign(value,{step:'start',task,survey:{survey_id:1},photos:{LEFT:{photo:{photo_id:2}}},busy:false,
   choosePhotoCrop:choice,render(){},onError:e=>errors.push(e.message),ensureTask:async()=>calls.push(['ensureTask']),
   discard:async p=>calls.push(['discard',p.photo_id]),api:async(method,p)=>{calls.push([method,p]);
    if(method==='preview_photo_file')return source;if(method==='import_cropped_photo')return photo;
    if(method==='get_photo_preview')return {data_url:'cropped-image'};throw Error(method);}});
  return {value,calls,errors};
 }
 const cancelled=flow(async()=>null);await cancelled.value.setPhoto('LEFT','source.png');
 assert.deepEqual(cancelled.calls.map(c=>c[0]),['preview_photo_file']);assert.equal(cancelled.value.photos.LEFT.photo.photo_id,2);
 const successful=flow(async()=>rect);await successful.value.setPhoto('LEFT','source.png');
 assert.deepEqual(successful.calls.map(c=>c[0]),['preview_photo_file','ensureTask','import_cropped_photo','get_photo_preview','discard']);
 assert.deepEqual(successful.calls[2][1],{task_id:7,task_created_at:'original',file_path:'source.png',source_sha256:source.source_sha256,crop:rect});
 assert.equal(successful.value.photos.LEFT.photo.photo_id,42);assert.equal(successful.value.busy,false);
 const failed=flow(async()=>rect),api=failed.value.api;
 failed.value.api=async(m,p)=>{if(m==='import_cropped_photo')throw Error('save failed');return api(m,p);};
 await failed.value.setPhoto('LEFT','source.png');assert.equal(failed.value.photos.LEFT.photo.photo_id,2);
 assert.equal(failed.calls.some(c=>c[0]==='discard'),false);assert.deepEqual(failed.errors,['save failed']);
 let resolve;const late=new Promise(r=>resolve=r),stale=flow(()=>late);
 const request=stale.value.setPhoto('LEFT','source.png');await new Promise(r=>setImmediate(r));
 stale.value.reset();stale.value.busy='newer request';resolve(rect);await request;
 assert.equal(stale.calls.some(c=>c[0]==='ensureTask'),false);assert.equal(stale.value.busy,'newer request');assert.deepEqual(stale.value.photos,{});
 const pending=flow(async()=>rect);let release;pending.value.api=async()=>new Promise(r=>release=r);
 const first=pending.value.setPhoto('LEFT','a.png');await pending.value.setPhoto('RIGHT','b.png');
 pending.value.reset();release(source);await first;assert.deepEqual(pending.value.photos,{});
 console.log('PASS crop pixel mapping/bounds, cancel without registration, exact import target, failed replacement, reset and duplicate selection');
})().catch(error=>{console.error(error);process.exitCode=1;});
