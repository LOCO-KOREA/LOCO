// Pose engine configuration is described by the server, including model-specific defaults.
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderPoseSettings(settings,attribute='data-pose-setting') {
  const model=settings?.analysis?.pose_model || {};
  return (settings?.pose_contract?.fields || []).map(field=>`<label>${esc(field.label)} ${field.choices ?
    `<select ${attribute}="${esc(field.key)}">${field.choices.map(c=>`<option value="${esc(c.value)}" ${model[field.key]===c.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>` :
    `<input ${attribute}="${esc(field.key)}" type="${field.kind==='number'?'number':'text'}" ${field.kind==='number'?`min="${field.minimum}" max="${field.maximum}" step="any"`:''} value="${esc(model[field.key])}">`}</label>`).join('');
}
export function readPoseSettings(settings,read) {
  if(!settings.pose_contract)return structuredClone(settings);
  const result=structuredClone(settings),previous=settings.analysis.pose_model;
  const identity=read('model_id')??previous.model_id;
  const selected=settings.pose_contract.models[identity];if(!selected)throw Error('자세 모델을 선택해 주세요.');
  const changed=identity!==previous.model_id,model={...selected};
  for(const field of settings.pose_contract.fields) {
    const raw=read(field.key);if(raw==null){if(!changed&&field.key in previous)model[field.key]=previous[field.key];continue;}
    if(changed&&['model_path','model_sha256'].includes(field.key)&&raw===String(previous[field.key]??''))continue;
    model[field.key]=field.kind==='number'?Number(raw):raw.trim();
  }
  result.analysis.pose_model=model;return result;
}
export function poseForView(flow,view) {
  return flow.preview?.views?.[view] || flow.result?.pose?.slots?.find(s=>s.photo_id===flow.photos[view]?.photo.photo_id) || {};
}
export function mountPoseSettings(host,settings,attribute='data-pose-setting') {
  if(!settings?.pose_contract)return;
  const select=host.querySelector(`[${attribute}="model_id"]`);if(!select)return;
  select.addEventListener('change',()=>{
    const model=settings.pose_contract.models[select.value];if(!model)return;
    for(const key of ['model_path','model_sha256']) {
      const input=host.querySelector(`[${attribute}="${key}"]`);if(input)input.value=model[key];
    }
  });
}
