// S04: docs/ui/05_사진등록.svg — five phase rows, three cycle columns, right observation panel.
class PhotoWorkspace {
  constructor(options) {
    Object.assign(this, options);
    this.host = document.querySelector('#photo-workspace');
    this.task = null;
    this.photos = [];
    this.capture = null;
    this.selected = 1;
    this.previews = new Map();
    this.pending = Promise.resolve();
    this.failures = [];
    this.dialog = document.createElement('dialog');
    this.dialog.className = 'photo-dialog';
    document.body.append(this.dialog);
    this.host.addEventListener('click', event => this.click(event));
    this.host.addEventListener('change', event => this.change(event));
    this.dialog.addEventListener('click', event => this.click(event));
    for (const target of [this.host, this.dialog]) {
      target.addEventListener('dragover', event => { event.preventDefault(); });
      target.addEventListener('drop', event => {
        event.preventDefault();
        const paths = [], missing = [];
        for (const file of event.dataTransfer.files) {
          try {
            const path = window.loco?.path_for_file(file);
            if (path) paths.push(path); else missing.push(file.name);
          } catch { missing.push(file.name); }
        }
        this.run(async () => {
          if (paths.length) await this.importPaths(paths);
          if (missing.length) { this.failures.push(...missing.map(name => `${name}: 파일 경로를 읽지 못했습니다. 사진 추가 버튼을 이용하세요.`)); this.render(); }
        });
      });
    }
  }
  esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  emptyObservation() { return {phase_verified:'UNKNOWN',load_state:'UNKNOWN',single_person:'UNKNOWN',full_frame:'UNKNOWN',camera_fixed:'UNKNOWN',normal_cycle:'UNKNOWN',evidence:{source:null,text:null,observed_at:null}}; }
  run(action) { this.pending = this.pending.then(() => { this.clearError(); return action(); }).catch(error => this.onError(error)); return this.pending; }
  async flush() { await this.pending; if (this.task?.task_id) await this.save(); }
  async open(taskId) {
    const bundle = await this.api('get_task', {task_id:taskId});
    if (this.task?.task_id !== taskId) { this.selected = 1; this.failures = []; this.previews.clear(); }
    this.task = bundle.task;
    this.capture = structuredClone(bundle.task.capture);
    this.photos = bundle.photos;
    this.render();
  }
  preview() {
    this.task = {task_id:null,task_name:'',capture:{protocol:'BOX_LIFT_15_V1',camera_side:null,forward_direction:null,slots:Array.from({length:15}, (_, i) => ({slot_no:i+1,cycle_no:Math.floor(i/5)+1,phase:PhotoWorkspace.phases[i%5][0],photo_id:null,observation:this.emptyObservation()}))}};
    this.capture = structuredClone(this.task.capture);
    this.photos = [];
    this.render();
  }
  dirty() { return JSON.stringify(this.capture) !== JSON.stringify(this.task.capture); }
  status() { const node = this.host.querySelector('[data-photo-status]'); if (node) node.textContent = !this.task.task_id ? '화면 미리보기' : this.dirty() ? '● 저장 전 변경 사항' : '● 저장됨'; }
  select(label, key, value, options, extra = '') {
    return `<label>${label}<select aria-label="${label}" ${extra} data-photo-field="${key}">${options.map(([v, text]) => `<option value="${v}" ${String(value ?? '') === v ? 'selected' : ''}>${text}</option>`).join('')}</select></label>`;
  }
  truth(label, key, value) { return this.select(label, key, value, [['UNKNOWN','모름'],['YES','예'],['NO','아니오']]); }
  slot() { return this.capture.slots.find(slot => slot.slot_no === this.selected); }
  photo(id) { return this.photos.find(photo => photo.photo_id === id); }
  async save() {
    if (!this.task?.task_id) throw Error('사진 저장은 Electron에서 조사를 선택하고 작업을 저장한 뒤 사용할 수 있습니다.');
    if (!this.dirty()) return;
    const sent = structuredClone(this.capture);
    const task = await this.api('set_capture', {task_id:this.task.task_id,capture:sent});
    if (JSON.stringify(this.capture) === JSON.stringify(sent)) this.capture = structuredClone(task.capture);
    this.task = task;
    this.onSaved(task);
    this.status();
  }
  render() {
    if (!this.capture) return;
    const count = this.capture.slots.filter(slot => slot.photo_id !== null).length;
    const ids = this.capture.slots.map(slot => slot.photo_id).filter(id => id !== null);
    const duplicate = new Set(ids.map(id => this.photo(id)?.file_path || id)).size < ids.length;
    this.setTitle('사진 등록과 15슬롯 배정', '같은 조건의 정상 작업 3회에서 다섯 순간을 촬영합니다. 시간 간격을 맞출 필요는 없습니다.');
    this.host.innerHTML = `
      <div class="photo-context"><strong>${this.esc(this.surveyTitle() || '조사 미선택')} / ${this.esc(this.task.task_name || '작업 미선택')}</strong><span data-photo-status></span></div>
      <div class="task-steps">${['작업 정보','사진 등록','자세 분석','판정 검토','보고서'].map((name,i) => `<button type="button" class="${i===1?'active':''}" data-photo-action="${i===0?'back':i===1?'stay':'unlinked'}"><b>${i+1}</b>${name}</button>`).join('')}</div>
      <div class="photo-columns">
        <section class="panel photo-board" aria-label="사진 배정표">
          <div class="photo-heading"><h2>3회 × 5순간 · 사진 배정 ${count} / 15</h2><button type="button" class="primary" data-photo-action="import" title="JPG·PNG 선택 또는 배정표에 끌어놓기">＋ 사진 추가</button></div>
          <div class="photo-grid" role="table" aria-label="5순간 3회차 사진 배정">
            <div class="photo-grid-row photo-grid-head" role="row"><span role="columnheader">번호 · 순간</span>${[1,2,3].map(c => `<strong role="columnheader">${c}회차</strong>`).join('')}</div>
            ${PhotoWorkspace.phases.map(([phase,name,load],i) => `<div class="photo-grid-row" role="row"><div class="photo-phase" role="rowheader"><strong>${name}</strong><small>${load}</small></div>${[0,1,2].map(c => this.slotCard(this.capture.slots[c*5+i])).join('')}</div>`).join('')}
          </div>
          <div class="photo-camera">${this.select('카메라 위치','camera_side',this.capture.camera_side,[['','미입력'],['LEFT','왼쪽 정측면'],['RIGHT','오른쪽 정측면']])}${this.select('작업자의 앞 방향','forward_direction',this.capture.forward_direction,[['','미입력'],['SCREEN_RIGHT','화면 오른쪽'],['SCREEN_LEFT','화면 왼쪽']])}</div>
          <div class="photo-candidate-line"><span>후보 사진 ${this.photos.length}장 · 미배정 슬롯도 결과에서 표시하며 분석할 수 있습니다.</span><button type="button" data-photo-action="candidates">후보 사진 보기</button></div>
          ${duplicate?'<p class="photo-notice">같은 사진이 여러 슬롯에 배정돼 있습니다. 서로 다른 15장 사용을 권장합니다.</p>':''}
          ${this.failures.length?`<div class="photo-notice" role="status"><strong>등록하지 못한 사진</strong><ul>${this.failures.map(message=>`<li>${this.esc(message)}</li>`).join('')}</ul></div>`:''}
        </section>
        <aside class="panel photo-observation" aria-label="촬영 안내와 관찰 입력">${this.observationPanel()}</aside>
      </div>
      <div class="task-bottom"><button type="button" data-photo-action="back">이전</button><button type="button" class="dark" data-photo-action="save">배정·관찰 저장</button><button type="button" class="primary" data-photo-action="analysis">15슬롯 분석 시작 →</button></div>`;
    this.status();
  }
  slotCard(slot) {
    const photo = this.photo(slot.photo_id);
    return `<div role="cell" class="photo-slot ${slot.slot_no===this.selected?'selected':''} ${photo?'assigned':''}">
      <button type="button" class="photo-slot-name" data-select-slot="${slot.slot_no}" aria-pressed="${slot.slot_no===this.selected}" title="${this.esc(photo?.file_name || '사진 미배정')}">${String(slot.slot_no).padStart(2,'0')} · ${this.esc(photo?.file_name || '사진 미배정')}</button>
      <div class="photo-slot-actions"><button type="button" data-assign-slot="${slot.slot_no}">${photo?'교체':'사진 배정'}</button><button type="button" data-clear-slot="${slot.slot_no}">해제</button></div></div>`;
  }
  observationPanel() {
    const slot = this.slot(), o = slot.observation, photo = this.photo(slot.photo_id);
    return `<h2>촬영 안내</h2><div class="photo-guide-copy"><p>한 사람 · 정측면 · 렌즈 수평<br>위치·줌·방향을 15장 동안 유지<br>전신·상자·바닥·선반을 포함<br>가까운 쪽 관절이 가려지면 재촬영<br>정상 작업을 멈추거나 과장하지 않기<br>중간 순간은 상자 <strong>바닥</strong>이<br>선반 높이의 절반을 통과할 때</p><button type="button" data-photo-action="guide">자세한 촬영 안내</button></div>
      <h3>선택: ${slot.cycle_no}회차 · ${PhotoWorkspace.phases[(slot.slot_no-1)%5][1]}</h3>
      ${this.truth('촬영 순간 확인','phase_verified',o.phase_verified)}
      ${this.select('하중 상태','load_state',o.load_state,[['UNKNOWN','모름'],['UNLOADED','하중 없음'],['FULL_BOX','상자 전체 중량']])}
      <div class="photo-observation-group">${this.truth('한 사람','single_person',o.single_person)}${this.truth('전신','full_frame',o.full_frame)}${this.truth('카메라 고정','camera_fixed',o.camera_fixed)}</div>
      <div class="photo-observation-group two">${this.truth('정상 작업','normal_cycle',o.normal_cycle)}<div class="photo-consent-summary"><span>동의 기록</span><button type="button" data-photo-action="details">${photo?({YES:'예',NO:'아니오',UNKNOWN:'미기록'}[photo.consent]):'사진 미배정'}</button></div></div>
      <button type="button" class="photo-details-button" data-photo-action="details">관찰 근거 · 사진 경로 · 동의 기록</button>`;
  }
  change(event) {
    const key = event.target.dataset.photoField;
    if (!key) return;
    if (['camera_side','forward_direction'].includes(key)) {
      this.capture[key] = event.target.value || null;
      for (const slot of this.capture.slots) slot.observation = this.emptyObservation();
      this.render();
      this.run(async () => { if (this.task.task_id) await this.save(); this.notify('카메라 방향 변경으로 촬영 관찰과 수동값을 초기화했습니다.'); });
    } else { this.slot().observation[key] = event.target.value; this.status(); }
  }
  click(event) {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.selectSlot) { this.selected = Number(button.dataset.selectSlot); this.render(); return; }
    if (button.dataset.assignSlot) { this.selected = Number(button.dataset.assignSlot); this.render(); this.showCandidates(this.selected); return; }
    if (button.dataset.clearSlot) { const number = Number(button.dataset.clearSlot); this.run(()=>this.assign(number,null)); return; }
    if (button.dataset.usePhoto) { const number = this.assignTarget; const id = Number(button.dataset.usePhoto); this.run(async()=>{await this.assign(number,id); this.dialog.close();}); return; }
    if (button.dataset.removePhoto) { const id = Number(button.dataset.removePhoto); this.run(()=>this.remove(id)); return; }
    if (button.dataset.previewPhoto) { this.showPreview(Number(button.dataset.previewPhoto)); return; }
    const action = button.dataset.photoAction;
    if (action==='close') { this.dialog.close(); return; }
    if (action==='guide') { this.showGuide(); return; }
    if (action==='candidates') { this.showCandidates(null); return; }
    if (action==='details') { this.showDetails(); return; }
    this.run(async () => {
      if (action==='import') await this.choosePhotos();
      else if (action==='save') { await this.save(); this.notify('사진 배정과 관찰 입력을 저장했습니다.'); }
      else if (action==='back') { if (this.task.task_id) await this.save(); await this.onBack(); }
      else if (action==='analysis') { if (this.task.task_id) { await this.save(); this.notify('사진 입력을 저장했습니다. 분석 실행은 다음 구현 단계에서 연결합니다.'); } else this.notify('분석 실행은 다음 구현 단계에서 연결합니다.'); }
      else if (action==='unlinked') this.notify('분석·판정·보고서 화면은 다음 구현 단계입니다.');
      else if (action==='keep-details') await this.keepDetails();
    });
  }
  async assign(number, id) {
    const slot = this.capture.slots.find(slot => slot.slot_no===number);
    this.selected = number;
    if (slot.photo_id !== id) { slot.photo_id=id; slot.observation=this.emptyObservation(); }
    this.render();
    if (this.task.task_id) await this.save();
  }
  async choosePhotos() {
    if (!window.loco) throw Error('사진 선택은 Electron 앱에서 사용할 수 있습니다.');
    const paths = await window.loco.choose_photo_paths();
    if (paths.length) await this.importPaths(paths);
  }
  async importPaths(paths) {
    if (!this.task?.task_id) throw Error('작업을 먼저 저장한 뒤 사진을 등록하세요.');
    const report = await this.api('import_photos', {task_id:this.task.task_id,file_paths:paths});
    this.photos.push(...report.added);
    this.failures = report.unreadable.map(file => `${file.file_path}: ${file.message}`);
    this.render();
    this.showCandidates(this.dialog.open ? this.assignTarget : null);
    this.notify(`${report.added.length}장 등록했습니다. 회차와 순간을 선택해 사진을 배정하세요.`);
  }
  async remove(id) {
    await this.save();
    await this.api('delete_photo', {photo_id:id});
    const bundle = await this.api('get_task', {task_id:this.task.task_id});
    this.task=bundle.task; this.capture=structuredClone(bundle.task.capture); this.photos=bundle.photos;
    this.onSaved(bundle.task); this.previews.delete(id); this.render(); this.showCandidates(this.assignTarget);
    this.notify('사진 등록을 삭제했습니다. 원본 파일은 유지됩니다.');
  }
  showDialog(title, content) {
    this.dialog.innerHTML=`<div class="photo-dialog-heading"><h2>${this.esc(title)}</h2><button type="button" data-photo-action="close">닫기</button></div>${content}`;
    if (!this.dialog.open) this.dialog.showModal();
  }
  showCandidates(number) {
    this.assignTarget=number;
    const slot = number ? this.capture.slots.find(slot=>slot.slot_no===number) : null;
    this.showDialog(slot?`${slot.cycle_no}회차 · ${PhotoWorkspace.phases[(number-1)%5][1]} 사진 배정`:'후보 사진', `
      <p class="photo-dialog-note">사진을 선택한 순서로 자동 배정하지 않습니다. 사용할 사진을 직접 고르세요.</p>
      <button type="button" class="primary" data-photo-action="import">＋ 사진 추가</button>
      <div class="photo-candidates">${this.photos.map(photo=>`<article class="photo-candidate"><div class="photo-thumbnail" data-thumbnail="${photo.photo_id}">미리보기 불러오는 중…</div><strong title="${this.esc(photo.file_name)}">${this.esc(photo.file_name)}</strong><small>${this.capture.slots.filter(s=>s.photo_id===photo.photo_id).map(s=>`${String(s.slot_no).padStart(2,'0')}번`).join(', ') || '미배정'}</small><div>${number?`<button type="button" data-use-photo="${photo.photo_id}">이 사진 배정</button>`:`<button type="button" data-preview-photo="${photo.photo_id}">크게 보기</button>`}<button type="button" class="danger" data-remove-photo="${photo.photo_id}">등록 삭제</button></div></article>`).join('') || '<p class="photo-dialog-note">등록된 사진이 없습니다. JPG·PNG를 추가하거나 여기에 끌어놓으세요.</p>'}</div>`);
    this.loadThumbnails();
  }
  async previewData(photo) {
    if (!this.previews.has(photo.photo_id)) {
      const request=this.api('get_photo_preview',{photo}).catch(error=>{this.previews.delete(photo.photo_id);throw error;});
      this.previews.set(photo.photo_id,request);
    }
    return this.previews.get(photo.photo_id);
  }
  async loadThumbnails() {
    for (const element of this.dialog.querySelectorAll('[data-thumbnail]')) {
      const photo=this.photo(Number(element.dataset.thumbnail));
      if (!element.isConnected) return;
      try {
        const preview=await this.previewData(photo);
        if (element.isConnected) { const img=document.createElement('img');img.src=preview.data_url;img.alt=photo.file_name;element.replaceChildren(img); }
      } catch(error) { if(element.isConnected) element.textContent=error.message; }
    }
  }
  showPreview(id) {
    const photo=this.photo(id);
    this.showDialog(photo.file_name, `<div class="photo-large-preview" data-thumbnail="${id}">미리보기 불러오는 중…</div><p class="photo-file-path">${this.esc(photo.file_path)}</p>`);
    this.loadThumbnails();
  }
  showDetails() {
    const slot=this.slot(), photo=this.photo(slot.photo_id), evidence=slot.observation.evidence;
    this.detailsSlot=slot.slot_no;
    const time=evidence.observed_at ? new Date(new Date(evidence.observed_at).getTime()+9*60*60*1000).toISOString().slice(0,16) : '';
    this.showDialog(`${slot.cycle_no}회차 · ${PhotoWorkspace.phases[(slot.slot_no-1)%5][1]} 관찰 기록`, `
      ${photo?`<div class="photo-detail-top"><div class="photo-thumbnail" data-thumbnail="${photo.photo_id}">미리보기 불러오는 중…</div><div><strong>${this.esc(photo.file_name)}</strong><p class="photo-file-path">${this.esc(photo.file_path)}</p></div></div><label>원본 사진 경로<input id="photo-path" value="${this.esc(photo.file_path)}"></label><p class="photo-dialog-note">같은 원본의 이동 경로를 다시 연결합니다. 다른 사진으로 바꿀 때는 배정표의 교체를 사용하세요.</p><label>동의 기록<select id="photo-consent"><option value="UNKNOWN" ${photo.consent==='UNKNOWN'?'selected':''}>미기록</option><option value="YES" ${photo.consent==='YES'?'selected':''}>예</option><option value="NO" ${photo.consent==='NO'?'selected':''}>아니오</option></select></label>`:'<p class="photo-dialog-note">사진 미배정 · 관찰 근거는 먼저 기록할 수 있습니다.</p>'}
      <label>관찰 근거<textarea id="photo-evidence" aria-label="관찰 근거">${this.esc(evidence.text)}</textarea></label>
      <div class="photo-evidence-pair"><label>근거 출처<select id="photo-source">${[['','미입력'],['DIRECT_OBSERVATION','직접 관찰'],['INTERVIEW','면담'],['DOCUMENT','문서'],['OTHER','기타']].map(([key,name])=>`<option value="${key}" ${(evidence.source||'')===key?'selected':''}>${name}</option>`).join('')}</select></label><label>관찰 시각 (한국시간)<input id="photo-time" type="datetime-local" value="${time}"></label></div>
      <button type="button" class="primary" data-photo-action="keep-details">관찰 기록 저장</button>`);
    this.loadThumbnails();
  }
  async keepDetails() {
    const slot=this.capture.slots.find(slot=>slot.slot_no===this.detailsSlot), photo=this.photo(slot.photo_id);
    const time=this.dialog.querySelector('#photo-time').value;
    slot.observation.evidence={text:this.dialog.querySelector('#photo-evidence').value||null,source:this.dialog.querySelector('#photo-source').value||null,observed_at:time?new Date(time+'+09:00').toISOString():null};
    this.status();
    if (photo) {
      const updated=await this.api('update_photo',{photo_id:photo.photo_id,file_path:this.dialog.querySelector('#photo-path').value,consent:this.dialog.querySelector('#photo-consent').value});
      this.photos=this.photos.map(p=>p.photo_id===updated.photo_id?updated:p); this.previews.delete(photo.photo_id);
    }
    await this.save(); this.dialog.close(); this.render(); this.notify('관찰 근거와 사진 기록을 저장했습니다.');
  }
  showGuide() {
    this.showDialog('촬영 안내', `<ol class="photo-full-guide">
      <li>상자 전체 중량을 저울/표기 근거로 기록합니다. 바닥에서 선반 상판 윗면까지 수직 높이를 기록합니다. 모르면 비워 두고 무게를 추측하지 않습니다.</li>
      <li>바닥을 높이 0으로 잡고 줄자/높이 표시로 선반 높이의 절반을 확인합니다. 중간 사진은 상자 <strong>바닥면</strong>이 그 높이를 통과하는 순간입니다. 상자 중심이나 손 높이가 아닙니다.</li>
      <li>카메라는 작업자 왼쪽/오른쪽 정측면에 고정합니다. 작업자 앞쪽이 화면 오른쪽/왼쪽인지 기록합니다. 렌즈 축은 수평이며 작업자의 시상면에 직각입니다.</li>
      <li>삼각대 높이는 무릎/허리 부근에서 전체 동작을 담도록 잡습니다. 시작·숙임·올림·종료 동안 머리·어깨·팔꿈치·손목·골반·무릎·발목·양발 전체, 상자 전체, 바닥과 선반 상판이 프레임 안에 들도록 여백을 둡니다.</li>
      <li>15장 동안 카메라 위치·줌·방향을 유지합니다. 가까운 쪽 필수 관절이 상자/선반에 가려지면 다시 찍습니다. 먼 쪽 팔은 가려질 수 있으며 자동 각도를 비워 두고 현장 관찰로 확인합니다. 안 보이는 값을 추측하지 않습니다.</li>
      <li>한 장에 대상은 한 사람입니다. 촬영을 위해 동작을 멈추거나 느리게/과장되게 수행시키지 않습니다. 같은 조건의 연속된 정상 작업 3회를 기록합니다. 연사에서 개별 사진을 고를 수 있으며 동영상 입력은 없습니다.</li>
      </ol><p class="photo-dialog-note">시간 간격을 맞출 필요는 없습니다. 사건·지지 상태가 불명확하면 하중 상태를 모름으로 남깁니다. 부분 지지 사진은 교체를 권장합니다.</p>`);
  }
}
PhotoWorkspace.phases=[['CYCLE_START','손 닿기 전','하중 0kg'],['LIFT_OFF','바닥 분리 직후','상자 전체 중량'],['MID_LIFT','바닥면 절반 높이','상자 전체 중량'],['SHELF_APPROACH','선반 접촉 직전','상자 전체 중량'],['CYCLE_END','손 놓은 후','하중 0kg']];
