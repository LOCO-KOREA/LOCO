"""Small reproducible Heavy/Full comparison against published COCO-format annotations.

Person crops use annotated bounding boxes: this tests pose inference with a supplied
person region, not autonomous worker detection or industrial/3D accuracy.
"""
import argparse
import hashlib
import json
import math
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ergo import pose_contract as contract
from ergo.pose import engine
from ergo.engine.joint_angles import angles

SOURCE='https://raw.githubusercontent.com/open-mmlab/mmpose/main/tests/data/coco/'
SOURCES={'test_coco.json':'6dbaa1cc67f0bbe7a761abbaeb7e639c91aacbfc7e34dba146352303a528628f',
 '000000000785.jpg':'83981537a7baeafbeb9c8cb67b3484dc26433f574b3685d021fa537e277e4726',
 '000000040083.jpg':'89b9c3771c9428e0e25134cde9bc0a962318a477d267ef47f8e1872526207da7',
 '000000196141.jpg':'8e66c7dd60fe81fb0eae99314eb5e6c191e53f739760fa36ae7ba56f10115814',
 '000000197388.jpg':'dec0fbb931cb609bf481e56b89cd2fbbab79839f22832c3bbe69a8fae2769cdd'}


def acquire(folder):
    folder.mkdir(parents=True,exist_ok=True)
    for name,digest in SOURCES.items():
        path=folder/name
        if not path.exists():path.write_bytes(urllib.request.urlopen(SOURCE+name,timeout=45).read())
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Comparison fixture changed: '+name)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=ROOT/'.local/pose-comparison');parser.add_argument('--repeats',type=int,default=3);args=parser.parse_args()
    folder=args.directory;acquire(folder);data=json.loads((folder/'test_coco.json').read_text())
    images={i['id']:i for i in data['images']};samples=[]
    for annotation in data['annotations']:
        raw=annotation['keypoints'];visible=sum(raw[i]==2 for i in range(2,len(raw),3))
        if visible<6:continue
        image_info=images[annotation['image_id']];image=Image.open(folder/image_info['file_name']).convert('RGB')
        x,y,w,h=annotation['bbox'];padding=0.1*max(w,h)
        box=(max(0,int(x-padding)),max(0,int(y-padding)),min(image.width,math.ceil(x+w+padding)),min(image.height,math.ceil(y+h+padding)))
        crop=image.crop(box);path=folder/f"person-{annotation['id']}.png";crop.save(path)
        truth=[dict(point_no=i,name=n,x_px=raw[3*i]-box[0],y_px=raw[3*i+1]-box[1],confidence=1.0 if raw[3*i+2]==2 else 0.0) for i,n in enumerate(contract.COCO_NAMES)]
        samples.append(dict(annotation_id=annotation['id'],image_id=image_info['id'],file=path,box=box,normalizer=math.hypot(w,h),truth=truth))
    rows=[];summaries=[]
    for identity in ('mediapipe-heavy','mediapipe-full'):
        settings=contract.for_model(identity);errors=[];angle_errors=[];latencies=[];visible_total=hits=detected=0;model_rows=[]
        for sample in samples:
            slot=dict(slot_no=1,photo_id=1,camera_side='RIGHT',forward_direction='SCREEN_RIGHT',side_view_verified='YES',observation=dict(single_person='YES',full_frame='YES',normal_work='YES'))
            snapshot=dict(photos=[dict(photo_id=1,file_path=str(sample['file']))],settings=dict(pose_model=settings))
            start=time.perf_counter();result=engine.process(slot,snapshot);cold_ms=(time.perf_counter()-start)*1000
            if result['status']=='ERROR':raise RuntimeError(str(result['diagnostics']))
            for _ in range(args.repeats):
                start=time.perf_counter();result=engine.process(slot,snapshot);latencies.append((time.perf_counter()-start)*1000)
            points={p['name']:p for p in result['points']};found=bool(points);detected+=found
            local_errors=[];local_hits=0;sample_angles={}
            for truth in sample['truth']:
                if truth['confidence']!=1:continue
                visible_total+=1;point=points.get(truth['name'])
                if point:
                    distance=math.hypot(point['x_px']-truth['x_px'],point['y_px']-truth['y_px']);errors.append(distance);local_errors.append(distance)
                    good=distance<=0.1*sample['normalizer'];hits+=good;local_hits+=good
            image=Image.open(sample['file']);truth_angles=angles(sample['truth'],'SCREEN_RIGHT',image.width,image.height,0.5)
            reference={(a['side'],a['angle_code']):a['value_deg'] for a in truth_angles if a['value_deg'] is not None}
            for angle in result['angles']:
                key=(angle['side'],angle['angle_code'])
                if key in reference and angle['value_deg'] is not None:
                    difference=abs((angle['value_deg']-reference[key]+180)%360-180);angle_errors.append(difference);sample_angles[angle['side']+'.'+angle['angle_code']]=difference
            # Labeled points and predictions are drawn as distinct colors for human inspection.
            canvas=image.copy();draw=ImageDraw.Draw(canvas)
            for group,color in ((sample['truth'],'#00c853'),(result['points'],'#e53935')):
                for point in group:
                    if point['confidence']<0.5:continue
                    x,y=point['x_px'],point['y_px'];draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
            canvas.save(folder/f"{identity}-{sample['annotation_id']}.png")
            row=dict(model=identity,annotation_id=sample['annotation_id'],image_id=sample['image_id'],detected=found,visible_points=sum(p['confidence']==1 for p in sample['truth']),pck_hits=local_hits,
                     angle_errors=sample_angles,mean_pixel_error=statistics.mean(local_errors) if local_errors else None,first_call_ms=cold_ms,points=result['points'],world_angles=result['world_angles'])
            rows.append(row);model_rows.append(row)
        summary=dict(model=identity,samples=len(samples),detected=detected,visible_ground_truth_points=visible_total,pck_bbox_diagonal_10pct=hits/visible_total,
                     mean_pixel_error_detected=statistics.mean(errors) if errors else None,mean_2d_angle_error_deg=statistics.mean(angle_errors) if angle_errors else None,
                     compared_angles=len(angle_errors),median_warm_ms=statistics.median(latencies),artifact=contract.MODELS[identity]['model_sha256'])
        summaries.append(summary);print(json.dumps(summary),flush=True)
    # Whole-image detection is reported separately; GT crops above are not presented as autonomous detection.
    full_frames=[]
    for info in data['images']:
        for identity in ('mediapipe-heavy','mediapipe-full'):
            result=engine.process(dict(slot_no=1,photo_id=1),dict(photos=[dict(photo_id=1,file_path=str(folder/info['file_name']))],settings=dict(pose_model=contract.for_model(identity))))
            full_frames.append(dict(image_id=info['id'],model=identity,detected=bool(result['points']),point_count=len(result['points']),diagnostics=result['diagnostics']))
    paired={summary['model']:[] for summary in summaries}
    by_sample={}
    for row in rows:by_sample.setdefault(row['annotation_id'],{})[row['model']]=row['angle_errors']
    for sample in by_sample.values():
        common=set.intersection(*(set(a) for a in sample.values()))
        for model,errors in sample.items():paired[model].extend(errors[k] for k in common)
    for summary in summaries:
        matches=paired[summary['model']];summary['matched_angle_count']=len(matches);summary['matched_angle_mae_deg']=statistics.mean(matches) if matches else None
    report=dict(scope='4 public COCO-format fixture images; annotated person crops; not an industrial or 3D accuracy benchmark',
                sources={k:dict(url=SOURCE+k,sha256=v) for k,v in SOURCES.items()},licenses=data.get('licenses'),
                method=dict(visible_ground_truth='COCO visibility=2',crop='annotated bbox plus 10 percent max dimension padding',pck='Euclidean pixel error <= 0.1 * original annotated bbox diagonal; misses count as incorrect',
                            angle_error='2D segment angle difference on annotated visible triples; conditional on detected usable joints',colors=dict(green='published ground truth',red='model prediction')),
                summaries=summaries,person_results=rows,whole_images=full_frames)
    (folder/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
