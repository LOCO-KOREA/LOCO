const assert = require('node:assert/strict');
class Node {
  constructor() { this.listeners = {}; this.nodes = {}; this.disabled = false; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  querySelector(key) { return this.nodes[key] ||= new Node(); }
  emit(type) { return this.listeners[type]?.({preventDefault() {}}); }
  showModal() { this.open = true; }
  close() { this.open = false; }
  remove() { this.removed = true; }
  focus() { this.focused = true; }
}
async function main() {
  const {createDeleteConfirmation} = await import('../frontend/delete-confirmation.js');
  const dialogs = [];
  const document = {createElement() { const node = new Node(); dialogs.push(node); return node; }, body: {append() {}}};
  const confirm = createDeleteConfirmation(document);
  let calls = 0;
  const options = {title: '조사 삭제', message: '<img onerror=bad> 한글 조사 #7', remove: async () => { calls++; }};
  for (const cancelType of ['click', 'cancel']) {
    const pending = confirm(options), dialog = dialogs.at(-1);
    assert.equal(dialog.querySelector('[data-cancel]').focused, true);
    assert.equal(dialog.querySelector('#delete-confirmation-message').textContent, options.message);
    if (cancelType === 'cancel') dialog.emit('cancel');
    else dialog.querySelector('[data-cancel]').emit('click');
    assert.equal(await pending, false); assert.equal(calls, 0); assert.equal(dialog.removed, true);
  }
  let finish;
  const pending = confirm({...options, remove: () => { calls++; return new Promise(resolve => { finish = resolve; }); }});
  const dialog = dialogs.at(-1);
  assert.equal(await confirm(options), false);
  const click = dialog.querySelector('[data-confirm]').emit('click');
  dialog.querySelector('[data-confirm]').emit('click');
  dialog.emit('cancel'); dialog.querySelector('[data-cancel]').emit('click');
  assert.equal(calls, 1); assert.equal(dialog.open, true);
  assert.equal(dialog.querySelector('[data-cancel]').disabled, true);
  assert.equal(dialog.querySelector('[data-confirm]').disabled, true);
  finish(); await click; assert.equal(await pending, true); assert.equal(dialog.removed, true);
  const failure = confirm({...options, remove: async () => { throw Error('service failed'); }});
  const rejected = assert.rejects(failure, /service failed/);
  await dialogs.at(-1).querySelector('[data-confirm]').emit('click'); await rejected;
  assert.equal(dialogs.at(-1).removed, true);
  const retry = confirm(options); dialogs.at(-1).emit('cancel'); assert.equal(await retry, false);

  const {events} = await import('../frontend/task/events.js');
  const requested = [], notifications = [];
  const editor = {current: {task_id: 7, task_name: '작업 A'}, saved: {task_id: 7}, surveyId: 3,
    buffers: new Map([[7, 'draft A'], [8, 'draft B']]), bufferBases: new Map([[7, {}]]),
    run(action) { this.pending = action(); }, confirmDeletion: confirm,
    api: async (method, params) => { requested.push([method, params.task_id]); },
    onChanged: async () => {}, open: async () => {}, notify: text => notifications.push(text)};
  const deleteClick = () => events.click.call(editor, {target: {closest: () => ({dataset: {do: 'delete'}})}});
  deleteClick(); dialogs.at(-1).emit('cancel'); await editor.pending;
  assert.deepEqual(requested, []); assert.equal(editor.current.task_id, 7);
  editor.api = async () => { throw Error('offline'); };
  deleteClick(); const failed = assert.rejects(editor.pending, /offline/);
  await dialogs.at(-1).querySelector('[data-confirm]').emit('click'); await failed;
  assert.equal(editor.current.task_id, 7); assert.equal(editor.buffers.get(7), 'draft A');
  assert.equal(notifications.length, 0);
  editor.api = async (method, params) => { requested.push([method, params.task_id]); };
  deleteClick(); assert.match(dialogs.at(-1).querySelector('#delete-confirmation-message').textContent, /작업 A.*#7/);
  await dialogs.at(-1).querySelector('[data-confirm]').emit('click'); await editor.pending;
  assert.deepEqual(requested, [['delete_task', 7]]); assert.equal(editor.current, null);
  assert.equal(editor.buffers.has(7), false); assert.equal(editor.buffers.get(8), 'draft B');
  assert.equal(editor.bufferBases.has(7), false); assert.equal(notifications.length, 1);

  // Exercise the actual survey click handler, with a failing service and another survey present.
  const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
  const source = fs.readFileSync(path.join(__dirname, '../frontend/desktop.js'), 'utf8');
  const start = source.indexOf("$('#delete-survey').addEventListener");
  const end = source.indexOf('\nfor(const selector', start);
  assert.ok(start >= 0 && end > start);
  let listener, operation, serviceFails = false;
  const surveyCalls = [], resets = [], messages = [];
  const state = {selected: 12, editorId: 12, surveys: [{survey_id:12,title:'조사 A',task_count:2},{survey_id:13,title:'조사 B'}], drafts:new Map([[12,'draft A'],[13,'draft B']]), details:new Map([[12,{}],[13,{}]])};
  vm.runInNewContext(source.slice(start, end), {
    $: () => ({addEventListener(type, fn) { listener = fn; }}), state, confirmDeletion: confirm,
    perform(fn) { operation = fn(); }, api: async (method, params) => {
      if (serviceFails) throw Error('already deleted or unavailable');
      surveyCalls.push([method, params.survey_id]);
    }, taskUI:{resetSurvey(id) { resets.push(id); }}, fill() {}, blank: () => ({}), page() {},
    refresh: async () => {}, notify: text => messages.push(text)
  });
  listener(); dialogs.at(-1).emit('cancel'); await operation;
  assert.deepEqual(surveyCalls, []); assert.equal(state.selected, 12);
  serviceFails = true; listener(); const surveyFailed = assert.rejects(operation, /already deleted/);
  await dialogs.at(-1).querySelector('[data-confirm]').emit('click'); await surveyFailed;
  assert.equal(state.selected, 12); assert.equal(state.drafts.get(12), 'draft A');
  assert.deepEqual(resets, []); assert.deepEqual(messages, []);
  serviceFails = false; listener();
  assert.match(dialogs.at(-1).querySelector('#delete-confirmation-message').textContent, /조사 A.*#12/);
  await dialogs.at(-1).querySelector('[data-confirm]').emit('click'); await operation;
  assert.deepEqual(surveyCalls, [['delete_survey',12]]); assert.deepEqual(resets, [12]);
  assert.equal(state.selected, null); assert.equal(state.drafts.has(12), false);
  assert.equal(state.drafts.get(13), 'draft B'); assert.equal(state.details.has(13), true);
  console.log('PASS deletion cancellation/Esc, safe target text, duplicate requests, pending modal, failure/retry, and survey/task state preservation');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
