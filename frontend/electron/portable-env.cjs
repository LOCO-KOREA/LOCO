const {readFileSync} = require('node:fs');
const {join,resolve} = require('node:path');
const ALLOWED = new Set(['OPENAI_API_KEY','OPENAI_BASE_URL','LOCO_AI_MODEL',
  'LOCO_AI_REASONING_EFFORT','LOCO_AI_MAX_OUTPUT_TOKENS','LOCO_DB_PATH',
  'LOCO_POSE_MODEL_ID','LOCO_POSE_MODEL_PATH','LOCO_POSE_MODEL_SHA256',
  'LOCO_POSE_CONFIDENCE_MIN','LOCO_POSE_DETECTION_MIN','LOCO_POSE_PRESENCE_MIN']);

function loadPortableEnv({directory,env=process.env}) {
  let source;
  try { source=readFileSync(join(directory,'loco.env'),'utf8'); }
  catch(error) { if(error.code==='ENOENT')return; throw new Error('loco.env 파일을 읽지 못했어요. 파일 권한을 확인해 주세요.'); }
  const values={};
  for(const [index,line] of source.replace(/^\uFEFF/,'').split(/\r?\n/).entries()) {
    const text=line.trim();
    if(!text||text.startsWith('#'))continue;
    const match=/^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/.exec(text);
    if(!match||!ALLOWED.has(match[1]))throw new Error(`loco.env ${index+1}번째 줄의 변수 이름·형식을 확인해 주세요.`);
    let value=match[2].trim();
    if(value.startsWith('"')||value.startsWith("'")) {
      const quote=value[0],end=value.indexOf(quote,1);
      if(end<0||!/^\s*(#.*)?$/.test(value.slice(end+1)))throw new Error(`loco.env ${index+1}번째 줄의 따옴표를 확인해 주세요.`);
      value=value.slice(1,end);
    } else value=value.replace(/\s+#.*$/,'').trim();
    if(value)values[match[1]]=value;
  }
  for(const [key,value] of Object.entries(values)) {
    if(env[key]!==undefined)continue; // Explicit process/Windows environment wins.
    env[key]=key==='LOCO_DB_PATH'&&value!==':memory:'?resolve(directory,value):value;
  }
}
module.exports={loadPortableEnv};
