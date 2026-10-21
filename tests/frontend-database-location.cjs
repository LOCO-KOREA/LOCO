/* Independent N02 counterexamples. This suite never opens or writes a DB.
 * Run after copying to repo/tests, or set LOCO_TEST_ROOT to the repository.
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const root = process.env.LOCO_TEST_ROOT || path.resolve(__dirname, '..');
const {resolveDatabaseLocation, createDatabaseLocationBridge} = require(path.join(root, 'frontend/electron/database-location.cjs'));
const passed = [];
const check = (name, run) => Promise.resolve().then(run).then(() => { passed.push(name); console.log('PASS ' + name); });
const ok = value => ({ok: true, value});
const error = (code, message) => ({ok: false, error: {code, message}});
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const fileLocation = {path: 'C:\\조사 자료\\현장 A\\loco.db', storage: 'file'};

function serviceBridge(overrides = {}) {
  const calls = [], copied = [], opened = [];
  const bridge = createDatabaseLocationBridge({
    location: fileLocation,
    call: async (method, params) => { calls.push({method, params}); return ok([]); },
    clipboard: {writeText(value) { copied.push(value); }},
    shell: {async openPath(value) { opened.push(value); return ''; }},
    ...overrides,
  });
  return {bridge, calls, copied, opened};
}

function node(dataset = {}) {
  const attributes = new Map(), handlers = new Map();
  return {
    textContent: '', disabled: false, hidden: false, dataset, style: {},
    classList: {add() {}, remove() {}, toggle() {}},
    setAttribute(key, value) { attributes.set(key, String(value)); },
    removeAttribute(key) { attributes.delete(key); },
    getAttribute(key) { return attributes.get(key) ?? null; },
    addEventListener(kind, handler) { handlers.set(kind, handler); },
    removeEventListener(kind) { handlers.delete(kind); },
    matches() { return false; },
  };
}
function host() {
  const names = ['path', 'status', 'copy', 'open', 'refresh'];
  const nodes = Object.fromEntries(names.map(name => [name, node({['db' + name[0].toUpperCase() + name.slice(1)]: ''})]));
  const element = node();
  element.querySelector = selector => nodes[/^\[data-db-(.+)\]$/.exec(selector)?.[1]] || null;
  element.querySelectorAll = () => Object.values(nodes);
  return {element, nodes};
}
const disconnectedControls = nodes => {
  assert.equal(nodes.copy.disabled, true, 'copy must require a confirmed file DB');
  assert.equal(nodes.open.disabled, true, 'open must require a confirmed file DB');
};
const rendererBridge = overrides => ({
  copy_database_path: async () => ok({message: '경로 복사 완료'}),
  open_database_folder: async () => ok({message: '폴더 열기 완료'}),
  ...overrides,
});

async function main() {
  await check('DB selection resolves defaults, explicit relative paths, Korean spaces and memory without guessing', () => {
    const base = {env: {}, cwd: 'D:\\앱 위치\\LOCO', home: 'C:\\Users\\현장 사용자'};
    assert.deepEqual(resolveDatabaseLocation(base), {path: 'C:\\Users\\현장 사용자\\AppData\\Local\\LOCO\\loco_demo.db', storage: 'file'});
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCALAPPDATA: 'E:\\사용자 자료\\Local'}}), {path: 'E:\\사용자 자료\\Local\\LOCO\\loco_demo.db', storage: 'file'});
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: '.\\검증 자료\\현장 A.db'}}), {path: 'D:\\앱 위치\\LOCO\\검증 자료\\현장 A.db', storage: 'file'});
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: '..\\다른 자료\\현장 B.db'}}), {path: 'D:\\앱 위치\\다른 자료\\현장 B.db', storage: 'file'});
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: fileLocation.path}}), fileLocation);
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: ':memory:'}}), {path: ':memory:', storage: 'memory'});
    assert.deepEqual(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: '', LOCALAPPDATA: 'E:\\Local'}}), {path: 'E:\\Local\\LOCO\\loco_demo.db', storage: 'file'});
    // A whitespace-only filename is truthy in Python; stripping changes the DB.
    assert.equal(resolveDatabaseLocation({...base, env: {LOCO_DB_PATH: '  '}}).path, 'D:\\앱 위치\\LOCO\\  ');
  });

  await check('info confirms the actual service by a read-only list request and keeps the chosen path', async () => {
    const {bridge, calls, copied, opened} = serviceBridge();
    assert.deepEqual(await bridge.info(), ok({...fileLocation, connected: true, error: null}));
    assert.deepEqual(calls, [{method: 'list_surveys', params: {}}]);
    assert.deepEqual(copied, []); assert.deepEqual(opened, []);
  });

  await check('DB errors and stopped services cannot masquerade as a connected database', async () => {
    for (const call of [async () => error('DB_ERROR', '지원하지 않는 DB 구조입니다.'), async () => { throw new Error('Python 서비스가 종료되었습니다.'); }]) {
      const {bridge} = serviceBridge({call});
      const result = await bridge.info();
      assert.equal(result.ok, true); assert.equal(result.value.path, fileLocation.path);
      assert.equal(result.value.connected, false); assert.equal(result.value.error.code, 'DB_ERROR');
      assert.ok(result.value.error.message);
    }
  });

  await check('malformed or wrong-shaped service replies cannot enable file actions', async () => {
    for (const value of [undefined, null, {}, {ok: true}, ok(null), ok({}), ok('not a survey list'), {ok: false}]) {
      const {bridge, copied, opened} = serviceBridge({call: async () => value});
      const result = await bridge.info();
      assert.equal(result.ok, true); assert.equal(result.value.connected, false);
      assert.equal(result.value.path, fileLocation.path); assert.equal(result.value.error.code, 'DB_ERROR');
      assert.equal((await bridge.copy()).ok, false); assert.equal((await bridge.openFolder()).ok, false);
      assert.deepEqual(copied, []); assert.deepEqual(opened, []);
    }
  });

  await check('file actions recheck service availability and operate only on the held DB location', async () => {
    const {bridge, calls, copied, opened} = serviceBridge();
    const copiedResult = await bridge.copy(), openedResult = await bridge.openFolder();
    assert.equal(copiedResult.ok, true); assert.ok(copiedResult.value.message);
    assert.equal(openedResult.ok, true); assert.ok(openedResult.value.message);
    assert.deepEqual(copied, [fileLocation.path]);
    assert.deepEqual(opened, ['C:\\조사 자료\\현장 A']);
    assert.equal(calls.length, 2, 'each file action needs its own availability check');
    assert.ok(calls.every(item => item.method === 'list_surveys' && Object.keys(item.params).length === 0), 'no domain writes or extra service methods');
  });

  await check('a service that dies after successful info prevents clipboard and folder side effects', async () => {
    let live = true;
    const {bridge, copied, opened} = serviceBridge({call: async () => live ? ok([]) : error('DB_ERROR', '연결이 종료되었습니다.')});
    assert.equal((await bridge.info()).value.connected, true); live = false;
    for (const action of ['copy', 'openFolder']) {
      const result = await bridge[action](); assert.equal(result.ok, false); assert.equal(result.error.code, 'DB_ERROR');
    }
    assert.deepEqual(copied, []); assert.deepEqual(opened, []);
  });

  await check('clipboard exceptions and shell error strings are failures, not success messages', async () => {
    const clipboardFailure = serviceBridge({clipboard: {writeText() { throw new Error('클립보드 사용 불가'); }}});
    const result = await clipboardFailure.bridge.copy(); assert.equal(result.ok, false); assert.equal(result.error.code, 'FILE_ERROR');
    const shellFailure = serviceBridge({shell: {async openPath() { return 'Failed to open directory'; }}});
    const opened = await shellFailure.bridge.openFolder(); assert.equal(opened.ok, false); assert.equal(opened.error.code, 'FILE_ERROR');
    const shellThrow = serviceBridge({shell: {async openPath() { throw new Error('경로 접근 실패'); }}});
    assert.equal((await shellThrow.bridge.openFolder()).error.code, 'FILE_ERROR');
  });

  await check('memory DB has no file side effects even with a successful service response', async () => {
    const {bridge, copied, opened} = serviceBridge({location: {path: ':memory:', storage: 'memory'}});
    assert.equal((await bridge.info()).value.storage, 'memory');
    assert.equal((await bridge.copy()).ok, false); assert.equal((await bridge.openFolder()).ok, false);
    assert.deepEqual(copied, []); assert.deepEqual(opened, []);
  });

  await check('an unresponsive service times out locally and late replies cannot trigger file side effects', async () => {
    const waiting = [];
    const {bridge, copied, opened} = serviceBridge({
      verificationTimeoutMs: 5,
      call: () => { const request = deferred(); waiting.push(request); return request.promise; },
    });
    let guard;
    const results = await Promise.race([
      Promise.all([bridge.info(), bridge.copy(), bridge.openFolder()]),
      new Promise((_, reject) => { guard = setTimeout(() => reject(new Error('DB verification remained pending beyond its local deadline')), 500); }),
    ]).finally(() => clearTimeout(guard));
    assert.equal(results[0].ok, true); assert.equal(results[0].value.connected, false);
    assert.equal(results[0].value.path, fileLocation.path); assert.equal(results[0].value.error.code, 'DB_ERROR');
    for (const result of results.slice(1)) { assert.equal(result.ok, false); assert.equal(result.error.code, 'DB_ERROR'); }
    assert.deepEqual(copied, []); assert.deepEqual(opened, []);
    assert.equal(waiting.length, 3);
    for (const request of waiting) request.resolve(ok([]));
    await new Promise(resolve => setTimeout(resolve, 15));
    assert.deepEqual(copied, [], 'late success must not run a timed-out clipboard action');
    assert.deepEqual(opened, [], 'late success must not run a timed-out folder action');
  });

  const {DatabaseLocation} = await import(pathToFileURL(path.join(root, 'frontend/database-location.js')).href);
  await check('browser preview never fabricates a DB path or enables desktop file actions', async () => {
    const {element, nodes} = host(), ui = new DatabaseLocation({element});
    await ui.initialize(); disconnectedControls(nodes);
    assert.doesNotMatch(nodes.path.textContent, /loco_demo\.db|LOCALAPPDATA|^[A-Z]:\\/i);
    assert.match(nodes.status.textContent + nodes.path.textContent, /Electron|미리보기/);
    await ui.act('copy'); await ui.act('openFolder'); disconnectedControls(nodes);
  });

  await check('renderer displays the held Korean path as text and preserves it when verification later fails', async () => {
    const {element, nodes} = host(); let connected = true;
    const ui = new DatabaseLocation({element, bridge: rendererBridge({
      get_database_info: async () => ok({...fileLocation, connected, error: connected ? null : {code: 'DB_ERROR', message: '서비스 연결 실패'}}),
    })});
    await ui.initialize(); assert.equal(nodes.path.textContent, fileLocation.path);
    assert.equal(nodes.copy.disabled, false); assert.equal(nodes.open.disabled, false);
    connected = false; await ui.act('refresh');
    assert.equal(nodes.path.textContent, fileLocation.path); disconnectedControls(nodes);
    assert.match(nodes.status.textContent, /실패|확인|연결/);
  });

  await check('renderer rejects overlapping refresh and file actions while a request is pending', async () => {
    const {element, nodes} = host(), first = deferred(), copied = deferred(); let reads = 0, copies = 0;
    const ui = new DatabaseLocation({element, bridge: rendererBridge({
      get_database_info: async () => { reads++; return first.promise; },
      copy_database_path: async () => { copies++; return copied.promise; },
      open_database_folder: async () => { throw new Error('overlap must not reach folder action'); },
    })});
    const a = ui.initialize(), b = ui.initialize();
    await Promise.resolve(); assert.equal(reads, 1); disconnectedControls(nodes);
    first.resolve(ok({...fileLocation, connected: true, error: null})); await Promise.all([a, b]);
    const one = ui.act('copy'), two = ui.act('copy'), three = ui.act('openFolder');
    await Promise.resolve(); assert.equal(copies, 1); disconnectedControls(nodes);
    copied.resolve(ok({message: '경로 복사 완료'})); await Promise.all([one, two, three]);
    assert.equal(nodes.copy.disabled, false); assert.equal(nodes.open.disabled, false);
  });

  await check('renderer bridge rejection preserves the last known path and disables unsafe actions', async () => {
    const {element, nodes} = host(); let fail = false;
    const ui = new DatabaseLocation({element, bridge: rendererBridge({get_database_info: async () => { if (fail) throw new Error('Python 서비스 종료'); return ok({...fileLocation, connected: true, error: null}); }})});
    await ui.initialize(); fail = true; await ui.act('refresh');
    assert.equal(nodes.path.textContent, fileLocation.path); disconnectedControls(nodes);
    assert.ok(nodes.status.textContent);
  });

  await check('renderer uses the dedicated copy and folder bridges and reports a late DB disconnect', async () => {
    const {element, nodes} = host(), actions = []; let live = true;
    const ui = new DatabaseLocation({element, bridge: rendererBridge({
      get_database_info: async () => ok({...fileLocation, connected: live, error: live ? null : {code: 'DB_ERROR', message: 'DB 연결 종료'}}),
      copy_database_path: async () => { actions.push('copy'); return ok({message: '경로를 복사했습니다.'}); },
      open_database_folder: async () => { actions.push('open'); return live ? ok({message: 'DB 폴더를 열었습니다.'}) : error('DB_ERROR', 'DB 연결 종료'); },
    })});
    await ui.initialize(); await ui.act('copy'); await ui.act('openFolder');
    assert.deepEqual(actions, ['copy', 'open']);
    live = false; await ui.act('openFolder');
    assert.equal(nodes.path.textContent, fileLocation.path); disconnectedControls(nodes);
    assert.match(nodes.status.textContent, /종료|실패|연결/);
  });

  await check('renderer keeps memory DB file controls disabled after a successful query', async () => {
    const {element, nodes} = host();
    const ui = new DatabaseLocation({element, bridge: rendererBridge({get_database_info: async () => ok({path: ':memory:', storage: 'memory', connected: true, error: null})})});
    await ui.initialize(); disconnectedControls(nodes);
    assert.ok(nodes.path.textContent || nodes.status.textContent);
  });

  console.log(`PASS ${passed.length} independent database-location checks; no database files opened or written`);
}
main().catch(reason => { console.error(reason); process.exitCode = 1; });
