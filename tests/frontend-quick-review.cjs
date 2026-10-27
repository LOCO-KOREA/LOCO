const assert=require('node:assert/strict');
(async()=>{
  const {renderMeasurementQuality,renderPostureReview}=await import('../frontend/quick-review.js');
  const {QuickFlow}=await import('../frontend/quick-flow.js');
  const calls=[];
  const flow=Object.assign(Object.create(QuickFlow.prototype),{api:async(method,params)=>{calls.push({method,params});return method==='create_survey'?{survey_id:9}:{task_id:10};}});
  await flow.ensureTask();
  assert.equal(calls[0].method,'create_survey');
  assert.equal(Object.hasOwn(calls[0].params.draft,'survey_type'),false,'quick flow must not record an unasked default as a user answer');
  assert.equal(Object.hasOwn(calls[0].params.draft,'survey_date'),false,'quick flow must not create an unasked survey date');
  assert.equal(Object.hasOwn(calls[0].params.draft,'title'),false,'quick flow must not create an unasked survey title');
  assert.equal(calls[1].params.draft.task_name,'','an unasked machine task name must not be persisted');
  const reviewCalls=[],reviewSurvey={survey_id:9,metadata_revision:4};
  const reviewFlow=Object.assign(Object.create(QuickFlow.prototype),{
    survey:reviewSurvey,task:{task_id:10},result:{analysis_id:101,currentness:'CURRENT'},review:{reviewer:'검토자 A',note:'작업 A 확인'},
    api:async(method,params)=>{reviewCalls.push({method,params});if(method==='get_survey')return reviewSurvey;if(method==='set_survey_review')return params.review;throw Error(`unexpected ${method}`);},
    run:async(_label,fn)=>fn(),notify:()=>{}
  });
  await reviewFlow.markReviewed(true);
  assert.deepEqual(reviewCalls.find(x=>x.method==='set_survey_review').params.review.reviewed_analysis_ids,[101],
    'quick review must include only the displayed task A analysis; unseen task B stays unreviewed');
  const blockedReviewCalls=[],blockedReviewNotices=[];
  const staleReviewFlow=Object.assign(Object.create(QuickFlow.prototype),{
    survey:{survey_id:9,metadata_revision:4},result:{analysis_id:101,currentness:'STALE'},review:{reviewer:'검토자 A',note:'이전 입력 검토'},
    api:async(method,params)=>{blockedReviewCalls.push({method,params});throw Error('stale review must not call the API');},
    run:async(_label,fn)=>fn(),notify:message=>blockedReviewNotices.push(message)
  });
  await staleReviewFlow.markReviewed(true);
  assert.deepEqual(blockedReviewCalls,[],'stale analysis must never be written as a current review');
  assert.match(blockedReviewNotices[0],/최신 분석/,'stale review must explain how to proceed');
  const reviewResult={analysis_id:101,currentness:'CURRENT',snapshot:{schema_version:'2.0',analysis_scope:{pose:false,reba:false},capture:{slots:[]}},module_states:{pose:'NOT_REQUESTED',reba:'NOT_REQUESTED'}};
  const reviewView=review=>{
    const view=Object.assign(Object.create(QuickFlow.prototype),{survey:{metadata_revision:4,review},result:reviewResult,review:{reviewer:'검토자',note:''},photoStrip:()=>'',photoVisionPanel:()=>'',criteriaRows:()=>'',aiPanel:()=>''});
    return view.viewReview();
  };
  const currentReview={reviewed:true,reviewed_analysis_ids:[101],reviewed_metadata_revision:4};
  assert.match(reviewView(currentReview),/data-quick="unreview"/);
  assert.match(reviewView(currentReview),/검토 완료/);
  assert.match(reviewView(currentReview),/data-quick="questions" data-reveal-photo="1">자세 분석값 수정/,'the result step exposes posture corrections without requiring another interview');
  const previousAnalysisReview={...currentReview,reviewed_analysis_ids:[100]};
  const previousHtml=reviewView(previousAnalysisReview);
  assert.doesNotMatch(previousHtml,/data-quick="unreview"/);
  assert.match(previousHtml,/현재 분석의 검토 표시는 없어요/);
  assert.match(previousHtml,/이전 검토 기록은 남아 있어요/);
  reviewResult.currentness='STALE';
  const staleReviewHtml=reviewView(currentReview);
  assert.doesNotMatch(staleReviewHtml,/data-quick="unreview"/);
  assert.match(staleReviewHtml,/data-quick="reviewed" disabled/,'stale analysis cannot be marked reviewed from Step 5');
  reviewResult.currentness='CURRENT';
  const priorMetadataView=Object.assign(Object.create(QuickFlow.prototype),{survey:{metadata_revision:5,review:currentReview},result:reviewResult,review:{reviewer:'검토자',note:''},photoStrip:()=>'',photoVisionPanel:()=>'',criteriaRows:()=>'',aiPanel:()=>''}).viewReview();
  assert.doesNotMatch(priorMetadataView,/data-quick="unreview"/);
  const aiCalls=[];
  const aiFlow=Object.assign(Object.create(QuickFlow.prototype),{settings:{gpt_enabled:true,gpt_model:'test'},result:{analysis_id:88},preview:{score:{total:7,risk:'MEDIUM'},views:{LEFT:{photo_id:21},FRONT:{photo_id:22}}},api:async(method,params)=>{aiCalls.push({method,params});return {};},run:async(_label,fn)=>fn(),refreshResult:async()=>{}});
  await aiFlow.generateAi();
  assert.deepEqual(aiCalls.find(x=>x.method==='generate_ai_text').params.provisional_reba,{total:7,risk:'MEDIUM',photo_ids:[21,22]});
  const html=renderPostureReview({
    snapshot:{schema_version:'2.0',analysis_scope:{pose:true,reba:true},capture:{slots:[
      {slot_no:70,photo_id:98765,label:'왼쪽 <script>',analysis_target:true},
      {slot_no:81,photo_id:98766,label:'오른쪽 사진',analysis_target:true}]}},
    module_states:{pose:'INCOMPLETE',reba:'INCOMPLETE'},
    pose:{valid_count:1,total_slot_count:2,slots:[
      {slot_no:70,status:'VALID',engine:{name:'MediaPipe Heavy',version:'v1'},
       points:[{name:'left_shoulder',x_px:120.5,y_px:201.25,z_normalized:.2,confidence:.91}],
       world_points:[{name:'left_shoulder',x_m:.1,y_m:.2,z_m:.3,confidence:.91}],
       angles:[{side:'LEFT',angle_code:'TRUNK_TILT_VERT',value_deg:28.5,min_confidence:.91}],
       world_angles:[{side:'LEFT',angle_code:'ARM_3D',label:'팔꿈치 굽힘',value_deg:41.2,min_confidence:.8}]},
      {slot_no:81,status:'ERROR',diagnostics:[{code:'MODEL_ERROR',message:'사진 판독 실패'}],points:[],angles:[]} ]},
    measurement_quality:{measured_points:26,total_points:33,mean_confidence:.73,confidence_level:'MEDIUM',slots:[
      {slot_no:70,photo_id:98765,measured_points:26,total_points:33,mean_confidence:.73,confidence_level:'MEDIUM'},
      {slot_no:81,photo_id:98766,measured_points:0,total_points:33,mean_confidence:null,confidence_level:'MISSING'}]},
    reba:{summary:{complete_count:0,total_slot_count:2,available_max:4,full_max:null,current_score:{total:4,risk:'MEDIUM',kind:'WITH_ASSUMPTIONS',slot_no:70,assumed:['common.neck_base'],assumption:'목은 부담 없음으로 가정했어요.'}},slots:[
      {slot_no:70,status:'INCOMPLETE',effective_load_kg:3.2,left:{trunk:2,total:4,risk:'MEDIUM',missing_fields:['common.neck_base'],review_reasons:[]},
       right:{trunk:2,total:3,risk:'LOW',missing_fields:[],review_reasons:[]},candidates:[{scope:'COMMON',field:'trunk_base',proposed_value:2,angles:[{side:'LEFT',angle_code:'TRUNK_TILT_VERT',value_deg:28.5}],min_confidence:.91,review_reasons:['BOUNDARY_REVIEW']}]}
    ]}, tags:[{tag:'SQUAT',yes_count:1,observed_count:2}]
  });
  assert.match(html,/data-posture-review/);
  assert.match(html,/id="quick-posture-review"/);
  assert.match(html,/id="quick-posture-photo-1"/);
  assert.match(html,/120\.5/);
  assert.match(html,/28\.5°/);
  assert.match(html,/41\.2°/);
  assert.match(html,/공통 · 목 기본 자세/);
  assert.match(html,/관절 좌표 전체 1개/);
  assert.match(html,/REBA에 사용하지 않음/);
  assert.match(html,/사진 판독 실패/);
  assert.match(html,/REBA 4점 · 보통 · 가정 포함/,'the current score must be shown beside its source photo');
  assert.match(html,/측정된 관절 26\/33개/,'the measured point count must use the backend contract');
  assert.match(html,/신뢰도 보통/,'the per-photo confidence grade must be visible');
  assert.doesNotMatch(html,/측정된 관절 26\/66개/,'quality must not mix the denominator across photos');
  assert.doesNotMatch(html,/<script>/);
  assert.doesNotMatch(html,/98765|98766|사진 행 70|사진 행 81|common\\.neck_base|INPUT_CONFLICT|BOUNDARY_REVIEW/);
  const reference=renderMeasurementQuality({measured_points:0,total_points:33,mean_confidence:null,confidence_level:'MISSING'});
  assert.match(reference,/측정된 관절 0\/33개/);
  assert.match(reference,/신뢰도 측정 전/);
  const referenceScore=renderPostureReview({
    snapshot:{schema_version:'2.0',analysis_scope:{pose:true,reba:true},capture:{slots:[{slot_no:91,photo_id:98770,label:'참고 사진',analysis_target:true}]}},
    pose:{valid_count:0,total_slot_count:1,slots:[]},measurement_quality:{slots:[{slot_no:91,photo_id:98770,measured_points:0,total_points:33,mean_confidence:null,confidence_level:'MISSING'}]},
    reba:{summary:{complete_count:0,total_slot_count:1,current_score:{total:1,risk:'NEGLIGIBLE',kind:'ASSUMED_REFERENCE',slot_no:91,assumed:['common.trunk_base'],assumption:'자세 측정값이 없어 기준 점수를 표시합니다.'}},slots:[]}
  });
  assert.match(referenceScore,/REBA 1점 · 무시 가능 · 참고값/,'a backend-provided reference score remains visible without pose points');
  assert.match(referenceScore,/측정된 관절 0\/33개/,'missing measurements must stay explicit beside the reference score');
  assert.match(referenceScore,/자세 측정값이 없어 기준 점수를 표시합니다/);
  const individual=renderPostureReview({
    snapshot:{schema_version:'2.0',capture:{slots:[
      {slot_no:1,photo_id:7,label:'첫 사진',analysis_target:true},
      {slot_no:2,photo_id:8,label:'다음 사진',analysis_target:true}]}},
    reba:{summary:{current_score:{total:11,risk:'VERY_HIGH',kind:'WITH_ASSUMPTIONS',slot_no:2}},slots:[
      {slot_no:1,status:'INCOMPLETE',current_score:{total:2,risk:'LOW',kind:'WITH_ASSUMPTIONS'}},
      {slot_no:2,status:'INCOMPLETE',current_score:{total:11,risk:'VERY_HIGH',kind:'WITH_ASSUMPTIONS'}}]}
  });
  const firstPhoto=individual.split('id="quick-posture-photo-2"')[0];
  assert.match(firstPhoto,/REBA 2점/,'a nonrepresentative photo must use its own projected score');
  assert.doesNotMatch(firstPhoto,/REBA 11점|REBA 점수 미산출/);
  const foreign={snapshot:{schema_version:'2.0',capture:{slots:[{slot_no:1,photo_id:7,label:'현재 사진',analysis_target:true}]}},
    pose:{slots:[{slot_no:1,photo_id:999,angles:[{side:'LEFT',angle_code:'TRUNK_TILT_VERT',value_deg:111.1}],world_points:[{name:'nose',x_m:999.123}]}]},
    reba:{summary:{current_score:{slot_no:1,total:14,risk:'VERY_HIGH'}},slots:[{slot_no:1,photo_id:999,total:14,risk:'VERY_HIGH'}]},
    measurement_quality:{slots:[{slot_no:1,photo_id:999,measured_points:27,total_points:33,mean_confidence:.79,confidence_level:'HIGH'}]}};
  const rejected=renderPostureReview(foreign);
  assert.doesNotMatch(rejected,/111\.1°|999\.123|REBA 14점|27\/33/,'foreign measurements, coordinates, score, and quality must not be relabelled by slot');
  assert.match(rejected,/사진 연결 정보가 맞지 않아/);
  assert.match(rejected,/자세 측정 신뢰도 정보 없음/,'a rejected quality row must not manufacture zero measurements');
  const exact=structuredClone(foreign);
  exact.pose.slots.push({slot_no:1,photo_id:7,angles:[{side:'LEFT',angle_code:'TRUNK_TILT_VERT',value_deg:33.3}],world_points:[{name:'nose',x_m:.123}]});
  const owned=renderPostureReview(exact);
  assert.match(owned,/33\.3°/,'one exact owner wins over a different photo row');
  assert.match(owned,/0\.123/,'owned raw coordinates remain available in human review');
  exact.pose.slots.push(structuredClone(exact.pose.slots[1]));
  assert.doesNotMatch(renderPostureReview(exact),/33\.3°|0\.123/,'ambiguous duplicate owned rows must not be arbitrarily selected');
  const world={snapshot:{schema_version:'2.0',capture:{slots:[{slot_no:1,photo_id:7,label:'현재 사진',analysis_target:true}]}},
    pose:{slots:[{slot_no:1,photo_id:7,world_angles:[{side:'LEFT',angle_code:'ELBOW_FLEX_3D',value_deg:57.2,min_confidence:.9}]}]},
    reba:{slots:[{slot_no:1,photo_id:7,current_score:{total:6,risk:'MEDIUM',kind:'WITH_ASSUMPTIONS'},candidates:[{scope:'LEFT',field:'lower_arm_base',angles:[{side:'LEFT',angle_code:'ELBOW_FLEX_3D',value_deg:57.2,coordinate_space:'INFERRED_WORLD_3D',used_for_reba:true}]}]}]}};
  assert.doesNotMatch(renderPostureReview(world),/현재 REBA 초안에 사용/,'candidate availability must not imply current score use');
  world.reba.slots[0].current_score.measurement_refs=[{scope:'LEFT',field:'lower_arm_base',angles:world.reba.slots[0].candidates[0].angles}];
  assert.match(renderPostureReview(world),/현재 REBA 초안에 사용/,'selected current draft refs must identify used 3D measurements');
  world.reba.slots[0].current_score.kind='CONFIRMED';
  assert.doesNotMatch(renderPostureReview(world),/현재 REBA 초안에 사용/,'automatic estimates must stay separate from human confirmed results');
  const rounded=structuredClone(world);
  const rawKnee={side:'LEFT',angle_code:'KNEE_FLEX_3D',value_deg:66.88395999428462,coordinate_space:'INFERRED_WORLD_3D',used_for_reba:false};
  rounded.pose.slots[0].world_angles=[rawKnee];
  rounded.reba.slots[0].current_score={total:8,kind:'WITH_ASSUMPTIONS',measurement_refs:[{scope:'COMMON',field:'knee_band',angles:[{...rawKnee,value_deg:66.9,used_for_reba:true}]}]};
  const beforeRounded=JSON.stringify(rounded);
  assert.match(renderPostureReview(rounded),/현재 REBA 초안에 사용/,'stored one-decimal knee reference must match its original 66.88395999428462 degree observation');
  assert.equal(JSON.stringify(rounded),beforeRounded,'display must not rewrite measured angles or scores');
  for(const [raw,reference,expected] of [[66.88395999428462,66.89,false],[66.84,66.9,false],[66.84,66.8,true],[66.25,66.2,true],[66.25,66.3,false],[66.55,66.5,true],[66.55,66.6,false]]){
    const value=structuredClone(rounded);value.pose.slots[0].world_angles[0].value_deg=raw;value.reba.slots[0].current_score.measurement_refs[0].angles[0].value_deg=reference;
    assert.equal(/현재 REBA 초안에 사용/.test(renderPostureReview(value)),expected,`raw ${raw} reference ${reference} must follow the stored Python one-decimal precision`);
  }
  for(const change of [value=>value.reba.slots[0].photo_id=999,value=>value.pose.slots[0].world_angles[0].side='RIGHT',
    value=>value.pose.slots[0].world_angles[0].angle_code='ELBOW_FLEX_3D',value=>value.pose.slots[0].world_angles[0].coordinate_space='IMAGE_2D',
    value=>value.reba.slots[0].current_score.measurement_refs[0].angles[0].coordinate_space='IMAGE_2D',
    value=>value.reba.slots[0].current_score.measurement_refs[0].angles[0].used_for_reba=false,value=>value.snapshot.capture.slots[0].analysis_target=false]){
    const value=structuredClone(rounded);change(value);assert.doesNotMatch(renderPostureReview(value),/현재 REBA 초안에 사용/,'rounded precision must not cross photo, side, angle, coordinate, selection or target ownership');
  }
  world.snapshot.input_revision=3;
  const estimate={target:'manual.COMMON.neck_base',condition:'photo:7',photo_id:7,state:'ESTIMATED',source:'VISION',value:2,measurement_method:'AI_PHOTO_CATEGORY',vision_confidence:.75,
    vision_proof:{scope:'COMMON',field:'neck_base',value:'NECK_OVER_20',status:'OBSERVED',confidence:.75,evidence:'목을 숙인 사진 근거'}};
  world.snapshot.conditions={intake_session:{projected_revision:3,facts:{estimate}}};
  world.reba.slots[0].current_score={total:6,risk:'MEDIUM',kind:'WITH_ASSUMPTIONS',measurement_refs:[{scope:'COMMON',field:'neck_base',value:2,measurement_method:'AI_PHOTO_CATEGORY'}]};
  const visionEstimate=renderPostureReview(world);
  assert.match(visionEstimate,/사진에서 추정한 자세 · 사람 확인 전/);
  assert.match(visionEstimate,/AI 사진 추정/);assert.match(visionEstimate,/75%/);assert.match(visionEstimate,/목을 숙인 사진 근거/);
  assert.match(visionEstimate,/현재 REBA 초안에 사용/);
  const badEstimate=mutate=>{const copy=structuredClone(world);mutate(copy,copy.snapshot.conditions.intake_session.facts.estimate);return renderPostureReview(copy);};
  for(const mutate of [(v,f)=>f.photo_id=999,(v,f)=>f.condition='photo:999',(v,f)=>f.alias_of='other',(v,f)=>f.vision_proof.status='UNCERTAIN',(v,f)=>f.vision_proof.confidence=.49,
    v=>v.snapshot.conditions.intake_session.projected_revision=2,(v,f)=>v.snapshot.conditions.intake_session.facts.answer={...f,source:'USER',state:'UNKNOWN',value:null},
    v=>v.snapshot.manual=[{slot_no:1,photo_id:7,scope:'COMMON',field:'neck_base',value:1,source:'INTERVIEW'}],
    (v,f)=>v.snapshot.conditions.intake_session.facts.duplicate=structuredClone(f)])assert.doesNotMatch(badEstimate(mutate),/목을 숙인 사진 근거/,'stale, foreign, duplicate, uncertain, and overridden estimates must remain excluded');
  process.stdout.write('Human review includes all anonymous pose, coordinate, candidate, REBA, and failure results.\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
