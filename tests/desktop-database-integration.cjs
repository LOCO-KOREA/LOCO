/* Real JSON Lines/Python/SQLite through the actual main/preload modules.
 * Electron window, clipboard and shell adapters are mocks; this is not GUI QA.
 * Only new verification DBs are used. No existing user database is opened.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const {spawn, spawnSync} = require('node:child_process');
const root = process.env.LOCO_TEST_ROOT || path.resolve(__dirname, '..');
const python = process.env.LOCO_VERIFY_PYTHON || path.join(root, '.venv/Scripts/python.exe');
const mainFile = path.join(root, 'frontend/electron/main.cjs');
const localRequire = createRequire(mainFile);
let base;
const checks = [];
const check = name => { checks.push(name); console.log('PASS ' + name); };

async function bounded(promise) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(Error('Python/IPC verification timed out')), 20000); })]); }
  finally { clearTimeout(timer); }
}

async function boot(overrides) {
  const handlers = new Map(), events = new Map(), copied = [], opened = [];
  let child, spawned, bridge;
  const electron = {
    app: {isPackaged: false, setAppUserModelId(id) { assert.equal(id, 'kr.loco.desktop'); }, whenReady: () => ({then(run) { run(); }}), on(name, run) { events.set(name, run); }, quit() {}},
    BrowserWindow: class { constructor(options) { assert.equal(options.icon, path.join(root, 'frontend/assets/app-icon.ico')); this.webContents = {on() {}}; } loadFile() {} },
    ipcMain: {handle(name, run) { handlers.set(name, run); }},
    clipboard: {writeText(text) { copied.push(text); }},
    shell: {async openPath(folder) { opened.push(folder); return ''; }},
    dialog: {},
    contextBridge: {exposeInMainWorld(name, value) { assert.equal(name, 'loco'); bridge = value; }},
    ipcRenderer: {invoke(name, ...args) { return handlers.get(name)({}, ...args); }},
    webUtils: {},
  };
  const env = {...process.env, LOCO_PYTHON: python, ...overrides};
  // Main owns all other dependencies. Only native Electron/OS adapters are mocks.
  vm.runInNewContext(await fs.readFile(mainFile, 'utf8'), {
    __dirname: path.dirname(mainFile), console,
    process: {env, platform: 'win32', resourcesPath: root, stderr: {write() {}}},
    require(name) {
      if (name === 'electron') return electron;
      if (name === 'node:child_process') return {spawn(binary, args, options) {
        spawned = {binary, args, options}; child = spawn(binary, args, options); return child;
      }};
      return localRequire(name);
    },
  }, {filename: mainFile});
  vm.runInNewContext(await fs.readFile(path.join(root, 'frontend/electron/preload.cjs'), 'utf8'), {
    require(name) { assert.equal(name, 'electron'); return electron; },
  });
  return {bridge, spawned, copied, opened, child, close() { events.get('before-quit')(); }};
}

function readRows(file) {
  const code = "import json,sqlite3,sys; from pathlib import Path; c=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row; names=sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\")); print(json.dumps({n:[dict(r) for r in c.execute('SELECT * FROM '+n+' ORDER BY 1')] for n in names},ensure_ascii=False)); c.close()";
  const result = spawnSync(python, ['-B', '-c', code, file], {encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}, windowsHide: true});
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

async function fileCase(name, configured, expected, extraEnv = {}) {
  const app = await boot({LOCO_DB_PATH: configured, ...extraEnv});
  try {
    const info = await bounded(app.bridge.get_database_info());
    assert.equal(info.ok, true); assert.equal(info.value.connected, true);
    assert.equal(info.value.path, expected);
    assert.equal(app.spawned.options.env.LOCO_DB_PATH, expected, 'display must equal the path passed to the actual Python worker');
    assert.equal(app.spawned.options.windowsHide, true);
    const saved = await bounded(app.bridge.call('create_survey', {draft: {title: 'N02 경로 검증 · ' + name, survey_type: 'REGULAR'}}));
    assert.equal(saved.ok, true, JSON.stringify(saved));
    assert.equal((await bounded(app.bridge.get_database_info())).value.connected, true);
    const before = readRows(expected);
    assert.deepEqual(Object.keys(before).sort(), ['ANALYSIS', 'APP_SETTINGS', 'EXPORT_LOG', 'PHOTO', 'SURVEY', 'TASK']);
    assert.equal(JSON.parse(before.SURVEY[0].metadata_json).title, 'N02 경로 검증 · ' + name);
    assert.equal((await bounded(app.bridge.copy_database_path('C:\\ignored\\other.db'))).ok, true);
    assert.equal((await bounded(app.bridge.open_database_folder('C:\\ignored'))).ok, true);
    assert.deepEqual(app.copied, [expected]); assert.deepEqual(app.opened, [path.dirname(expected)]);
    assert.deepEqual(readRows(expected), before, 'location actions must preserve every stored row and JSON string');
    check(name + ': worker env, preload path, real stored survey and unchanged six-table rows agree');
  } finally { app.close(); }
}

async function main() {
  base = await fs.mkdtemp(path.join(os.tmpdir(), 'loco-n02-'));
  const absolute = path.join(base, '한글 공백 검증', '현장 A.db');
  await fileCase('absolute Korean path', absolute, absolute);
  const localAppData = path.join(base, '사용자 앱 자료');
  await fileCase('unchanged default location', '', path.join(localAppData, 'LOCO/loco_demo.db'), {LOCALAPPDATA: localAppData});
  const relative = path.join('.local', 'n02-' + path.basename(base), '상대 경로 검증', '현장 B.db');
  await fileCase('relative worker path', relative, path.resolve(root, relative));
  const broken = path.join(base, '손상 파일.db');
  await fs.writeFile(broken, 'not a sqlite database');
  const app = await boot({LOCO_DB_PATH: broken});
  try {
    const info = await bounded(app.bridge.get_database_info());
    assert.equal(info.value.path, broken); assert.equal(info.value.connected, false);
    assert.equal((await bounded(app.bridge.copy_database_path())).ok, false);
    assert.equal((await bounded(app.bridge.open_database_folder())).ok, false);
    assert.deepEqual(app.copied, []); assert.deepEqual(app.opened, []);
    assert.equal(await fs.readFile(broken, 'utf8'), 'not a sqlite database');
    check('corrupt DB stays unmodified, retains its path and cannot trigger clipboard/folder success');
  } finally { app.close(); }
  const missing = await boot({LOCO_PYTHON: path.join(base, 'missing-python.exe'), LOCO_DB_PATH: path.join(base, 'not-opened.db')});
  try {
    assert.equal((await bounded(missing.bridge.get_database_info())).value.connected, false);
    assert.equal((await bounded(missing.bridge.open_database_folder())).ok, false);
    assert.deepEqual(missing.opened, []);
    check('Python launch failure stays disconnected through actual main/preload IPC');
  } finally { missing.close(); }
  await fs.writeFile(path.join(base, 'receipt.json'), JSON.stringify({kind: 'actual main/preload modules with mocked Electron shell/window; real Python/SQLite', checks, source_commit: process.env.LOCO_TEST_COMMIT || null}, null, 2));
  console.log('Verification artifacts: ' + base);
  console.log(`PASS ${checks.length} real-service integration cases; native window/clipboard/folder interaction is not covered`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
