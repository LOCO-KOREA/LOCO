/* Hidden user settings entries; fixture service setup -> maintenance settings view -> SQLite -> restart. No external AI or OS input. */
const {_electron}=require('../frontend/node_modules/playwright');
const path=require('node:path'),fs=require('node:fs/promises'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),directory=path.join(root,'.local',`ai-settings-${Date.now()}`);
let app,page;
const receipt={kind:'offscreen Electron/Python/SQLite settings; no external AI',checks:[]};
async function api(method,params={}){const r=await page.evaluate(async x=>window.loco.call(x.method,x.params),{method,params});assert.equal(r.ok,true,JSON.stringify(r.error));return r.value;}
async function launch(){
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv/Scripts/python.exe'),LOCO_AI_MODEL:'environment-model'};
 delete env.OPENAI_API_KEY;delete env.ELECTRON_RUN_AS_NODE;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});
 page=await app.firstWindow();await page.locator('#connection.connected').waitFor();
 const state=await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows()[0];return {bounds:w.getBounds(),focusable:w.isFocusable()};});
 assert.ok(state.bounds.x<=-10000);assert.equal(state.focusable,false);
}
async function main(){
 await fs.mkdir(directory,{recursive:true});await launch();
 assert.equal(await page.locator('.quick-settings').count(),0);
 assert.equal(await page.locator('[data-quick="settings"]').count(),0);
 assert.equal(await page.locator('[data-setting="gpt_model"]').count(),0);
 const {gpt_contract,gpt_key_present,pose_contract,...fixtureSettings}=await api('get_settings');
 await api('update_settings',{settings:{...fixtureSettings,analysis:{...fixtureSettings.analysis,pose_model:{...pose_contract.models['mediapipe-full'],confidence_min:0.65}},gpt_model:'fixture-configured-model',gpt_reasoning_effort:'high',gpt_timeout_seconds:12.5,gpt_max_output_tokens:8192}});
 let saved=await api('get_settings');assert.equal(saved.gpt_model,'fixture-configured-model');assert.equal(saved.gpt_reasoning_effort,'high');assert.equal('gpt_timeout_seconds' in saved,false);assert.equal(saved.gpt_max_output_tokens,8192);
 receipt.checks.push('quick home omits settings controls while fixture settings persist through the actual service');
 await page.locator('#mode-toggle').click();
 assert.equal(await page.locator('[data-nav="S10"]').count(),0);
 // The retained settings view is entered only by maintenance dispatch, not a user menu.
 await page.evaluate(()=>document.dispatchEvent(new CustomEvent('loco-guide-action',{detail:{action:'S10'}})));
 await page.locator('[data-field="gpt_model"]').waitFor();assert.equal(await page.locator('[data-field="gpt_timeout_seconds"]').count(),0);
 assert.equal(await page.locator('[data-pose-field="model_id"]').inputValue(),'mediapipe-full');
 await page.locator('[data-pose-field="model_id"]').selectOption('mediapipe-heavy');
 assert.match(await page.locator('[data-pose-field="model_path"]').inputValue(),/pose_landmarker_heavy.task$/);
 await page.locator('[data-pose-field="confidence_min"]').fill('0.62');
 await page.locator('[data-pose-field="detection_min"]').fill('0.4');
 await page.locator('[data-pose-field="presence_min"]').fill('0.55');
 await page.locator('[data-action="save-analysis-settings"]').click();
 await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('분석 보조 설정을 저장'));
 saved=await api('get_settings');assert.equal(saved.analysis.pose_model.model_id,'mediapipe-heavy');assert.equal(saved.analysis.pose_model.presence_min,0.55);
 receipt.checks.push('advanced pose settings restore Heavy and save provider-specific thresholds');
 assert.equal(await page.locator('[data-field="gpt_reasoning_effort"]').inputValue(),'high');
 await page.locator('[data-field="gpt_model"]').fill('advanced-configured-model');
 await page.locator('[data-field="gpt_reasoning_effort"]').selectOption('low');
 await page.locator('[data-field="gpt_max_output_tokens"]').fill('12288');
 await page.locator('[data-action="save-gpt-settings"]').click();
 await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('GPT 설정을 저장'));
 saved=await api('get_settings');assert.equal(saved.gpt_model,'advanced-configured-model');assert.equal(saved.gpt_reasoning_effort,'low');assert.equal('gpt_timeout_seconds' in saved,false);assert.equal(saved.gpt_max_output_tokens,12288);
 receipt.checks.push('advanced navigation omits settings while the maintenance view preserves the shared contract and persisted values');
 await app.close();await launch();
 saved=await api('get_settings');assert.equal(saved.gpt_model,'advanced-configured-model');assert.equal(saved.gpt_contract.defaults.gpt_model,'environment-model');assert.equal(saved.gpt_reasoning_effort,'low');assert.equal('gpt_timeout_seconds' in saved,false);assert.equal(saved.gpt_max_output_tokens,12288);
 receipt.checks.push('restart restores all explicit values ahead of environment defaults');
 assert.equal(saved.analysis.pose_model.model_id,'mediapipe-heavy');assert.equal(saved.analysis.pose_model.confidence_min,0.62);assert.equal(saved.analysis.pose_model.detection_min,0.4);assert.equal(saved.analysis.pose_model.presence_min,0.55);
 receipt.settings={model:saved.gpt_model,effort:saved.gpt_reasoning_effort,tokens:saved.gpt_max_output_tokens};
 for(const name of receipt.checks)console.log('PASS '+name);
}
main().catch(error=>{receipt.error=error.stack;console.error(error);process.exitCode=1;}).finally(async()=>{await app?.close().catch(()=>{});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');console.log('Evidence: '+directory);});
