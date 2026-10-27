/* The color scale must agree with REBA boundaries and never invent an uncomputed score. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const moduleUrl = name => pathToFileURL(path.resolve(__dirname, '..', 'frontend', name)).href;

const attr = (source, name) => new RegExp('\\b' + name + '=["\']([^"\']*)["\']').exec(source)?.[1];
function steps(html) {
  return [...html.matchAll(/<li\b([^>]*)>([\s\S]*?)<\/li>/g)]
    .map(match => ({classes: (attr(match[1], 'class') || '').split(/\s+/), score: Number(attr(match[1], 'data-score')), text: match[2].replace(/<[^>]+>/g, '')}))
    .filter(step => step.classes.includes('reba-scale-step'));
}
function current(html, score) {
  const cells = steps(html), chosen = cells.filter(cell => cell.classes.includes('is-current'));
  assert.equal(chosen.length, 1, 'there must be exactly one current score');
  assert.equal(chosen[0].score, score, 'the marker must follow the actual score');
  return chosen[0];
}

(async () => {
  const {renderRebaScale} = await import(moduleUrl('reba-scale.js'));
  const {QuickFlow} = await import(moduleUrl('quick-flow.js'));
  const bands = [
    {scores: [1], css: 'negligible', risk: '무시 가능'},
    {scores: [2, 3], css: 'low', risk: '낮음'},
    {scores: [4, 5, 6, 7], css: 'medium', risk: '보통'},
    {scores: [8, 9, 10], css: 'high', risk: '높음'},
    {scores: [11, 12, 13, 14, 15], css: 'very-high', risk: '매우 높음'},
  ];
  for (const band of bands) for (const score of band.scores) {
    const html = renderRebaScale(score), cells = steps(html);
    assert.deepEqual(cells.map(cell => cell.score), Array.from({length: 15}, (_, i) => i + 1), 'every score from 1 to 15 must appear in order');
    for (const cell of cells) assert.match(cell.text, new RegExp('\\b' + cell.score + '\\b'), 'score numbers must remain readable without color');
    assert.ok(current(html, score).classes.includes('reba-risk-' + band.css), `${score} must belong to ${band.css}`);
    const accessible = /<[^>]+\brole=["']img["'][^>]*>/g;
    const image = [...html.matchAll(accessible)].find(match => attr(match[0], 'aria-label'))?.[0];
    assert.ok(image, 'the visual must have an accessible description');
    const label = attr(image, 'aria-label');
    assert.ok(label.includes(`${score}점`), 'accessible description must name the current score');
    assert.ok(label.includes(band.risk), 'accessible description must name the risk without requiring color');
  }
  for (const value of [null, undefined, 0, 16, -1, NaN, Infinity, '7', 1.5]) {
    assert.equal(renderRebaScale(value), '', 'an invalid/missing score must not turn into a green minimum: ' + String(value));
  }

  function flow() {
    const ui = Object.create(QuickFlow.prototype);
    Object.assign(ui, {photos: {}, answers: {}, preview: null, intakeText: '', reopened: false, step: 'provisional'});
    return ui;
  }
  for (const score of [1, 7, 15]) {
    const ui = flow(), assumption = '확인하지 않은 조건은 부담 없음으로 가정한 1차 점수입니다.';
    ui.preview = {score: {total: score, risk: score === 1 ? 'NEGLIGIBLE' : score === 7 ? 'MEDIUM' : 'VERY_HIGH', assumption}, measured: [], front: [], diagnostics: [], questions: []};
    const provisional = ui.viewProvisional();
    current(provisional, score);
    assert.ok(provisional.includes(assumption), 'the provisional no-burden assumption must remain visible');
    current(renderRebaScale(score, {provisional: true}), score);
    ui.result = {reba: {slots: [{total: score, risk: ui.preview.score.risk, selected_side: 'LEFT', left: {total: score}, right: {total: 1}}]}};
    const final = ui.rebaPanel();
    current(final, score);
    assert.ok(final.includes('REBA 현재 점수'));
  }

  const missing = flow();
  missing.preview = {score: null, measured: [], front: [], diagnostics: [], questions: []};
  assert.equal(steps(missing.viewProvisional()).length, 0, 'a missing provisional score must not show a current score');
  missing.result = {reba: {slots: [{total: null, left: {total: 4, missing_fields: []}, right: {total: null, missing_fields: ['right.wrist_base']}}]}};
  const incomplete = missing.rebaPanel();
  assert.equal(steps(incomplete).length, 0, 'one complete side must not be presented as a complete total');
  assert.ok(incomplete.includes('아직 점수를 계산할 수 없어요'));
  missing.result = {reba: {slots: []}};
  assert.equal(steps(missing.rebaPanel()).length, 0, 'no REBA calculation must stay uncomputed');

  console.log('PASS REBA scale boundaries 1–15, accessible current marker, invalid/missing values, and provisional/final placement');
})().catch(error => { console.error(error); process.exitCode = 1; });
