const {assert,pose,fact,setup,count,dataRow,noImplicitControls}=require('./intake-editor-fixture.cjs');
(async()=>{
 const left=pose('LEFT','upper_arm_base','photo:2',{choices:[{value:3,label:'45~90°'}]}),right=pose('RIGHT','lower_arm_base'),conflict=pose('COMMON','neck_base'),refused=pose('COMMON','seated','photo:3',{photo_unused:true}),unknown=pose('RIGHT','wrist_base');
 const t=await setup([left,right,conflict,refused,unknown],[fact(left,3,'ESTIMATED','POSE',{quote:'3D 관절 근거 <원문>'}),fact(right,'YES','KNOWN','VISION'),fact(conflict,'YES','CONFLICT','AI',{conflict:{value:'NO'}}),fact(refused,'YES','KNOWN','POSE'),fact(unknown,null,'UNKNOWN','USER')]);
 const html=t.editor();noImplicitControls(html);assert.equal(count(html,'data-intake-data'),5);
 assert.match(dataRow(html,left.identity),/왼쪽 위팔 들림/);assert.match(dataRow(html,left.identity),/45~90°/);assert.match(dataRow(html,left.identity),/MediaPipe 측정 · 추정값/);
 assert.match(html,/3D 관절 근거 &lt;원문&gt;/);assert.doesNotMatch(html,/<원문>/);
 assert.match(dataRow(html,right.identity),/오른쪽 팔꿈치 굽힘/);assert.match(dataRow(html,right.identity),/AI 사진 관찰/);
 assert.match(dataRow(html,conflict.identity),/값 불일치/);assert.doesNotMatch(dataRow(html,conflict.identity),/현재 점수에 반영/);
 assert.match(dataRow(html,refused.identity),/사진 사용 안 함/);assert.doesNotMatch(dataRow(html,refused.identity),/현재 점수에 반영/);
 assert.match(dataRow(html,unknown.identity),/모름으로 저장/);
 const before=JSON.stringify(t.state.facts);t.intake.dataEditing.add(unknown.identity);assert.match(dataRow(t.editor(),unknown.identity),/<option value="" selected>모름 \/ 미확인/);assert.deepEqual(t.intake.formAnswers(),[]);assert.equal(JSON.stringify(t.state.facts),before);
 console.log('PASS side-specific noun labels, source/evidence, conflict/refusal status and USER unknown without forced reconfirmation');
})().catch(e=>{console.error(e);process.exitCode=1;});
