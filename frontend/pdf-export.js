/* PDF requests keep the target selected before a save dialog or delayed reply. */
const pending = new Map();
const previewUrls = new Set();
function viewerUrl(dataUrl){
 const bytes=Uint8Array.from(atob(dataUrl.split(',')[1]),c=>c.charCodeAt(0));
 const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));
 previewUrls.add(url);
 // The caller inserts the returned markup synchronously. Release viewers removed
 // by a subsequent render, while retaining URLs still used by an open iframe.
 if(typeof document!=='undefined')setTimeout(()=>{
  const mounted=new Set([...document.querySelectorAll('iframe')].map(frame=>frame.src.split('#')[0]));
  for(const previous of previewUrls)if(!mounted.has(previous)){
   URL.revokeObjectURL(previous);previewUrls.delete(previous);
  }
 },0);
 return url;
}
const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function previewPdf(api,params){
 const fixed=structuredClone(params),key='preview:'+JSON.stringify(fixed);
 if(pending.has(key))return pending.get(key);
 const result=Promise.resolve().then(()=>api('preview_pdf',fixed)).finally(()=>pending.delete(key));
 pending.set(key,result);return result;
}

export function exportPdf(api,choose,params){
 const fixed=structuredClone(params),key='export:'+JSON.stringify(fixed);
 if(pending.has(key))return pending.get(key);
 const result=Promise.resolve().then(async()=>{
  const destination=await choose();
  if(!destination)return null;
  return api('export_pdf',{...fixed,spec:{...fixed.spec,destination}});
 }).finally(()=>pending.delete(key));
 pending.set(key,result);return result;
}

export function renderPdfPreview(preview){
 if(!preview)return '<p>PDF 미리보기를 불러와 주세요.</p>';
 if(typeof preview.data_url!=='string'||!/^data:application\/pdf;base64,[A-Za-z0-9+/=]+$/.test(preview.data_url))
  return '<p>PDF 미리보기 응답을 표시할 수 없습니다.</p>';
 return `<p>원본 양식 · ${Number(preview.page_count)||0}쪽</p>
  ${(preview.warnings||[]).map(w=>`<p class="input-guide">${escape(w)}</p>`).join('')}
  <iframe title="유해요인조사표 PDF 미리보기" src="${viewerUrl(preview.data_url)}#view=FitH" style="width:100%;height:75vh;border:1px solid #dce2ec"></iframe>`;
}
