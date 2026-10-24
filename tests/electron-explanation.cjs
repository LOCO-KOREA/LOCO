/* Real OpenAI SDK + loopback protocol fixture, never an external GPT call. */
const {_electron}=require('../frontend/node_modules/playwright');
const http=require('node:http'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),dir=path.join(root,'.local',`explanation-${Date.now()}`);
const packaged=process.env.LOCO_VERIFY_EXECUTABLE;
const receipt={kind:'local Responses HTTP fixture; not a real GPT account',checks:[],requests:[]};
let mode='valid',electron,page;
const server=http.createServer(async(req,res)=>{
 let raw='';for await(const chunk of req)raw+=chunk;
 const request=JSON.parse(raw),summary=JSON.parse(request.input[1].content);
 receipt.requests.push({method:req.method,path:req.url,mode,strict:request.text.format.strict});
 assert.equal(request.text.format.type,'json_schema');assert.equal(request.text.format.strict,true);
 assert.equal(summary.criteria.length,11);assert.ok(!raw.includes('private worker')&&!raw.includes('private task'));
 const content={summary:'로컬 모의 응답: 저장된 계산 근거를 확인하세요.',reba_comparison:summary.provisional_reba?'가정한 1차 REBA와 실제 분석을 비교하세요.':'',posture_explanations:(summary.posture_results||[]).map(item=>({photo_ref:item.photo_ref,explanation:'사진 자세·REBA 입력을 확인하세요.'})),criteria:summary.criteria.map(c=>({criterion_no:c.criterion_no,explanation:'입력값과 문턱을 대조하세요.',basis_refs:c.basis.slice(0,1).map(b=>b.item_code)})),check_items:['현장 조건을 확인하세요.'],improvement_options:[{proposal:'작업 조건을 조사자와 검토하세요.',basis_refs:[summary.criteria[0].basis[0].item_code],needs_confirmation:true}]};
 if(mode==='invalid')content.criteria[0].basis_refs=['C99-B99'];
 if(mode==='delayed')await new Promise(resolve=>setTimeout(resolve,1500));
 if(mode==='slow')await new Promise(resolve=>setTimeout(resolve,18000));
 if(res.destroyed)return;
 res.writeHead(200,{'content-type':'application/json'});
 res.end(JSON.stringify({id:'resp_local_fixture',object:'response',created_at:1,status:'completed',model:'local-fixture',output:[{id:'msg_local_fixture',type:'message',status:'completed',role:'assistant',content:[{type:'output_text',text:JSON.stringify(content),annotations:[]}]}]}));
});
async function api(method,params={}){const result=await page.evaluate(async p=>window.loco.call(p.method,p.params),{method,params});assert.equal(result.ok,true,JSON.stringify(result.error));return result.value;}
async function poll(read,predicate){const end=Date.now()+20000;while(Date.now()<end){const value=await read();if(predicate(value))return value;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Fixture verification timeout');}
const pass=name=>{receipt.checks.push(name);console.log('PASS '+name);};
async function main(){
 await fs.mkdir(dir,{recursive:true});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_PYTHON:path.join(root,'.venv','Scripts','python.exe'),LOCO_DB_PATH:path.join(dir,'loco.db'),OPENAI_API_KEY:'local-protocol-fixture-only',OPENAI_BASE_URL:`http://127.0.0.1:${server.address().port}/v1/`};delete env.ELECTRON_RUN_AS_NODE;
 if(packaged){delete env.LOCO_PYTHON;delete env.LOCO_SERVICE_ENTRY;delete env.LOCO_MOVENET_MODEL;env.PATH=process.env.SystemRoot+'\\System32;'+process.env.SystemRoot;}
 electron=await _electron.launch({executablePath:packaged||require('../frontend/node_modules/electron'),args:packaged?[]:[path.join(root,'frontend')],env,cwd:root});page=await electron.firstWindow();page.setDefaultTimeout(15000);
 receipt.runtime=await electron.evaluate(({app})=>({packaged:app.isPackaged,executable:process.execPath}));
 await page.locator('#connection.connected').waitFor();await page.evaluate(()=>{if(document.body.classList.contains('quick-mode'))document.querySelector('#mode-toggle').click();});
 const survey=await api('create_survey',{draft:{survey_type:'REGULAR',title:'private task',survey_date:'2026-10-16'}});
 const task=await api('create_task',{survey_id:survey.survey_id,draft:{task_name:'private task',conditions:{worker_code:'private worker'}}});
 const original=await api('recalculate_judgments',{task_id:task.task_id});
 const settings=await api('get_settings');settings.gpt_enabled=true;settings.gpt_model='local-fixture';await api('update_settings',{settings});
 await page.reload();await page.locator('#connection.connected').waitFor();await page.evaluate(()=>{if(document.body.classList.contains('quick-mode'))document.querySelector('#mode-toggle').click();});await page.locator('[data-nav="S02"]').click();await page.locator(`#survey-rows [data-id="${survey.survey_id}"]`).first().click();await page.locator('#close-survey-editor').click();await page.locator('#open-survey').click();await page.locator('[data-nav="S06"]').click();
 await page.locator('[data-action="generate-explanation"]').click();
 let generated=await poll(()=>api('get_analysis',{analysis_id:original.analysis_id}),a=>a.ai.length===1);
 assert.equal(generated.ai[0].result,'GENERATED');assert.deepEqual(generated.judgment,original.judgment);
 await page.locator('.explanation-evidence summary').click();await page.locator('[data-action="show-basis"]').first().click();await page.locator('.modal-backdrop').waitFor();
 await page.screenshot({path:path.join(dir,'basis.png'),fullPage:true});
 await page.locator('.modal-backdrop [data-action="open-next-input"]').click();
 await page.locator('[data-path="legal.criteria.0.condition_present"]').waitFor();assert.equal(await page.evaluate(()=>document.activeElement.dataset.path),'legal.criteria.0.condition_present');
 pass('strict SDK response renders linked criterion grounds and navigates to the source field');
 await page.locator('[data-nav="S06"]').click();await page.locator('#explanation-text').fill('로컬 응답을 조사자가 수정한 설명');await page.locator('[data-action="edit-explanation"]').click();await page.locator('[data-action="apply-edited"]').click();
 const active=(await api('get_analysis',{analysis_id:original.analysis_id})).ai.find(x=>x.is_active);assert.equal(active.applied_text,'로컬 응답을 조사자가 수정한 설명');
 mode='invalid';await page.locator('[data-action="generate-explanation"]').click();
 let failed=await poll(()=>api('get_analysis',{analysis_id:original.analysis_id}),a=>a.ai.length===2);
 assert.equal(failed.ai[1].result,'FALLBACK');assert.equal(failed.ai[1].fallback_reason,'INVALID_STRUCTURED_CONTENT');assert.equal(failed.ai.find(x=>x.is_active).text_id,active.text_id);assert.deepEqual(failed.judgment,original.judgment);
 pass('invalid basis references fall back and preserve the active edited text and calculations');
 mode='delayed';await page.locator('[data-action="generate-explanation"]').click();const started=Date.now();await api('get_settings');assert.ok(Date.now()-started<1000);await poll(()=>api('get_analysis',{analysis_id:original.analysis_id}),a=>a.ai.length===3);
 pass('network-backed generation does not block other service requests');
 mode='slow';const began=Date.now();await page.locator('[data-action="generate-explanation"]').click();const slow=await poll(()=>api('get_analysis',{analysis_id:original.analysis_id}),a=>a.ai.length===4);
 assert.equal(slow.ai[3].result,'GENERATED');assert.ok(Date.now()-began>=17000);assert.equal(receipt.requests.length,4);assert.deepEqual(slow.judgment,original.judgment);
 pass('18-second fixture completes without an application deadline and the request is not automatically retried');
 receipt.completed_at=new Date().toISOString();
}
main().catch(error=>{receipt.failure=error.stack;console.error(error);process.exitCode=1;}).finally(async()=>{if(electron)await electron.close().catch(()=>{});server.close();await fs.writeFile(path.join(dir,'receipt.json'),JSON.stringify(receipt,null,2));console.log('Evidence: '+dir);});
