const assert=require('node:assert/strict');
(async()=>{
 const {userText}=await import('../frontend/user-language.js');
 const {renderQuickExplanation}=await import('../frontend/quick-explanation.js');
 const {AdaptiveIntake}=await import('../frontend/intake/client.js');
 const {QuickFlow}=await import('../frontend/quick-flow.js');
 assert.equal(userText('AI가 정리했어요.'),'AI가 정리했어요.');assert.equal(userText('계산 초안 상태는 NEEDS_INPUT입니다.'),'계산에 필요한 정보가 아직 없어요.');
 const raw='NEEDS_INPUT입니다. NOT_APPLICABLE이고 YES, NO, UNKNOWN입니다. 20kg · 0분';
 const display=userText(raw);
 assert.doesNotMatch(display,/NEEDS_INPUT|NOT_APPLICABLE|YES|UNKNOWN/);
 assert.match(display,/20kg · 0분/);assert.equal(userText('UNKNOWN_FIELD YESMAN C01-B01'),'UNKNOWN_FIELD YESMAN C01-B01');
 const content={summary:raw,criteria:[{criterion_no:1,explanation:raw}],check_items:[raw],improvement_options:[{proposal:raw}]};
 const ai={content,generated_text:raw};
 assert.doesNotMatch(renderQuickExplanation(ai,raw),/NEEDS_INPUT|NOT_APPLICABLE|UNKNOWN/);assert.equal(ai.generated_text,raw,'history is immutable');
 const fields=[{target:'a',identity:'a@default',label:'기존 시간',kind:'number',destination:{type:'criterion'}},{target:'b',identity:'b@default',label:'추가 시간',kind:'number',destination:{type:'criterion'}}];
 const intake=new AdaptiveIntake({api(){},notify(){},changed(){}});
 intake.state={contract:{policy:{text_limit:2400}},form_fields:fields,facts:[{identity:'a@default',state:'KNOWN',source:'AI',value:20}]};intake.formStage=1;intake.dialogOpen=true;
 const html=intake.dialog(false),pending=html.split('data-intake-unanswered>')[1].split('data-intake-confirmed')[0];
 assert.doesNotMatch(pending,/data-intake-form="a@default"/);assert.match(html,/data-intake-confirmed/);assert.match(html,/value="20"/);
 // Text typed in the form must be submitted when moving to results, even without a separate send click.
 intake.text='20kg 상자예요';let submitted,finished=0;
 intake.turn=async(text,answers)=>{submitted={text,answers};return intake.state;};
 const flow=Object.assign(Object.create(QuickFlow.prototype),{intake,async ensureAiOn(){},async run(label,fn){await fn();},async finish(){finished++;}});
 await flow.saveIntakeForm();assert.equal(submitted.text,'20kg 상자예요');assert.equal(finished,1);
 console.log('PASS user language, code boundaries, immutable explanation, confirmed inputs collapsed and unsent form explanation submitted');
})().catch(e=>{console.error(e);process.exitCode=1;});
