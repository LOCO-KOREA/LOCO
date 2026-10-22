// Field names, defaults, choices and types are supplied by the Python AI contract.
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderAiSettings(settings, attribute='data-setting') {
  return (settings?.gpt_contract?.fields || []).map(field=>{
    const value=settings[field.key] ?? settings.gpt_contract.defaults[field.key];
    const choices=field.kind==='boolean' ? [{value:'YES',label:'사용'},{value:'NO',label:'사용 안 함'}] : field.choices;
    const selected=field.kind==='boolean' ? value?'YES':'NO' : value;
    const control=choices ? `<select ${attribute}="${esc(field.key)}">${choices.map(c=>`<option value="${esc(c.value)}" ${String(selected)===String(c.value)?'selected':''}>${esc(c.label)}</option>`).join('')}</select>` :
      `<input ${attribute}="${esc(field.key)}" type="${['number','integer'].includes(field.kind)?'number':'text'}" ${field.kind==='integer'?'min="1" step="1"':field.kind==='number'?'min="0" step="any"':''} value="${esc(value)}">`;
    return `<label>${esc(field.label)} ${control}</label>`;
  }).join('');
}
export function readAiSettings(settings, read) {
  const result=structuredClone(settings);
  for(const field of settings.gpt_contract?.fields || []) {
    const raw=read(field.key); if(raw==null)continue;
    result[field.key]=field.kind==='boolean'?raw==='YES':['number','integer'].includes(field.kind)?Number(raw):raw.trim();
  }
  return result;
}
export function enabledAiSettings(settings) {
  const result=structuredClone(settings);
  for(const field of settings.gpt_contract?.fields || []) result[field.key] ??= settings.gpt_contract.defaults[field.key];
  result.gpt_enabled=true;
  result.gpt_model ||= settings.gpt_contract?.defaults.gpt_model || '';
  return result;
}
export function persistedSettings(settings) {
  const {gpt_contract,gpt_key_present,...value}=structuredClone(settings);
  return value;
}
