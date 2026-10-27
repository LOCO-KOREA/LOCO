const {assert,field,number,pose,fact,setup,count,noImplicitControls,edit}=require('./intake-editor-fixture.cjs');
(async()=>{
 const work=field('work_type.lift','work_type'),mass=number('card.lift.mass','kg',{condition:'heavy',identity:'card.lift.mass@heavy'}),known=pose('RIGHT','upper_arm_base');
 const t=await setup([work,mass,known],[fact(work,'YES','KNOWN','AI'),fact(known,3,'ESTIMATED','POSE')],[mass]);
 assert.equal(count(t.defaultHtml(),'data-intake-question'),1);assert.doesNotMatch(t.defaultHtml(),/data-intake-form=/);
 noImplicitControls(t.editor());assert.deepEqual(t.intake.formAnswers(),[],'reading saved values never rewrites provenance');
 t.intake.dataEditing.add(mass.identity);assert.equal(count(t.editor(),'data-intake-form'),1);
 edit(t.flow,mass,'0');assert.deepEqual(t.intake.formAnswers(),[{target:mass.target,condition:'heavy',value:0}]);
 let fail=true,requests=0;
 t.intake.turn=async(text,answers)=>{requests++;assert.equal(text,'');assert.deepEqual(answers,[{target:mass.target,condition:'heavy',value:0}]);if(fail)throw Error('offline');return t.state;};
 await assert.rejects(t.flow.saveIntakeForm(),/offline/);assert.equal(t.intake.dialogOpen,true);assert.equal(t.intake.formValues.get(mass.identity),0);assert.equal(t.log.finished,0);
 fail=false;await t.flow.saveIntakeForm();assert.equal(requests,2);assert.equal(t.log.finished,1);assert.equal(t.intake.formValues.size,0);assert.equal(t.intake.dialogOpen,false);
 assert.deepEqual(t.state.facts.map(f=>[f.source,f.value]),[['AI','YES'],['POSE',3]],'untouched automatic facts are never submitted as USER');
 console.log('PASS current question, explicit edit, zero/condition identity, failure retention and one saved result');
})().catch(e=>{console.error(e);process.exitCode=1;});
