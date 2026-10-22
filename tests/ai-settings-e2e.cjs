/* Actual settings screens -> service -> SQLite -> restart; no external AI or OS input. */
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
 await page.locator('.quick-settings summary').click();
 await page.locator('[data-setting="gpt_model"]').fill('quick-configured-model');
 await page.locator('[data-setting="gpt_reasoning_effort"]').selectOption('high');
 await page.locator('[data-setting="gpt_timeout_seconds"]').fill('12.5');
 await page.locator('[data-setting="gpt_max_output_tokens"]').fill('8192');
 await page.locator('[data-quick="settings"]').click();await page.waitForFunction(()=>!document.querySelector('.quick-busy'));
 let saved=await api('get_settings');assert.equal(saved.gpt_model,'quick-configured-model');assert.equal(saved.gpt_reasoning_effort,'high');assert.equal(saved.gpt_timeout_seconds,12.5);assert.equal(saved.gpt_max_output_tokens,8192);
 receipt.checks.push('quick settings save every typed field through the actual service');
 await page.locator('#mode-toggle').click();await page.locator('[data-nav="S10"]').click();
 assert.equal(await page.locator('[data-field="gpt_reasoning_effort"]').inputValue(),'high');
 await page.locator('[data-field="gpt_model"]').fill('advanced-configured-model');
 await page.locator('[data-field="gpt_reasoning_effort"]').selectOption('low');
 await page.locator('[data-field="gpt_timeout_seconds"]').fill('17.5');
 await page.locator('[data-field="gpt_max_output_tokens"]').fill('12288');
 await page.locator('[data-action="save-gpt-settings"]').click();
 await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('GPT 설정을 저장'));
 saved=await api('get_settings');assert.equal(saved.gpt_model,'advanced-configured-model');assert.equal(saved.gpt_reasoning_effort,'low');assert.equal(saved.gpt_timeout_seconds,17.5);assert.equal(saved.gpt_max_output_tokens,12288);
 receipt.checks.push('advanced settings consume and update the same contract and persisted values');
 await app.close();await launch();
 saved=await api('get_settings');assert.equal(saved.gpt_model,'advanced-configured-model');assert.equal(saved.gpt_contract.defaults.gpt_model,'environment-model');assert.equal(saved.gpt_reasoning_effort,'low');assert.equal(saved.gpt_timeout_seconds,17.5);assert.equal(saved.gpt_max_output_tokens,12288);
 receipt.checks.push('restart restores all explicit values ahead of environment defaults');
 receipt.settings={model:saved.gpt_model,effort:saved.gpt_reasoning_effort,timeout:saved.gpt_timeout_seconds,tokens:saved.gpt_max_output_tokens};
 for(const name of receipt.checks)console.log('PASS '+name);
}
main().catch(error=>{receipt.error=error.stack;console.error(error);process.exitCode=1;}).finally(async()=>{await app?.close().catch(()=>{});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2),'utf8');console.log('Evidence: '+directory);});
