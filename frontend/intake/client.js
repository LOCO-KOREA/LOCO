// Only the bootstrap method is fixed here. All further methods and policies come from the service contract.
import {renderSummary, renderQuestions} from './view.js';
export const INTAKE_CONTRACT_METHOD = 'intake_contract';

export class AdaptiveIntake {
  constructor({api, changed, notify}) { Object.assign(this, {api, changed, notify}); this.reset(); }
  reset() { for (const timer of this.timers?.values() || []) clearTimeout(timer.id); this.timers = new Map(); this.generation = (this.generation || 0) + 1; this.state = null; this.questions = []; this.text = ''; this.editing = null; this.values = new Map(); this.saving = false; this.saveError = ''; this.serial = Promise.resolve(); }
  async loadContract() { return this.contract ||= await this.api(INTAKE_CONTRACT_METHOD, {}); }
  hasSession(task) { return Boolean(task.conditions?.[this.contract?.session_key]); }
  async open(taskId, views) {
    const generation = ++this.generation;
    const contract = await this.loadContract();
    const result = await this.api(contract.methods.session, {task_id: taskId, ...(views === undefined ? {} : {views})});
    if (generation !== this.generation) return null;
    this.state = result; this.questions = result.questions; this.values.clear(); return result;
  }
  async turn(text = '', answers = [], plan = true) {
    const generation = this.generation, taskId = this.state?.task.task_id;
    if (!taskId) return null;
    const operation = async () => {
      if (generation !== this.generation) return null;
      this.saving = true; this.saveError = '';
      try {
        const state = this.state;
        const result = await this.api(state.contract.methods.turn, {task_id: taskId, text, answers, plan,
          task_created_at: state.task.created_at,
          expected_revision: state.task.input_revision, focus: this.questions.map(q => ({target: q.target, condition: q.condition}))});
        if (generation !== this.generation) return null;
        this.state = result;
        if (plan) { this.questions = result.questions; this.text = ''; this.values.clear(); this.editing = null; }
        if (result.reason === 'INPUT_CHANGED') this.notify('다른 화면에서 바뀐 최신 입력을 불러왔어요. 새 답변을 다시 확인해 주세요.');
        return result;
      } catch (error) { if (generation === this.generation) this.saveError = error.message; throw error; }
      finally { if (generation === this.generation) this.saving = false; }
    };
    const request = this.serial.then(operation, operation);
    this.serial = request.catch(() => {});
    return request;
  }
  field(identity) {
    const question = this.questions.find(q => q.identity === identity);
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
  async flush() { for (const [identity,timer] of [...this.timers]) await this.answer(identity,timer.value); await this.serial; if (this.saveError) throw Error(this.saveError); }
  summary() { return renderSummary(this); }
  panel(busy) { return renderQuestions(this, busy); }
}
