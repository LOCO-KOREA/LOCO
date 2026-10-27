const {assert,field,number,pose,fact,setup,count,noImplicitControls}=require('./intake-editor-fixture.cjs');
(async()=>{
 const members=Array.from({length:5},(_,i)=>field('work_type.pending_'+i,'work_type'));
 const q=field('other_work','other_work',{text:'아래 작업 특징도 있나요?',ai_writable:false,answer_questions:members});
 const numeric=Array.from({length:15},(_,i)=>number('card.extra.time_'+i));
 const measured=pose('RIGHT','upper_arm_base');
 const t=await setup([q,...numeric,measured],[fact(measured,2,'ESTIMATED','POSE')],[q]);
 const html=t.defaultHtml();assert.equal(count(html,'data-intake-question'),1);assert.equal(count(html,'data-intake-pick'),3,'one grouped work question has yes/no/unknown');
 assert.equal(count(html,'data-intake-group-value'),0,'other_work does not expand five features into five questions');
 assert.doesNotMatch(html,/data-intake-form=|data-intake-flag=|남은 항목|role="progressbar"/);
 assert.equal(t.intake.questions.length,1);assert.equal(t.intake.formFields().length,17,'editing metadata is deliberately larger than the question queue');
 const editor=t.editor();noImplicitControls(editor);assert.equal(count(editor,'data-intake-data'),17);assert.equal(count(editor,'data-intake-edit-field'),17);
 assert.match(editor,/작업·조사 정보/);assert.match(editor,/위팔 들림/);
 t.intake.dataEditing.add(numeric[0].identity);assert.equal(count(t.editor(),'data-intake-form'),1);assert.deepEqual(t.intake.formAnswers(),[]);
 t.intake.questions=t.intake.questionQueue({...t.state,questions:[measured]});assert.equal(t.intake.hasOpenItems(),false);assert.equal(t.intake.openPageOnce(),false);
 console.log('PASS selected one question vs 17 data fields, no 15-question bypass, explicit single editor and no automatic reopening');
})().catch(e=>{console.error(e);process.exitCode=1;});
