"""Read-only comparison of recorded runtime hashes, current disk and immutable Git blobs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

def git(root,*args):return subprocess.check_output(['git',*args],cwd=root)
def sha(value):return hashlib.sha256(value).hexdigest()
def main(root,output,campaigns):
    if output.exists():raise ValueError('Fresh independent output required')
    output.mkdir(parents=True);head=git(root,'rev-parse','HEAD').decode().strip()
    names=git(root,'ls-files','-z','--cached','backend','frontend').decode().split('\0');names=[name for name in names if name]
    blobs={name:git(root,'show',head+':'+name) for name in names};tracked={name:sha(value) for name,value in blobs.items()};disk={name:sha((root/name).read_bytes()) for name in names}
    manifests=[];checks=[]
    def check(name,expected,actual):checks.append(dict(name=name,expected=expected,actual=actual,pass_=expected==actual))
    raw_mismatches={name:dict(git=tracked[name],disk=disk[name],git_crlf=blobs[name].count(b'\r\n'),disk_crlf=(root/name).read_bytes().count(b'\r\n'),exact_lf_to_crlf=(root/name).read_bytes()==blobs[name].replace(b'\n',b'\r\n')) for name in names if disk[name]!=tracked[name]}
    check('every raw Git/disk difference is exactly LF to CRLF, without other byte changes',{}, {name:row for name,row in raw_mismatches.items() if not row['exact_lf_to_crlf']})
    for campaign in campaigns:
        path=campaign/'application-source-manifest.json';raw=path.read_bytes();manifest=json.loads(raw);files=manifest['files'];shutil.copy2(path,output/(campaign.name+'-manifest.json'))
        check(campaign.name+' exact tracked application file membership',sorted(tracked),sorted(files))
        check(campaign.name+' every recorded file equals final Git bytes or its exact LF-to-CRLF serialization',{}, {name:dict(recorded=value,git=tracked.get(name)) for name,value in files.items() if value not in (tracked.get(name),sha(blobs[name].replace(b'\n',b'\r\n')) if name in blobs else None)})
        check(campaign.name+' every recorded runtime file hash equals current disk',{}, {name:dict(recorded=value,disk=sha((root/name).read_bytes()) if (root/name).is_file() else None) for name,value in files.items() if not (root/name).is_file() or sha((root/name).read_bytes())!=value})
        manifests.append(dict(campaign=str(campaign),recorded_baseline=manifest['baseline'],raw_manifest_sha256=sha(raw),application_file_count=len(files),application_hash=sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode()),files=files))
    if len(manifests)>1:check('all campaigns used byte-identical complete application file maps',True,all(item['files']==manifests[0]['files'] for item in manifests[1:]))
    result=dict(final_head=head,scope='all tracked backend/frontend bytes; runtime dependencies/models and tests are separate evidence',raw_git_disk_differences=raw_mismatches,checks=checks,defects=[row for row in checks if not row['pass_']],campaigns=manifests)
    (output/'application-source-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(head=head,files=len(names),checks=len(checks),defects=len(result['defects']),application_hash=manifests[0]['application_hash'])))
    if result['defects']:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('output',type=Path);parser.add_argument('campaigns',type=Path,nargs='+');args=parser.parse_args();main(args.root.resolve(),args.output.resolve(),[path.resolve() for path in args.campaigns])
