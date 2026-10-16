/* Workspace composition; rendering, input state and events are independent modules. */
import {inputs} from './survey/inputs.js';
import {views} from './survey/views.js';
import {events} from './survey/events.js';
export class SurveyIntake {
 constructor(form, onChanged) {
    this.form = form;
    this.onChanged = onChanged;
    this.responses = [];
    this.host = document.createElement('section');
    this.host.id = 'survey-intake';
    this.form.querySelector('.type-switch').insertAdjacentHTML('afterbegin','<label><input type="radio" name="survey_type" value="INITIAL"><span>최초</span></label>');
    this.form.querySelector('#save-survey').before(this.host);
    this.form.addEventListener('click', event => this.click(event));
    this.render();
  }
}
Object.assign(SurveyIntake.prototype,inputs, views, events);
