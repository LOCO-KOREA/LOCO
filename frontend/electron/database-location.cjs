// Electron owns one database location for the lifetime of its Python worker.
// Paths shown in the UI are the exact values passed through LOCO_DB_PATH.
const {resolve, join, dirname} = require('node:path');

function resolveDatabaseLocation({env, cwd, home}) {
  const configured = env.LOCO_DB_PATH;
  if (configured === ':memory:') return {path: configured, storage: 'memory'};
  const fallback = join(env.LOCALAPPDATA || join(home, 'AppData', 'Local'), 'LOCO', 'loco_demo.db');
  return {path: resolve(cwd, configured || fallback), storage: 'file'};
}

function createDatabaseLocationBridge({location, call, clipboard, shell, verificationTimeoutMs = 8000}) {
  const failed = (code, message) => ({ok: false, error: {code, message}});
  async function info() {
    let connected = false, timer;
    try {
      // Bound only this read-only check; domain writes retain their existing IPC behavior.
      const response = await Promise.race([
        call('list_surveys', {}),
        new Promise(resolveTimeout => { timer = setTimeout(() => resolveTimeout(null), verificationTimeoutMs); }),
      ]);
      connected = response?.ok === true && Array.isArray(response.value);
    } catch { /* A failed worker is an unavailable DB, not a confirmed connection. */ }
    finally { clearTimeout(timer); }
    return {ok: true, value: {...location, connected, error: connected ? null : {
      code: 'DB_ERROR',
      message: 'DB 연결을 확인하지 못했습니다. 앱 실행 설정과 파일 접근 권한을 확인하세요.',
    }}};
  }
  async function fileAction(action) {
    const {value} = await info();
    if (!value.connected) return {ok: false, error: value.error};
    if (value.storage !== 'file') return failed('DB_ERROR', '메모리 DB에는 파일 경로나 저장 폴더가 없습니다.');
    try {
      if (action === 'copy') {
        clipboard.writeText(value.path);
        return {ok: true, value: {message: 'DB 경로를 복사했습니다.'}};
      }
      const error = await shell.openPath(dirname(value.path));
      if (error !== '') return failed('FILE_ERROR', 'DB 폴더를 열지 못했습니다. 폴더 위치와 접근 권한을 확인하세요.');
      return {ok: true, value: {message: 'DB가 저장된 폴더를 열었습니다.'}};
    } catch {
      return failed('FILE_ERROR', action === 'copy'
        ? 'DB 경로를 복사하지 못했습니다. 다시 시도해 주세요.'
        : 'DB 폴더를 열지 못했습니다. 폴더 위치와 접근 권한을 확인하세요.');
    }
  }
  return {info, copy: () => fileAction('copy'), openFolder: () => fileAction('open')};
}

module.exports = {resolveDatabaseLocation, createDatabaseLocationBridge};
