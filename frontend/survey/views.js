import {inputPlaceholder} from '../input-placeholders.js';
export const views={
esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); },
input(name, label, type='text', attrs='') {
    const hint=inputPlaceholder(label,type,name);
    return `<label>${label}<input data-intake="${name}" type="${type}" ${hint&&!/placeholder\s*=/.test(attrs)?`placeholder="${this.esc(hint)}"`:""} ${attrs}></label>`;
  },
render() {
    this.host.innerHTML=`
      <section class="panel intake-panel"><h2>선택 입력 · 이전 조사일</h2>
        <p>알고 있는 경우에만 입력하세요. 모르면 비워 둬도 조사를 저장할 수 있습니다.</p>
        <div class="intake-grid">${this.input('previous_survey_date','이전 조사일','date')}</div>
      </section>`;
  }
};
