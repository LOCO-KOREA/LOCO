// Only the bootstrap method is fixed here. All further methods and policies come from the service contract.
import {renderSummary, renderQuestions} from './view.js';
import {renderDialog, mountDialog} from './dialog.js';
import {DRAFT_POLICY,intakeDraftKey} from '../drafts.js';
export const INTAKE_CONTRACT_METHOD = 'intake_contract';
// Quote of every box "확인 끝" fills. Such a fill says "does not apply" for a box nobody answered, so it is sent after a typed sentence and never beats a value somebody else saved.
export const CHECKLIST_CONFIRM_QUOTE = '자세 체크리스트에서 체크하지 않은 항목을 해당 없음으로 직접 확인';
// Quote of every work feature "나머지 작업은 모두 안 해요" fills with "no".
export const ABSENT_WORK_QUOTE = '표시된 남은 작업은 하지 않는다고 직접 확인';

export class AdaptiveIntake {
  constructor({api, changed, notify,drafts=null}) { Object.assign(this, {api, changed, notify,drafts}); this.reset(); }
  reset() { for (const timer of this.timers?.values() || []) clearTimeout(timer.id); this.timers = new Map(); this.pending=new Map(); this.pendingConflicts=new Set(); this.pendingVersion=0; this.generation = (this.generation || 0) + 1; this.state = null; this.questions = []; this.text = ''; this.writingFor = null; this.pairValues = new Map(); this.focusPair = null; this.busyElapsedSeconds = 0; this.reviewThreshold = null; this.pageShown = false; this.formValues = new Map(); this.editing = null; this.dialogOpen = false; this.values = new Map(); this.saving = false; this.saveError = ''; this.saveErrorKind = null; this.serial = Promise.resolve(); this.fillNote = ''; }
  persistPending(){if(this.drafts&&this.state)this.drafts.put('intake',intakeDraftKey(this.state.task),{taskId:this.state.task.task_id,createdAt:this.state.task.created_at,entries:[...this.pending]});}
  pendingValue(identity,value){const field=this.field(identity);if(!field)return;const old=this.pending.get(identity);this.pending.set(identity,{value,target:field.target,condition:field.condition,base:old?old.base:this.state.facts.find(f=>f.identity===identity)?.value??null,version:++this.pendingVersion});this.values.set(identity,value);this.persistPending();}
  async restorePending(){
    const saved=this.drafts?.get('intake',intakeDraftKey(this.state.task));
    if(!saved||saved.createdAt!==this.state.task.created_at)return;
    const recover=[];
    for(const [identity,item] of saved.entries||[]){const field=this.state.contract.fields.find(f=>f.target===item.target);const current=this.state.facts.find(f=>f.identity===identity)?.value??null;if(field&&current===item.value)continue;this.pending.set(identity,{...item,version:++this.pendingVersion});this.values.set(identity,item.value);if(!field||current!==item.base)this.pendingConflicts.add(identity);else recover.push([identity,item.value]);}
    this.persistPending();
    for(const [identity,value] of recover)try{await this.answer(identity,value);}catch{break;}
  }
  saveStatus(){return this.saveError||this.drafts?.error?'입력을 저장하지 못했어요. 입력한 내용은 유지되니 다시 시도해 주세요.':this.pendingConflicts.size?'다른 화면에서 값이 바뀌었어요. 임시 수정값을 확인해 주세요.':this.saving?'입력을 저장하고 있어요…':this.pending.size?'수정값을 이 PC에 임시 저장했어요. 작업 기록에 저장 중이에요…':'입력과 출처를 이 작업에 저장했어요.';}

