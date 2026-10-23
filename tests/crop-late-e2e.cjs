/* A real crop/import response remains pending beyond the former harness timeout. No external AI. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),fixture=path.resolve(process.argv[2]||''),directory=path.resolve(process.argv[3]||path.join(root,'.local/crop-late-'+Date.now()));
let app,page;
(async()=>{
 await fs.mkdir(directory,{recursive:true});const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_API_KEY;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'profile')}`,path.join(root,'frontend')],cwd:root,env});page=await app.firstWindow();await page.locator('#connection.connected').waitFor();
 const runtime=await app.evaluate(({BrowserWindow,ipcMain,dialog},fixture)=>{const w=BrowserWindow.getAllWindows()[0],original=ipcMain._invokeHandlers.get('loco:call');globalThis.__cropTest={held:false,calls:[],release:null};ipcMain.removeHandler('loco:call');ipcMain.handle('loco:call',async(event,method,params)=>{globalThis.__cropTest.calls.push(method);const result=await original(event,method,params);if(method==='get_photo_preview'&&!globalThis.__cropTest.held){globalThis.__cropTest.held=true;await new Promise(resolve=>globalThis.__cropTest.release=resolve);}return result;});dialog.showOpenDialog=async()=>({canceled:false,filePaths:[fixture]});return {focusable:w.isFocusable(),bounds:w.getBounds()};},fixture);
 assert.equal(runtime.focusable,false);assert.ok(runtime.bounds.x<=-10000);
 await page.locator('[data-quick="new"]').click();await page.locator('[data-quick-intake]').fill('지연돼도 보관해야 하는 사진 등록 시험');await page.locator('[data-choose="RIGHT"]').click();await page.locator('[data-photo-crop] [data-confirm]').waitFor();await page.waitForFunction(()=>document.querySelector('[data-photo-crop] [data-confirm]')?.disabled===false);await page.locator('[data-photo-crop] [data-confirm]').click();
 while(!await app.evaluate(()=>globalThis.__cropTest.held))await page.waitForTimeout(10);
 const completion=page.waitForFunction(()=>!document.querySelector('#quick-workspace .quick-busy'),{},{timeout:0});
 await new Promise(resolve=>setTimeout(resolve,31000));assert.equal(await page.locator('.quick-slot.filled').count(),0);assert.ok(await page.locator('.quick-busy').count());
 await app.evaluate(()=>globalThis.__cropTest.release());await completion;assert.equal(await page.locator('.quick-slot.filled').count(),1);
 const calls=await app.evaluate(()=>globalThis.__cropTest.calls);assert.ok(!calls.some(method=>['intake_turn','start_analysis','generate_ai_text'].includes(method)));
 await page.screenshot({path:path.join(directory,'registered-after-delay.png'),fullPage:true});const receipt={completed:true,held_response_ms:31000,runtime,calls,external_ai:false,native_input:false};await fs.writeFile(path.join(directory,'receipt.json'),JSON.stringify(receipt,null,2));await app.close();app=null;console.log(JSON.stringify({directory,completed:true,held_response_ms:31000}));
})().catch(async error=>{await page?.screenshot({path:path.join(directory,'error.png'),fullPage:true}).catch(()=>{});await app?.close().catch(()=>{});console.error(error.stack);process.exitCode=1;});
