/* An unfinished REBA shows the score so far, labelled as not final, and never looks like a final result. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const moduleUrl = name => pathToFileURL(path.resolve(__dirname, '..', 'frontend', name)).href;

const attr = (source, name) => new RegExp('\\b' + name + '=["\']([^"\']*)["\']').exec(source)?.[1];
const markers = html => [...html.matchAll(/<li\b([^>]*)>/g)]
  .map(match => ({classes: (attr(match[1], 'class') || '').split(/\s+/), score: Number(attr(match[1], 'data-score'))}))
  .filter(step => step.classes.includes('reba-scale-step') && step.classes.includes('is-current'));

(async () => {
  const {QuickFlow} = await import(moduleUrl('quick-flow.js'));
  const {renderRebaScale} = await import(moduleUrl('reba-scale.js'));
  const flow = slot => {
    const ui = Object.create(QuickFlow.prototype);
    Object.assign(ui, {photos: {}, answers: {}, preview: null, intakeText: '', reopened: false, step: 'result', result: {reba: {slots: [slot]}}});
    return ui;
  };
  const soFar = {total: 3, risk: 'LOW', selected_side: 'RIGHT', left: 1, right: 3, assumed: ['common.neck_base', 'left.upper_arm_base', 'observation.load_state'],
    assumption: '지금까지 확인한 값으로 계산하고, 확인하지 못한 항목은 부담 없음으로 가정한 점수입니다. 실제 점수는 이 점수보다 높거나 낮을 수 있고 확정 점수가 아닙니다.'};
  const unfinished = {total: null, left: {total: 1, missing_fields: []}, right: {total: null, missing_fields: ['right.wrist_base']}};

  const shown = flow({...unfinished, score_so_far: soFar}).rebaPanel();
  assert.ok(shown.includes('REBA 현재 점수') && shown.includes('미확인 항목을 가정한 점수'), 'the current score stays prominent and is labelled as assumption-based');
  assert.ok(shown.includes('확정 점수가 아닙니다') && shown.includes('미확인 항목 3개를 가정한 현재 점수예요'), 'the assumption and its size must be visible');
  assert.ok(shown.includes('낮음'), 'the risk name must be readable without color');
  assert.deepEqual(markers(shown).map(marker => marker.score), [3], 'exactly one marker, on the score so far');
  assert.ok(shown.includes('확인 전 현재 REBA 3점'), 'the accessible description must say it is provisional, not a first-pass or final score');
  assert.ok(!shown.includes('처음 사진 기준 점수'), 'it must not be mislabelled as the first-pass score');

  assert.ok(!shown.includes('임시로 썼어요'), 'no photo-confirmation note when every value was confirmed');
  const borrowed = flow({...unfinished, score_so_far: {...soFar, unconfirmed_photo: ['common.trunk_base', 'right.upper_arm_base']}}).rebaPanel();
  assert.ok(borrowed.includes('사진 상황 미확인으로 측정값 2개를 임시 사용했어요'), 'values borrowed from an unconfirmed photo must be named');

  const bare = flow(unfinished).rebaPanel();
  assert.ok(bare.includes('아직 점수를 계산할 수 없어요'));
  assert.equal(markers(bare).length, 0, 'without a score so far nothing is invented');

  // The unfinished score keeps one plain way back to the single input page (the user's own move, not a request); a finished score, or a task without the adaptive form, has no such button.
  const withForm = slot => { const ui = flow(slot); ui.intake = {state: {form_fields: []}}; return ui.rebaPanel(); };
  const action = withForm({...unfinished, score_so_far: soFar});
  assert.match(action, /<button type="button" data-quick="questions" data-reveal-photo="1">입력 수정하기<\/button>/);
  assert.doesNotMatch(action, /확정하기|class="primary"|→/, 'a plain button: no request, not the main button');
  assert.ok(action.includes('미확인 항목을 가정한 점수'), 'the button comes with the score explanation, not instead of it');
  assert.match(withForm(unfinished), /data-quick="questions"/, 'it is offered even when no score so far can be shown');
  assert.doesNotMatch(shown, /data-quick="questions"/, 'no form to reopen, no button');
  assert.doesNotMatch(withForm({total: 3, risk: 'LOW', selected_side: 'LEFT', left: {total: 3}, right: {total: 1}}), /data-quick="questions"/, 'a final score needs no button');

  const final = flow({total: 3, risk: 'LOW', selected_side: 'LEFT', left: {total: 3}, right: {total: 1}, score_so_far: soFar}).rebaPanel();
  assert.ok(!final.includes('확정 전'), 'a final score must not carry the not-final label');

  const compactUi = Object.create(QuickFlow.prototype);
  const longAssumption = '확인한 입력과 사진 측정값으로 계산했으며 미확인 항목은 부담 없음으로 가정한 확정 전 점수입니다. 실제 점수는 이 점수보다 높거나 낮을 수 있습니다.';
  Object.assign(compactUi, {photos: {}, answers: {}, preview: null, intakeText: '', reopened: false, step: 'review', result: {
    reba: {summary: {complete_count: 0, total_slot_count: 1, current_score: {total: 11, risk: 'VERY_HIGH', kind: 'WITH_ASSUMPTIONS', slot_no: 2,
      assumed: Array.from({length: 6}, (_, index) => `right.item_${index + 1}`), assumption: longAssumption},
      first_pass: {total: 5, risk: 'MEDIUM', slot_no: 2, assumption: {text: '답변 전 사진 기준 가정'}}},
      slots: [{slot_no: 2, total: null, left: {total: null}, right: {total: null}, score_so_far: {left: null, right: null}}]},
    measurement_quality: {slots: [{slot_no: 1, measured_points: 0, total_points: 33, mean_confidence: null, confidence_level: 'MISSING'},
      {slot_no: 2, measured_points: 26, total_points: 33, mean_confidence: .79, confidence_level: 'HIGH'}]}}});
  const compact = compactUi.rebaPanel({compact: true}), primary = compact.slice(0, compact.indexOf('<details'));
  assert.match(primary, /class="quick-big"><strong[^>]*>11<\/strong><span>점 · 매우 높음/);
  assert.match(primary, /미확인 항목 6개/,'the compact count comes from canonical current_score.assumed');
  assert.match(primary, /측정된 관절 26\/33개/,'quality matches the score slot, not another photo');
  assert.doesNotMatch(primary, /0\/33개/);
  assert.match(primary, /실제 점수는 이 점수보다 높거나 낮을 수 있습니다/,'the review score caveat is visible without a toggle');
  assert.doesNotMatch(compact, /\[object Object\]/,'structured first-pass notes never stringify as an object');
  assert.match(compact, /답변 전 사진 기준 가정/,'structured assumption text stays readable in details');
  assert.doesNotMatch(compact, /왼쪽 —점|오른쪽 —점/,'missing side totals are omitted instead of shown as dashes');
  assert.ok(compact.indexOf('reba-scale') < compact.indexOf('<details'),'the risk band is visible before optional first-pass history');
  assert.equal((compact.match(/REBA 현재 점수/g) || []).length, 0,'the review wrapper owns the single score heading');

  assert.ok(renderRebaScale(5, {provisional: true}).includes('1차 REBA 5점'), 'the first-pass label stays as it was');
  assert.ok(renderRebaScale(5).includes('"REBA 5점') || renderRebaScale(5).includes('aria-label="REBA 5점'), 'the default label stays as it was');
  console.log('PASS unfinished REBA shows a labelled score so far; first-pass and final labels unchanged');
})().catch(error => { console.error(error); process.exitCode = 1; });
