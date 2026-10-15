const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('node:child_process');
const { join } = require('node:path');
const readline = require('node:readline');
let worker, win, sequence = 0, workerError;
const pending = new Map();
function failAll(error) {
  workerError = error;
  for (const { reject } of pending.values()) reject(error);
  pending.clear();
}
app.whenReady().then(() => {
  worker = spawn(process.env.LOCO_PYTHON || 'python', ['-u', join(__dirname, 'backend', 'server.py')], {
    cwd: __dirname, windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['pipe', 'pipe', 'pipe']
  });
  worker.on('error', failAll);
  worker.on('exit', code => failAll(new Error(`Python 서비스가 종료되었습니다 (${code}). LOCO_PYTHON 실행 경로를 확인하세요.`)));
  worker.stdin.on('error', failAll);
  worker.stderr.on('data', data => process.stderr.write(data));
  const lines = readline.createInterface({ input: worker.stdout, crlfDelay: Infinity });
  lines.on('line', line => {
    try {
      const response = JSON.parse(line), request = pending.get(response.request_id);
      if (request) { pending.delete(response.request_id); request.resolve(response.result); }
    } catch (error) { failAll(new Error(`Python 응답을 읽지 못했습니다: ${error.message}`)); }
  });
  ipcMain.handle('loco:call', (_, method, params) => new Promise((resolve, reject) => {
    if (workerError) return reject(workerError);
    const request_id = ++sequence;
    pending.set(request_id, { resolve, reject });
    worker.stdin.write(JSON.stringify({ request_id, method, params }) + '\n', 'utf8', error => {
      if (error) { pending.delete(request_id); reject(error); }
    });
  }));
  ipcMain.handle('loco:photos', async () => {
    const result = await dialog.showOpenDialog(win, { properties: ['openFile', 'multiSelections'], filters: [{ name: '사진', extensions: ['jpg', 'jpeg', 'png'] }] });
    return result.canceled ? [] : result.filePaths;
  });
  ipcMain.handle('loco:export', async () => {
    const result = await dialog.showSaveDialog(win, { defaultPath: 'LOCO_작업분석.xlsx', filters: [{ name: 'Excel', extensions: ['xlsx'] }] });
    return result.canceled ? null : result.filePath;
  });
  win = new BrowserWindow({ width: 1440, height: 940, minWidth: 1100, minHeight: 740, backgroundColor: '#f5f6fa',
    webPreferences: { preload: join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false } });
  win.loadFile(join(__dirname, 'renderer', 'index.html'));
});
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { if (worker) worker.kill(); });
