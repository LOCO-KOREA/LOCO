"""Read-only Heavy/Full disagreement report for photos already registered to a task."""
import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ergo.pose import engine
from ergo import pose_contract
from ergo.engine import quick_assess
from ergo.engine.joint_angles import angles
from ergo.engine.images import read_image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('database',type=Path);parser.add_argument('--task',type=int,default=1);parser.add_argument('--output',type=Path,default=ROOT/'.local/pose-comparison/task-photos.json');args=parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT photo_id,metadata_json FROM PHOTO WHERE task_id=? ORDER BY photo_id',(args.task,)).fetchall()
    report=[];seen=set()
    for photo_id,encoded in rows:
        photo=json.loads(encoded);path=Path(photo['file_path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:continue
        seen.add(digest);predictions={}
        for identity in ('mediapipe-heavy','mediapipe-full'):
            selected=pose_contract.for_model(identity);result=engine.process(dict(slot_no=1,photo_id=photo_id),dict(photos=[dict(photo_id=photo_id,file_path=str(path))],settings=dict(pose_model=selected)))
            guess=quick_assess.guess_view(result['points'],selected['confidence_min']) if result['points'] else None
            image=read_image(path);measured=angles(result['points'],guess['forward_direction'],*image.size,selected['confidence_min']) if guess else []
            predictions[identity]=dict(detected=bool(result['points']),point_count=len(result['points']),world_point_count=len(result['world_points']),view_estimate=guess,
                angles={a['side']+'.'+a['angle_code']:a['value_deg'] for a in measured if a['value_deg'] is not None})
        heavy=predictions['mediapipe-heavy']['angles'];full=predictions['mediapipe-full']['angles']
        shared=sorted(set(heavy)&set(full));difference={key:abs((heavy[key]-full[key]+180)%360-180) for key in shared}
        report.append(dict(photo_id=photo_id,sha256=digest,predictions=predictions,shared_2d_angle_count=len(shared),angle_disagreement_deg=difference))
    result=dict(scope='registered task photos; no ground truth, so disagreement is not an accuracy ranking',registered_photo_count=len(rows),unique_image_count=len(seen),photos=report)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(registered_photos=len(rows),unique_images=len(seen),models=['mediapipe-heavy','mediapipe-full'],no_ground_truth=True)))


if __name__=='__main__':main()
