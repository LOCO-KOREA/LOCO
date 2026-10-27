/* Workspace composition; rendering and input state are independent modules. */
import {inputs} from './survey/inputs.js';
import {views} from './survey/views.js';
export class SurveyIntake {
 constructor(form) {
    this.form = form;
    this.host = document.createElement('section');
    this.host.id = 'survey-intake';
    this.form.querySelector('.type-switch').insertAdjacentHTML('afterbegin','<label><input type="radio" name="survey_type" value="INITIAL"><span>최초</span></label>');
    this.form.querySelector('#save-survey').before(this.host);
    this.render();
  }
}
Object.assign(SurveyIntake.prototype,inputs, views);
