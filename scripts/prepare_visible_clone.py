"""Copy an existing SQLite survey read-only; relocate only current PHOTO files."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys


def prepare(source_directory, destination_directory):
    source=Path(source_directory).resolve()
    destination=Path(destination_directory).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    media=destination/'media';media.mkdir()
    with sqlite3.connect((source/'loco.db').as_uri()+'?mode=ro',uri=True) as original:
        with sqlite3.connect(destination/'loco.db') as clone:
            original.backup(clone)
            snapshots=list(clone.execute('select analysis_id,snapshot_json from ANALYSIS'))
            copied=[]
            for photo_id,raw in clone.execute('select photo_id,metadata_json from PHOTO').fetchall():
                metadata=json.loads(raw);old=Path(metadata['file_path']).resolve()
                try:relative=old.relative_to((source/'media').resolve())
                except ValueError:relative=Path('photo-'+str(photo_id)+old.suffix)
                target=media/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(old,target)
                before=hashlib.sha256(old.read_bytes()).hexdigest()
                after=hashlib.sha256(target.read_bytes()).hexdigest()
                if before!=after:raise ValueError('사진 복사 결과가 원본과 다릅니다.')
                metadata['file_path']=str(target)
                clone.execute('update PHOTO set metadata_json=? where photo_id=?',(json.dumps(metadata,ensure_ascii=False),photo_id))
                copied.append(dict(photo_id=photo_id,source=str(old),destination=str(target),sha256=after))
            clone.commit()
            if snapshots!=list(clone.execute('select analysis_id,snapshot_json from ANALYSIS')):
                raise ValueError('기존 분석 기록이 달라졌습니다.')
            if clone.execute('pragma quick_check').fetchone()[0]!='ok':raise ValueError('복사한 DB를 확인해 주세요.')
            tables=[row[0] for row in clone.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
            counts={name:clone.execute('select count(*) from "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
    receipt=dict(source=str(source),destination=str(destination),source_opened_read_only=True,
        source_app_stopped=False,original_analysis_snapshots_unchanged=True,
        current_photo_paths_relocated=True,photos=copied,table_counts=counts)
    (destination/'clone-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return receipt


if __name__=='__main__':
    result=prepare(sys.argv[1],sys.argv[2])
    print(json.dumps(dict(destination=result['destination'],photos=len(result['photos']),tables=result['table_counts']),ensure_ascii=True))
