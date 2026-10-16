/* Validate the actual Electron page and its local assets; no static mock build. */
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),front=path.join(root,'frontend');
const html=fs.readFileSync(path.join(front,'desktop.html'),'utf8');
for(const match of html.matchAll(/(?:src|href)="([^"]+)"/g)){
 const ref=match[1];if(/^(?:https?:|data:|#)/.test(ref))continue;
 if(!fs.existsSync(path.resolve(front,ref)))throw Error('Missing desktop asset: '+ref);
}
function check(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
 if(['node_modules','.local'].includes(entry.name))continue;
 const file=path.join(dir,entry.name);
 if(entry.isDirectory()){check(file);continue;}
 if(!/\.(?:js|cjs)$/.test(file))continue;
 const result=spawnSync(process.execPath,['--check',file],{encoding:'utf8'});
 if(result.status!==0)throw Error(result.stderr);
 for(const match of fs.readFileSync(file,'utf8').matchAll(/from\s+['"](\.[^'"]+)['"]/g))if(!fs.existsSync(path.resolve(dir,match[1])))throw Error('Missing module: '+match[1]);
}}
check(front);
console.log('PASS actual Electron page assets and JavaScript syntax');
