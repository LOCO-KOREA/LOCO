const {assert,pose,fact,setup,count,dataRow,noImplicitControls,edit}=require('./intake-editor-fixture.cjs');
(async()=>{
 const common=['trunk_twisted','trunk_side_bent','neck_twisted','neck_side_bent','legs_support','seated','shock_force','static_over_1min','small_repeat_over_4min','rapid_change_or_unstable'];
 const arms=['shoulder_raised','arm_abducted_or_rotated','arm_supported_or_gravity_assisted','wrist_deviated_or_twisted'];
 const rows=[...common.map(n=>pose('COMMON',n)),...['LEFT','RIGHT'].flatMap(s=>arms.map(n=>pose(s,n)))];
 const legs=rows.find(f=>f.destination.field==='legs_support');legs.choices=[{value:'UNILATERAL_OR_UNSTABLE',label:'불안정'},{value:'BILATERAL_STABLE',label:'안정'}];
 const t=await setup(rows,[fact(rows[0],'YES','ESTIMATED','VISION'),fact(rows[1],null,'UNKNOWN','USER')],rows);
 assert.equal(t.intake.questions.length,0,'18 posture values are data, not a fresh interview');assert.equal(t.intake.hasOpenItems(),false);
 const html=t.editor();assert.equal(count(html,'data-intake-data'),18);noImplicitControls(html);
 assert.match(dataRow(html,rows[0].identity),/AI 사진 관찰 · 추정값 · 현재 점수에 반영/);
 assert.match(dataRow(html,rows[1].identity),/직접 입력 · 모름으로 저장/);
 assert.match(dataRow(html,rows[2].identity),/미확인/);assert.deepEqual(t.intake.formAnswers(),[],'unselected rows must not silently become NO');
 t.intake.dataEditing.add(legs.identity);assert.equal(count(t.editor(),'data-intake-form'),1);
 edit(t.flow,legs,'BILATERAL_STABLE');assert.deepEqual(t.intake.formAnswers(),[{target:legs.target,condition:'photo:2',value:'BILATERAL_STABLE'}]);
 assert.equal(t.intake.formValues.has(rows[2].identity),false);assert.equal(t.state.facts[0].source,'VISION');assert.equal(t.state.facts[1].value,null);
 console.log('PASS all 18 posture rows read-only, measured and USER unknown preserved, explicit leg enum only and no bulk NO');
})().catch(e=>{console.error(e);process.exitCode=1;});
