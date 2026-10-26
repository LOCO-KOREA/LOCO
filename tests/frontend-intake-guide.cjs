/* The description box tells what to mention so that fewer questions are asked. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

(async () => {
  const {QuickFlow} = await import(pathToFileURL(path.join(__dirname, '../frontend/quick-flow.js')).href);
  const ui = Object.create(QuickFlow.prototype);
  Object.assign(ui, {photos: {}, answers: {}, preview: null, intakeText: '', busy: false, stale: false, baseline: null, intake: {contract: {policy: {text_limit: 600}}}});
  const html = ui.viewStart();
  assert.match(html, /이런 것을 말해 주시면 질문이 줄어요/);
  for (const phrase of ['1년에 며칠', '하루 총 몇 시간', '무게와 하루 횟수', '충격·반복·같은 자세 유지']) assert.ok(html.includes(phrase), `the guide must name: ${phrase}`);
  assert.ok(/placeholder="[^"]*1년에 220일[^"]*20kg 상자[^"]*"/.test(html), 'the example must show a schedule and a lift in one description');
  assert.ok(!/placeholder="[^"]*충격은 없어요/.test(html), 'the example must not nudge a "none" answer the user did not mean');
  console.log('PASS the description box names what to mention and shows a fuller example');
})().catch(error => { console.error(error); process.exitCode = 1; });
