/* Contract-driven UI, autosave ownership, stale responses and a recoverable save failure. */
const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url');
const url=name=>pathToFileURL(path.join(__dirname,'../frontend/intake',name)).href;
(async()=>{
 const {AdaptiveIntake}=await import(url('client.js'));
 const {connectionStatus}=await import(url('view.js'));
 const contract={version:'test',session_key:'test_metadata',methods:{session:'custom_session',turn:'custom_turn'},policy:{default_condition:'row',text_limit:321,question_limit:1},fields:[{target:'custom.weight',kind:'number',label:'무게 <기록>',unit:'kg',choices:[],maximum:100}]};
 const question={...contract.fields[0],identity:'custom.weight@row',condition:'row',text:'남은 무게만 알려 주세요',reason:'아직 모르는 값'};
 const initial={contract,task:{task_id:1,input_revision:1},facts:[],questions:[question],remaining_count:1,complete:false};
 const calls=[]; let state=structuredClone(initial),fail=false,late=null;
 const api=async(method,args)=>{
  calls.push({method,args});
  if(method==='intake_contract')return contract;
  if(method==='custom_session')return structuredClone(state);
  assert.equal(method,'custom_turn');
  if(late)return await late;
  if(fail)throw Error('저장 실패');
  assert.equal(args.expected_revision,state.task.input_revision);
  state={...structuredClone(state),task:{task_id:1,input_revision:state.task.input_revision+1}};
  for(const answer of args.answers)state.facts=[{...answer,identity:'custom.weight@row',source:'USER',state:answer.value===null?'UNKNOWN':'KNOWN',label:question.label,unit:'kg'}];
  return structuredClone(state);
 };
 const intake=new AdaptiveIntake({api,changed(){},notify(){}});
 await intake.open(1,{});
 assert.equal(intake.parseValue(question.identity,'0'),0);
 assert.equal(intake.parseValue(question.identity,'12.5'),12.5,'numeric candidate buttons must retain the proposed value');
 assert.equal(intake.parseValue(question.identity,''),null);
 await Promise.all([intake.answer(question.identity,0),intake.answer(question.identity,null)]);
 assert.equal(calls.filter(c=>c.method==='custom_turn')[0].args.answers[0].value,0);
 assert.equal(state.facts[0].value,null);
 intake.editing=question.identity;
 assert.match(intake.summary(),/role="status"/,'the compact summary keeps the saved-input status');
 assert.equal(intake.editing,question.identity,'summary rendering must retain an explicit edit in progress');
 intake.editing=null;
 intake.dialogOpen=true;
 assert.match(intake.dialog(false),/maxlength="321"/);
 assert.match(intake.dialog(false),/<dialog/);
 assert.ok(!intake.dialog(false).includes('type="number"'),'the conversation must not expose a numeric form');
 assert.ok(!intake.panel(false).includes('data-intake-question'),'the page must not list question fields');
 assert.equal(connectionStatus(intake),'','an unrequested connection must not add technical status clutter');
 const privateModel='PRIVATE_MODEL_MARKER <img src=x>',privateEffort='PRIVATE_EFFORT_MARKER xhigh & details';
 intake.state.ai={status:'CONNECTED',model:privateModel,reasoning_effort:privateEffort};
 assert.equal(connectionStatus(intake),'','an already successful response needs no persistent connection label');
 const assertNoProviderDetails=html=>{
  assert.doesNotMatch(html,/PRIVATE_MODEL_MARKER|PRIVATE_EFFORT_MARKER|PRIVATE_ERROR_MARKER|HTTP_502_SECRET|xhigh/,'provider metadata must not appear even as escaped HTML text');
  assert.doesNotMatch(html,/<img\b|&lt;img/,'model metadata must be omitted, not merely escaped');
 };
 for(const status of ['CONNECTED','NOT_REQUESTED',undefined,'UNRECOGNIZED_PROVIDER_STATUS']){
  intake.state.ai={status,model:privateModel,reasoning_effort:privateEffort,reason:'PRIVATE_ERROR_MARKER HTTP_502_SECRET'};
  assert.equal(connectionStatus(intake),'');
  assertNoProviderDetails(intake.dialog(false));assertNoProviderDetails(intake.panel(false));assertNoProviderDetails(intake.summary());
 }
 for(const reason of ['DISABLED','NO_API_KEY','TIMEOUT','API_ERROR','INVALID_STRUCTURED_CONTENT','PRIVATE_ERROR_MARKER HTTP_502_SECRET']){
  intake.state.ai={status:'ERROR',model:privateModel,reasoning_effort:privateEffort,reason};
  const status=connectionStatus(intake);
  assert.match(status,/data-ai-state="ERROR"/);assert.match(status,/role="status"/);
  assert.match(status,/다시 시도해 주세요/,'an error must tell the user how to continue');
  assertNoProviderDetails(status);assert.ok(!status.includes(reason),'provider error codes must not be used as fallback labels');
  assertNoProviderDetails(intake.dialog(false));assertNoProviderDetails(intake.panel(false));
  const waiting=connectionStatus(intake,true);
  assert.match(waiting,/data-ai-state="REQUESTING"/);assert.match(waiting,/답변을 정리하고 있어요/);
  assert.doesNotMatch(waiting,/다시 시도/,'an in-flight retry should show its current activity instead of the old error');
  assertNoProviderDetails(waiting);
 }
 intake.saveError='PRIVATE_ERROR_MARKER HTTP_502_SECRET';
 assert.match(intake.summary(),/입력을 저장하지 못했어요/);
 assert.match(intake.summary(),/다시 시도해 주세요/);assertNoProviderDetails(intake.summary());
 intake.saveError='';intake.state.ai={status:'CONNECTED',model:'actual-response'};
 intake.state.contract.fields.push({target:'work_type.sample',label:'아직 확인하지 않은 특징',destination:{type:'work_type'}});
 intake.questions=[{...question,ai_writable:false}];
 assert.match(intake.dialog(false),/확인할 특징: 아직 확인하지 않은 특징/,'a grouped absence answer must disclose its exact feature scope');
 intake.questions=[question];intake.state.contract.fields.pop();
 // Choice replies should not present a second required-looking writing step.
 assert.equal(intake.writingFor,null,'a new workflow must start with no explicitly opened writer');
 const beforeChoices={state:intake.state,questions:intake.questions,text:intake.text,writingFor:intake.writingFor};
 const choiceQuestion={...question,target:'custom.confirm',identity:'custom.confirm@row',kind:'choice',unit:'',
  text:'평소 작업 모습인가요?',choices:[{value:'YES',label:'예'},{value:'NO',label:'아니오'}]};
 const choiceState={...structuredClone(initial),questions:[choiceQuestion],facts:[]};
 intake.state=choiceState;intake.questions=[choiceQuestion];intake.text='';intake.writingFor=null;
 const closedChoice=intake.dialog(false);
 assert.doesNotMatch(closedChoice,/<textarea\b|data-intake-reply|data-quick="adaptive-next"/,'ordinary choice questions must omit both the writer and send button');
 const writeButton=/<button\b[^>]*data-quick="intake-write"[^>]*>/.exec(closedChoice)?.[0];
 assert.ok(writeButton,'choice questions must offer an explicit way to add a written explanation');
 assert.match(writeButton,/aria-expanded="false"/);assert.match(writeButton,/aria-controls="intake-writing"/);
 assert.match(closedChoice,/직접 설명하기/);
 const replies=/<div\b[^>]*class="quick-choices intake-quick-replies"[^>]*>([\s\S]*?)<\/div>/.exec(closedChoice)?.[1]||'';
 for(const value of ['YES','NO',''])assert.ok(replies.includes(`data-value="${value}"`),'yes/no and unknown must be together in the quick replies');
 assert.match(replies,/모르겠어요/);
 intake.writingFor=choiceQuestion.identity;
 const openedChoice=intake.dialog(false);
 assert.match(openedChoice,/id="intake-writing"/);assert.match(openedChoice,/<textarea\b/);
 assert.match(openedChoice,/data-quick="adaptive-next"/);
 assert.match(intake.dialog(true),/<textarea\b[^>]*disabled/,'waiting must keep the opened writer visible and disabled');
 intake.writingFor='a.previous.question@row';
 assert.doesNotMatch(intake.dialog(false),/<textarea\b/,'opening one question must not open a different question');
 intake.text='추가 설명 <보관> & 내용';
 assert.match(intake.dialog(false),/추가 설명 &lt;보관&gt; &amp; 내용/,'a nonempty draft must remain visible and escaped even without an explicit writer flag');
 intake.text=' \n\t ';
 assert.doesNotMatch(intake.dialog(false),/<textarea\b/,'whitespace is not a draft that forces writing open');
 intake.text='';intake.writingFor=null;intake.state.ai={status:'ERROR',reason:'TIMEOUT'};
 const errorChoice=intake.dialog(false);
 assert.doesNotMatch(errorChoice,/<textarea\b/,'an AI error alone must not expand the optional writing section');
 const retry=/<button\b[^>]*data-quick="adaptive-next"[^>]*>/.exec(errorChoice)?.[0];
 assert.ok(retry,'a failed connection must still be retryable without opening the writer');
 assert.doesNotMatch(retry,/\bdisabled\b/);assert.match(errorChoice,/다시 시도/);
 assert.match(/<button\b[^>]*data-quick="adaptive-next"[^>]*>/.exec(intake.dialog(true))?.[0]||'',/\bdisabled\b/);
 delete intake.state.ai;
 for(const fallback of [question,{...choiceQuestion,kind:'text'},
  {...choiceQuestion,choices:[]},{...choiceQuestion,choices:undefined},{...choiceQuestion,choices:null}]) {
  intake.questions=[fallback];
  assert.match(intake.dialog(false),/<textarea\b/,'number/text or unavailable choices must retain the natural-language answer route');
  assert.match(intake.dialog(false),/data-quick="adaptive-next"/);
  assert.doesNotMatch(intake.dialog(false),/data-quick="intake-write"/);
 }
 intake.questions=[];
 assert.match(intake.dialog(false),/<textarea\b/,'a completed question set must still allow extra task information');
 Object.assign(intake,beforeChoices);

 // Writer state belongs to the current draft, including retry and revision conflicts.
 let writingReply={...structuredClone(choiceState),reason:'TIMEOUT',ai:{status:'ERROR',reason:'TIMEOUT'}},writingFailure=false;
 const writingClient=new AdaptiveIntake({changed(){},notify(){},api:async method=>{
  if(method==='intake_contract')return contract;
  if(method==='custom_session')return structuredClone(choiceState);
  if(writingFailure)throw Error('합성 저장 오류');
  return structuredClone(writingReply);
 }});
 await writingClient.open(1,{});writingClient.dialogOpen=true;
 writingClient.writingFor=choiceQuestion.identity;writingClient.text='계속 보관할 초안';
 await writingClient.turn(writingClient.text);
 assert.equal(writingClient.writingFor,choiceQuestion.identity);assert.equal(writingClient.text,'계속 보관할 초안');
 assert.match(writingClient.dialog(false),/계속 보관할 초안/);
 writingFailure=true;await assert.rejects(()=>writingClient.turn(writingClient.text),/합성 저장 오류/);
 assert.equal(writingClient.writingFor,choiceQuestion.identity);assert.equal(writingClient.text,'계속 보관할 초안');
 writingFailure=false;writingReply={...structuredClone(choiceState),reason:'INPUT_CHANGED'};
 await writingClient.turn(writingClient.text);
 assert.equal(writingClient.writingFor,choiceQuestion.identity,'a revision conflict must not discard an opened draft');
 assert.equal(writingClient.text,'계속 보관할 초안');
 writingReply=structuredClone(choiceState);
 await writingClient.turn('',[],false);
 assert.equal(writingClient.writingFor,choiceQuestion.identity,'an unrelated autosave must not close the writer');
 assert.equal(writingClient.text,'계속 보관할 초안');
 writingReply.questions=[{...choiceQuestion,identity:'custom.confirm@next',condition:'next'}];
 await writingClient.turn(writingClient.text);
 assert.equal(writingClient.writingFor,null,'a successful planned turn must reset the explicit writer');
 assert.equal(writingClient.text,'');assert.doesNotMatch(writingClient.dialog(false),/<textarea\b/,'the next choice should return to quick replies');
 writingClient.writingFor=writingReply.questions[0].identity;writingClient.reset();
 assert.equal(writingClient.writingFor,null,'reset must not carry an opened writer into another task');
 // Paired left/right questions require two independent, explicit choices.
 assert.ok(intake.pairValues instanceof Map,'pair selections need identity-based state');
 const beforePair={state:intake.state,questions:intake.questions,text:intake.text,writingFor:intake.writingFor};
 const rightQuestion={...choiceQuestion,target:'manual.RIGHT.coupling',identity:'manual.RIGHT.coupling@row',
  text:'오른손 잡기 상태 <확인>',destination:{type:'manual',scope:'RIGHT',field:'coupling'},choices:[{value:'POOR',label:'오른손 선택 & 원본'},{value:'GOOD',label:'오른손 양호'}]};
 const leftQuestion={...choiceQuestion,target:'manual.LEFT.coupling',identity:'manual.LEFT.coupling@row',
  text:'왼손 잡기 상태 <확인>',destination:{type:'manual',scope:'LEFT',field:'coupling'},choices:[{value:'GOOD',label:'왼손 선택 <원본>'},{value:'FAIR',label:'왼손 보통'}],paired_question:rightQuestion};
 const pairedState={...structuredClone(initial),facts:[],questions:[leftQuestion]};
 intake.state=pairedState;intake.questions=[leftQuestion];intake.text='';intake.writingFor=null;intake.pairValues.clear();
 const pairButton=(html,identity,value)=>[...html.matchAll(/<button\b[^>]*>/g)].map(m=>m[0]).find(tag=>tag.includes(`data-intake-pair-pick="${identity}"`)&&tag.includes(`data-value="${value}"`));
 const pairSave=html=>/<button\b[^>]*data-quick="intake-pair-save"[^>]*>/.exec(html)?.[0];
 const pairedClosed=intake.dialog(false);
 assert.doesNotMatch(pairedClosed,/<textarea\b|data-quick="adaptive-next"/,'paired choice questions also start without a writing form');
 assert.match(pairSave(pairedClosed)||'',/\bdisabled\b/,'no default choice may permit submitting a pair');
 for(const [identity,values] of [[leftQuestion.identity,['GOOD','FAIR','']],[rightQuestion.identity,['POOR','GOOD','']]]){
  for(const value of values){const button=pairButton(pairedClosed,identity,value);assert.ok(button,'each side must keep its own choices plus explicit unknown');assert.match(button,/aria-pressed="false"/);}
 }
 assert.ok(!pairButton(pairedClosed,rightQuestion.identity,'FAIR'),'one side must not inherit the other side’s option set');
 assert.match(pairedClosed,/왼손 선택 &lt;원본&gt;/);assert.match(pairedClosed,/오른손 선택 &amp; 원본/);
 assert.doesNotMatch(pairedClosed,/<원본>|<확인>/,'both question and choice labels must be escaped');
 assert.equal((pairedClosed.match(/<legend>왼쪽<\/legend>/g)||[]).length,1);assert.equal((pairedClosed.match(/<legend>오른쪽<\/legend>/g)||[]).length,1,'both sides must have distinct labels');
 assert.equal(intake.parseValue(rightQuestion.identity,'POOR'),'POOR','the paired field must use its own choices when parsing');
 assert.equal(intake.parseValue(rightQuestion.identity,''),null);
 intake.pairValues.set(leftQuestion.identity,'GOOD');
 const halfPair=intake.dialog(false);
 assert.match(pairButton(halfPair,leftQuestion.identity,'GOOD'),/aria-pressed="true"/);
 assert.match(pairButton(halfPair,rightQuestion.identity,'GOOD'),/aria-pressed="false"/,'choosing left must not select a value on right');
 assert.match(pairSave(halfPair),/\bdisabled\b/,'one answered side is still an incomplete pair');
 intake.pairValues.set(rightQuestion.identity,null);
 const unknownPair=intake.dialog(false);
 assert.match(pairButton(unknownPair,rightQuestion.identity,''),/aria-pressed="true"/,'explicit unknown must remain selected');
 assert.doesNotMatch(pairSave(unknownPair),/\bdisabled\b/,'explicit unknown counts as an answer, not a missing selection');
 intake.pairValues.set(rightQuestion.identity,'POOR');
 const differentPair=intake.dialog(false);
 assert.match(pairButton(differentPair,leftQuestion.identity,'GOOD'),/aria-pressed="true"/);
 assert.match(pairButton(differentPair,rightQuestion.identity,'POOR'),/aria-pressed="true"/,'left and right may have different actual values');
 assert.match(pairSave(intake.dialog(true)),/\bdisabled\b/,'a complete pair must not submit again while saving');
 intake.text='양손 상태가 달라요 <초안>';
 assert.match(intake.dialog(false),/<textarea\b/);assert.match(intake.dialog(false),/양손 상태가 달라요 &lt;초안&gt;/);
 assert.equal(intake.pairValues.get(rightQuestion.identity),'POOR','opening a free-text draft must not discard pair selections');
 intake.text='';intake.writingFor=leftQuestion.identity;assert.match(intake.dialog(false),/<textarea\b/);
 intake.writingFor=null;
 const zeroQuestion={...leftQuestion,choices:[{value:0,label:'실제 0'},{value:false,label:'실제 false'}],paired_question:{...rightQuestion,choices:[{value:0,label:'오른쪽 0'},{value:false,label:'오른쪽 false'}]}};
 intake.questions=[zeroQuestion];intake.pairValues.set(leftQuestion.identity,0);intake.pairValues.set(rightQuestion.identity,false);
 assert.equal(intake.parseValue(rightQuestion.identity,'false'),false);
 assert.match(pairButton(intake.dialog(false),leftQuestion.identity,'0'),/aria-pressed="true"/);
 assert.match(pairButton(intake.dialog(false),rightQuestion.identity,'false'),/aria-pressed="true"/);
 assert.doesNotMatch(pairSave(intake.dialog(false)),/\bdisabled\b/,'actual zero and false are both explicit selections');
 intake.pairValues.clear();Object.assign(intake,beforePair);

 // Failed turns retain only selections belonging to the returned question identities.
 let pairReply={...structuredClone(pairedState),reason:'TIMEOUT',ai:{status:'ERROR',reason:'TIMEOUT'}},pairFailure=false,pairLate=null;const pairCalls=[];
 const pairClient=new AdaptiveIntake({changed(){},notify(){},api:async (method,args)=>{
  if(method==='intake_contract')return contract;
  if(method==='custom_session')return structuredClone(pairedState);
  pairCalls.push(args);
  if(pairLate)return await pairLate;
  if(pairFailure)throw Error('합성 묶음 저장 오류');
  return structuredClone(pairReply);
 }});
 await pairClient.open(1,{});pairClient.dialogOpen=true;
 pairClient.pairValues.set(leftQuestion.identity,'GOOD');pairClient.pairValues.set('an.old.question@row','NO');
 pairClient.text='보존할 좌우 설명';pairClient.writingFor=leftQuestion.identity;
 await pairClient.turn(pairClient.text);
 assert.deepEqual(pairCalls[0].focus,[{target:leftQuestion.target,condition:leftQuestion.condition},{target:rightQuestion.target,condition:rightQuestion.condition}],'free-text turns must retain both sides in their question context');
 assert.deepEqual(pairCalls[0].answers,[],'a natural-language turn must not invent a missing-side answer');
 assert.equal(pairClient.pairValues.get(leftQuestion.identity),'GOOD');
 assert.equal(pairClient.pairValues.has(rightQuestion.identity),false,'a failed partial answer must not fill the other side');
 assert.equal(pairClient.pairValues.has('an.old.question@row'),false,'stale unrelated pair choices must be discarded');
 assert.equal(pairClient.text,'보존할 좌우 설명');assert.equal(pairClient.writingFor,leftQuestion.identity);
 pairClient.pairValues.set(rightQuestion.identity,'POOR');
 const explicitPair=[{target:leftQuestion.target,condition:leftQuestion.condition,value:'GOOD'},{target:rightQuestion.target,condition:rightQuestion.condition,value:'POOR'}];
 pairFailure=true;await assert.rejects(()=>pairClient.turn(pairClient.text,explicitPair),/합성 묶음 저장 오류/);
 assert.equal(pairClient.pairValues.get(leftQuestion.identity),'GOOD','a thrown save failure must preserve pending explicit selections');
 assert.equal(pairClient.pairValues.get(rightQuestion.identity),'POOR');assert.equal(pairClient.text,'보존할 좌우 설명');
 await pairClient.flush(); // respondIntake flushes before retrying a submitted reply.
 assert.equal(pairClient.pairValues.get(leftQuestion.identity),'GOOD');assert.equal(pairClient.pairValues.get(rightQuestion.identity),'POOR');
 assert.equal(pairClient.text,'보존할 좌우 설명','preparing a reply retry must not clear the user draft');
 const beforeReplyRetry=pairCalls.length;pairFailure=false;
 await pairClient.turn(pairClient.text,explicitPair);
 assert.equal(pairCalls.length,beforeReplyRetry+1,'a transport failure must not permanently block the next submitted reply');
 assert.deepEqual(pairCalls.at(-1).answers,explicitPair,'retry must resend the actual separate left and right answers');
 assert.equal(pairClient.pairValues.get(leftQuestion.identity),'GOOD');assert.equal(pairClient.pairValues.get(rightQuestion.identity),'POOR');

 // Unsaved editor inputs still block result/reply navigation after an autosave failure.
 pairFailure=true;pairClient.schedule(leftQuestion.identity,'GOOD',()=>{});
 await assert.rejects(()=>pairClient.flush(),/합성 묶음 저장 오류/);
 assert.equal(pairCalls.at(-1).plan,false,'the pending input is an autosave, not a submitted reply');
 const afterAutosaveFailure=pairCalls.length;
 await assert.rejects(()=>pairClient.flush(),/합성 묶음 저장 오류/,'the saved autosave error must continue to block navigation');
 assert.equal(pairCalls.length,afterAutosaveFailure,'a blocked flush must not silently retry or discard an unsaved field');
 assert.equal(pairClient.text,'보존할 좌우 설명');assert.equal(pairClient.pairValues.get(rightQuestion.identity),'POOR');
 pairFailure=false;await pairClient.answer(leftQuestion.identity,'GOOD');await pairClient.flush();
 assert.equal(pairClient.saveError,'','a successful explicit autosave retry must remove the navigation block');
 pairClient.pairValues.set(rightQuestion.identity,null);
 pairReply={...structuredClone(pairedState),questions:[{...leftQuestion,paired_question:undefined}],reason:'TIMEOUT'};
 await pairClient.turn(pairClient.text);
 assert.equal(pairClient.pairValues.get(leftQuestion.identity),'GOOD');assert.equal(pairClient.pairValues.has(rightQuestion.identity),false,'a server-resolved counterpart must not leak into the remaining single question');
 pairReply={...structuredClone(pairedState),questions:[{...choiceQuestion,identity:'new.question@row'}],reason:'TIMEOUT'};
 await pairClient.turn(pairClient.text);
 assert.equal(pairClient.pairValues.size,0,'a saved answer followed by AI failure may advance to an entirely different question');
 pairReply=structuredClone(pairedState);pairClient.pairValues.set(leftQuestion.identity,'GOOD');pairClient.pairValues.set(rightQuestion.identity,'POOR');
 await pairClient.turn(pairClient.text);
 assert.equal(pairClient.pairValues.size,0,'a successful planned turn must clear the submitted selections');
 pairClient.pairValues.set(leftQuestion.identity,'GOOD');
 let releasePair;pairLate=new Promise(resolve=>{releasePair=resolve;});
 const pendingPair=pairClient.turn('지연된 좌우 답변');await new Promise(resolve=>setImmediate(resolve));pairClient.reset();
 releasePair({...structuredClone(pairedState),reason:'TIMEOUT'});await pendingPair;
 assert.equal(pairClient.pairValues.size,0);assert.equal(pairClient.state,null,'a late pair response must not revive a reset workflow');
 // Groups can save any explicitly selected subset without inventing missing answers.
 const groupMembers=Array.from({length:9},(_,i)=>({...choiceQuestion,target:`work_type.sample_${i}`,identity:`work_type.sample_${i}@row`,
  label:`작업 특징 ${i+1}`,destination:{type:'work_type'},choices:i===0?[{value:0,label:'실제 0'},{value:1,label:'실제 1'}]:i===1?[{value:false,label:'아니오'},{value:true,label:'예'}]:choiceQuestion.choices}));
 groupMembers[8]={...groupMembers[8],label:'작업 <img data-x=1> & 아홉',choices:[{value:'YES" data-danger="1',label:'선택 <해당>'},{value:'NO',label:'아니오'}]};
 const groupedQuestion={...choiceQuestion,target:'other_work',identity:'other_work@row',ai_writable:false,group_title:'관련 작업 <확인>',answer_questions:groupMembers,paired_question:rightQuestion};
 const groupState={...structuredClone(initial),facts:[],questions:[groupedQuestion],remaining_count:9,preview:{}};
 const beforeGroup={state:intake.state,questions:intake.questions,text:intake.text,writingFor:intake.writingFor};
 intake.state=groupState;intake.questions=[groupedQuestion];intake.text='';intake.writingFor=null;intake.pairValues.clear();
 const groupSave=html=>/<button\b[^>]*data-quick="intake-group-save"[^>]*>/.exec(html)?.[0];
 let groupHtml=intake.dialog(false);
 assert.equal((groupHtml.match(/data-intake-group-value=/g)||[]).length,9,'one screen must contain the current actual group members');
 assert.match(groupHtml,/관련 작업 &lt;확인&gt;/);assert.match(groupHtml,/아는 항목만 선택해도 돼요/);assert.match(groupHtml,/모두 답하지 않아도/);
 assert.doesNotMatch(groupHtml,/data-intake-pair-pick=|data-quick="allno"|<textarea\b/,'groups take priority over legacy pairs and never offer implicit all-no');
 assert.match(groupSave(groupHtml),/\bdisabled\b/);
 assert.match(groupHtml,/value="__unselected__" selected/);assert.match(groupHtml,/value="__unknown__"/,'unknown and no selection must have separate option values');
 assert.match(groupHtml,/&lt;img data-x=1&gt;/);assert.match(groupHtml,/YES&quot; data-danger=&quot;1/);assert.doesNotMatch(groupHtml,/<img\b|data-danger="1"/);
 intake.pairValues.set(groupedQuestion.identity,'NO');intake.pairValues.set(rightQuestion.identity,'POOR');
 assert.match(groupSave(intake.dialog(false)),/\bdisabled\b/,'virtual root or legacy pair values do not answer actual group fields');
 assert.equal(intake.selectGroupValue(groupMembers[0].identity,'0'),true);
 assert.equal(intake.selectGroupValue(groupMembers[1].identity,'false'),true);
 assert.equal(intake.selectGroupValue(groupMembers[2].identity,'__unknown__'),true);
 assert.deepEqual(intake.selectedAnswers().map(a=>a.value),[0,false,null]);
 assert.doesNotMatch(groupSave(intake.dialog(false)),/\bdisabled\b/,'a partial group is enough to save');
 assert.equal(intake.selectedAnswers().length,3,'six unselected fields must stay absent from answers');
 assert.ok(!intake.selectedAnswers().some(a=>a.target==='other_work'||a.target===rightQuestion.target));
 assert.equal(intake.selectGroupValue(groupMembers[0].identity,'invalid'),false);assert.equal(intake.pairValues.get(groupMembers[0].identity),0);
 intake.selectGroupValue(groupMembers[0].identity,'__unselected__');assert.equal(intake.pairValues.has(groupMembers[0].identity),false);
 assert.deepEqual(intake.selectedAnswers().map(a=>a.value),[false,null]);
 intake.selectGroupValue(groupMembers[8].identity,'YES" data-danger="1');assert.equal(intake.selectedAnswers().at(-1).value,'YES" data-danger="1','service choice strings must keep their original values');
 assert.match(groupSave(intake.dialog(true)),/\bdisabled\b/);assert.match(intake.dialog(true),/<select\b[^>]*disabled/);
 intake.text='별도로 남겨 둔 설명 <초안>';assert.match(intake.dialog(false),/별도로 남겨 둔 설명 &lt;초안&gt;/);
 intake.questions=[{...groupedQuestion,answer_questions:[question]}];assert.match(intake.dialog(false),/<textarea\b/,'an unexpected non-choice group still needs a text fallback');
 intake.pairValues.clear();Object.assign(intake,beforeGroup);

 let groupReply=structuredClone(groupState),groupThrow=false,groupLate=null;const groupCalls=[];
 const groupClient=new AdaptiveIntake({changed(){},notify(){},api:async(method,args)=>{
  if(method==='intake_contract')return contract;if(method==='custom_session')return structuredClone(groupState);
  groupCalls.push(args);if(groupLate)return await groupLate;if(groupThrow)throw Error('합성 그룹 통신 오류');return structuredClone(groupReply);
 }});
 await groupClient.open(1,{});groupClient.dialogOpen=true;
 groupClient.selectGroupValue(groupMembers[0].identity,'0');groupClient.selectGroupValue(groupMembers[1].identity,'false');groupClient.text='아직 보내지 않은 설명';groupClient.writingFor=groupedQuestion.identity;
 groupThrow=true;await assert.rejects(()=>groupClient.turn('',groupClient.selectedAnswers()),/합성 그룹 통신 오류/);await groupClient.flush();
 assert.equal(groupClient.pairValues.get(groupMembers[0].identity),0);assert.equal(groupClient.pairValues.get(groupMembers[1].identity),false);assert.equal(groupClient.text,'아직 보내지 않은 설명');
 groupThrow=false;groupReply={...structuredClone(groupState),reason:'INPUT_CHANGED',questions:[{...groupedQuestion,answer_questions:[groupMembers[1],groupMembers[2]]}]};
 await groupClient.turn('',groupClient.selectedAnswers());
 assert.equal(groupCalls[0].focus.length,9);assert.ok(groupCalls[0].focus.every(f=>f.target!=='other_work'),'the virtual grouping prompt must not become an answer target or AI field');
 assert.equal(groupClient.pairValues.has(groupMembers[0].identity),false);assert.equal(groupClient.pairValues.get(groupMembers[1].identity),false,'only choices still belonging to returned group members survive a revision conflict');
 assert.equal(groupClient.field(groupMembers[2].identity).target,groupMembers[2].target);
 groupReply={...structuredClone(groupState),questions:[]};await groupClient.turn('',groupClient.selectedAnswers());
 assert.equal(groupClient.text,'아직 보내지 않은 설명','a successful structured save must not erase separate unsent prose');assert.equal(groupClient.pairValues.size,0);

 // Exercise real QuickFlow event/submit methods without opening a DB or Electron.
 const {QuickFlow}=await import(pathToFileURL(path.join(__dirname,'../frontend/quick-flow.js')).href);
 await groupClient.open(1,{});groupClient.dialogOpen=true;groupClient.text='아직 보내지 않은 설명';
 const saveControl={disabled:true},flow=Object.create(QuickFlow.prototype);let enables=0,finished=0,rendered=0,submitted=null;const labels=[];
 Object.assign(flow,{intake:groupClient,busy:false,host:{querySelector:()=>saveControl},keepDraft(){},render(){rendered++;},ensureAiOn:async()=>{enables++;},finish:async()=>{finished++;},run:async(label,action)=>{labels.push(label);await action();}});
 flow.respondIntake=(...args)=>(submitted=QuickFlow.prototype.respondIntake.apply(flow,args));
 flow.input({type:'change',target:{dataset:{intakeGroupValue:groupMembers[0].identity},value:'0'}});
 assert.equal(saveControl.disabled,false);assert.equal(groupClient.pairValues.get(groupMembers[0].identity),0);assert.equal(rendered,0,'native select changes must not replace the dialog or jump its scroll position');
 flow.busy=true;flow.input({type:'change',target:{dataset:{intakeGroupValue:groupMembers[1].identity},value:'false'}});assert.equal(groupClient.pairValues.has(groupMembers[1].identity),false);flow.busy=false;
 flow.click({target:{closest:()=>({disabled:false,dataset:{quick:'intake-group-save'}})}});await submitted;
 assert.equal(enables,0,'structured answers must not make a settings/AI enable request');assert.match(labels[0],/답변을 저장/);
 assert.deepEqual(groupCalls.at(-1).answers,[{target:groupMembers[0].target,condition:'row',value:0}]);assert.equal(groupCalls.at(-1).text,'');
 assert.equal(finished,0,'unsent prose must keep the dialog open even when all structured questions are resolved');assert.equal(groupClient.dialogOpen,true);assert.equal(groupClient.text,'아직 보내지 않은 설명');
 await flow.respondIntake();assert.equal(enables,1,'sending the actual prose still enables the AI flow');assert.equal(finished,1);assert.equal(groupClient.text,'');
 await groupClient.open(1,{});groupClient.selectGroupValue(groupMembers[1].identity,'false');let releaseGroup;groupLate=new Promise(resolve=>{releaseGroup=resolve;});
 const pendingGroup=groupClient.turn('',groupClient.selectedAnswers());await new Promise(resolve=>setImmediate(resolve));groupClient.reset();releaseGroup(structuredClone(groupState));await pendingGroup;
 assert.equal(groupClient.state,null);assert.equal(groupClient.pairValues.size,0,'a delayed group reply must not restore a reset task');
 // Restoring saved work resets its data while the surrounding request keeps ownership.
 // Use the actual run/reset/restoration methods so a lost timer cannot hide the final screen.
 const storageDescriptor=Object.getOwnPropertyDescriptor(globalThis,'localStorage');
 let restorationDraft=null;
 Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{
  getItem:key=>key==='loco.quick.draft.v1'?restorationDraft:null,
  setItem:(key,value)=>{if(key==='loco.quick.draft.v1')restorationDraft=value;},
  removeItem:key=>{if(key==='loco.quick.draft.v1')restorationDraft=null;},
 }});
 try {
  for(const target of ['result','provisional','questions']) {
   const survey={survey_id:31,created_at:'survey-lifetime',title:'saved survey'};
   const savedTask={task_id:32,survey_id:31,created_at:'task-lifetime',latest_analysis_id:33,capture:{slots:[]},conditions:{test_metadata:{}}};
   const restoredState={task:savedTask,preview:{questions:[]},questions:target==='questions'?[question]:[],ai:{status:'CONNECTED'}};
   let releaseRestore,openStarted=false,intakeResets=0,duplicateActions=0;
   const delayedRestore=new Promise(resolve=>{releaseRestore=resolve;});
   const restoredFlow=Object.create(QuickFlow.prototype),restorationRenders=[],restoreErrors=[];
   Object.assign(restoredFlow,{busy:false,step:'home',settings:{gpt_enabled:true},host:{querySelectorAll:()=>[]},
    intake:{reset(){intakeResets++;this.state=null;this.dialogOpen=false;this.text='';},hasSession:()=>true,restorePage(shown){this.pageShown=Boolean(shown);},
     async open(){openStarted=true;this.state=await delayedRestore;return this.state;}},
    render(){restorationRenders.push({step:this.step,busy:this.busy});},onError:error=>restoreErrors.push(error),
    api:async method=>{
     if(method==='get_survey')return survey;
     if(method==='list_tasks')return [savedTask];
     if(method==='get_task_result')return {analysis:{analysis_id:33}};
     if(method==='get_analysis')return {analysis_id:33};
     if(method==='get_task')return {task:savedTask,photos:[]};
     if(method==='get_settings')return {gpt_enabled:true};
     throw Error('Unexpected restoration API '+method);
    },
   });
   restorationDraft=JSON.stringify({surveyId:31,createdAt:survey.created_at,taskId:32,photos:{},adaptive:true,
    step:target==='questions'?'questions':'start',reply:'보존할 작성 중 답변',intakeText:'저장된 작업 설명'});
   const restoring=target==='result'?restoredFlow.openExisting(31):restoredFlow.resumeDraft();
   try {
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(openStarted,true,'restoration must reach the delayed intake request');
    assert.equal(intakeResets,1,'restoration must reset stale intake data');
    assert.equal(typeof restoredFlow.busy,'string','reset inside restoration must retain its busy label');
    assert.ok(restoredFlow.busyTimer,'reset inside restoration must retain the owning activity timer');
    assert.equal(typeof restoredFlow.busyStartedAt,'number','elapsed activity must continue while intake is loading');
    await restoredFlow.run('duplicate request',async()=>{duplicateActions++;});
    assert.equal(duplicateActions,0,'restoring work must keep concurrent user operations locked');
   } finally {
    releaseRestore(restoredState);
    await restoring;
   }
   assert.deepEqual(restoreErrors,[]);
   assert.equal(restoredFlow.step,target);
   assert.equal(restoredFlow.busy,false);
   assert.equal(restoredFlow.busyTimer,null,'completed restoration must release its timer');
   assert.equal(restoredFlow.busyStartedAt,null,'completed restoration must release its elapsed origin');
   assert.deepEqual(restorationRenders.at(-1),{step:target,busy:false},'the restored screen must actually be rendered after its busy state clears');
   assert.equal(restorationRenders.length,2,'restoration should render its loading and completed screens');
   if(target!=='result')assert.equal(restoredFlow.intake.text,'보존할 작성 중 답변');
  }
 } finally {
  if(storageDescriptor)Object.defineProperty(globalThis,'localStorage',storageDescriptor);
  else delete globalThis.localStorage;
 }
 // A single visible question and saved fact count are not the calculation scope.
 const priorState=intake.state, priorQuestions=intake.questions;
 intake.state={...structuredClone(initial),facts:[
  {identity:question.identity,target:question.target,condition:'row',value:0,state:'KNOWN',source:'USER'},
  {identity:'other.unknown@row',target:'other.unknown',condition:'row',value:null,state:'UNKNOWN',source:'USER'},
  {identity:'other.unrelated@row',target:'other.unrelated',condition:'row',value:99,state:'KNOWN',source:'AI'},
 ],remaining_count:17,progress:{completed_count:7,total_count:24,remaining_count:17,percent:29,dynamic:true}};
 intake.questions=[question];
 const progressbar=html=>/<[^>]+\brole="progressbar"[^>]*>/.exec(html)?.[0];
 const assertProgress=(html,{completed_count:done,total_count:total,remaining_count:left,percent})=>{
  const bar=progressbar(html);
  assert.ok(bar,'a valid service progress DTO must produce an accessible horizontal progress bar');
  assert.match(bar,/aria-valuemin="0"/); assert.match(bar,/aria-valuemax="100"/);
  assert.ok(bar.includes(`aria-valuenow="${percent}"`),'the bar must use the service percentage');
  assert.match(html,new RegExp(`<strong>\\s*${percent}%\\s*</strong>`),'show the same percentage as visible text');
  assert.match(html,new RegExp(`class="intake-progress-fill"[^>]*style="[^\"]*width:\\s*${percent}%`),'fill width must match the accessible value');
  const counts=(/class="intake-progress-counts"[^>]*>([\s\S]*?)<\/p>/.exec(html)?.[1]||'').replace(/<[^>]*>/g,'');
  assert.match(counts,new RegExp(`확인한\\s*항목\\s*${done}`));
  assert.match(counts,new RegExp(`전체\\s*${total}`));
  assert.match(counts,new RegExp(`남은\\s*항목\\s*${left}`));
 };
 assertProgress(intake.dialog(false),intake.state.progress);
 assert.match(intake.dialog(false),/답변에 따라/,'dynamic scope must be explained instead of promising a fixed number of turns');
 assertProgress(intake.dialog(true),intake.state.progress);
 assert.match(intake.dialog(true),/답변을 정리하는 중/,'waiting must preserve the last confirmed progress');
 intake.state.ai={status:'ERROR',reason:'TIMEOUT'};
 assertProgress(intake.dialog(false),intake.state.progress);
 assert.match(intake.dialog(false),/다시 시도/,'failure must preserve progress and retry');
 intake.state.remaining_count=10; intake.state.progress={completed_count:2,total_count:12,remaining_count:10,percent:16,dynamic:true};
 assertProgress(intake.dialog(false),intake.state.progress);
 intake.state.remaining_count=23; intake.state.progress={completed_count:2,total_count:25,remaining_count:23,percent:8,dynamic:true};
 assertProgress(intake.dialog(false),intake.state.progress); // New relevant fields may lower the percentage.
 assert.equal(intake.questions.length,1,'the displayed question slice is unrelated to the remaining count');

 intake.state.remaining_count=17;
 const validProgress={completed_count:7,total_count:24,remaining_count:17,percent:29,dynamic:true};
 for(const invalid of [undefined,null,{},
  {...validProgress,completed_count:-1}, {...validProgress,total_count:Infinity},
  {...validProgress,remaining_count:NaN}, {...validProgress,percent:101},
  {...validProgress,percent:'29'}, {...validProgress,total_count:24.5},
  {...validProgress,total_count:Number.MAX_SAFE_INTEGER+1},
  {...validProgress,remaining_count:16}, {...validProgress,percent:30},
 ]) {
  intake.state.progress=invalid;
  const html=intake.dialog(false);
  assert.equal(progressbar(html),undefined,'old/invalid DTOs must not invent a percentage');
  assert.doesNotMatch(html,/%/,'a fabricated percentage must not be visible either');
  assert.match(html.replace(/<[^>]*>/g,''),/남은 확인 항목\s*17/,'retain only the valid legacy remaining count');
 }
 for(const invalidRemaining of [undefined,-1,NaN,Infinity,1.5,'17']) {
  intake.state.progress=null; intake.state.remaining_count=invalidRemaining;
  const html=intake.dialog(false);
  assert.equal(progressbar(html),undefined);
  assert.doesNotMatch(html,/NaN|Infinity|undefined|남은\s*-|남은\s*1\.5/,'bad legacy counters must not leak into the UI');
 }
 intake.questions=[]; intake.state.questions=[]; intake.state.remaining_count=0;
 for(const progress of [
  {completed_count:1,total_count:1,remaining_count:0,percent:100,dynamic:true},
  {completed_count:0,total_count:0,remaining_count:0,percent:100,dynamic:true},
 ]) {
  intake.state.progress=progress; intake.state.complete=false;
  const html=intake.dialog(false);
  assertProgress(html,progress);
  assert.match(html,/추가 질문이 없어요/,'no candidates means no more questions, including an empty scope');
  assert.match(html,/입력·검토가 필요한 항목은 결과에서 확인해 주세요/,'a handled unknown must not be mistaken for completed calculations');
  assert.doesNotMatch(html,/계산 완료|모든 정보.*완료/);
 }
 intake.state=priorState;intake.questions=priorQuestions;
 state={...structuredClone(state),remaining_count:1,progress:{completed_count:4,total_count:5,remaining_count:1,percent:80,dynamic:true}};
 await intake.answer(question.identity,0);
 assertProgress(intake.dialog(false),state.progress);
 assert.equal(intake.questions[0].identity,question.identity,'plan:false saves may retain the previous question while progress comes from the latest service response');
 assert.ok(intake.hasSession({conditions:{test_metadata:{}}}));
 fail=true; await assert.rejects(()=>intake.answer(question.identity,12));
 assert.equal(intake.value(question.identity),12,'failed save must retain the typed value');
 assert.match(intake.summary(),/입력을 저장하지 못했어요/);
 assert.ok(intake.panel(false).includes('현재 정보로 결과 보기'));
 fail=false;
 const beforeApi=intake.api;
 intake.text='저장한 답변';
 intake.api=async()=>({...structuredClone(state),reason:'TIMEOUT',ai:{status:'ERROR',reason:'TIMEOUT'}});
 await intake.turn(intake.text);
 assert.equal(intake.text,'저장한 답변','a failed AI response must retain the written answer for retry');
 assert.match(intake.dialog(false),/다시 시도/);
 intake.api=beforeApi;
 state={...structuredClone(state),progress:{completed_count:4,total_count:5,remaining_count:1,percent:80,dynamic:true}};
 let resolve; late=new Promise(r=>{resolve=r;});
 const request=intake.turn('새 답변'); await new Promise(r=>setImmediate(r)); intake.reset();
 resolve(structuredClone(state)); await request;
 assert.equal(intake.state,null,'a response from a closed workflow must not resurrect it');
 assert.equal(intake.dialog(false),'','a late response must not resurrect the progress UI either');
 console.log('PASS dynamic methods/metadata/unit/limits, choice-first writing, partial grouped answers and independent paired selections/draft ownership, zero/unknown saves, saved-work restoration activity ownership/final render, service progress boundaries, plain user status without provider metadata, reply retry without bypassing failed autosaves and stale response ownership');
})().catch(error=>{console.error(error);process.exitCode=1;});
