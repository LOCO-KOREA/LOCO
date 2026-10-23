// Local drafts are separate from saved/applied results and are scoped to the held DB.
export const DRAFT_POLICY={prefix:'loco.drafts.v2',legacyQuick:'loco.quick.draft.v1',autosaveDelayMs:500};
export class LocalDrafts {
 constructor({storage=()=>globalThis.localStorage,scope='profile'}={}){Object.assign(this,{storage,scope,error:''});}
 key(kind){return `${DRAFT_POLICY.prefix}:${encodeURIComponent(this.scope)}:${kind}`;}
 bucket(kind){try{const raw=this.storage()?.getItem(this.key(kind));const value=raw?JSON.parse(raw):{};if(!value||typeof value!=='object'||Array.isArray(value))throw Error('invalid drafts');return value;}catch{this.error='임시 저장을 읽지 못했어요. 저장 공간을 확인해 주세요.';return null;}}
 get(kind,id){const bucket=this.bucket(kind);return structuredClone(bucket&&Object.hasOwn(bucket,id)?bucket[id]:null);}
 list(kind){return Object.values(this.bucket(kind)||{}).map(value=>structuredClone(value));}
 write(kind,value){try{const storage=this.storage();if(!storage)throw Error('storage unavailable');storage.setItem(this.key(kind),JSON.stringify(value));this.error='';return true;}catch{this.error='임시 저장에 실패했어요. 앱을 닫기 전에 저장 공간을 확인해 주세요.';return false;}}
 put(kind,id,value){const bucket=this.bucket(kind);return bucket!==null&&this.write(kind,{...bucket,[id]:structuredClone(value)});}
 remove(kind,id){const value=this.bucket(kind);if(value===null)return false;delete value[id];return this.write(kind,value);}
}
const shared=new LocalDrafts();let initialized;
export const localDrafts=()=>shared;
export async function initializeDrafts(bridge=globalThis.window?.loco){
 if(!bridge?.get_database_info)return shared;
 return initialized||=(async()=>{try{const result=await bridge.get_database_info();if(result?.ok!==true||typeof result.value?.path!=='string')throw Error('DB scope unavailable');shared.scope=result.value.path;}catch{initialized=null;shared.error='임시 저장 위치를 확인하지 못했어요. 앱 연결을 확인해 주세요.';}return shared;})();
}
export const newDraftId=()=>globalThis.crypto.randomUUID();
export const intakeDraftKey=task=>JSON.stringify([task.task_id,task.created_at]);
export const explanationDraftKey=(analysis,ai)=>analysis&&ai?JSON.stringify([analysis.analysis_id,analysis.created_at,ai.purpose,ai.text_id,ai.created_at]):null;
export function selectedExplanation(state){const list=(state.analysis?.ai||[]).filter(ai=>ai.purpose===(state.aiPurpose||'TASK_EXPLANATION'));return list.find(ai=>ai.text_id===state.aiTextId)||list.find(ai=>ai.is_active)||list.at(-1);}
export function readExplanationDraft(analysis,ai,store=shared){const key=explanationDraftKey(analysis,ai);return key?store.get('explanation',key):null;}
export function saveExplanationDraft(analysis,ai,text,store=shared){const key=explanationDraftKey(analysis,ai);if(!key)return false;const base=ai.edited_text??ai.generated_text??'';return text===base?store.remove('explanation',key):store.put('explanation',key,{text,base,updatedAt:new Date().toISOString()});}
export function clearExplanationDraft(analysis,ai,text,store=shared){const key=explanationDraftKey(analysis,ai),draft=key&&store.get('explanation',key);return draft?.text===text?store.remove('explanation',key):true;}
