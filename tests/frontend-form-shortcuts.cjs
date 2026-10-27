const {assert,pose,fact,setup,count,dataRow,noImplicitControls,edit}=require('./intake-editor-fixture.cjs');
(async()=>{
 const left=pose('LEFT','wrist_base','photo:2',{choices:[{value:1,label:'낮음'},{value:2,label:'높음'}]}),right={...pose('RIGHT','wrist_base'),choices:left.choices};
 const other=pose('LEFT','wrist_base','photo:3',{choices:left.choices,suggestion:{value:2,quote:'다른 사진',photo_label:'다른 사진'}});
 const t=await setup([left,right,other],[fact(left,null,'UNKNOWN','USER'),fact(right,2,'KNOWN','POSE')]);
 noImplicitControls(t.editor());assert.doesNotMatch(t.editor(),/한 번에 채우기|같아요|맞아요, 채우기/);
 assert.match(dataRow(t.editor(),left.identity),/모름으로 저장/);assert.match(dataRow(t.editor(),other.identity),/미확인/,'a different photo suggestion is not copied into a value');
 assert.deepEqual(t.intake.formAnswers(),[]);t.intake.dataEditing.add(other.identity);assert.equal(count(t.editor(),'data-intake-form'),1);
 edit(t.flow,other,'1');assert.deepEqual(t.intake.formAnswers(),[{target:other.target,condition:'photo:3',value:1}]);
 assert.equal(t.intake.formValue(right),2);assert.equal(t.intake.formValues.has(left.identity),false);assert.equal(t.state.facts[0].source,'USER');
 t.intake.dataEditing.add(left.identity);edit(t.flow,left,'');assert.deepEqual(t.intake.formAnswers().find(a=>a.condition==='photo:2'),{target:left.target,condition:'photo:2',value:null});
 assert.equal(t.intake.formAnswers().some(a=>a.target===right.target),false,'untouched opposite arm never becomes a copied USER answer');
 console.log('PASS no bulk/copy/suggestion controls, per-photo explicit edit, USER unknown and untouched opposite side preserved');
})().catch(e=>{console.error(e);process.exitCode=1;});
