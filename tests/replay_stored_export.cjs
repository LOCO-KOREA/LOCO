/* Read-only source backup, real isolated Electron/Python/SQLite/Excel replay; no new AI or analysis. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),python=path.join(root,'.venv/Scripts/python.exe');
if(!process.argv[2]||!process.argv[3])throw Error('Usage: node tests/replay_stored_export.cjs SOURCE_CASE NEW_ISOLATED_DIRECTORY');
const source=path.resolve(process.argv[2]),directory=path.resolve(process.argv[3]);
const runAudit=mode=>JSON.parse(execFileSync(python,['tests/replay_stored_export_audit.py',mode,path.resolve(source),path.resolve(directory)],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
const receipt={scope:'Stored actual external-Luna evidence replay; no new external AI or analysis',native_input:false,checks:[],exports:[]};let app,page;
const check=(name,expected,actual)=>{receipt.checks.push({name,expected,actual,pass:JSON.stringify(expected)===JSON.stringify(actual)});};
async function api(method,params={}){const value=await page.evaluate(p=>window.loco.call(p.method,p.params),{method,params});if(!value.ok)throw Error(method+': '+JSON.stringify(value.error));return value.value;}
async function launch(profile){
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:python,LOCO_LIVE_TRACE:path.join(directory,'openai.jsonl'),PYTHONPATH:path.join(root,'tests/live_trace')};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_API_KEY;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,profile)}`,path.join(root,'frontend')],cwd:root,env});page=await app.firstWindow();page.setDefaultTimeout(30000);await page.locator('#connection.connected').waitFor();
 const runtime=await app.evaluate(({BrowserWindow,ipcMain})=>{const w=BrowserWindow.getAllWindows()[0];const original=ipcMain._invokeHandlers.get('loco:call');globalThis.__storedReplay={calls:[],armed:false,held:false,release:null};ipcMain.removeHandler('loco:call');ipcMain.handle('loco:call',async(event,method,params)=>{const log=globalThis.__storedReplay;log.calls.push({method,params});const result=await original(event,method,params);if(log.armed&&method==='get_task'){log.armed=false;log.held=true;await new Promise(resolve=>log.release=resolve);}return result;});return {bounds:w.getBounds(),focusable:w.isFocusable()};});check('hidden focusable',false,runtime.focusable);check('hidden offscreen',true,runtime.bounds.x<=-10000);
 await page.locator(`[data-open="${receipt.survey_id}"]`).click();await page.locator('[data-quick="preview"]').waitFor();await page.locator('[data-quick="preview"]').click();await page.locator('.quick-excel-page .quick-sheet').first().waitFor();
}
async function saveExcel(mode){
 const destination=path.join(directory,mode+'.xlsx');await fs.writeFile(path.join(directory,mode+'-preview.json'),JSON.stringify(await api('preview_excel_sheets',{survey_id:receipt.survey_id,analysis_ids:[receipt.analysis_id]}),null,2));
 await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},destination);
 const selector=mode==='quick'?'[data-quick="excel"]':'[data-action="export"]';await page.locator(selector).click();await page.waitForFunction(selector=>document.querySelector(selector)?.disabled===false,selector,{timeout:0});
 // The completion condition is the persisted export log and real file, not elapsed time.
 await page.waitForFunction(async params=>{const r=await window.loco.call('list_export_logs',{survey_id:params.survey_id});return r.ok&&r.value.some(log=>log.file_path===params.destination);},{survey_id:receipt.survey_id,destination},{timeout:0});
 const log=(await api('list_export_logs',{survey_id:receipt.survey_id})).find(log=>log.file_path===destination);receipt.exports.push({mode,...log});check(mode+' workbook exists',true,Boolean((await fs.stat(destination)).size));await page.screenshot({path:path.join(directory,mode+'.png'),fullPage:true});
}
async function calls(){return await app.evaluate(()=>globalThis.__storedReplay.calls);}
(async()=>{
 await fs.mkdir(directory,{recursive:true});const backup=runAudit('backup');Object.assign(receipt,backup);await launch('quick-profile');await saveExcel('quick');receipt.quick_calls=await calls();await app.close();app=null;runAudit('checkpoint');
 await launch('advanced-profile');await app.evaluate(()=>globalThis.__storedReplay.armed=true);await page.locator('[data-quick="detail"]').click();
 // Delay exactly one successful get_task response: an ordinary backend latency ordering.
 for(;;){if(await app.evaluate(()=>globalThis.__storedReplay.held))break;await page.waitForTimeout(10);}
 await page.locator('[data-nav="S08"]').click();await page.locator('[data-nav="S08"].active').waitFor();receipt.race={while_task_response_pending:'S08'};
 await app.evaluate(()=>globalThis.__storedReplay.release());await api('get_settings');receipt.race.after_late_task_response=await page.locator('#navigation .active').getAttribute('data-nav');check('late detail completion respects the newer navigation',process.env.LOCO_EXPECT_NAVIGATION_RACE==='1'?'S04':'S08',receipt.race.after_late_task_response);
 if(receipt.race.after_late_task_response==='S04'){await page.locator('#task-workspace .task-context').waitFor();await page.locator('[data-nav="S08"]').click();}await page.locator('[data-nav="S08"].active').waitFor();await page.locator('[data-action="export"]').waitFor();await saveExcel('advanced');receipt.advanced_calls=await calls();
 const prohibited=[...receipt.quick_calls,...receipt.advanced_calls].filter(c=>['start_analysis','generate_ai_text','recalculate_judgments'].includes(c.method)||c.method==='intake_turn'&&c.params?.text);check('no new AI input or analysis',[],prohibited);await app.close();app=null;
 await fs.writeFile(path.join(directory,'replay-receipt.json'),JSON.stringify(receipt,null,2));receipt.audit=runAudit('verify');await fs.writeFile(path.join(directory,'replay-receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({directory,checks:receipt.checks.length,failures:receipt.checks.filter(c=>!c.pass),audit:receipt.audit}));if(receipt.audit.defects||receipt.checks.some(c=>!c.pass))process.exitCode=1;
})().catch(async error=>{receipt.error=error.stack;await page?.screenshot({path:path.join(directory,'error.png'),fullPage:true}).catch(()=>{});await app?.close().catch(()=>{});await fs.writeFile(path.join(directory,'replay-receipt.json'),JSON.stringify(receipt,null,2));console.error(error.stack);process.exitCode=1;});
