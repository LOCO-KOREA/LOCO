// "What should I do next?" hint derived only from saved survey/task state.
// It never claims a result: it points to the earliest unfinished workflow step.
export function nextStep({survey = null, tasks = []} = {}) {
  if (!survey) return {screen: 'S02', label: '새 조사를 만들어 시작하세요.', done: []};
  const done = ['S02'];
  if (!tasks.length) return {screen: 'S03', label: '이 조사에 작업을 등록하세요.', done};
  done.push('S03');
  const calculated = tasks.some(task => task.latest_analysis_id != null);
  if (!calculated) return {screen: 'S04', label: '11개 기준을 입력하고 초안을 계산하세요.', done};
  done.push('S04');
  if (!survey.reviewed) return {screen: 'S07', label: '계산 초안을 조사자가 검토하세요.', done};
  done.push('S07');
  return {screen: 'S08', label: '검토를 마쳤습니다. Excel로 출력하거나 개선 전후를 비교하세요.', done};
}

export function renderNextStep(host, step, screens) {
  if (!host) return;
  const target = screens.find(screen => screen.id === step.screen);
  host.replaceChildren();
  const text = document.createElement('span');
  text.textContent = `다음 할 일 · ${step.label}`;
  const go = document.createElement('button');
  go.type = 'button';
  go.dataset.nextStep = step.screen;
  go.textContent = `${target ? target.name : step.screen} 열기`;
  host.append(text, go);
  host.dataset.screen = step.screen;
  host.hidden = false;
}

export function markDone(navigation, done) {
  for (const button of navigation.querySelectorAll('[data-nav]')) {
    button.classList.toggle('step-done', done.includes(button.dataset.nav));
  }
}
