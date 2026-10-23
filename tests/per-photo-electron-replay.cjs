/* Stored per-photo evidence -> actual hidden Electron preview and Excel; no new AI/analysis. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),python=path.join(root,'.venv/Scripts/python.exe');
const source=path.resolve(process.argv[2]),directory=path.resolve(process.argv[3]);let app,page;
const receipt={scope:'hidden Electron/Python/SQLite/Excel over stored per-photo analysis; direct USER synthetic corrections; no new AI or analysis',native_input:false,checks:[]};
const check=(name,value)=>{assert.ok(value,name);receipt.checks.push(name);};
async function api(method,params={}){const r=await page.evaluate(p=>window.loco.call(p.method,p.params),{method,params});if(!r.ok)throw Error(method+JSON.stringify(r.error));return r.value;}
(async()=>{
 await fs.mkdir(directory,{recursive:false});const expected=JSON.parse(await fs.readFile(path.join(source,'receipt.json'),'utf8')),database=path.join(directory,'loco.db');
 execFileSync(python,['-c','import sqlite3,sys,pathlib; a=sqlite3.connect("file:"+pathlib.Path(sys.argv[1]).as_posix()+"?mode=ro",uri=True); b=sqlite3.connect(sys.argv[2]); a.backup(b); a.close(); b.close()',path.join(source,'loco.db'),database],{cwd:root});
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:database,LOCO_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_API_KEY;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});page=await app.firstWindow();await page.locator('#connection.connected').waitFor();
 receipt.runtime=await app.evaluate(({BrowserWindow,ipcMain})=>{const w=BrowserWindow.getAllWindows()[0],original=ipcMain._invokeHandlers.get('loco:call');globalThis.__photoReplayCalls=[];ipcMain.removeHandler('loco:call');ipcMain.handle('loco:call',(e,m,p)=>{globalThis.__photoReplayCalls.push(m);return original(e,m,p);});return {focusable:w.isFocusable(),bounds:w.getBounds()};});
 check('window is hidden from user input',!receipt.runtime.focusable&&receipt.runtime.bounds.x<=-10000);
 await page.locator('[data-open]').first().click();await page.locator('[data-quick="preview"]').waitFor();await page.locator('[data-quick="preview"]').click();await page.locator('.quick-tabs').waitFor();
 const tab=page.locator('[data-quick="excel-tab"]').filter({hasText:'입력한 값'});await tab.click();
 receipt.rows=await page.locator('.quick-sheet tr').allTextContents();
 for(const row of expected.rows){const matched=receipt.rows.filter(text=>text.includes('USER: '+row.quote));check('visible original photo quote '+row.photo_id,matched.length===1);check('visible corresponding photo direction '+row.photo_id,matched[0].includes(row.photo_id===expected.rows[0].photo_id?'왼쪽에서 찍은 사진':'오른쪽에서 찍은 사진'));}
 check('preview visible text has no photo machine identity',!receipt.rows.some(text=>text.includes('photo:')));await page.screenshot({path:path.join(directory,'preview.png'),fullPage:true});
 const workbook=path.join(directory,'frontend-export.xlsx');await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});},workbook);await page.locator('[data-quick="excel"]').click();
 await page.waitForFunction(async destination=>{const r=await window.loco.call('list_export_logs',{survey_id:1});return r.ok&&r.value.some(row=>row.file_path===destination);},workbook,{timeout:0});
 const actual=JSON.parse(execFileSync(python,['-c','from openpyxl import load_workbook;import sys,json;b=load_workbook(sys.argv[1],data_only=False);print(json.dumps([[c.value for c in row] for row in b["입력한 값"]],ensure_ascii=False));b.close()',workbook],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
 for(const row of expected.rows)check('actual frontend workbook exact source quote '+row.photo_id,actual.filter(cells=>cells.includes('USER: '+row.quote)).length===1);
 receipt.calls=await app.evaluate(()=>globalThis.__photoReplayCalls);check('no new analysis or AI',!receipt.calls.some(method=>['start_analysis','generate_ai_text','intake_turn'].includes(method)));
 receipt.workbook=workbook;await app.close();app=null;await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({directory,checks:receipt.checks.length,workbook}));
})().catch(async error=>{receipt.error=error.stack;await page?.screenshot({path:path.join(directory,'error.png'),fullPage:true}).catch(()=>{});await app?.close().catch(()=>{});await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2));console.error(error.stack);process.exitCode=1;});
