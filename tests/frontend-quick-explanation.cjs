/* Readable explanations must keep their source and apply the text the user chose. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const moduleUrl = name => pathToFileURL(path.resolve(__dirname, '..', 'frontend', name)).href;

(async () => {
  const {renderQuickExplanation} = await import(moduleUrl('quick-explanation.js'));
  const {QuickFlow} = await import(moduleUrl('quick-flow.js'));
  const unsafe = '<img src=x onerror="alert(1)"> & 설명';
  const content = {
    summary: '핵심 요약 원문 ' + unsafe,
    check_items: ['CHECK_1 ' + unsafe, 'CHECK_2', 'CHECK_3', 'CHECK_4_추가확인'],
    criteria: Array.from({length: 11}, (_, i) => ({criterion_no: i + 1, explanation: `CRITERION_${i + 1}_원문 ${unsafe}`, basis_refs: []})),
    improvement_options: [{proposal: '개선 선택지 원문 ' + unsafe, basis_refs: [], needs_confirmation: true}],
  };
  const generated = '생성된 설명 전체입니다.\n' + content.criteria.map(x => x.explanation).join('\n');
  const ai = {text_id: 'text-1', purpose: 'TASK_EXPLANATION', result: 'GENERATED',
    generated_text: generated, edited_text: null, content, is_active: false};
  const html = renderQuickExplanation(ai, generated);
  assert.match(html, /핵심 요약/);
  assert.match(html, /먼저 확인할/);
  for (let i = 1; i <= 11; i++) assert.ok(html.includes(`CRITERION_${i}_원문`), 'criterion explanation must remain accessible: ' + i);
  for (const check of ['CHECK_1', 'CHECK_2', 'CHECK_3', 'CHECK_4_추가확인']) assert.ok(html.includes(check), check);
  assert.ok(html.includes('개선 선택지 원문'));
  assert.ok(!html.includes('<img'), 'AI text must not be interpreted as markup');
  assert.ok(html.includes('&lt;img'), 'escaped source must remain readable');
  assert.ok(html.includes('&amp;'), 'ampersands must be escaped');
  const details = [...html.matchAll(/<details\b([^>]*)>([\s\S]*?)<\/details>/g)];
  assert.ok(details.length >= 2, 'long criteria/improvements must be expandable');
  assert.ok(details.some(x => x[2].includes('CRITERION_11_원문')), 'all criteria must be in expandable details');
  assert.ok(details.some(x => x[2].includes('CHECK_4_추가확인')), 'extra checks must stay available behind expansion');
  for (const item of details) assert.doesNotMatch(item[1], /\bopen\b/, 'details must start collapsed');

  const edited = '조사자가 수정한 설명입니다.\n다음 줄도 보존합니다. ' + unsafe;
  const editedHtml = renderQuickExplanation({...ai, edited_text: edited}, edited);
  assert.ok(editedHtml.includes('조사자가 수정한 설명입니다.'));
  assert.ok(!editedHtml.includes('핵심 요약 원문'), 'generated summary must not masquerade as the edited explanation');
  assert.ok(!editedHtml.includes('CHECK_1'), 'generated checks must not masquerade as the edited explanation');
  assert.ok(!editedHtml.includes('<img'));
  const fallback = renderQuickExplanation({...ai, content: null, result: 'FALLBACK', generated_text: '기본 설명입니다.'}, '기본 설명입니다.');
  assert.ok(fallback.includes('기본 설명입니다.'), 'plain/old records must remain readable');

  function harness(record = ai, draft = null) {
    const flow = Object.create(QuickFlow.prototype), calls = [], errors = [];
    flow.result = {analysis_id: 42, ai: [record]}; flow.aiDraft = draft;
    flow.api = async (method, params) => { calls.push({method, params}); return {}; };
    flow.refreshResult = async () => {};
    flow.notify = () => {};
    flow.onError = error => errors.push(error.message);
    flow.run = async (_label, action) => { try { await action(); } catch (error) { flow.onError(error); } };
    return {flow, calls, errors};
  }

  const decode = text => text.replace(/&(amp|lt|gt|quot|#39);/g, (_all, key) => ({amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'"}[key]));
  const panel = harness();
  panel.flow.settings = {gpt_key_present: true}; panel.flow.busy = false; panel.flow.aiEditorOpen = false;
  const panelHtml = panel.flow.aiPanel();
  const editor = /<details\b([^>]*\bdata-ai-editor[^>]*)>([\s\S]*?)<\/details>/.exec(panelHtml);
  assert.ok(editor, 'the complete source must remain available in a separate editor');
  assert.doesNotMatch(editor[1], /\bopen\b/, 'long source editor must start collapsed');
  const textarea = /<textarea\b[^>]*>([\s\S]*?)<\/textarea>/.exec(editor[2]);
  assert.equal(decode(textarea[1]), generated, 'the editor must preserve the complete source without shortening it');

  const applied = harness({...ai, is_active: true, applied_text: 'APPLIED_보고서에 들어갈 수정문', edited_text: 'SAVED_아직 적용하지 않은 다음 수정문'});
  applied.flow.settings = {gpt_key_present: true}; applied.flow.busy = false;
  const appliedHtml = applied.flow.aiPanel();
  const reading = appliedHtml.slice(0, appliedHtml.indexOf('<textarea'));
  assert.ok(reading.includes('APPLIED_보고서에 들어갈 수정문'), 'the reading preview must match the applied report text');
  assert.ok(!reading.includes('핵심 요약 원문'), 'an applied investigator edit must not show generated claims as its preview');
  assert.equal(decode(/<textarea\b[^>]*>([\s\S]*?)<\/textarea>/.exec(appliedHtml)[1]), 'SAVED_아직 적용하지 않은 다음 수정문');

  for (const [record, draft, expected] of [
    [ai, null, generated],
    [{...ai, edited_text: edited}, null, edited],
    [{...ai, edited_text: edited}, '새로 고친 설명', '새로 고친 설명'],
  ]) {
    const {flow, calls, errors} = harness(record, draft);
    await flow.applyAi(true);
    assert.deepEqual(errors, []);
    assert.deepEqual(calls.map(x => x.method), ['edit_ai_text', 'apply_ai_text']);
    assert.equal(calls[0].params.text, expected, 'apply must use draft, saved edit or original in that order');
    assert.equal(calls[0].params.text_id, 'text-1');
    assert.equal(calls[1].params.use_edited, true);
  }
  for (const draft of ['', '  \n\t ']) {
    const {flow, calls, errors} = harness(ai, draft);
    await flow.applyAi(true);
    assert.equal(calls.length, 0, 'empty draft must not overwrite a saved explanation or call apply');
    assert.equal(errors.length, 1, 'empty draft must produce a user-facing error');
  }
  const original = harness({...ai, edited_text: edited}, '미적용 편집');
  await original.flow.applyAi(false);
  assert.deepEqual(original.calls.map(x => x.method), ['apply_ai_text']);
  assert.equal(original.calls[0].params.use_edited, false, 'original apply must remain explicitly original');

  const snapshot = harness(ai, '적용 버튼을 누른 순간의 수정문');
  snapshot.flow.run = async (_label, action) => { snapshot.flow.aiDraft = '렌더 중 달라진 값'; await action(); };
  await snapshot.flow.applyAi(true);
  assert.equal(snapshot.calls[0].params.text, '적용 버튼을 누른 순간의 수정문', 'a render must not change the target captured by apply');
  console.log('PASS compact explanation details, escaped text, plain/edited records, and exact original/edited apply targets');
})().catch(error => { console.error(error); process.exitCode = 1; });
