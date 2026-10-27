import {userText} from '../user-language.js';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const PHOTO_VISION_COPY={
  title:'AI가 사진에서 확인한 모습',source:'AI 사진 관찰',
  note:'사진별 동작과 자세를 먼저 보고, 자세한 근거는 펼쳐서 확인하세요.',
  statuses:{OBSERVED:'사진에서 확인했어요',UNCERTAIN:'일부 모습은 확인이 필요해요',NOT_VISIBLE:'사진에서 보이지 않아요',ERROR:'사진 확인을 완료하지 못했어요',DISABLED:'사진 관찰을 진행하지 못했어요'},
  labels:{activity:'보이는 동작',trunk:'허리·몸통',neck:'목',knees:'무릎',arm_left:'왼팔',arm_right:'오른팔',wrist_left:'왼쪽 손목',wrist_right:'오른쪽 손목',holding:'물건을 잡는 모습'},
  views:{LEFT:'왼쪽에서 찍은 사진',RIGHT:'오른쪽에서 찍은 사진',FRONT:'정면·후면 사진'},
  primary:['activity','trunk','knees'],details:'목·팔·손목과 관찰 근거 보기',
  unclear:'가림이나 촬영 방향 때문에 자세를 확실히 확인하지 못했어요.',empty:'이 사진에서 자세와 동작을 확인한 내용이 아직 없어요.'
};
const internalCode=/\b(?:OBSERVED|UNCERTAIN|NOT_VISIBLE|DISABLED|ERROR|UNKNOWN|VISION|FRONT|LEFT|RIGHT|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b/;
const text=(value,fallback='')=>typeof value==='string'&&value.trim()&&!internalCode.test(value)?userText(value.trim()):fallback;
const uniqueSentences=value=>{
  const seen=new Set();
  return text(value).split(/(?<=[.!?。])\s+/u).map(part=>part.trim()).filter(part=>{
    if(!part||seen.has(part))return false;
    seen.add(part);return true;
  }).join(' ');
};

export function photoVisionForTask(task,contract){
  return contract?.session_key?task?.conditions?.[contract.session_key]?.photo_vision:null;
}

export function renderPhotoVision(vision,contract={}, {photoIds,expandDetails=false}={}) {
  if(!Array.isArray(vision?.photos)||!vision.photos.length)return '';
  const copy=PHOTO_VISION_COPY,allowed=photoIds==null?null:new Set(photoIds.map(String));
  const photos=new Map();
  for(const photo of vision.photos)if(photo&&photo.photo_active!==false&&(!allowed||allowed.has(String(photo.photo_id))))photos.set(String(photo.photo_id),photo);
  if(!photos.size)return '';
  const catalogue=contract.photo_vision?.catalogue||vision.catalogue||Object.entries(copy.labels).map(([key,label])=>({key,label}));
  const knownKeys=new Set(Object.keys(copy.labels));
  const fields=catalogue.filter(field=>knownKeys.has(field.key)).map(field=>({key:field.key,label:text(field.label,copy.labels[field.key])}));
  const status=value=>copy.statuses[value]||copy.statuses.UNCERTAIN;
  const observation=(photo,field,showEvidence=false)=>{
    const item=photo.observations?.[field.key];if(!item)return '';
    const value=text(item.value),evidence=text(item.evidence),reason=text(item.reason);
    const uncertain=item.status!=='OBSERVED';
    const description=value||(!uncertain?evidence:reason)||status(item.status);
    const detail=uncertain?(reason||copy.unclear):(evidence&&evidence!==description?evidence:'');
    return `<tr data-photo-vision-field="${esc(field.key)}"><th scope="row">${esc(field.label)}</th><td><span>${esc(description)}</span>${uncertain?`<small class="intake-photo-vision-uncertain">${esc(status(item.status))}</small>`:''}${(showEvidence||uncertain)&&detail&&detail!==description?`<small class="intake-photo-vision-evidence">${esc(detail)}</small>`:''}</td></tr>`;
  };
  const table=(rows,label)=>`<table aria-label="${esc(label)}"><thead><tr><th scope="col">항목</th><th scope="col">사진 관찰</th></tr></thead><tbody>${rows}</tbody></table>`;
  const application=uniqueSentences(vision.application_reason);
  return `<section class="intake-photo-vision" data-photo-vision><h3>${copy.title}</h3><p class="quick-note">${copy.note}</p>${application?`<p class="intake-photo-vision-application" data-photo-vision-application>${esc(application)}</p>`:''}${[...photos.values()].map(photo=>{
    const main=fields.filter(field=>copy.primary.includes(field.key)).map(field=>observation(photo,field)).join('');
    const other=fields.filter(field=>!copy.primary.includes(field.key)).map(field=>observation(photo,field,true)).join('');
    const grounds=fields.filter(field=>copy.primary.includes(field.key)).map(field=>{
      const item=photo.observations?.[field.key],value=text(item?.value),evidence=text(item?.evidence);
      return item?.status==='OBSERVED'&&evidence&&evidence!==value?`<li><strong>${esc(field.label)}</strong> ${esc(evidence)}</li>`:'';
    }).join('');
    const summary=text(photo.summary),messages=(Array.isArray(photo.diagnostics)?photo.diagnostics:[]).map(item=>text(item?.message)).filter(Boolean);
    const reason=uniqueSentences(text(photo.reason)||messages.join(' '));
    const label=text(photo.photo_label,copy.views[photo.view]||'등록한 사진');
    const empty=!main&&!other;
    const failed=photo.status==='ERROR'||photo.status==='DISABLED';
    const details=other||grounds||reason&&!failed;
    return `<article data-photo-vision-photo="${esc(photo.photo_id)}"><div class="intake-photo-vision-header"><div><h4>${esc(label)} <small>${copy.source}</small></h4>${summary?`<p>${esc(summary)}</p>`:''}</div><span class="intake-photo-vision-status">${esc(status(photo.status))}</span></div>${main?table(main,`${label} 주요 관찰`):''}${details?`<details${expandDetails?' open':''}><summary>${copy.details}</summary>${other?table(other,`${label} 추가 관찰`):''}${grounds?`<div class="intake-photo-vision-ground"><strong>주요 관찰 근거</strong><ul>${grounds}</ul></div>`:''}${reason&&!failed?`<p class="intake-photo-vision-reason">${esc(reason)}</p>`:''}</details>`:''}${failed?`<p class="intake-photo-vision-reason" role="status">${esc(reason||status(photo.status))}</p>`:''}${empty&&!failed?`<p class="quick-note">${esc(copy.empty)}</p>`:''}</article>`;
  }).join('')}</section>`;
}
