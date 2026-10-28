const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {loadPortableEnv}=require('../frontend/electron/portable-env.cjs');
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'loco-env-')),file=path.join(directory,'loco.env');
try {
 const absent={};loadPortableEnv({directory,env:absent});assert.deepEqual(absent,{});
 fs.writeFileSync(file,'\uFEFF# 설정\r\nOPENAI_API_KEY="test-only-key"\r\nOPENAI_BASE_URL="https://example.invalid/v1#part" # comment\r\nLOCO_AI_MODEL=gpt-6-luna\r\nLOCO_DB_PATH=data/한글.db\r\nLOCO_POSE_MODEL_ID=mediapipe-heavy\r\n');
 const env={OPENAI_API_KEY:'existing-process-key'};loadPortableEnv({directory,env});
 assert.equal(env.OPENAI_API_KEY,'existing-process-key');assert.equal(env.OPENAI_BASE_URL,'https://example.invalid/v1#part');assert.equal(env.LOCO_DB_PATH,path.join(directory,'data','한글.db'));assert.equal(env.LOCO_POSE_MODEL_ID,'mediapipe-heavy');
 fs.writeFileSync(file,'OPENAI_API_KEY=\nOPENAI_BASE_URL=\n');const blank={};loadPortableEnv({directory,env:blank});assert.deepEqual(blank,{});
 fs.writeFileSync(file,'OPENAI_API_KEY=test-only-key\nNODE_OPTIONS=secret-never-log\n');const invalid={};assert.throws(()=>loadPortableEnv({directory,env:invalid}),error=>!error.message.includes('secret-never-log')&&error.message.includes('2번째'));assert.deepEqual(invalid,{});
 fs.writeFileSync(file,'OPENAI_API_KEY="private-test-value\n');assert.throws(()=>loadPortableEnv({directory,env:{}}),error=>!error.message.includes('private-test-value'));
 console.log('PASS portable env optional/blank/BOM/quoted values, Windows priority, relative DB paths, atomic errors and redacted diagnostics');
} finally {if(fs.existsSync(file))fs.unlinkSync(file);fs.rmdirSync(directory);}
