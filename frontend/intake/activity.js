const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const seconds=value=>Number.isFinite(value)?Math.max(0,Math.floor(value)):0;
const elapsed=value=>{const s=seconds(value);return s<60?`${s}초 경과`:`${Math.floor(s/60)}분 ${s%60}초 경과`;};
const note=value=>seconds(value)>=45?'응답이 늦어지고 있어요. 입력한 내용은 유지되며, 응답이 오면 이어서 진행해요.':seconds(value)>=15?'응답을 기다리고 있어요. 입력한 내용은 유지돼요.':'처리 중이에요. 잠시만 기다려 주세요.';

export function renderActivity(label,elapsedSeconds=0) {
  return `<section class="intake-activity quick-busy" data-intake-activity role="status"><span class="intake-activity-spinner" aria-hidden="true"></span><div class="intake-activity-copy"><strong>${esc(label)}</strong><p data-activity-note>${note(elapsedSeconds)}</p></div><span class="intake-activity-elapsed" data-activity-elapsed aria-live="off">${elapsed(elapsedSeconds)}</span><div class="intake-activity-track" aria-hidden="true"><span></span></div></section>`;
}

export function updateActivity(host,elapsedSeconds) {
  // Update only the live status: never replace the dialog or its answer controls.
  for(const element of host.querySelectorAll('[data-activity-elapsed]'))element.textContent=elapsed(elapsedSeconds);
  for(const element of host.querySelectorAll('[data-activity-note]'))element.textContent=note(elapsedSeconds);
}
