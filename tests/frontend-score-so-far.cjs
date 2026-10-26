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
    assumption: '지금까지 확인한 값으로 계산하고, 확인하지 못한 항목은 부담 없음으로 가정한 점수입니다. 확정 점수가 아닙니다.'};
  const unfinished = {total: null, left: {total: 1, missing_fields: []}, right: {total: null, missing_fields: ['right.wrist_base']}};

  const shown = flow({...unfinished, score_so_far: soFar}).rebaPanel();
  assert.ok(shown.includes('아직 점수를 계산할 수 없어요'), 'the missing-items warning must stay');
  assert.ok(shown.includes('최종 REBA 점수') && shown.includes('확정 전'), 'the heading must say the score is not final');
  assert.ok(shown.includes('확정 점수가 아닙니다') && shown.includes('가정한 항목 3개'), 'the assumption and its size must be visible');
  assert.ok(shown.includes('낮음'), 'the risk name must be readable without color');
  assert.deepEqual(markers(shown).map(marker => marker.score), [3], 'exactly one marker, on the score so far');
  assert.ok(shown.includes('지금까지 기준 REBA 3점'), 'the accessible description must say it is the score so far, not a first-pass or final score');
  assert.ok(!shown.includes('1차 REBA'), 'it must not be mislabelled as the first-pass score');

  assert.ok(!shown.includes('임시로 썼어요'), 'no photo-confirmation note when every value was confirmed');
  const borrowed = flow({...unfinished, score_so_far: {...soFar, unconfirmed_photo: ['common.trunk_base', 'right.upper_arm_base']}}).rebaPanel();
  assert.ok(borrowed.includes('사진 상황(한 사람·전신·평소 작업)을 아직 확인하지 않아 사진에서 읽은 값 2개를 임시로 썼어요'), 'values borrowed from an unconfirmed photo must be named');

  const bare = flow(unfinished).rebaPanel();
  assert.ok(bare.includes('아직 점수를 계산할 수 없어요'));
  assert.equal(markers(bare).length, 0, 'without a score so far nothing is invented');

  // The unfinished score points the way back to the posture checklist; a finished score, or a task without the adaptive form, has no such button.
  const withForm = slot => { const ui = flow(slot); ui.intake = {state: {form_fields: []}}; return ui.rebaPanel(); };
  const action = withForm({...unfinished, score_so_far: soFar});
  assert.match(action, /<button type="button" class="primary" data-quick="questions" data-reveal-photo="1">자세 항목 확인하고 확정하기 →<\/button>/);
  assert.ok(action.includes('아직 점수를 계산할 수 없어요'), 'the button comes with the explanation, not instead of it');
  assert.match(withForm(unfinished), /data-quick="questions"/, 'it is offered even when no score so far can be shown');
  assert.doesNotMatch(shown, /data-quick="questions"/, 'no form to reopen, no button');
  assert.doesNotMatch(withForm({total: 3, risk: 'LOW', selected_side: 'LEFT', left: {total: 3}, right: {total: 1}}), /data-quick="questions"/, 'a final score needs no button');

  const final = flow({total: 3, risk: 'LOW', selected_side: 'LEFT', left: {total: 3}, right: {total: 1}, score_so_far: soFar}).rebaPanel();
  assert.ok(!final.includes('확정 전'), 'a final score must not carry the not-final label');

  assert.ok(renderRebaScale(5, {provisional: true}).includes('1차 REBA 5점'), 'the first-pass label stays as it was');
  assert.ok(renderRebaScale(5).includes('"REBA 5점') || renderRebaScale(5).includes('aria-label="REBA 5점'), 'the default label stays as it was');
  console.log('PASS unfinished REBA shows a labelled score so far; first-pass and final labels unchanged');
})().catch(error => { console.error(error); process.exitCode = 1; });
