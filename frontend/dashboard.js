// S01 layout: docs/ui/01_대시보드.svg. Counts use persisted SurveySummary data.
class DashboardWorkspace {
  constructor({api, onOpen, onNew, onList, onError}) {
    Object.assign(this, {api, onOpen, onNew, onList, onError});
    this.host = document.querySelector('#dashboard-workspace');
    this.revision = 0;
    this.host.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button) return;
      if (button.dataset.dashboard === 'new') onNew();
      else if (button.dataset.dashboard === 'list') onList();
      else if (button.dataset.survey) onOpen(Number(button.dataset.survey), button.dataset.task ? Number(button.dataset.task) : null);
    });
  }
  async open(surveys, selected) {
    const revision = ++this.revision;
    const recent = [...surveys].sort((a,b) => (b.survey_date || '').localeCompare(a.survey_date || '') || b.survey_id-a.survey_id);
    const survey = recent.find(item => item.survey_id === selected) || recent[0];
    this.render(recent, survey);
    if (!survey) return;
    try {
      const [detail, tasks] = await Promise.all([
        this.api('get_survey', {survey_id:survey.survey_id}),
        this.api('list_tasks', {survey_id:survey.survey_id})
      ]);
      if (revision === this.revision) this.render(recent, survey, detail, tasks);
    } catch (error) { if (revision === this.revision) this.onError(error); }
  }
  badge(survey) {
    const kind = survey.review_current ? 'current' : survey.reviewed ? 'history' : 'none';
    return `<span class="badge ${kind}">${survey.review_current ? '검토 완료' : survey.reviewed ? '이전 결과 검토' : '미검토'}</span>`;
  }
  render(recent, survey, detail, tasks) {
    const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const task = tasks?.[0];
    const counts = [
      ['등록된 조사', recent.length, '조사 단위'],
      ['등록된 상자 올리기 작업', recent.reduce((sum,s)=>sum+s.task_count,0), '작업 단위'],
      ['미검토 조사', recent.filter(s=>!s.reviewed).length, '계산 완전성과 별도 표시'],
      ['이전 결과를 검토한 조사', recent.filter(s=>s.reviewed&&!s.review_current).length, '현재 입력으로 다시 확인 가능']
    ];
    this.host.innerHTML = `
      <div class="dashboard-actions"><button class="primary" data-dashboard="new">＋ 새 조사</button></div>
      <div class="dashboard-stats">${counts.map(([label,value,note])=>`<section class="panel"><h2>${label}</h2><div><strong>${window.loco ? value : '—'}</strong><span>${note}</span></div></section>`).join('')}</div>
      <h2 class="dashboard-heading">이어 할 조사</h2>
      <div class="dashboard-columns">
        <section class="panel dashboard-continue">
          <div class="dashboard-card-heading"><h2>${e(survey?.title || (survey ? '제목 없는 조사' : '새 조사를 시작해 보세요'))}</h2>${survey ? this.badge(survey) : ''}</div>
          <p>${survey ? `조사일 ${e(survey.survey_date || '미입력')} · 조사자 ${e(detail ? detail.investigator || '미입력' : '불러오는 중…')} · 단위작업 ${survey.task_count}개` : window.loco ? '아직 저장된 조사가 없습니다. 현장과 작업 정보를 기록해 주세요.' : 'Electron 앱에서 저장된 조사와 작업 현황을 확인할 수 있습니다.'}</p>
          <div class="dashboard-result"><strong>${survey ? '조사 개요와 작업 입력을 이어서 작성하세요.' : '조사 개요 → 작업 정보 → 사진 등록'}</strong><span>분석 결과 연결 예정</span></div>
          <p class="dashboard-note">검토 표시는 입력·계산의 완전성과 별개입니다.</p>
          <div class="dashboard-card-actions">${survey ? `<button class="dark" data-survey="${survey.survey_id}">조사 이어가기 →</button>` : '<button class="dark" data-dashboard="new">첫 조사 만들기 →</button>'}</div>
        </section>
        <section class="panel dashboard-next">
          <h2>다음에 확인할 단위작업</h2>
          <h3>${e(task ? task.task_name || '이름 없는 작업' : survey ? tasks ? '등록된 작업이 없습니다' : '작업 불러오는 중…' : '조사를 먼저 등록하세요')}</h3>
          <p>${task ? `사진 배정 ${task.capture.slots.filter(slot=>slot.photo_id!==null).length} / 15 · 작업 조건과 하루 노출시간을 확인하세요.` : '작업별 조건과 하루 누적시간을 직접 입력합니다.'}</p>
          <p class="dashboard-note">사진 비율로 하루 노출시간을 계산하지 않습니다.</p>
          ${task ? `<button class="primary" data-survey="${survey.survey_id}" data-task="${task.task_id}">직접 입력 열기 →</button>` : '<button class="primary" data-dashboard="list">조사 개요 열기 →</button>'}
        </section>
        <section class="panel dashboard-recent">
          <div class="dashboard-card-heading"><h2>최근 조사</h2><button class="text-button" data-dashboard="list">전체 보기 →</button></div>
          <div class="table-wrap"><table><thead><tr><th>조사명</th><th>조사일</th><th>단위작업</th><th>상태</th></tr></thead><tbody>${recent.slice(0,3).map(s=>`<tr><td><button class="row-button" data-survey="${s.survey_id}"><strong>${e(s.title || '제목 없는 조사')}</strong></button></td><td>${e(s.survey_date || '미입력')}</td><td>${s.task_count}</td><td>${this.badge(s)}</td></tr>`).join('') || `<tr><td colspan="4" class="empty">${window.loco ? '등록된 조사가 없습니다.' : '브라우저 미리보기 · 실제 목록은 Electron에서 표시됩니다.'}</td></tr>`}</tbody></table></div>
        </section>
        <section class="panel dashboard-guide"><h2>작업 자세 분석 안내</h2><ol><li>조사 개요와 작업 조건을 기록합니다.</li><li>같은 조건의 정상 작업 3회에서 사진 15장을 배정합니다.</li><li>분석 결과와 조사자 검토 상태를 구분해 확인합니다.</li></ol><p>모르는 값은 비워 두고 이어서 작성할 수 있습니다.</p></section>
      </div>`;
  }
}
