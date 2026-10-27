/* The description box tells what to mention so that fewer questions are asked. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

(async () => {
  const {QuickFlow} = await import(pathToFileURL(path.join(__dirname, '../frontend/quick-flow.js')).href);
  const ui = Object.create(QuickFlow.prototype);
  Object.assign(ui, {photos: {}, answers: {}, preview: null, intakeText: '', busy: false, stale: false, baseline: null, intake: {contract: {policy: {text_limit: 600}}}});
  const html = ui.viewStart();
  assert.match(html, /질문을 줄이는 설명 예시/);
  for (const phrase of ['하루 작업시간', '물건 무게와 횟수', '반복·충격·자세 유지', '모르면 비워도 돼요']) assert.ok(html.includes(phrase), `the optional guide must name: ${phrase}`);
  assert.ok(/placeholder="[^"]*20kg 상자[^"]*하루 30번[^"]*"/.test(html), 'one short example supplies weight and frequency without making a long questionnaire');
  assert.match(html, /작업 설명 <small>선택<\/small>/);
  assert.ok(!/placeholder="[^"]*충격은 없어요/.test(html), 'the example must not nudge a "none" answer the user did not mean');
  console.log('PASS the description box names what to mention and shows a fuller example');
})().catch(error => { console.error(error); process.exitCode = 1; });