  async loadContract() { return this.contract ||= await this.api(INTAKE_CONTRACT_METHOD, {}); }
  hasSession(task) { return Boolean(task.conditions?.[this.contract?.session_key]); }
  async open(taskId, views) {
    this.reset();
    const generation = ++this.generation;
    const contract = await this.loadContract();
    const result = await this.api(contract.methods.session, {task_id: taskId, ...(views === undefined ? {} : {views})});
    if (generation !== this.generation) return null;
    this.state = result; this.questions = result.questions; this.values.clear(); this.pairValues.clear(); this.focusPair = null; await this.restorePending(); return this.state;
  }
  async turn(text = '', answers = [], plan = true) {
    const generation = this.generation, taskId = this.state?.task.task_id;
    if (!taskId) return null;
    const operation = async () => {
      if (generation !== this.generation) return null;
      this.saving = true; this.saveError = ''; this.saveErrorKind = null;
      if (plan && text) this.text=text;
      try {
        const state = this.state;
        const result = await this.api(state.contract.methods.turn, {task_id: taskId, text, answers, plan,
          task_created_at: state.task.created_at,
          expected_revision: state.task.input_revision, focus: this.answerFields().map(q => ({target: q.target, condition: q.condition}))});
        if (generation !== this.generation) return null;
        this.state = result;
        this.dropAnsweredConfirmations();
        if (plan) {
          this.questions = result.questions;
          if (!result.reason) {
            // Structured saves must keep a separate, unsent natural-language draft.
            if (!this.text.trim() || this.text === text) { this.text = ''; this.writingFor = null; }
            this.pairValues.clear(); this.focusPair = null;
          }
          else {
            const current = new Set(this.questions.flatMap(q => [q, ...this.answerFields(q)]).map(q => q.identity));
            for (const identity of this.pairValues.keys()) if (!current.has(identity)) this.pairValues.delete(identity);
            if (!current.has(this.focusPair)) this.focusPair = null;
          }
          this.values.clear(); this.editing = null;
        }
        if (result.reason === 'INPUT_CHANGED') this.notify('다른 화면에서 바뀐 최신 입력을 불러왔어요. 새 답변을 다시 확인해 주세요.');
        return result;
      } catch (error) { if (generation === this.generation) { this.saveError = error.message; this.saveErrorKind = plan ? 'reply' : 'autosave'; } throw error; }
      finally { if (generation === this.generation) this.saving = false; }
    };
    const request = this.serial.then(operation, operation);
    this.serial = request.catch(() => {});
    return request;
  }
  // One page: work features, conditions, photo questions and the posture checklist are one list. (The old stage argument is ignored.)
  formFields() {
    return this.state?.form_fields||[];
  }
  formHandled(field) {
    if(field.photo_unused)return false;
    const saved=this.state?.facts.find(f=>f.identity===field.identity);
    return saved?.state==='KNOWN'||saved?.state==='UNKNOWN'&&saved.source==='USER'||
      field.destination.type==='manual'&&saved?.state==='ESTIMATED'&&saved.value!=null&&['POSE','MOVENET','VISION'].includes(saved.source);
  }
  optionalPhoto(field) {
    return (this.state?.contract.policy.optional_photo_destinations||['manual','view']).includes(field.destination.type);
  }
  pendingFormFields(_stage,{includePhoto=false}={}) {
    return this.formFields().filter(field=>!this.formHandled(field)&&(includePhoto||!this.optionalPhoto(field)));
  }
  /** Something on the page still waits for an answer, photo questions included: the page is worth opening. */
  hasOpenItems() { return this.pendingFormFields(undefined,{includePhoto:true}).some(field=>field.destination.type!=='manual'); }
  /** The page opens by itself at most once per analysis: only while nothing was shown yet and something is open. */
  openPageOnce() {
    if(this.pageShown||!this.hasOpenItems())return false;
    this.pageShown=true; this.dialogOpen=true; return true;
  }
  /** A restored draft opens the page only if it had not been shown yet. */
  restorePage(shown) {
    this.pageShown=Boolean(shown);
    if(Array.isArray(this.state?.form_fields))this.openPageOnce(); else this.dialogOpen=Boolean(this.state?.questions?.length);
  }
  /** The user opens the page by pressing a button. */
  showPage() { this.pageShown=true; this.dialogOpen=true; }
  /** The user leaves the page (closed or saved): nothing opens it again by itself. */
  closePage() { this.pageShown=true; this.dialogOpen=false; this.fillNote=''; }
  /** An answer that decides which other fields exist: a work feature (its conditions) or the photo situation (the photo rows). */
  isGate(field) { return field.target==='context'||String(field.target).startsWith('work_type.'); }
  /** Does this answer change which fields are on the page? A "no" for a work feature whose conditions are not shown changes nothing, so it waits for the final save like any other answer. */
  changesFields(field,value) {
    if(!this.isGate(field))return false;
    if(field.target==='context')return true;
    const gate=String(field.target).slice('work_type.'.length);
    return value==='YES'||this.formFields().some(f=>f.gate===gate);
  }
  formValue(field) {
    if(this.formValues.has(field.identity))return this.formValues.get(field.identity);
    const saved=this.state.facts.find(f=>f.identity===field.identity);
    return this.formHandled(field)&&saved?.value!=null&&!field.photo_unused?saved.value:undefined;
  }
  formAnswers() {
    return this.formFields().filter(f=>this.formValues.has(f.identity)).map(f=>({target:f.target,condition:f.condition,value:this.formValues.get(f.identity),
      ...(this.formValues.has('quote:'+f.identity)?{quote:this.formValues.get('quote:'+f.identity)}:{})}));
  }
  /** A fill that says "does not apply" for boxes nobody answered ("확인 끝", "나머지 작업은 모두 안 해요"): it must never beat what a typed sentence says. */
  isBulkAnswer(answer) { return answer.quote===CHECKLIST_CONFIRM_QUOTE||answer.quote===ABSENT_WORK_QUOTE; }
  /** The form answers split into what may travel with a typed sentence and the bulk fills that must follow it. */
  splitFormAnswers(answers=this.formAnswers()) {
    return {direct:answers.filter(a=>!this.isBulkAnswer(a)),confirmed:answers.filter(a=>this.isBulkAnswer(a))};
  }
  /** The fills that still decide something: a box the sentence, the photo or the user answered in the meantime is not blank any more. */
  stillBlank(confirmed) {
    const fields=this.state?.form_fields||[];
    return confirmed.filter(a=>{const field=fields.find(f=>f.identity===a.target+'@'+a.condition);return field&&!this.formHandled(field);});
  }
  /** A saved "does not apply" fill for a box that has an answer now is only a stale draft: the saved value is shown and stays. */
  dropAnsweredConfirmations() {
    for(const field of this.state?.form_fields||[]) {
      const quote=this.formValues.get('quote:'+field.identity);
      if((quote===CHECKLIST_CONFIRM_QUOTE||quote===ABSENT_WORK_QUOTE)&&this.formHandled(field))this.clearFormValue(field.identity);
    }
  }
  // A value picked by a shortcut says how it was chosen; any later edit makes it the user's own answer again.
  // shortcut: the quote rides in formValues as 'quote:<identity>' so the saved form draft keeps it without touching four serializers.
  setFormValue(identity,value,quote) {
    this.formValues.set(identity,value);
    if(quote)this.formValues.set('quote:'+identity,quote);else this.formValues.delete('quote:'+identity);
  }
  clearFormValue(identity) { this.formValues.delete(identity); this.formValues.delete('quote:'+identity); }
  savedState(field) { return this.state?.facts.find(f=>f.identity===field.identity)?.state; }
  /** The sentence a bulk "does not apply" answer carries as its quote. A copy may replace such a value, never a real choice. */
  static CONFIRM_QUOTE=CHECKLIST_CONFIRM_QUOTE;
  /** A yes/no posture row the checklist can hold. A photo estimate or a conflict needs its own decision, so those stay ordinary boxes. */
  checkable(field) { return Boolean(field.checklist)&&!['ESTIMATED','CONFLICT'].includes(this.savedState(field)); }
  /** The user already set this row in the form: a value, or an explicit "don't know" (the blank choice is an answer too). */
  explicit(field) { return this.formValues.has(field.identity); }
  /** A value the checklist confirmation wrote in bulk, not a choice the user made for this row. */
  bulk(field) { return this.formValues.get('quote:'+field.identity)===AdaptiveIntake.CONFIRM_QUOTE; }
  /** A box with no answer: not saved as the user's own answer, no value in the form, and no estimate or conflict that asks for a decision. */
  unanswered(field) {
    return !this.formHandled(field)&&this.formValue(field)==null&&!['ESTIMATED','CONFLICT'].includes(this.savedState(field));
  }
  /** A box a bulk helper (the confirmation, a copy) may fill: unanswered, and not set by the user to "don't know" either. A press on one row's own suggestion may still answer it. */
  fillable(field) { return this.unanswered(field)&&!this.explicit(field); }
  /** A box a copy may write to: a fillable one, or one the checklist confirmation filled in bulk (so the order of the two buttons does not matter). */
  copyTarget(field) {
    return this.fillable(field)||this.bulk(field)&&!this.formHandled(field)&&!['ESTIMATED','CONFLICT'].includes(this.savedState(field));
  }
  /** What a copy takes from a row: a saved or chosen value; never a bulk "does not apply", an estimate or a "don't know". */
  copySource(field) { return this.bulk(field)?null:this.formValue(field); }
  /** The checklist boxes of one photo that are still empty (neither ticked nor answered). */
  checklistRows(condition) { return this.formFields().filter(f=>f.condition===condition&&this.checkable(f)&&!this.formHandled(f)&&this.formValue(f)==null); }
  checklistOpen(condition) { return this.checklistRows(condition).length; }
  /** Yes/no rows a photo estimate or a conflict moved out of the checklist; they are decided one by one below it. */
  checklistUndecided(condition) { return this.formFields().filter(f=>f.checklist&&f.condition===condition&&!this.checkable(f)&&!this.formHandled(f)&&!this.explicit(f)&&this.formValue(f)==null).length; }
  /** The sentence that tells the user what is still open. A box that shows a front-photo reading is never counted as "does not apply". */
  checklistStatus(condition) {
    const rows=this.checklistRows(condition), asked=rows.filter(f=>f.suggestion).length, plain=rows.length-asked, pick=this.checklistUndecided(condition), parts=[];
    if(plain)parts.push(`체크하지 않은 ${plain}개는 아직 비어 있어요. 해당 없으면 위 버튼을 눌러 주세요.`);
    if(asked)parts.push(`사진이 본 ${asked}개는 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요.`);
    if(pick)parts.push(`사진 추정·충돌 ${pick}개는 아래에서 직접 골라 주세요.`);
    return parts.length?parts.join(' '):'입력·사진 분석값을 채웠어요. 결과 설명에서 수정할 수 있어요.';
  }
  /** The user refused the photo (or never confirmed it): its measurements are not in use, so none of them is "already reflected". */
  photoUnused(condition) {
    const context=(this.state?.facts||[]).find(f=>f.target==='context');
    return this.formFields().some(f=>f.condition===condition&&f.photo_unused)||Boolean(context&&context.value!=='YES');
  }
  /** How many posture values the photo itself already measured for one photo; they are in use and are not asked. */
  measuredCount(condition) {
    if(this.photoUnused(condition))return 0;
    return (this.state?.facts||[]).filter(f=>f.target.startsWith('manual.')&&f.condition===condition&&f.state==='KNOWN'&&['POSE','MOVENET'].includes(f.source)&&f.photo_active!==false&&!f.alias_of).length;
  }
  /** The boxes a shortcut press would fill: only unanswered ones, never an answer the user already gave. */
  fillPlan({kind,condition,side,identity}) {
    const fields=this.formFields(), manual=(f,scope)=>f.destination.type==='manual'&&f.destination.scope===scope&&f.condition===condition;
    // A box that still shows a front-photo reading waits for the user's yes or no; the bulk confirmation leaves it alone.
    if(kind==='no-work')return fields.filter(f=>f.destination.type==='work_type'&&this.fillable(f)).map(f=>({field:f,value:'NO',quote:ABSENT_WORK_QUOTE}));
    if(kind==='confirm')return fields.filter(f=>f.checklist&&f.condition===condition&&this.fillable(f)&&!f.suggestion).map(f=>({field:f,value:f.checklist.no,quote:AdaptiveIntake.CONFIRM_QUOTE}));
    if(kind==='mirror') {
      const name={LEFT:'왼쪽',RIGHT:'오른쪽'}, from=side==='LEFT'?'RIGHT':'LEFT';
      return fields.filter(f=>manual(f,side)&&this.copyTarget(f)).flatMap(f=>{
        const other=fields.find(g=>manual(g,from)&&g.destination.field===f.destination.field), value=other&&this.copySource(other);
        return value==null?[]:[{field:f,value,quote:`${name[side]}은 ${name[from]}과 같다고 직접 선택 (선택한 때의 값)`}];
      });
    }
    const field=fields.find(f=>f.identity===identity), reading=field?.suggestion;
    if(kind==='decline')return reading&&field.checklist&&this.unanswered(field)?[{field,value:field.checklist.no,quote:`${reading.photo_label}에서 읽은 값(${reading.quote})은 아니라고 직접 선택`}]:[];
    return kind==='suggest'&&reading&&this.unanswered(field)?[{field,value:reading.value,quote:`${reading.photo_label}에서 ${reading.estimated?'추정한':'읽은'} 값(${reading.quote})을 확인해 직접 선택`}]:[];
  }
  /** Why a copy has nothing to do right now: the other side has no value yet, or everything it has was already copied. */
  mirrorHint({side,condition}) {
    const from=side==='LEFT'?'RIGHT':'LEFT', name={LEFT:'왼쪽',RIGHT:'오른쪽'};
    const sources=this.formFields().filter(g=>g.destination.type==='manual'&&g.destination.scope===from&&g.condition===condition&&this.copySource(g)!=null).length;
    return sources?'복사할 값이 더 없어요.':`${name[from]} 값을 먼저 정해 주세요.`;
  }
  /** The hint of a dimmed button (empty while the press would still fill something). */
  fillHint(spec) { return spec.kind==='mirror'&&!this.fillPlan(spec).length?this.mirrorHint(spec):''; }
  /** The sentence shown inside the dialog after a shortcut press; an empty press says why nothing happened. */
  fillMessage(spec,plan) {
    const waiting=spec.kind==='confirm'?this.checklistRows(spec.condition).filter(f=>f.suggestion).length:0;
    if(!plan.length) {
      if(spec.kind==='mirror')return this.mirrorHint(spec).replace(/^(왼쪽|오른쪽) 값/,'반대쪽 값');
      if(spec.kind==='no-work')return '아직 고르지 않은 작업이 없어요.';
      if(spec.kind==='confirm')return waiting?`사진이 본 ${waiting}개는 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요.`:'체크하지 않은 항목이 없어서 채울 칸이 없어요.';
      return '채울 수 있는 값이 없어요.';
    }
    return `${plan.length}개 항목을 채웠어요. 저장하면 반영돼요. 다르면 직접 고쳐 주세요.${waiting?` 사진이 본 ${waiting}개는 비워 뒀어요. 위에서 ‘맞아요, 체크’나 ‘아니에요’를 눌러 주세요.`:''}`;
  }
  /** Copy buttons for one section's unanswered rows. Each press is a fillPlan; a button with nothing to copy yet is shown dimmed with its hint. */
  shortcuts(rows) {
    const fields=this.formFields(), result=[];
    for(const condition of new Set(rows.filter(f=>f.destination.type==='manual').map(f=>f.condition))) {
      const here=rows.filter(f=>f.condition===condition);
      for(const side of ['LEFT','RIGHT']) {
        const from=side==='LEFT'?'RIGHT':'LEFT';
        // Offer a copy only when the other side is on the form: either already filled or still waiting for its own answer.
        if(here.some(f=>f.destination.scope===side&&this.copyTarget(f)&&fields.some(g=>g.destination.type==='manual'&&g.destination.scope===from&&g.condition===condition&&g.destination.field===f.destination.field&&(!this.formHandled(g)||this.formValue(g)!=null))))
          result.push({label:`${side==='LEFT'?'왼쪽':'오른쪽'} 팔·손목은 ${from==='LEFT'?'왼쪽':'오른쪽'}과 같아요`,data:{kind:'mirror',side,condition}});
      }
    }
    return result.map(shortcut=>{const count=this.fillPlan(shortcut.data).length;return {...shortcut,count,hint:count?'':this.mirrorHint(shortcut.data)};});
  }
  reviewCount() {
    const userFacts=(this.state?.facts||[]).filter(f=>!f.alias_of&&f.photo_active!==false&&f.source==='USER'&&['KNOWN','UNKNOWN'].includes(f.state)).length;
    return Math.max(userFacts,this.state?.messages?.length||0);
  }
  reviewInterval() {
    const value=this.state?.contract.policy.quick_review_interval;
    return Number.isSafeInteger(value)&&value>0?value:5;
  }
  shouldReview() {
    return Boolean(this.questions.length&&!this.text.trim()&&!this.saveError&&this.reviewCount()>=(this.reviewThreshold??this.reviewInterval()));
  }
  continueQuestions() { this.reviewThreshold=this.reviewCount()+this.reviewInterval(); }
  numericAnswer(text) {
    const q=this.questions[0];
    if(!q||q.kind!=='number'||q.answer_questions?.length||q.paired_question)return null;
    const match=String(text).trim().match(/^(\d+(?:\.\d+)?)\s*([^\d\s]*)$/);
    if(!match)return null;
    const value=Number(match[1]),suffix=match[2],unit=q.unit||'';
    const allowed=unit.startsWith('회')?['번','회']:unit==='kg'?['kg','킬로그램']:unit.startsWith('분')?['분']:unit==='일'?['일']:unit==='개월'?['개월']:[];
    if(suffix&&!allowed.includes(suffix)||!Number.isFinite(value)||q.maximum!=null&&value>q.maximum)return null;
    return {target:q.target,condition:q.condition,value};
  }
  answerFields(question = this.questions[0]) {
    const members = Array.isArray(question?.answer_questions) && question.answer_questions.length
      ? question.answer_questions : [question, question?.paired_question];
    const seen = new Set();
    return members.filter(field => field && typeof field.identity === 'string' && field.identity && !seen.has(field.identity) && seen.add(field.identity));
  }
  selectGroupValue(identity, raw) {
    const field = this.answerFields().find(field => field.identity === identity);
    if (!field) return false;
    if (raw === '__unselected__') this.pairValues.delete(identity);
    else if (raw === '__unknown__') this.pairValues.set(identity, null);
    else {
      const choice = field.choices?.find(choice => String(choice.value) === raw);
      if (!choice) return false;
      this.pairValues.set(identity, choice.value);
    }
    this.focusPair = identity;
    return true;
  }
  selectedAnswers(question = this.questions[0]) {
    return this.answerFields(question).filter(field => this.pairValues.has(field.identity))
      .map(field => ({target: field.target, condition: field.condition, value: this.pairValues.get(field.identity)}));
  }
  field(identity) {
    const question = this.questions.flatMap(q => [q, ...this.answerFields(q)]).find(q => q.identity === identity);
    if (question) return question;
    const fact = this.state?.facts.find(f => f.identity === identity);
    const pending=this.pending.get(identity),field = this.state?.contract.fields.find(f => f.target === (fact?.target||pending?.target));
    return field && {...field, identity, condition: fact?.condition||pending.condition};
  }
  value(identity) { return this.values.has(identity) ? this.values.get(identity) : this.state?.facts.find(f => f.identity === identity)?.value; }
  parseValue(identity, raw) {
    const field = this.field(identity);
    if (raw.trim() === '') return null;
    return field.kind === 'number' ? Number(raw) : field.kind === 'choice' ? field.choices.find(c => String(c.value) === raw)?.value : raw;
  }
  async answer(identity, value) {
    clearTimeout(this.timers.get(identity)?.id); this.timers.delete(identity);
    const field = this.field(identity); if (!field) return;
    this.pendingValue(identity,value);this.pendingConflicts.delete(identity);const version=this.pending.get(identity)?.version;
    const result = await this.turn('', [{target: field.target, condition: field.condition, value}], false);
    if(result?.reason==='INPUT_CHANGED'){this.pendingConflicts.add(identity);this.persistPending();}
    else if (result&&this.pending.get(identity)?.version===version){this.pending.delete(identity);this.values.delete(identity);this.persistPending();}
    else if(result&&this.pending.has(identity)){this.pending.get(identity).base=result.facts.find(f=>f.identity===identity)?.value??null;this.persistPending();}
    if (result) this.changed();
  }
  schedule(identity, value, onError) {
    this.pendingValue(identity,value); clearTimeout(this.timers.get(identity)?.id);this.changed();
    const id=setTimeout(() => this.answer(identity,value).catch(onError), this.state?.contract.policy.autosave_delay_ms??DRAFT_POLICY.autosaveDelayMs);
    this.timers.set(identity,{id,value});
  }
  async flush() { if(this.pendingConflicts.size)throw Error('다른 화면에서 바뀐 값이 있어요. 임시 수정값을 확인해 주세요.');for (const [identity,timer] of [...this.timers]) await this.answer(identity,timer.value);await this.serial;if (this.saveError && this.saveErrorKind !== 'reply') throw Error(this.saveError);for(const [identity,item] of [...this.pending])await this.answer(identity,item.value);if (this.saveError && this.saveErrorKind !== 'reply') throw Error(this.saveError); }
  summary() { return renderSummary(this); }
  panel(busy) { return renderQuestions(this, busy); }
  dialog(busy) { return renderDialog(this,busy); }
  mount(host,busy) { mountDialog(host,busy,this.focusPair); }
}
