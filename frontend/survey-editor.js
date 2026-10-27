// Keep the original form and all survey fields mounted while showing one section.
export class SurveyEditor {
  constructor(form, {remember, isBusy}) {
    this.form = form;
    this.remember = remember;
    this.isBusy = isBusy;
    this.dialog = document.querySelector('#survey-editor');
    const intake = form.querySelector('#survey-intake');
    const save = form.querySelector('#save-survey');
    const basic = document.createElement('section');
    basic.className = 'survey-editor-basic';
    for (const child of [...form.children]) if (child !== intake && child !== save) basic.append(child);
    this.sections = [basic, ...intake.children];
    this.content = document.createElement('div');
    this.content.className = 'survey-editor-content';
    this.content.append(basic, intake);
    this.nav = document.createElement('aside');
    this.nav.className = 'survey-editor-nav';
    this.nav.setAttribute('aria-label', '조사 입력 항목');
    const labels = ['기본 정보', '이전 조사'];
    this.sections.forEach((section, index) => {
      section.id = `survey-editor-section-${index}`;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = labels[index];
      button.setAttribute('aria-controls', section.id);
      button.addEventListener('click', () => this.select(index));
      this.nav.append(button);
    });
    const layout = document.createElement('div');
    layout.className = 'survey-editor-layout';
    layout.append(this.nav, this.content);
    const footer = document.createElement('div');
    footer.className = 'survey-editor-footer';
    const note = document.createElement('span');
    note.textContent = '닫으면 입력 중 내용은 유지됩니다. DB 저장은 저장 버튼을 눌러 주세요.';
    footer.append(note, save);
    form.append(layout, footer);
    document.querySelector('#close-survey-editor').addEventListener('click', () => this.close());
    this.dialog.addEventListener('cancel', event => { event.preventDefault(); this.close(); });
    this.form.addEventListener('invalid', event => this.revealInvalid(event.target), true);
    this.select(0);
  }
  revealInvalid(input) {
    const index = this.sections.findIndex(section => section.contains(input));
    if (index < 0 || this.invalidBatch) return;
    // Native validation reports every invalid control before focusing the first.
    this.invalidBatch = true;
    queueMicrotask(() => { this.invalidBatch = false; });
    for (let parent = input.parentElement; parent && parent !== this.form; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    this.select(index);
  }
  select(index) {
    this.sections.forEach((section, i) => { section.hidden = i !== index; });
    [...this.nav.children].forEach((button, i) => {
      button.classList.toggle('active', i === index);
      button.setAttribute('aria-pressed', String(i === index));
    });
    this.content.scrollTo({top: 0});
  }
  open() {
    this.select(0);
    if (!this.dialog.open) this.dialog.showModal();
    this.form.elements.namedItem('title').focus();
  }
  close(saved = false) {
    if (this.isBusy() && !saved) return;
    if (!saved) this.remember();
    this.dialog.close();
  }
}
