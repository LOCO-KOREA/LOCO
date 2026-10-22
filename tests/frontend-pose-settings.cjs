const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const {readPoseSettings,renderPoseSettings,mountPoseSettings}=await import(pathToFileURL(path.join(__dirname,'../frontend/pose-settings.js')).href);
 const a={model_id:'custom-a',model_path:'a.task',model_sha256:'aaa',confidence_min:.5,point_count:33},b={...a,model_id:'custom-b',model_path:'b.task',model_sha256:'bbb'};
 const settings={analysis:{pose_model:a},pose_contract:{models:{'custom-a':a,'custom-b':b},fields:[{key:'model_id',label:'서버 선택',choices:[{value:'custom-a',label:'A'},{value:'custom-b',label:'B'}]},{key:'model_path',label:'경로',kind:'text'},{key:'model_sha256',label:'해시',kind:'text'},{key:'confidence_min',label:'문턱',kind:'number',minimum:0,maximum:1}]}};
 const values={model_id:'custom-b',model_path:'a.task',model_sha256:'aaa',confidence_min:'0.7'};
 const changed=readPoseSettings(settings,key=>values[key]);assert.equal(changed.analysis.pose_model.model_path,'b.task');assert.equal(changed.analysis.pose_model.model_sha256,'bbb');assert.equal(changed.analysis.pose_model.confidence_min,.7);
 values.model_path='custom.task';values.model_sha256='custom-sha';assert.equal(readPoseSettings(settings,key=>values[key]).analysis.pose_model.model_path,'custom.task');
 assert.match(renderPoseSettings(settings),/서버 선택/);assert.match(renderPoseSettings(settings),/custom-b/);
 let change;const nodes={model_id:{value:'custom-b',addEventListener(event,fn){change=fn;}},model_path:{value:'a.task'},model_sha256:{value:'aaa'}};
 mountPoseSettings({querySelector(selector){return nodes[selector.match(/="([^"]+)"/)[1]];}},settings);change();assert.equal(nodes.model_path.value,'b.task');assert.equal(nodes.model_sha256.value,'bbb');
 console.log('PASS pose fields/model defaults come from the contract; switching replaces only unchanged artifact fields');
})().catch(error=>{console.error(error);process.exitCode=1;});
