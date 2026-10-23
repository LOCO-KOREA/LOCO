/* Crop coordinates always refer to the EXIF-corrected source, never CSS pixels. */
export function rectFromPoints(a,b,width,height){
 const clamp=(v,max)=>Math.max(0,Math.min(max,v));
 const x=Math.floor(clamp(Math.min(a.x,b.x),width)),y=Math.floor(clamp(Math.min(a.y,b.y),height));
 const right=Math.ceil(clamp(Math.max(a.x,b.x),width)),bottom=Math.ceil(clamp(Math.max(a.y,b.y),height));
 return {x,y,width:right-x,height:bottom-y};
}
export function pointOnImage(clientX,clientY,bounds,width,height){
 return {x:Math.max(0,Math.min(width,(clientX-bounds.left)*width/bounds.width)),
         y:Math.max(0,Math.min(height,(clientY-bounds.top)*height/bounds.height))};
}
export function moveRect(rect,dx,dy,width,height){
 return {...rect,x:Math.max(0,Math.min(width-rect.width,Math.round(rect.x+dx))),
                 y:Math.max(0,Math.min(height-rect.height,Math.round(rect.y+dy)))};
}
export function validRect(r,w,h){
 return ['x','y','width','height'].every(k=>Number.isInteger(r[k]))&&r.x>=0&&r.y>=0&&r.width>0&&r.height>0&&r.x+r.width<=w&&r.y+r.height<=h;
}

