import {renderActivity} from './activity.js';
import {renderIntakeHistory} from './history-view.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Selectable presets for number boxes: only suggestions. The box stays empty until the user picks one or types a value.
const PRESETS={days:[100,150,200,220,250,300,365],minutes:[30,60,120,240,360,480],perDay:[10,25,50,100,200,500],perMinute:[1,2,3,5,10],kg:[1,5,10,15,20,25],months:[1,3,6,12,24]};
const PRESET_OF_UNIT={'일':'days','분':'minutes','분/일':'minutes','회/일':'perDay','회/분':'perMinute','kg':'kg','개월':'months'};
// A gate answer decides which other rows exist (a work feature opens its card, the photo question opens the posture rows), so the page refreshes in place when it changes.
const isGate=f=>f.target==='context'||String(f.target||'').startsWith('work_type.');
const isContext=f=>f.target==='context'||f.destination.type==='context';
/** The whole input in ONE page: work features, conditions, the photo question, the posture checklist and the angles the photo could not read. */
export function renderForm(intake,busy) {
  const fields=intake.formFields(), facts=intake.state.facts, SIDE={LEFT:'왼쪽',RIGHT:'오른쪽'}, lists=new Map();
  const presetList=f=>{
    const kind=f.kind==='number'?PRESET_OF_UNIT[f.unit||'']:'';
    const values=kind?PRESETS[kind].filter(v=>f.maximum==null||v<=f.maximum):[];
    if(!values.length)return '';
    const id=`intake-presets-${kind}-${values.length}`;
    lists.set(id,values);
    return id;
  };
  // Another photo's reading is only offered: the user's press fills the box, and saving makes it an answer.
  // A checklist box has no select to say "no" with, so its line carries that answer too; a left/right line says which side it is about.
  const hintFor=f=>{
    const value=intake.formValue(f), saved=facts.find(s=>s.identity===f.identity), who=f.checklist&&SIDE[f.destination.scope]?`${SIDE[f.destination.scope]} · `:'';
    const press=(kind,label)=>`<button type="button" data-quick="intake-fill" data-fill-kind="${kind}" data-fill-identity="${esc(f.identity)}" ${busy?'disabled':''}>${label}</button>`;
    return f.suggestion&&saved?.state!=='CONFLICT'?`<small class="intake-suggestion" data-suggestion-for="${esc(f.identity)}" ${value==null?'':'hidden'}>${who}${esc(f.suggestion.photo_label)}에서 ${esc(f.suggestion.reading||'읽은 값이 있어요')}${f.suggestion.estimated?', 확신은 낮아요':''}${f.suggestion.quote?` (${esc(f.suggestion.quote)})`:''}. 맞나요? ${press('suggest',f.checklist?'맞아요, 체크':'맞아요, 채우기')}${f.checklist?press('decline','아니에요'):''}</small>`:'';
  };
  const control=f=>{
    const value=intake.formValue(f), saved=facts.find(s=>s.identity===f.identity);
    const attrs=`data-intake-form="${esc(f.identity)}"${isGate(f)&&f.kind==='choice'?' data-intake-gate="1"':''} ${busy?'disabled':''}`, list=presetList(f);
    const input=f.kind==='choice'?`<select ${attrs}><option value="" ${value==null?'selected':''}>모름 / 미확인</option>${f.choices.map(c=>`<option value="${esc(c.value)}" ${value===c.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:
      `<input ${attrs} type="${f.kind==='number'?'number':'text'}" ${f.kind==='number'?`min="0" step="any" ${f.maximum!=null?`max="${f.maximum}"`:''}`:''}${list?` list="${list}"`:''} value="${esc(value)}" placeholder="미확인">`;
    const status=saved?.state==='CONFLICT'?'<small class="quick-warn">기존 설명과 다른 값이 있어 확인이 필요해요.</small>':saved?.state==='ESTIMATED'?`<small>사진 추정: ${esc(f.choices?.find(c=>c.value===saved.value)?.label??saved.value)} · 직접 확인해 주세요.</small>`:saved?.source==='AI'&&saved.state==='KNOWN'?'<small>설명에서 자동 정리</small>':'';
    const reason=(f.destination.type==='manual'||f.reask)&&f.reason?`<small class="intake-measurement-reason">${esc(f.reason)}</small>`:'';
    return `<div class="intake-group-item"><label class="intake-group-question"><span>${esc(f.label)}${f.unit?` <small>(${esc(f.unit)})</small>`:''}</span>${input}</label>${status}${reason}${hintFor(f)}</div>`;
  };
  const quickFill=rows=>{
    // A dimmed button cannot be focused, so the reason is written next to it (and linked with aria-describedby), not only shown on hover.
    const buttons=intake.shortcuts(rows).map(s=>{const hintId=`fill-hint-${s.data.side}-${s.data.condition}`;
      return `<span class="intake-fill-item"><button type="button" data-quick="intake-fill" ${Object.entries(s.data).map(([name,v])=>`data-fill-${name}="${esc(v)}"`).join(' ')} aria-describedby="${esc(hintId)}" ${busy||!s.count?'disabled':''} ${!s.count&&s.hint?`title="${esc(s.hint)}"`:''}>${esc(s.label)}</button><small class="intake-fill-hint" id="${esc(hintId)}" data-fill-hint-for="${esc(s.data.side)}" data-fill-hint-condition="${esc(s.data.condition)}" ${s.hint?'':'hidden'}>${esc(s.hint)}</small></span>`;}).join('');
    return buttons?`<div class="intake-quick-fill" role="group" aria-label="한 번에 채우기"><strong>한 번에 채우기</strong>${buttons}<small>누르면 칸만 채워지고, 저장해야 반영돼요. 다르면 직접 고쳐 주세요.</small></div>`:'';
  };
  // One list for the yes/no posture items: the user ticks what applies, and only an explicit press fills the rest with "does not apply".
  const checklist=(rows,condition)=>{
    const boxes=rows.filter(f=>f.condition===condition&&intake.checkable(f)).sort((a,b)=>a.checklist.order-b.checklist.order);
    if(!boxes.length)return '';
    const lines=new Map(), groups=new Map(), side=SIDE;
    for(const f of boxes) {const key=f.checklist.group+'|'+f.checklist.label;if(!lines.has(key))lines.set(key,{group:f.checklist.group,label:f.checklist.label,boxes:[]});lines.get(key).boxes.push(f);}
    for(const item of lines.values()) {if(!groups.has(item.group))groups.set(item.group,[]);groups.get(item.group).push(item);}
    // Only a reason that says something about this row is shown (not the generic "needed for the result"); a reason both sides share is written once.
    const why=f=>f.reason&&(f.photo_measurement_reason||f.reask||f.photo_unused)?f.reason:'';
    const reasonsOf=list=>{const texts=new Map();for(const f of list)if(why(f)){if(!texts.has(why(f)))texts.set(why(f),[]);texts.get(why(f)).push(f);}return [...texts].map(([text,owners])=>({text,owners,id:`reason-${owners[0].identity}`}));};
    const noteOf=(reason,all)=>`<small class="intake-measurement-reason" id="${esc(reason.id)}">${reason.owners.length<all.length?`${esc(reason.owners.map(f=>side[f.destination.scope]).join('·'))}: `:''}${esc(reason.text)}</small>`;
    const box=(f,text,reasons,name)=>{const ids=reasons.filter(r=>r.owners.includes(f)).map(r=>r.id).join(' ');
      return `<label class="intake-check"><input type="checkbox" data-intake-flag="${esc(f.identity)}" ${name?`aria-label="${esc(name)}"`:''} ${ids?`aria-describedby="${esc(ids)}"`:''} ${intake.formValue(f)===f.checklist.yes?'checked':''} ${busy?'disabled':''}> <span>${esc(text)}</span></label>`;};
    const line=item=>{const reasons=reasonsOf(item.boxes), notes=reasons.map(r=>noteOf(r,item.boxes)).join('');
      return item.boxes.some(f=>side[f.destination.scope])
        ?`<div class="intake-check-item intake-check-pair"><span>${esc(item.label)}</span><span class="intake-check-sides">${item.boxes.map(f=>box(f,side[f.destination.scope],reasons,`${item.label} · ${side[f.destination.scope]}`)).join('')}</span>${notes}${item.boxes.map(hintFor).join('')}</div>`
        :`<div class="intake-check-item">${box(item.boxes[0],item.label,reasons)}${notes}${hintFor(item.boxes[0])}</div>`;};
    return `<section class="intake-checklist" aria-label="해당하는 자세 체크"><h4>해당하는 자세에 체크해 주세요</h4><p>체크하지 않은 항목은 아래 버튼을 눌러야 ‘해당 없음’으로 채워져요. 저장하기 전에는 아무것도 기록되지 않아요.</p>${[...groups].map(([title,list])=>`<fieldset class="intake-checklist-group"><legend>${esc(title)}</legend>${list.map(line).join('')}</fieldset>`).join('')}<div class="intake-checklist-actions"><button type="button" data-quick="intake-fill" data-fill-kind="confirm" data-fill-condition="${esc(condition)}" ${busy||!intake.fillPlan({kind:'confirm',condition}).length?'disabled':''}>확인 끝 · 체크 안 한 항목은 해당 없음</button><small data-checklist-status="${esc(condition)}">${esc(intake.checklistStatus(condition))}</small></div></section>`;
  };
  const handled=f=>intake.formHandled(f);
  const pending=fields.filter(f=>!handled(f)), confirmed=fields.filter(handled);
  const optional=f=>(intake.state.contract.policy.optional_photo_destinations||['manual','view']).includes(f.destination.type);
  const photoPrefix=intake.state.contract.photo_policy?.condition_prefix||'photo:';
  const titleOf=field=>{const photo=field.photo_label||field.display_condition;const condition=field.condition&&!field.condition.startsWith(photoPrefix)&&field.condition!=='default'?field.condition:'';return (field.group||'기본 작업 정보')+(photo||condition?' · '+(photo||condition):'');};
  const grouped=rows=>{const groups=new Map();for(const field of rows) {const key=titleOf(field);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(field);}return [...groups];};
  const section=(name,title,body,{photo=false}={})=>`<details class="intake-form-section" data-intake-section="${name}"${photo?' data-intake-photo-optional':''} open><summary>${esc(title)}</summary>${body}</details>`;

  const workRows=pending.filter(f=>f.destination.type==='work_type');
  const conditionRows=pending.filter(f=>f.destination.type!=='work_type'&&!optional(f));
  const photoRows=pending.filter(f=>f.destination.type!=='work_type'&&optional(f)&&f.destination.type!=='manual').sort((a,b)=>(isContext(a)?0:a.destination.type==='view'?1:2)-(isContext(b)?0:b.destination.type==='view'?1:2));
  const manualRows=pending.filter(f=>f.destination.type==='manual');
  const photos=[...new Set(manualRows.map(f=>f.condition))];

  const work=workRows.length?section('work',`작업 특징 · ${workRows.length}개`,`<p class="intake-section-lead">설명한 작업 외에 아래 작업도 하나요? 해당하는 것만 ‘예’를 고르세요.</p>${workRows.map(control).join('')}<div class="intake-section-actions"><button type="button" data-quick="intake-no-other-work" ${busy?'disabled':''}>선택하지 않은 나머지 작업은 모두 안 해요</button></div>`):'';
  const conditions=conditionRows.length?section('conditions','작업 조건',grouped(conditionRows).map(([title,rows])=>`<div class="intake-form-group"><h3>${esc(title)}</h3>${rows.map(control).join('')}</div>`).join('')):'';
  // The photo question comes first: answering it opens the posture rows right below it.
  const asksContext=photoRows.some(isContext);
  const photo=photoRows.length?section('photo','사진 확인',`${asksContext?'<p class="intake-section-lead">사진이 한 사람의 전신이 나온 평소 작업 모습인지 먼저 골라 주세요. ‘예’를 고르면 바로 아래에 자세 항목이 나와요.</p>':''}${grouped(photoRows).map(([title,rows])=>`<div class="intake-form-group">${title==='사진 확인'?'':`<h3>${esc(title)}</h3>`}${rows.map(control).join('')}</div>`).join('')}`,{photo:true}):'';
  const labelOf=rows=>rows.find(f=>f.photo_label)?.photo_label||'';
  const measuredNote=condition=>{const measured=intake.measuredCount(condition);return measured?`<p class="intake-measured-note">사진이 잰 값 ${measured}개는 이미 반영했어요. 아래에서 해당하는 것만 알려 주세요.</p>`:'';};
  const photoBlock=(condition,rows,inner)=>`<div class="intake-photo-block" data-intake-condition="${esc(condition)}">${labelOf(rows)?`<h3>${esc(labelOf(rows))}</h3>`:''}${inner}</div>`;
  // The checklist comes with the note and the copy buttons of its photo; a photo without a checklist keeps them above its angle rows instead.
  const checklistBlocks=photos.map(condition=>{
    const rows=manualRows.filter(f=>f.condition===condition), panel=checklist(rows,condition);
    return panel?photoBlock(condition,rows,`${measuredNote(condition)}${panel}${quickFill(rows)}`):'';
  }).join('');
  const checklistPart=checklistBlocks?section('checklist','자세 체크리스트',checklistBlocks,{photo:true}):'';
  const angleBlocks=photos.map(condition=>{
    const rows=manualRows.filter(f=>f.condition===condition), rest=rows.filter(f=>!intake.checkable(f)), hasPanel=rows.some(f=>intake.checkable(f)), refused=intake.photoUnused(condition);
    if(!rest.length)return '';
    return photoBlock(condition,rows,`${hasPanel?'':`${measuredNote(condition)}${quickFill(rows)}`}${hasPanel&&!refused?'<h4 class="intake-angle-title">사진이 읽지 못해 직접 골라야 하는 항목</h4>':''}${rest.map(control).join('')}`);
  }).join('');
  const angles=angleBlocks?section('angles','사진 자세 직접 고르기',angleBlocks,{photo:true}):'';

  // One count for the page; the whole checklist is a single decision ("check what applies, then 확인 끝"), not eighteen questions.
  const blank=f=>intake.formValue(f)==null;
  const left=pending.filter(f=>!intake.checkable(f)&&blank(f)).length+new Set(pending.filter(f=>intake.checkable(f)&&blank(f)).map(f=>f.condition)).size;
  const sentence=`<details class="intake-form-section" data-intake-natural-answer${intake.text.trim()?' open':''}><summary>문장으로 더 적기</summary><p>아는 내용을 한 번에 적어 주세요. 설명에서 필요한 값을 정리해요.</p><textarea data-intake-reply maxlength="${intake.state.contract.policy.text_limit}" placeholder="예: 다른 작업은 없어요. 이 조건은 하루 30분, 1분에 1번 정도예요.">${esc(intake.text)}</textarea><button type="button" data-quick="adaptive-next" ${busy||!intake.text.trim()?'disabled':''}>답변 정리</button></details>`;
  const body=[work,conditions,photo,checklistPart,angles].join('');
  const datalists=[...lists].map(([id,values])=>`<datalist id="${id}">${values.map(v=>`<option value="${v}"></option>`).join('')}</datalist>`).join('');
  return `<dialog class="intake-dialog" data-intake-dialog aria-labelledby="intake-dialog-title" aria-busy="${Boolean(busy)}"><header class="intake-dialog-header"><div><span class="intake-eyebrow">LOCO · 작업 정보 확인</span><h2 id="intake-dialog-title">작업 정보를 한 번에 확인해 주세요</h2></div><button type="button" data-quick="intake-close" ${busy?'disabled':''} aria-label="닫기">×</button></header>
    ${busy?renderActivity(typeof busy==='string'?busy:'저장하고 있어요',intake.busyElapsedSeconds):''}
    <div class="intake-dialog-body"><p class="intake-remaining" data-intake-remaining>${left?`남은 확인 ${left}개 · 모르면 비워 두세요(미확인으로 남아요)`:'남은 확인이 없어요 · 저장하고 결과를 확인해 주세요'}</p><p class="intake-auto-note">아직 확인하지 못한 항목만 보여 드려요. 이미 정리한 값은 다시 입력하지 않아도 돼요.</p><div data-intake-unanswered>${body||'<p>추가로 입력할 항목이 없어요. 저장하고 결과를 확인해 주세요.</p>'}</div>${datalists}${sentence}${confirmed.length?`<details class="intake-form-section" data-intake-confirmed><summary>이미 확인한 정보 ${confirmed.length}개 · 수정하기</summary>${confirmed.map(control).join('')}</details>`:''}${renderIntakeHistory(intake.state,{details:false})}
    ${intake.saveError?'<p class="quick-warn">저장하지 못했어요. 입력은 유지돼요. 다시 시도해 주세요.</p>':''}</div>
    <footer class="intake-dialog-footer"><p class="intake-fill-note" data-intake-fill-note role="status" ${intake.fillNote?'':'hidden'}>${esc(intake.fillNote||'')}</p><button type="button" data-quick="intake-close" ${busy?'disabled':''}>나중에 확인</button><button type="button" class="primary" data-quick="intake-form-next" ${busy?'disabled':''}>저장하고 결과 보기 →</button></footer></dialog>`;
}
