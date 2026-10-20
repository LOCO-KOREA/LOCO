import {inputPlaceholder} from '../input-placeholders.js';
export const views={
esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); },
select(name, label, options) {
    return `<label>${label}<select data-intake="${name}">${options.map(([value,text])=>`<option value="${value}">${text}</option>`).join('')}</select></label>`;
  },
input(name, label, type='text', attrs='') {
    const hint=inputPlaceholder(label,type,name);
    return `<label>${label}<input data-intake="${name}" type="${type}" ${hint&&!/placeholder\s*=/.test(attrs)?`placeholder="${this.esc(hint)}"`:""} ${attrs}></label>`;
  },
render() {
    const sites=[['neck','목'],['shoulder','어깨'],['arm_elbow','팔/팔꿈치'],['hand_wrist','손/손목/손가락'],['back','허리'],['leg_foot','다리/발']];
    const regions=sites.map(([code,label])=>`<div class="symptom-region"><strong>${label}</strong>${this.select(`region-${code}-side`,'통증 방향',[['UNKNOWN','모름'],['NONE','없음'],['RIGHT','오른쪽'],['LEFT','왼쪽'],['BOTH','양쪽']])}${this.select(`region-${code}-duration`,'지속기간',[['UNKNOWN','모름'],['LT_1_DAY','1일 미만'],['DAY_TO_WEEK','1일~1주 미만'],['WEEK_TO_MONTH','1주~1개월 미만'],['MONTH_TO_6_MONTHS','1~6개월 미만'],['GE_6_MONTHS','6개월 이상']])}${this.select(`region-${code}-severity`,'통증 정도',[['UNKNOWN','모름'],['MILD','약함'],['MODERATE','중간'],['SEVERE','심함'],['VERY_SEVERE','매우 심함']])}${this.select(`region-${code}-last_week`,'지난 1주',[['UNKNOWN','모름'],['NO','아니오'],['YES','예']])}</div>`).join('');
    this.host.innerHTML=`
      <section class="panel intake-panel"><h2>조사 유형과 근거</h2>
        ${this.select('occasional_cause','수시조사 사유 유형',[['','선택'],['DISEASE_CASE','질환자 발생 또는 업무상 질병 인정'],['NEW_TASK_OR_EQUIPMENT','새 작업·설비 도입'],['WORK_ENVIRONMENT_CHANGE','작업량·공정·작업환경 변경'],['OTHER','기타']])}
        <div class="intake-grid">${this.input('previous_survey_date','이전 조사일','date')}<p class="form-note">질환자 발생 사유 수시조사에서만 고시 별지 1·2 기반 시트를 추가합니다. 다른 조사 유형은 LOCO 보조기록으로 출력합니다.</p></div>
      </section>
      <section class="panel intake-panel"><h2>작업장 상황 조사</h2><p>설비·작업량·작업속도·업무형태의 조사 시점 상태와 주요 내용을 기록합니다.</p>
        ${[['equipment','작업 설비'],['workload','작업량'],['speed','작업 속도'],['work_pattern','업무 형태']].map(([code,label])=>`<div class="situation-row"><strong>${label}</strong>${this.select(`${code}_status`,'변화 여부',[['UNKNOWN','모름'],['NO','변경 없음'],['YES','변경 있음']])}<label>관찰 내용<textarea data-intake="${code}_notes" rows="2" placeholder="${this.esc(inputPlaceholder('', 'textarea', `${code}_notes`))}"></textarea></label></div>`).join('')}
      </section>
      <section class="panel intake-panel"><h2>근로자 참여 기록</h2><p>안전보건규칙 제657조제3항에 따른 근로자대표 또는 해당 작업 근로자의 참여 여부와 의견을 기록합니다.</p>
        <div class="intake-grid">${this.select('participation_status','참여 여부',[['UNKNOWN','확인 필요'],['YES','참여함'],['NO','미참여']])}${this.select('participation_role','참여자 구분',[['UNKNOWN','확인 필요'],['WORKER_REPRESENTATIVE','근로자대표'],['AFFECTED_WORKER','해당 작업 근로자'],['BOTH','모두']])}${this.input('participant_code','참여자 코드 또는 표시명')}${this.select('participation_method','참여 방법',[['UNKNOWN','확인 필요'],['INTERVIEW','면담'],['MEETING','협의/회의'],['OBSERVATION','작업 관찰 참여'],['OTHER','기타']])}${this.input('participation_date','참여 일자','date')}</div>
        <label>문제점·개선 의견<textarea data-intake="participation_notes" rows="3" placeholder="${this.esc(inputPlaceholder('', 'textarea', `participation_notes`))}"></textarea></label>
      </section>
      <section class="panel intake-panel"><h2>근골격계 증상조사</h2><p>응답자는 이름 대신 익명 코드를 권장합니다. 이 로컬 파일에는 건강 관련 정보가 포함될 수 있으니 접근을 제한하세요. 이 설문은 진단 도구가 아닙니다.</p>
        <div class="intake-grid">${this.select('symptom_method','조사 방법',[['UNKNOWN','확인 필요'],['QUESTIONNAIRE','증상 설문'],['INTERVIEW','근로자 면담'],['OTHER','기타'],['NOT_DONE','미실시']])}${this.input('symptom_date','조사 일자','date')}${this.input('symptom_respondent_count','응답자 수','number','min="0" step="1"')}${this.input('symptom_summary','증상조사 요약')}</div>
        <details class="questionnaire-details"><summary>익명 증상 응답 입력</summary><div class="questionnaire-form">
          <div class="intake-grid">${this.input('response_code','응답 코드')}${this.input('response_name','성명 (선택)')}${this.input('response_age','연령','number','min="0" max="120"')}${this.select('response_sex','성별',[['UNKNOWN','미응답'],['MALE','남'],['FEMALE','여']])}${this.input('response_tenure','현 직장 경력 (개월)','number','min="0"')}${this.input('response_department','작업부서')}${this.input('response_job','수행 작업')}${this.input('response_current_work','현재 작업 내용')}${this.input('response_current_months','현재 작업 기간 (개월)','number','min="0"')}${this.input('response_daily_hours','1일 근무시간 (시간)','number','min="0"')}${this.input('response_rest_breaks','휴식시간 (식사시간 제외)')}${this.input('response_previous_work','이전 작업')}${this.input('response_previous_months','이전 작업 기간 (개월)','number','min="0"')}${this.input('response_leisure','여가·취미 활동')}${this.select('response_household','하루 가사노동',[['UNKNOWN','미응답'],['NONE','거의 없음'],['LT_1_HOUR','1시간 미만'],['1_TO_2_HOURS','1~2시간 미만'],['2_TO_3_HOURS','2~3시간 미만'],['GE_3_HOURS','3시간 이상']])}${this.select('response_medical','과거 진단 이력',[['UNKNOWN','미응답'],['NO','아니오'],['YES','예']])}${this.select('response_injury','과거 사고·상해',[['UNKNOWN','미응답'],['NO','아니오'],['YES','예']])}${this.select('response_burden','육체적 부담 정도',[['','미응답'],['1','전혀 힘들지 않음'],['2','견딜 만함'],['3','약간 힘듦'],['4','힘듦'],['5','매우 힘듦']])}${this.select('response_work_related','지난 1년 작업 관련 증상',[['UNKNOWN','미응답'],['NO','아니오'],['YES','예']])}</div>
          <label>과거 상해 부위 (쉼표로 구분)<input data-intake="response_injury_sites" placeholder="${this.esc(inputPlaceholder('', 'text', 'response_injury_sites'))}"></label>
          <div class="symptom-regions">${regions}</div><button type="button" data-add-response>응답 추가 · 현재 입력 저장</button>
        </div></details>
        <div id="symptom-response-list"></div>
      </section>`;
  },
renderResponses() {
    const list=this.host.querySelector('#symptom-response-list');if(!list)return;
    list.innerHTML=this.responses.map((response,index)=>`<article class="symptom-response"><strong>${this.esc(response.response_code||`익명-${index+1}`)}</strong><span>${this.esc(response.work_related_symptoms_last_year==='YES'?'지난 1년 작업 관련 증상 있음':response.work_related_symptoms_last_year==='NO'?'지난 1년 작업 관련 증상 없음':'증상 여부 미응답')} · 응답은 개별 진단이 아닙니다.</span><button type="button" data-remove-response="${index}">응답 삭제</button></article>`).join('')||'<p class="form-note">아직 추가된 응답이 없습니다. 외부에서 실시한 증상조사는 방법·응답 수·요약만 기록해도 됩니다.</p>';
  }
};