export function selectPhotoCrop(preview,{signal}={}){
 if(signal?.aborted)return Promise.resolve(null);
 if(!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(preview.data_url)||
    !Number.isInteger(preview.width_px)||!Number.isInteger(preview.height_px)||preview.width_px<1||preview.height_px<1)
  return Promise.reject(new Error('사진 미리보기를 읽을 수 없습니다.'));
 return new Promise((resolve,reject)=>{
  const previous=document.activeElement,dialog=document.createElement('dialog');
  dialog.dataset.photoCrop='';dialog.setAttribute('aria-label','사진 영역 선택');
  dialog.innerHTML=`<style>
   dialog[data-photo-crop]{box-sizing:border-box;width:min(1000px,95vw);max-height:95vh;overflow:auto;border:1px solid #dce2ec;border-radius:16px;padding:22px;color:#24324a;background:#fff}
   dialog[data-photo-crop]::backdrop{background:#18243c99}
   [data-photo-crop] h2{margin:0 0 10px}[data-photo-crop] p{font-size:14px}
   [data-photo-crop] .crop-stage{display:flex;justify-content:center;background:#eef0f5;margin:12px 0;overflow:hidden}
   [data-photo-crop] canvas{display:block;max-width:100%;max-height:52vh;width:auto;height:auto;touch-action:none;cursor:crosshair}
   [data-photo-crop] .crop-tools,[data-photo-crop] .crop-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
   [data-photo-crop] button{padding:9px 14px;border:1px solid #ccd3e0;border-radius:8px;background:#fff;color:#24324a;cursor:pointer}
   [data-photo-crop] button[aria-pressed=true],[data-photo-crop] button[data-confirm]{background:#6259de;color:white}
   [data-photo-crop] button:disabled{opacity:.5;cursor:default}[data-photo-crop] .crop-actions{justify-content:flex-end;margin-top:14px}
  </style><h2>사진 영역 선택</h2>
  <p>드래그해서 사용할 영역을 선택하세요. 분석할 작업자의 머리와 발이 포함되도록 선택해 주세요.</p>
  <div class="crop-tools"><button type="button" data-mode="draw" aria-pressed="true">영역 그리기</button><button type="button" data-mode="adjust" aria-pressed="false">이동·크기 조절</button><button type="button" data-full>전체 선택</button></div>
  <div class="crop-stage"><canvas aria-label="크롭할 사진. 마우스로 영역을 그리거나 이동·크기를 조절하세요."></canvas></div>
  <p data-crop-status role="status"></p><div class="crop-actions"><button type="button" data-cancel>취소</button><button type="button" data-confirm disabled>선택 영역 등록</button></div>`;
  const canvas=dialog.querySelector('canvas'),context=canvas.getContext('2d'),image=new Image();
  const w=preview.width_px,h=preview.height_px;
  // A bounded display canvas avoids allocating a second full-resolution bitmap.
  const scale=Math.min(1,1600/Math.max(w,h));canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
  let rect={x:0,y:0,width:w,height:h},mode='draw',drag=null,loaded=false,settled=false;
  const status=dialog.querySelector('[data-crop-status]'),confirm=dialog.querySelector('[data-confirm]');
  function finish(value,error){
   if(settled)return;settled=true;signal?.removeEventListener('abort',cancel);window.removeEventListener('pagehide',cancel);
   if(dialog.open)dialog.close();dialog.remove();
   if(previous?.isConnected)previous.focus();
   if(error)reject(error);else resolve(value);
  }
  function cancel(){finish(null);}
  function draw(){
   const valid=validRect(rect,w,h);confirm.disabled=!loaded||!valid;
   status.textContent=!loaded?'사진을 불러오고 있어요…':valid?'선택한 영역만 사진으로 등록돼요.':'사진 안에서 사용할 영역을 드래그해 주세요.';
   if(!loaded)return;
   const sx=canvas.width/w,sy=canvas.height/h;
   context.clearRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);
   context.fillStyle='#14213d88';context.fillRect(0,0,canvas.width,canvas.height);
   if(!valid)return;
   context.drawImage(image,rect.x,rect.y,rect.width,rect.height,rect.x*sx,rect.y*sy,rect.width*sx,rect.height*sy);
   context.strokeStyle='#6b5cff';context.lineWidth=2;context.strokeRect(rect.x*sx,rect.y*sy,rect.width*sx,rect.height*sy);
   context.fillStyle='#fff';
   for(const x of [rect.x,rect.x+rect.width])for(const y of [rect.y,rect.y+rect.height])context.fillRect(x*sx-4,y*sy-4,8,8);
  }
  function point(event){return pointOnImage(event.clientX,event.clientY,canvas.getBoundingClientRect(),w,h);}
  canvas.addEventListener('pointerdown',event=>{
   if(!loaded||event.button!==0)return;
   event.preventDefault();const start=point(event),initial={...rect};
   if(mode==='draw')drag={kind:'draw',start,initial};
   else{
    const bounds=canvas.getBoundingClientRect(),tx=14*w/bounds.width,ty=14*h/bounds.height;
    const cx=[rect.x,rect.x+rect.width].find(x=>Math.abs(start.x-x)<=tx);
    const cy=[rect.y,rect.y+rect.height].find(y=>Math.abs(start.y-y)<=ty);
    if(cx!==undefined&&cy!==undefined)drag={kind:'resize',start,initial,anchor:{x:cx===rect.x?rect.x+rect.width:rect.x,y:cy===rect.y?rect.y+rect.height:rect.y}};
    else if(start.x>=rect.x&&start.x<=rect.x+rect.width&&start.y>=rect.y&&start.y<=rect.y+rect.height)drag={kind:'move',start,initial};
    else return;
   }
   drag.pointer=event.pointerId;canvas.setPointerCapture(event.pointerId);
  });
  function updateDrag(event){
   if(!drag||drag.pointer!==event.pointerId)return;const at=point(event);
   if(drag.kind==='move')rect=moveRect(drag.initial,at.x-drag.start.x,at.y-drag.start.y,w,h);
   else rect=rectFromPoints(drag.kind==='resize'?drag.anchor:drag.start,at,w,h);
   draw();
  }
  canvas.addEventListener('pointermove',updateDrag);
  canvas.addEventListener('pointerup',event=>{updateDrag(event);if(drag?.pointer===event.pointerId){drag=null;canvas.releasePointerCapture(event.pointerId);}});
  canvas.addEventListener('pointercancel',()=>{drag=null;});
  for(const button of dialog.querySelectorAll('[data-mode]'))button.addEventListener('click',()=>{
   mode=button.dataset.mode;for(const b of dialog.querySelectorAll('[data-mode]'))b.setAttribute('aria-pressed',String(b===button));
   canvas.style.cursor=mode==='draw'?'crosshair':'move';
  });
  dialog.querySelector('[data-full]').addEventListener('click',()=>{rect={x:0,y:0,width:w,height:h};draw();});
  dialog.querySelector('[data-cancel]').addEventListener('click',cancel);
  dialog.addEventListener('cancel',event=>{event.preventDefault();cancel();});dialog.addEventListener('close',cancel);
  confirm.addEventListener('click',()=>{if(loaded&&validRect(rect,w,h))finish({...rect});});
  image.onload=()=>{if(settled)return;if(image.naturalWidth!==w||image.naturalHeight!==h)return finish(null,new Error('사진 크기가 변경되었습니다. 다시 선택해 주세요.'));loaded=true;draw();};
  image.onerror=()=>finish(null,new Error('사진 미리보기를 읽을 수 없습니다.'));
  signal?.addEventListener('abort',cancel,{once:true});window.addEventListener('pagehide',cancel,{once:true});
  document.body.append(dialog);dialog.showModal();draw();image.src=preview.data_url;
 });
}
