/* Saved answers must round-trip: build() writes them, savedAnswers() restores them, nothing is invented. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {savedAnswers}=await import(pathToFileURL(path.resolve(__dirname,'..','frontend','quick-flow.js')).href);
 const choices=values=>values.map(value=>({value,label:String(value)}));
 const questions=[
  {id:'context',kind:'choice',target:{type:'context'},choices:choices(['YES','NO'])},
  {id:'view_RIGHT',kind:'choice',target:{type:'slot',view:'RIGHT',field:'forward_direction'},choices:choices(['SCREEN_RIGHT','SCREEN_LEFT'])},
  {id:'load',kind:'choice',target:{type:'load'},choices:choices(['UNLOADED','MEASURED','UNKNOWN'])},
  {id:'load_kg',kind:'number',target:{type:'load_kg'}},
  {id:'trunk_base',kind:'choice',target:{type:'manual',scope:'COMMON',field:'trunk_base'},choices:choices([1,2,3,4])},
  {id:'coupling',kind:'choice',target:{type:'manual',scope:'BOTH',field:'coupling'},choices:choices(['GOOD','FAIR'])},
  {id:'posture_flags',kind:'checklist',target:{type:'flags'},items:[
   {key:'seated',sets:[{scope:'COMMON',field:'seated',checked:'YES',unchecked:'NO'}]},
   {key:'neck_turn',sets:[{scope:'COMMON',field:'neck_twisted',checked:'YES',unchecked:'NO'},{scope:'COMMON',field:'neck_side_bent',checked:null,unchecked:'NO'}]}]},
  {id:'daily_work_min',kind:'number',target:{type:'conditions',field:'daily_work_min'}},
  {id:'one_off',kind:'choice',target:{type:'conditions',field:'one_off'},choices:choices(['YES','NO','UNKNOWN'])},
  {id:'task_name',kind:'text',target:{type:'task',field:'task_name'}},
  {id:'investigator',kind:'text',target:{type:'survey',field:'investigator'}},
  {id:'situation_equipment',kind:'choice',target:{type:'situation',field:'equipment_status'},choices:choices(['YES','NO','UNKNOWN'])},
  {id:'participation',kind:'choice',target:{type:'participation',field:'status'},choices:choices(['YES','NO','UNKNOWN'])},
  {id:'crit_1',kind:'criterion',criterion:1,target:{type:'criterion_card',criterion:1},fields:[{key:'C1_KEYBOARD_FOCUSED',type:'number',to:{exposure:'C1_KEYBOARD_FOCUSED'}}]},
  {id:'crit_4',kind:'criterion',criterion:4,target:{type:'criterion_card',criterion:4},fields:[{key:'unsupported',type:'truth',to:{criterion:'unsupported'}},{key:'C4_TRUNK_FLEX',type:'number',to:{exposure:'C4_TRUNK_FLEX'}}]},
  {id:'crit_8',kind:'criterion',criterion:8,target:{type:'criterion_card',criterion:8},fields:[{key:'load_mass_kg',type:'number',to:{row:'load_mass_kg'}},{key:'lift_count_day',type:'number',to:{row:'lift_count_day'}}]},
  {id:'crit_9',kind:'criterion',criterion:9,target:{type:'criterion_card',criterion:9},fields:[{key:'load_mass_kg',type:'number',to:{row:'load_mass_kg'}}]}
 ];
 const criteria=Array.from({length:11},(_,i)=>({criterion_no:i+1,condition_present:'UNKNOWN',rows:i>=5?[]:undefined}));
 criteria[0].condition_present='YES';criteria[3].condition_present='YES';criteria[3].unsupported='YES';
 criteria[7].condition_present='YES';criteria[7].rows=[{row_id:'quick-1',load_mass_kg:30,lift_count_day:20}];
 const exposures=[{condition_code:'C1_KEYBOARD_FOCUSED',minutes:240},{condition_code:'C4_TRUNK_FLEX',minutes:120}];
 const task={task_name:'박스 포장',input_template:'LIFTING',conditions:{daily_work_min:480,one_off:'NO'},
  capture:{slots:[{slot_no:1,photo_id:7,camera_side:'RIGHT',forward_direction:'SCREEN_RIGHT',side_view_verified:'YES',observation:{single_person:'YES',load_state:'MEASURED',measured_load_kg:10}}]},
  manual:[{scope:'COMMON',field:'trunk_base',value:3},{scope:'LEFT',field:'coupling',value:'NOT_APPLICABLE'},{scope:'COMMON',field:'seated',value:'NO'},{scope:'COMMON',field:'neck_twisted',value:'YES'},{scope:'COMMON',field:'neck_side_bent',value:'NO'}],
  legal:{criteria,exposures}};
 const survey={investigator:'김조사',workplace_situation:{equipment_status:'NO'},participation:{status:'UNKNOWN'},symptom_survey:{method:'UNKNOWN'}};
 const a=savedAnswers(questions,task,survey);
 assert.equal(a.context,'YES');assert.equal(a.view_RIGHT,'SCREEN_RIGHT');assert.equal(a.load,'MEASURED');assert.equal(a.load_kg,10);
 assert.equal(a.trunk_base,3);assert.ok(!('coupling' in a),'NOT_APPLICABLE is derived from "no load", not an answer');
 assert.deepEqual(a.posture_flags,['neck_turn'],'only checked flags come back');
 assert.equal(a.daily_work_min,480);assert.equal(a.one_off,'NO');assert.equal(a.task_name,'박스 포장');assert.equal(a.investigator,'김조사');
 assert.equal(a.situation_equipment,'NO');assert.ok(!('participation' in a),'UNKNOWN is not restored as an answer');
 assert.deepEqual(a.crit_1,{present:'YES',values:{C1_KEYBOARD_FOCUSED:240}});
 assert.deepEqual(a.crit_4,{present:'YES',values:{unsupported:'YES',C4_TRUNK_FLEX:120}});
 assert.deepEqual(a.crit_8,{present:'YES',values:{load_mass_kg:30,lift_count_day:20}});
 assert.ok(!('crit_9' in a),'an unanswered criterion stays unanswered');
 const empty=savedAnswers(questions,{...task,capture:{slots:[]},manual:[],conditions:{},legal:{criteria:criteria.map(c=>({...c,condition_present:'UNKNOWN'})),exposures:[]},task_name:'사진 분석 작업'},{workplace_situation:{},participation:{},symptom_survey:{}});
 assert.deepEqual(empty,{},'nothing saved means nothing restored');
 console.log('PASS saved answers restore only what was really saved');
})().catch(error=>{console.error(error);process.exit(1);});
