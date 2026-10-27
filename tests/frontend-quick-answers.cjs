/* Saved answers must round-trip: build() writes them, savedAnswers() restores them, nothing is invented. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {savedAnswers}=await import(pathToFileURL(path.resolve(__dirname,'..','frontend','quick-flow.js')).href);
 const {QuickFlow}=await import(pathToFileURL(path.resolve(__dirname,'..','frontend','quick-flow.js')).href);
 const choices=values=>values.map(value=>({value,label:String(value)}));
 const card=(id,criterion,fields,extra={})=>({id,kind:'criterion',criterion,implicit:true,target:{type:'criterion_card',criterion},fields,...extra});
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
  {id:'work_types',kind:'checklist',target:{type:'work_types'},items:[]},
  {id:'daily_work_min',kind:'number',target:{type:'conditions',field:'daily_work_min'}},
  {id:'one_off',kind:'choice',target:{type:'conditions',field:'one_off'},choices:choices(['YES','NO','UNKNOWN'])},
  {id:'task_name',kind:'text',target:{type:'task',field:'task_name'}},
  {id:'investigator',kind:'text',target:{type:'survey',field:'investigator'}},
  card('crit_keyboard',1,[{key:'C1_KEYBOARD_FOCUSED',type:'number',to:{exposure:'C1_KEYBOARD_FOCUSED'}}]),
  card('crit_trunk_neck',4,[{key:'unsupported',type:'truth',to:{criterion:'unsupported'}},{key:'C4_TRUNK_FLEX',type:'number',to:{exposure:'C4_TRUNK_FLEX'}}]),
  card('crit_impact',11,[{key:'impact_rate_hour',type:'number',to:{row:'impact_rate_hour'}}]),
  card('crit_lift',null,[{key:'load_mass_kg',type:'number',to:{lift:'load_mass_kg'}},{key:'lift_count_day',type:'number',to:{lift:'lift_count_day'}},{key:'lift_rate_min',type:'number',to:{lift:'lift_rate_min'}}],{criteria:[8,9,10],mode:'lift'})
 ];
 const criteria=Array.from({length:11},(_,i)=>({criterion_no:i+1,condition_present:'UNKNOWN',rows:i>=5?[]:undefined}));
 criteria[0].condition_present='YES';criteria[1].condition_present='NO';criteria[3].condition_present='YES';criteria[3].unsupported='YES';
 for(const n of [8,9,10])criteria[n-1].condition_present='YES';
 criteria[7].rows=[{row_id:'quick-1',load_mass_kg:30,lift_count_day:20}];criteria[8].rows=[{row_id:'quick-1',load_mass_kg:30}];criteria[9].rows=[{row_id:'quick-1',load_mass_kg:30,lift_rate_min:2}];
 const exposures=[{condition_code:'C1_KEYBOARD_FOCUSED',minutes:240},{condition_code:'C4_TRUNK_FLEX',minutes:120}];
 const task={task_name:'박스 포장',input_template:'LIFTING',conditions:{daily_work_min:480,one_off:'NO'},
  capture:{slots:[{slot_no:1,photo_id:7,camera_side:'RIGHT',forward_direction:'SCREEN_RIGHT',side_view_verified:'YES',observation:{single_person:'YES',load_state:'MEASURED',measured_load_kg:10}}]},
  manual:[{scope:'COMMON',field:'trunk_base',value:3},{scope:'LEFT',field:'coupling',value:'NOT_APPLICABLE'},{scope:'COMMON',field:'seated',value:'NO'},{scope:'COMMON',field:'neck_twisted',value:'YES'},{scope:'COMMON',field:'neck_side_bent',value:'NO'}],
  legal:{criteria,exposures}};
 const survey={investigator:'김조사'};
 const a=savedAnswers(questions,task,survey);
 assert.equal(a.context,'YES');assert.equal(a.view_RIGHT,'SCREEN_RIGHT');assert.equal(a.load,'MEASURED');assert.equal(a.load_kg,10);
 assert.equal(a.trunk_base,3);assert.ok(!('coupling' in a),'NOT_APPLICABLE is derived from "no load", not an answer');
 assert.deepEqual(a.posture_flags,['neck_turn'],'only checked flags come back');
 assert.equal(a.daily_work_min,480);assert.equal(a.one_off,'NO');assert.equal(a.task_name,'박스 포장');assert.equal(a.investigator,'김조사');
 assert.deepEqual([...a.work_types].sort(),['keyboard','lift','trunk_neck'],'ticked work types come back from the criteria that were switched on');
 assert.deepEqual(a.crit_keyboard,{values:{C1_KEYBOARD_FOCUSED:240}});
 assert.deepEqual(a.crit_trunk_neck,{values:{unsupported:'YES',C4_TRUNK_FLEX:120}});
 assert.deepEqual(a.crit_lift,{values:{load_mass_kg:30,lift_count_day:20,lift_rate_min:2}},'one lifting card is rebuilt from the three criteria it fed');
 assert.ok(!('crit_impact' in a),'a work type that was not ticked has no card answer');
 const empty=savedAnswers(questions,{...task,capture:{slots:[]},manual:[],conditions:{},legal:{criteria:criteria.map(c=>({...c,condition_present:'UNKNOWN'})),exposures:[]},task_name:'사진 분석 작업'},{});
 assert.deepEqual(empty,{},'nothing saved means nothing restored');

 const noCriteria = () => Array.from({length: 11}, (_, i) => ({criterion_no: i + 1, condition_present: 'UNKNOWN', evidence: null, rows: [], rows_complete: 'UNKNOWN'}));
 const uncheckedInput = {legal: {criteria: noCriteria()}};
 const uncheckedFlow = Object.assign(Object.create(QuickFlow.prototype), {
  answers: {work_types: ['lift']}, preview: {questions: []}, visible: () => true
 });
 uncheckedFlow.applyCriteria(uncheckedInput);
 assert.equal(uncheckedInput.legal.criteria[0].condition_present, 'UNKNOWN', 'an unchecked criterion was not asked and stays UNKNOWN');
 assert.equal(uncheckedInput.legal.criteria[0].rows_complete, 'UNKNOWN', 'an unchecked criterion does not become complete');
 assert.equal(uncheckedInput.legal.criteria[7].condition_present, 'UNKNOWN', 'a checked work type alone does not invent a criterion answer');
 assert.equal(uncheckedInput.legal.criteria[7].rows_complete, 'UNKNOWN');
 assert.equal(uncheckedInput.legal.criteria[0].evidence, null, 'no provenance is attached to an unasked criterion');
 const explicitQuestion = {id: 'crit_lift', kind: 'criterion', criterion: 8, fields: [], mode: 'row'};
 const explicitInput = {legal: {criteria: noCriteria()}};
 const explicitFlow = Object.assign(Object.create(QuickFlow.prototype), {
  answers: {work_types: ['lift']}, preview: {questions: [explicitQuestion]}, group: 0,
  groups: () => [{questions: [explicitQuestion]}], visible: () => true, render() {}
 });
 explicitFlow.allNo();
 explicitFlow.applyCriteria(explicitInput);
 assert.equal(explicitInput.legal.criteria[7].condition_present, 'NO', 'the explicit all-no action preserves a direct user-confirmed NO');
 assert.match(explicitInput.legal.criteria[7].evidence.text, /직접 확인해 아니오로 선택/);
 assert.equal(explicitInput.legal.criteria[7].rows_complete, 'UNKNOWN', 'internal row completeness is not fabricated by an all-no answer');
 assert.equal(explicitInput.legal.criteria[0].condition_present, 'UNKNOWN', 'the explicit action only applies to the visible criterion');
 const liftQuestion = {id: 'crit_lift', kind: 'criterion', criteria: [8, 9, 10], fields: [], mode: 'lift'};
 const liftInput = {legal: {criteria: noCriteria()}};
 const liftFlow = Object.assign(Object.create(QuickFlow.prototype), {
  answers: {work_types: ['lift']}, preview: {questions: [liftQuestion]}, group: 0,
  groups: () => [{questions: [liftQuestion]}], visible: () => true, render() {}
 });
 liftFlow.allNo();
 liftFlow.applyCriteria(liftInput);
 assert.deepEqual([8, 9, 10].map(n => liftInput.legal.criteria[n - 1].condition_present), ['NO', 'NO', 'NO'], 'one explicit all-no answer covers all three related lift criteria');
 assert.deepEqual([8, 9, 10].map(n => liftInput.legal.criteria[n - 1].rows_complete), ['UNKNOWN', 'UNKNOWN', 'UNKNOWN']);
 const partialQuestion = {id: 'crit_impact', kind: 'criterion', criterion: 11, fields: [{key: 'impact_rate_hour'}], mode: 'row'};
 const partialFlow = Object.assign(Object.create(QuickFlow.prototype), {
  answers: {crit_impact: {values: {impact_rate_hour: 4}}}, preview: {questions: [partialQuestion]}, group: 0,
  groups: () => [{questions: [partialQuestion]}], visible: () => true, render() {}
 });
 partialFlow.allNo();
 assert.equal(partialFlow.answers.crit_impact.present, undefined, 'all-no does not overwrite a criterion the person already answered');
 assert.equal(partialFlow.answers.crit_impact.values.impact_rate_hour, 4);

 console.log('PASS saved answers restore only what was really saved');
 const {applyIntake, dropIntakeItem, settledByIntake, LATER_GROUPS} = await import(pathToFileURL(path.resolve(__dirname,'..','frontend','quick-flow.js')).href);
 const item = (target, kind, qid, extra = {}) => ({target, kind, question_id: qid, field_key: null, gate: null, value: true, quote: '근거', label: target, ...extra});
 const intake = [
  item('work_type.keyboard', 'tick', 'work_types', {gate: 'keyboard'}),
  item('work_type.lift', 'tick', 'work_types', {gate: 'lift'}),
  item('card.keyboard.C1_KEYBOARD_FOCUSED', 'number', 'crit_keyboard', {field_key: 'C1_KEYBOARD_FOCUSED', gate: 'keyboard', value: 240}),
  item('card.lift.load_mass_kg', 'number', 'crit_lift', {field_key: 'load_mass_kg', gate: 'lift', value: 20}),
  item('daily_work_min', 'number', 'daily_work_min', {value: 480}),
  item('one_off', 'choice', 'one_off', {value: 'NO'}),
 ];
 const preview = [{id: 'work_types', kind: 'checklist', items: [{key: 'trunk_neck', suggested: true}, {key: 'keyboard', suggested: false}, {key: 'lift', suggested: false}]}];
 const filled = applyIntake({}, preview, intake);
 assert.deepEqual([...filled.work_types].sort(), ['keyboard', 'lift', 'trunk_neck'], 'AI ticks are added to what the photo already suggested');
 assert.deepEqual(filled.crit_keyboard, {values: {C1_KEYBOARD_FOCUSED: 240}});
 assert.deepEqual(filled.crit_lift, {values: {load_mass_kg: 20}});
 assert.equal(filled.daily_work_min, 480); assert.equal(filled.one_off, 'NO');
 const kept = applyIntake({work_types: ['repeat'], crit_lift: {values: {lift_count_day: 5}}}, preview, intake);
 assert.deepEqual([...kept.work_types].sort(), ['keyboard', 'lift', 'repeat'], 'a person\'s own ticks stay');
 assert.deepEqual(kept.crit_lift.values, {lift_count_day: 5, load_mass_kg: 20}, 'values the person typed are kept next to the AI ones');
 const dropped = dropIntakeItem(dropIntakeItem(dropIntakeItem(structuredClone(filled), intake[3]), intake[5]), intake[1]);
 assert.deepEqual([...dropped.work_types].sort(), ['keyboard', 'trunk_neck'], 'dropping a work type removes only that type');
 assert.ok(!('crit_lift' in dropped), 'and its card answers');
 assert.ok(!('one_off' in dropped));
 assert.equal(dropped.daily_work_min, 480);
 const keyboardCard = {id: 'crit_keyboard', kind: 'criterion', fields: [{key: 'C1_KEYBOARD_FOCUSED'}]};
 const twoFields = {id: 'crit_lift', kind: 'criterion', fields: [{key: 'load_mass_kg'}, {key: 'lift_count_day'}]};
 assert.equal(settledByIntake(keyboardCard, filled, intake), true, 'a card the AI filled completely needs no second look');
 assert.equal(settledByIntake(twoFields, filled, intake), false, 'a card with blanks stays on the page, prefilled');
 assert.equal(settledByIntake({id: 'work_types', kind: 'checklist'}, filled, intake), false, 'the work-type checklist is always shown: it is where the AI ticks are confirmed');
 assert.equal(settledByIntake({id: 'daily_work_min', kind: 'number'}, filled, intake), true);
 assert.equal(settledByIntake({id: 'daily_work_min', kind: 'number'}, {...filled, daily_work_min: 300}, intake), false, 'a changed answer is no longer the AI\'s');
 assert.equal(settledByIntake({id: 'coupling', kind: 'choice'}, filled, intake), false);
 assert.deepEqual(LATER_GROUPS, ['조사 정보']);
 console.log('PASS AI intake fills, keeps a person\'s own answers, drops cleanly and settles only what it fully answered');
})().catch(error=>{console.error(error);process.exit(1);});
