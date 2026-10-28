// Uses only get_settings; the placeholder key is never sent to an external API.
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {_electron}=require(process.env.LOCO_PLAYWRIGHT_PATH||'../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'..');
const pkg=process.env.LOCO_VERIFY_PACKAGE||fs.readFileSync(path.join(root,'.local/latest-package.txt'),'utf8').trim();
const config=path.join(pkg,'loco.env'),original=fs.readFileSync(config);
assert.ok(original.equals(fs.readFileSync(path.join(root,'scripts/portable/loco.env.example'))),'only a fresh package with an unchanged empty template may be tested');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'loco-portable-config-'));
(async()=>{
 try {
  for(const configured of [true,false]) {
   fs.writeFileSync(config,configured?'OPENAI_API_KEY=placeholder-not-a-real-key\nLOCO_AI_MODEL=portable-config-test-model\nLOCO_AI_REASONING_EFFORT=medium\nLOCO_POSE_MODEL_ID=mediapipe-heavy\n':original);
   const env={...process.env};for(const key of Object.keys(env))if(key.startsWith('OPENAI_')||key.startsWith('LOCO_AI_')||key.startsWith('LOCO_POSE_'))delete env[key];
   delete env.ELECTRON_RUN_AS_NODE;
   env.LOCO_HIDDEN='1';env.LOCO_DB_PATH=path.join(temp,configured?'configured.db':'blank.db');
   env.PATH=(env.SystemRoot||'C:\\Windows')+'\\System32;'+(env.SystemRoot||'C:\\Windows');
   const app=await _electron.launch({executablePath:path.join(pkg,'LOCO.exe'),args:['--user-data-dir='+path.join(temp,configured?'profile-one':'profile-two')],cwd:temp,env,timeout:60000});
   try {
    const page=await app.firstWindow();await page.locator('#connection.connected').waitFor({timeout:60000});
    const response=await page.evaluate(()=>window.loco.call('get_settings',{}));assert.equal(response.ok,true);
    const s=response.value;assert.equal(s.gpt_key_present,configured);assert.equal(s.analysis.pose_model.provider,'mediapipe');assert.equal(s.analysis.pose_model.point_count,33);
    assert.ok(!JSON.stringify(s).includes('placeholder-not-a-real-key'),'the key must never reach the renderer');
    if(configured){assert.equal(s.gpt_model,'portable-config-test-model');assert.equal(s.gpt_reasoning_effort,'medium');}
    console.log('PASS packaged EXE, isolated DB, no Python/Node PATH, '+(configured?'loco.env loaded without exposing key':'blank key/local startup'));
   } finally {await app.close();}
  }
 } finally {fs.writeFileSync(config,original);}
})().catch(error=>{console.error(error);process.exitCode=1;});
