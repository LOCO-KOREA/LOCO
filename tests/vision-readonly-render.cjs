/* Open the selected stored analysis and inspect every expanded photo field. No AI. */
const {_electron}=require('../frontend/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),directory=path.resolve(process.argv[2]);let app,page;
(async()=>{
 const receipt=JSON.parse(await fs.readFile(path.join(directory,'receipt.json'),'utf8'));
 const before=(await fs.readFile(path.join(directory,'sdk.jsonl'),'utf8')).split('\n').filter(Boolean).length;
 const env={...process.env,LOCO_HIDDEN:'1',LOCO_DB_PATH:path.join(directory,'loco.db'),LOCO_PYTHON:path.join(root,'.venv/Scripts/python.exe'),LOCO_VISION_TRACE:path.join(directory,'sdk.jsonl'),PYTHONPATH:path.join(root,'tests/vision_trace')};delete env.ELECTRON_RUN_AS_NODE;delete env.OPENAI_BASE_URL;delete env.LOCO_LIVE_TRACE;
 app=await _electron.launch({executablePath:require('../frontend/node_modules/electron'),args:[`--user-data-dir=${path.join(directory,'read-only-profile')}`,path.join(root,'frontend')],cwd:root,env});page=await app.firstWindow();await page.locator('#connection.connected').waitFor();
 assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isFocusable()),false);await page.locator(`[data-open="${receipt.survey_id}"]`).click();await page.locator('[data-photo-vision]').waitFor();
 for(const element of await page.locator('[data-photo-vision-photo] details summary').all())await element.click();
 const checks=[];
 for(const photo of receipt.vision.photos)for(const [key,item] of Object.entries(photo.observations)){
  const node=page.locator(`[data-photo-vision-photo="${photo.photo_id}"] [data-photo-vision-field="${key}"]`);assert.equal(await node.isVisible(),true);const text=await node.innerText();if(item.value)assert.ok(text.includes(item.value),key);checks.push({photo_id:photo.photo_id,field:key,visible:true,text});
 }
 const visible=await page.locator('[data-photo-vision]').innerText();assert.doesNotMatch(visible,/\b(?:OBSERVED|UNCERTAIN|NOT_VISIBLE|VISION|POSE|USER|SAVED|UNKNOWN)\b/);await page.screenshot({path:path.join(directory,'expanded-stored-observations.png'),fullPage:true});await app.close();app=null;
 const after=(await fs.readFile(path.join(directory,'sdk.jsonl'),'utf8')).split('\n').filter(Boolean).length;assert.equal(after,before,'opening stored results must not request AI');await fs.writeFile(path.join(directory,'expanded-render-audit.json'),JSON.stringify({checks,additional_ai_events:after-before,native_input:false},null,2));console.log(JSON.stringify({visible_fields:checks.length,additional_ai_events:after-before}));
})().catch(async error=>{await app?.close().catch(()=>{});console.error(error.stack);process.exitCode=1;});
