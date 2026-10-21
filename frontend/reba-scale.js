// Display the existing REBA bands; this does not participate in score calculation.
const BANDS = [
  {min: 1, max: 1, key: 'negligible', label: '무시 가능', range: '1점'},
  {min: 2, max: 3, key: 'low', label: '낮음', range: '2~3점'},
  {min: 4, max: 7, key: 'medium', label: '보통', range: '4~7점'},
  {min: 8, max: 10, key: 'high', label: '높음', range: '8~10점'},
  {min: 11, max: 15, key: 'very-high', label: '매우 높음', range: '11~15점'},
];

const bandFor = value => Number.isInteger(value) ? BANDS.find(band => value >= band.min && value <= band.max) : undefined;

export function rebaScoreClass(score) {
  const band = bandFor(score);
  return band ? `reba-score-${band.key}` : '';
}

export function renderRebaScale(score, {provisional = false} = {}) {
  if (!Number.isInteger(score) || score < 1 || score > 15) return '';
  const current = bandFor(score);
  const description = `${provisional ? '1차 ' : ''}REBA ${score}점, 위험 수준 ${current.label}. 전체 범위 1~15점. ` + BANDS.map(band => `${band.range} ${band.label}`).join(', ');
  return `<div class="reba-scale" role="img" aria-label="${description}">
    <div aria-hidden="true">
      <div class="reba-scale-caption"><strong>점수별 위험 수준</strong><span>현재 ${score}점 · ${current.label}</span></div>
      <ol class="reba-scale-track">${Array.from({length: 15}, (_, i) => {
        const value = i + 1, band = bandFor(value);
        return `<li class="reba-scale-step reba-risk-${band.key}${value === score ? ' is-current' : ''}" data-score="${value}">${value}</li>`;
      }).join('')}</ol>
      <div class="reba-scale-legend">${BANDS.map(band => `<span class="reba-scale-key${band === current ? ' is-current' : ''}" style="grid-column: ${band.min} / span ${band.max - band.min + 1}"><i class="reba-risk-${band.key}"></i><span>${band.range}<small>${band.label}</small></span></span>`).join('')}</div>
    </div>
  </div>`;
}
