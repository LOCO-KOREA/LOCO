/* photo canvas; dependencies are composed by analysis-workspace.js. */
export function createPhotoCanvas(ctx){
 const {s, poseColors, poseEdges, $, api}=ctx;
async function previewPhoto(photo){const key=photo.photo_id+':'+photo.file_path;if(!s.previews.has(key))s.previews.set(key,await api('get_photo_preview',{photo}));return s.previews.get(key);}
// Same visible left/right/torso colors as pose2/utils.py's OpenCV rendering.
// OpenCV uses BGR; Canvas uses RGB, so (147,20,255) becomes #ff1493.

async function drawPhoto(){
  // Capture photo and analysis together before waiting for file decoding.
  const selected=s.analysis,slotNo=s.slot;const confidence=selected?.snapshot.settings.pose_model.confidence_min??.5;
  const slot=(selected?.snapshot.capture||s.bundle.task.capture).slots.find(s=>s.slot_no===slotNo);
  const photos=selected?.snapshot.photos||s.bundle.photos;
  const photo=slot?photos.find(p=>p.photo_id===slot.photo_id):null;
  const pose=selected?.pose?.slots.find(p=>p.slot_no===slotNo);
  const points=pose?.points||[];
  const edges=pose?.connections?.map(([a,b])=>[a,b,a.startsWith('left_')&&b.startsWith('left_')?'left':a.startsWith('right_')&&b.startsWith('right_')?'right':'center'])||poseEdges;
  const message=$('#photo-message'),canvas=$('#pose-canvas');
  canvas.parentElement.insertAdjacentHTML('afterend',`<div class="pose-legend" aria-label="관절 색상 안내"><span><i class="pose-left"></i>작업자 왼쪽</span><span><i class="pose-right"></i>작업자 오른쪽</span><span><i class="pose-center"></i>코·몸통 연결</span><small>화면 좌우가 아닌 신체 기준 · 신뢰도 ${confidence} 이상만 표시</small></div>`);
  if(!slot||!photo){message.textContent=slot?'이 사진 행에 사진이 없습니다.':'사진 행을 선택하세요.';canvas.style.display='none';return;}
  try{
    const preview=await previewPhoto(photo);
    if(!canvas.isConnected)return;
    const img=new Image();
    img.onload=()=>{
      if(!canvas.isConnected)return;
      canvas.width=preview.width_px;canvas.height=preview.height_px;
      const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0);
      const visible=point=>point&&point.confidence>=confidence&&point.x_px>=0&&point.x_px<canvas.width&&point.y_px>=0&&point.y_px<canvas.height;
      const lookup=Object.fromEntries(points.map(p=>[p.name,p]));
      const lineWidth=Math.max(2,canvas.width/250);
      ctx.lineCap='round';ctx.lineJoin='round';
      for(const [from,to,group] of edges){
        const a=lookup[from],b=lookup[to];
        if(!visible(a)||!visible(b))continue;
        ctx.beginPath();ctx.moveTo(a.x_px,a.y_px);ctx.lineTo(b.x_px,b.y_px);
        ctx.lineWidth=lineWidth+Math.max(1,lineWidth*.3);ctx.strokeStyle='rgba(36,45,65,.45)';ctx.stroke();
        ctx.lineWidth=lineWidth;ctx.strokeStyle=poseColors[group];ctx.stroke();
      }
      for(const point of points){
        if(!visible(point))continue;
        const group=point.name.startsWith('left_')?'left':point.name.startsWith('right_')?'right':'center';
        ctx.fillStyle=poseColors[group];ctx.lineWidth=Math.max(1,lineWidth*.4);ctx.strokeStyle='#242d41';
        ctx.beginPath();ctx.arc(point.x_px,point.y_px,Math.max(3,canvas.width/160),0,Math.PI*2);ctx.fill();ctx.stroke();
      }
      message.style.display='none';
    };
    img.onerror=()=>{if(canvas.isConnected){message.textContent='사진 미리보기를 표시하지 못했습니다.';canvas.style.display='none';}};
    img.src=preview.data_url;
  }catch(error){if(canvas.isConnected){message.textContent=error.message;canvas.style.display='none';}}
}

 return {previewPhoto, drawPhoto};
}
