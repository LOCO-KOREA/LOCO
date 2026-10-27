import {inputPlaceholder} from '../input-placeholders.js';
export const views={
esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); },
input(name, label, type='text', attrs='') {
    const hint=inputPlaceholder(label,type,name);
    return `<label>${label}<input data-intake="${name}" type="${type}" ${hint&&!/placeholder\s*=/.test(attrs)?`placeholder="${this.esc(hint)}"`:""} ${attrs}></label>`;
  },
render() {
    this.host.innerHTML=`
      <section class="panel intake-panel"><h2>이전 조사</h2>
        <div class="intake-grid">${this.input('previous_survey_date','이전 조사일','date')}</div>
      </section>`;
  }
};
