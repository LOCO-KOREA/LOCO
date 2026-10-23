// Only the bootstrap method is fixed here. All further methods and policies come from the service contract.
import {renderSummary, renderQuestions} from './view.js';
import {renderDialog, mountDialog} from './dialog.js';
export const INTAKE_CONTRACT_METHOD = 'intake_contract';

export class AdaptiveIntake {
  constructor({api, changed, notify}) { Object.assign(this, {api, changed, notify}); this.reset(); }
  reset() { for (const timer of this.timers?.values() || []) clearTimeout(timer.id); this.timers = new Map(); this.generation = (this.generation || 0) + 1; this.state = null; this.questions = []; this.text = ''; this.writingFor = null; this.pairValues = new Map(); this.focusPair = null; this.busyElapsedSeconds = 0; this.reviewThreshold = null; this.formStage = 0; this.formValues = new Map(); this.editing = null; this.dialogOpen = false; this.values = new Map(); this.saving = false; this.saveError = ''; this.saveErrorKind = null; this.serial = Promise.resolve(); }
  async loadContract() { return this.contract ||= await this.api(INTAKE_CONTRACT_METHOD, {}); }
  hasSession(task) { return Boolean(task.conditions?.[this.contract?.session_key]); }
  async open(taskId, views) {
    const generation = ++this.generation;
    const contract = await this.loadContract();
    const result = await this.api(contract.methods.session, {task_id: taskId, ...(views === undefined ? {} : {views})});
    if (generation !== this.generation) return null;
    this.state = result; this.questions = result.questions; this.values.clear(); this.pairValues.clear(); this.focusPair = null; return result;
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
  formFields(stage=this.formStage) {
    return (this.state?.form_fields||[]).filter(f => (f.destination.type==='work_type') === (stage===0));
  }
  formValue(field) {
    if(this.formValues.has(field.identity))return this.formValues.get(field.identity);
    const saved=this.state.facts.find(f=>f.identity===field.identity);
    return saved?.state==='KNOWN'?saved.value:undefined;
  }
  formAnswers() {
    return this.formFields().filter(f=>this.formValues.has(f.identity)).map(f=>({target:f.target,condition:f.condition,value:this.formValues.get(f.identity)}));
  }
  reviewCount() {
    const userFacts=(this.state?.facts||[]).filter(f=>f.source==='USER'&&['KNOWN','UNKNOWN'].includes(f.state)).length;
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
    const field = this.state?.contract.fields.find(f => f.target === fact?.target);
    return field && {...field, identity, condition: fact.condition};
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
    this.values.set(identity, value);
    const result = await this.turn('', [{target: field.target, condition: field.condition, value}], false);
    if (result) this.changed();
  }
  schedule(identity, value, onError) {
    this.values.set(identity,value); clearTimeout(this.timers.get(identity)?.id);
    const id=setTimeout(() => this.answer(identity,value).catch(onError), 500);
    this.timers.set(identity,{id,value});
  }
  async flush() { for (const [identity,timer] of [...this.timers]) await this.answer(identity,timer.value); await this.serial; if (this.saveError && this.saveErrorKind !== 'reply') throw Error(this.saveError); }
  summary() { return renderSummary(this); }
  panel(busy) { return renderQuestions(this, busy); }
  dialog(busy) { return renderDialog(this,busy); }
  mount(host,busy) { mountDialog(host,busy,this.focusPair); }
}
