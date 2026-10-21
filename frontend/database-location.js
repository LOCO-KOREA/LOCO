// Read-only database location controls. The Electron bridge owns the actual path.
export class DatabaseLocation {
  constructor({element, bridge}) {
    this.element = element;
    this.bridge = bridge;
    this.info = null;
    this.pending = false;
    element.classList.add('database-location');
    element.setAttribute('aria-label', '현재 데이터베이스');
    element.innerHTML = '<strong>DB 경로</strong><span class="database-path" data-db-path></span><span class="database-status" data-db-status role="status" aria-live="polite"></span><div class="button-group compact database-actions"><button type="button" data-db-copy disabled>경로 복사</button><button type="button" data-db-open disabled>폴더 열기</button><button type="button" data-db-refresh disabled>다시 확인</button></div>';
    this.path = element.querySelector('[data-db-path]');
    this.status = element.querySelector('[data-db-status]');
    this.copy = element.querySelector('[data-db-copy]');
    this.open = element.querySelector('[data-db-open]');
    this.refresh = element.querySelector('[data-db-refresh]');
    this.copy.addEventListener('click', () => this.act('copy'));
    this.open.addEventListener('click', () => this.act('openFolder'));
    this.refresh.addEventListener('click', () => this.act('refresh'));
  }

  available() {
    return ['get_database_info', 'copy_database_path', 'open_database_folder']
      .every(method => typeof this.bridge?.[method] === 'function');
  }

  controls() {
    const fileReady = this.info?.connected && this.info.storage === 'file';
    this.copy.disabled = this.open.disabled = this.pending || !this.available() || !fileReady;
    this.refresh.disabled = this.pending || !this.available();
    this.element.setAttribute('aria-busy', String(this.pending));
  }

  message(text, state) {
    this.status.textContent = text;
    this.element.dataset.state = state;
  }

  unwrap(result) {
    if (result?.ok !== true) throw Object.assign(new Error(result?.error?.message || 'DB 경로 정보를 확인하지 못했습니다.'), {code: result?.error?.code || 'DB_ERROR'});
    return result.value;
  }

  async initialize() { return this.act('refresh'); }

  async act(action) {
    if (this.pending) return;
    if (!this.available()) {
      this.path.textContent = '';
      this.message(this.bridge ? '앱을 다시 실행해 DB 경로를 확인하세요.' : '화면 미리보기 · DB 경로와 저장은 Electron 앱에서 확인하세요.', 'preview');
      this.controls();
      return;
    }
    if (action !== 'refresh' && (!this.info?.connected || this.info.storage !== 'file')) return;
    this.pending = true;
    this.controls();
    this.message(action === 'refresh' ? 'DB 연결 확인 중…' : '처리 중…', 'loading');
    try {
      if (action === 'refresh') {
        const info = this.unwrap(await this.bridge.get_database_info());
        if (!info || !['file', 'memory'].includes(info.storage) || typeof info.path !== 'string' || typeof info.connected !== 'boolean') throw new Error('DB 경로 응답을 확인하지 못했습니다. 앱을 다시 실행하세요.');
        this.info = info;
        this.path.textContent = info.storage === 'memory' ? '메모리 DB · 파일로 저장하지 않음' : info.path;
        this.path.title = info.path;
        this.message(info.connected ? '연결 확인됨' : info.error?.message || 'DB 연결 확인 실패', info.connected ? 'ready' : 'error');
      } else {
        const method = action === 'copy' ? 'copy_database_path' : 'open_database_folder';
        const value = this.unwrap(await this.bridge[method]());
        this.message(value.message, 'ready');
      }
    } catch (error) {
      if (action === 'refresh' || error.code === 'DB_ERROR') {
        if (this.info) this.info = {...this.info, connected: false};
      }
      this.message(error.message || 'DB 경로 작업을 완료하지 못했습니다.', 'error');
    } finally {
      this.pending = false;
      this.controls();
    }
  }
}
