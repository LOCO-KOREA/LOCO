const assert=require('node:assert/strict');
(async()=>{
  const {renderPostureReview}=await import('../frontend/quick-review.js');
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
    reba:{summary:{complete_count:0,total_slot_count:2,available_max:4,full_max:null},slots:[
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
  assert.doesNotMatch(html,/<script>/);
  assert.doesNotMatch(html,/98765|98766|사진 행 70|사진 행 81|common\\.neck_base|INPUT_CONFLICT|BOUNDARY_REVIEW/);
  process.stdout.write('Human review includes all anonymous pose, coordinate, candidate, REBA, and failure results.\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
