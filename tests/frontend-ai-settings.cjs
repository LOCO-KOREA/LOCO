const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const {renderAiSettings,readAiSettings,enabledAiSettings,persistedSettings}=await import(pathToFileURL(path.join(__dirname,'../frontend/ai-settings.js')).href);
 const settings={gpt_enabled:false,gpt_model:'',gpt_key_present:true,gpt_contract:{defaults:{gpt_model:'server-default'},fields:[
  {key:'gpt_model',label:'서버 모델',kind:'text'},{key:'custom_effort',label:'서버 추론',kind:'choice',choices:[{value:'custom',label:'서버 강도'}]},
  {key:'custom_limit',label:'서버 한도',kind:'integer'},{key:'gpt_enabled',label:'서버 사용',kind:'boolean'}]}};
 const html=renderAiSettings(settings,'data-field');assert.match(html,/data-field="custom_effort"/);assert.match(html,/서버 강도/);assert.match(html,/data-field="custom_limit"/);
 assert.equal(enabledAiSettings(settings).gpt_model,'server-default');
 const read={gpt_model:' chosen ',custom_effort:'custom',custom_limit:'8192',gpt_enabled:'YES'};
 const selected=readAiSettings(settings,key=>read[key]);assert.equal(selected.gpt_model,'chosen');assert.equal(selected.custom_limit,8192);assert.equal(selected.gpt_enabled,true);
 const persisted=persistedSettings(selected);assert.equal(persisted.custom_effort,'custom');assert.ok(!('gpt_contract' in persisted));assert.ok(!('gpt_key_present' in persisted));
 console.log('PASS AI fields, choices and defaults come from the server contract; typed settings save without metadata');
})().catch(error=>{console.error(error);process.exitCode=1;});
