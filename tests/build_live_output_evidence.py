"""Assemble immutable live-run evidence; never change an application's stored inputs."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.live_output_audit import verify

CAMPAIGNS=('live-output-ten-20261023','live-output-ten-postfix-20261023',
           'live-output-final-20261023','live-output-unloaded-final-20261023','live-output-unloaded-explicit-final-20261023')
FINDINGS=[
 ('LIVE-01','하루 시간·연간 일수 등의 Excel 출처/근거 누락','report/input_trace.py, report/plain.py'),
 ('LIVE-02','중량 근거를 같은 조건의 횟수·시간 근거로 잘못 복사','report/input_trace.py, report/plain.py'),
 ('LIVE-03','FOLLOWUP의 유효한 새 값을 질문 단계라는 이유로 무시','service/intake.py, gpt/intake.py, intake/facts.py'),
 ('LIVE-04','겹치지 않아요를 중복으로 오독하여 90+270분 합산 거절','intake/grounding.py'),
 ('LIVE-05','작업 NO일 때 명시한 노출 0을 Excel에서 숨김','report/plain.py'),
 ('LIVE-06','모든 조건 기록 여부를 DB에 저장하고 Excel에서는 누락','report/plain.py'),
 ('LIVE-07','조회 중 파생 별칭 생성으로 revision 변경, 후속 자연어가 AI 호출 전 거절됨','service/intake.py, intake/facts.py'),
 ('LIVE-08','최초 작업명을 소수점에서 끊어 12.5kg를 12로 저장','intake/facts.py'),
 ('LIVE-09','물건 없음의 손잡이 근거 시각이 조회 때마다 바뀌어 DB와 선택 분석이 달라짐','intake/facts.py'),
]

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    destination=ROOT/'.local/live-output-evidence-20261023';destination.mkdir(parents=True,exist_ok=True)
    campaigns=[];ledger=[];latest={};all_folders=[];schemas={}
    for name in CAMPAIGNS:
        campaign=ROOT/'.local'/name
        if not (campaign/'finished.json').exists():raise RuntimeError('Incomplete campaign: '+name)
        summary=dict(name=name,attempted=0,completed=0,cases=[],sdk_requests=0,sdk_responses=0,sdk_errors=0,phases={},models={})
        phases=collections.Counter();models=collections.Counter()
        for folder in sorted(p for p in campaign.iterdir() if p.is_dir() and (p/'receipt.json').exists()):
            verify(folder);receipt=read(folder/'receipt.json');audit=read(folder/'audit.json');all_folders.append(folder)
            for file in folder.glob('*-db.json'):
                schema=read(file)['schema'];digest=hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest()
                schemas.setdefault(digest,dict(schema=schema,checkpoints=[]))['checkpoints'].append(str(file))
            trace=[json.loads(line) for line in (folder/'openai.jsonl').read_text(encoding='utf-8').splitlines()]
            for event in trace:
                if event['kind']=='REQUEST':
                    summary['sdk_requests']+=1;request=event['request'];models[(request['model'],request.get('reasoning',{}).get('effort'))]+=1
                    if request.get('text',{}).get('format',{}).get('name')=='loco_adaptive_intake':phases[json.loads(request['input'][1]['content'])['phase']]+=1
                    else:phases['EXPLANATION']+=1
                elif event['kind']=='RESPONSE':summary['sdk_responses']+=1
                elif event['kind']=='ERROR':summary['sdk_errors']+=1
            row=dict(id=folder.name,completed=bool(receipt.get('completed')),ui_check_count=len(receipt['checks']),
                     ui_failures=receipt['defects'],errors=receipt['errors'],audit_counts=audit['counts'],
                     audit_failures=collections.Counter(d['name'] for d in audit['defects']),path=str(folder))
            summary['cases'].append(row);summary['attempted']+=1;summary['completed']+=row['completed']
            if row['completed'] and not row['ui_failures'] and not row['errors'] and not audit['defects']:latest[folder.name]=row
            ledger.extend(dict(campaign=name,case=folder.name,**entry) for entry in audit['ledger'])
        summary['phases']=dict(phases);summary['models']={model+'/'+str(effort):count for (model,effort),count in models.items()};campaigns.append(summary)
    if len(latest)!=10:raise RuntimeError('Not all ten case types have a clean actual rerun: '+str(sorted(latest)))
    if len(schemas)!=1:raise RuntimeError('Physical schemas differ between captured checkpoints')
    write(destination/'schema-map.json',dict(physical_schema_variants=schemas,
        intake_contracts={name:read(ROOT/'.local'/name/'baseline-intake-contract.json') for name in CAMPAIGNS},
        common_task_input_paths=['TASK.input_json','ANALYSIS.snapshot_json','EXPORT_LOG.snapshot_json.analyses[].snapshot'],
        note='Proposal DTO -> catalogue destination -> common typed TaskInput -> localized Excel cells. These outer schemas are intentionally distinct.'))
    selected_ledger=[entry for entry in ledger if str(ROOT/'.local'/entry['campaign']/entry['case'])==latest[entry['case']]['path']]
    write(destination/'field-ledger-all-runs.json',ledger);write(destination/'field-ledger-latest-passing.json',selected_ledger)
    columns=['campaign','case','export','identity','source','state','value','unit','quote','destination','db_paths','expected_display','cell','actual_value','actual_source','actual_quote','coverage','response_ids','message_ids']
    with (destination/'field-ledger-latest-passing.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns);writer.writeheader()
        for entry in selected_ledger:
            base={k:entry[k] for k in ('campaign','case','export','identity','source','state','value','unit','quote','coverage')}
            base.update(destination=json.dumps(entry['destination'],ensure_ascii=False),db_paths='; '.join(p['path'] for p in entry['projection']),
                        response_ids='; '.join(dict.fromkeys(p['response_id'] or '' for p in entry['lineage']['proposals'])),
                        message_ids='; '.join(dict.fromkeys([(p.get('message_id') or '') for p in entry['lineage']['source_texts']+entry['lineage']['direct_answers']]+[identity for p in entry['lineage']['proposals'] for identity in (p.get('decision') or {}).get('source_message_ids',[])])))
            if not entry['display']:writer.writerow(base)
            for display in entry['display']:
                for cell in display['cells'] or [{}]:writer.writerow(dict(base,expected_display=display['expected'],cell=cell.get('cell'),actual_value=cell.get('value'),actual_source=cell.get('source'),actual_quote=cell.get('quote')))
    # Dedicated backups remain valid independently of WAL checkpointing and the original app profile.
    for folder in all_folders:
        backup=destination/'databases'/folder.parent.name/(folder.name+'.sqlite');backup.parent.mkdir(parents=True,exist_ok=True)
        if backup.exists():backup.unlink()
        with sqlite3.connect('file:'+(folder/'loco.db').as_posix()+'?mode=ro',uri=True) as source,sqlite3.connect(backup) as target:source.backup(target)
    result=dict(source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                source_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                campaigns=campaigns,latest_passing_cases=latest,latest_passing_case_count=len(latest),
                latest_passing_audit_checks=sum(c['audit_counts']['checks'] for c in latest.values()),
                latest_passing_audit_mismatches=0,latest_passing_fact_export_pairs=len(selected_ledger),
                findings=[dict(id=i,description=d,modules=m,status='FIXED_AND_VERIFIED') for i,d,m in FINDINGS],
                schema_note='AI proposal DTO differs from nested TaskInput. Same typed TaskInput fields are compared DB -> AnalysisSnapshot -> ExportSnapshot; Excel formatting is compared by value, unit, condition and provenance.',
                limitation='Latest passing evidence spans documented patch versions, not one final-build ten-run campaign. Source manifests identify every run. Isolated local stack only; no origin/main integration, packaged or deployed proof.')
    write(destination/'summary.json',result)
    lines=['# 실호출 입력·DB·최종 Excel 대조 결과','',
      '최초 10회는 애플리케이션 소스를 변경하지 않고 모두 완료한 뒤 수정했다. 각 입력을 넣기 전에 기록하고 실제 외부 gpt-6-luna/xhigh 원응답, 단계별 SQLite 실물 행, 선택 분석/출력 snapshot과 실제 Excel 셀을 보관했다.',
      '', '| 구분 | 완료/시도 | 실제 SDK 요청/응답 | 출력 파일 |', '|---|---:|---:|---:|']
    for campaign in campaigns:lines.append(f"| {campaign['name']} | {campaign['completed']}/{campaign['attempted']} | {campaign['sdk_requests']}/{campaign['sdk_responses']} | {campaign['completed']*3} |")
    lines+=['','SDK 한 번을 E2E 한 회로 세지 않았다. 각 회차는 초기 자연어→추가 답변→초기 분석/출력→직접 수정→재시작→AI 재호출→최종 분석→실제 AI 설명/수정/적용→UI Excel 저장→과거 분석 재출력→재시작이다.',
      '', '## 확인된 결함과 수정','', '| ID | 결함 | 수정 모듈 |','|---|---|---|']
    lines += [f'| {i} | {d} | {m} |' for i,d,m in FINDINGS]
    lines+=['','## 회차별 대조','', '| 사례 | 최초 불일치 수 | 1차 수정 후 불일치 수 | 마지막 통과 근거 | 마지막 불일치 |','|---|---:|---:|---|---:|']
    for case in campaigns[0]['cases']:
        after=next(c for c in campaigns[1]['cases'] if c['id']==case['id']);selected=latest[case['id']]
        lines.append(f"| {case['id']} | {case['audit_counts']['defects']} | {after['audit_counts']['defects']} | {Path(selected['path']).parent.name} | 0 |")
    lines+=['',f"마지막 통과 근거 10종의 독립 대조 {result['latest_passing_audit_checks']:,}개, 불일치 0개. 값/출력 조합 {len(selected_ledger)}개를 기록했다. 마지막 근거는 수정 단계별 통과 회차의 조합이며, 최종 단일 빌드로 10회를 다시 실행했다는 뜻은 아니다.",
      '', '## 스키마 검증','',
      '- AI 응답은 target/condition/number/text/quote/calculation의 평면 제안 DTO다. DB의 중첩 TaskInput과 같은 JSON 스키마라고 주장하지 않는다.',
      '- 실제 SDK 요청의 strict schema를 당시 계약과 비교하고 raw 응답 타입·필수 키·허용값·계산 피연산자, 제안별 저장/미반영 결정을 대조했다.',
      '- 여섯 실제 테이블을 조회하고 TASK.input_json→ANALYSIS.snapshot_json→EXPORT_LOG.snapshot_json의 공통 입력 필드를 값·타입·조건별로 비교했다. 단순 버전 문자열 비교가 아니다.',
      '- Excel에서는 변환된 표시값, 단위, 조건 행, 출처, 해당 항목의 원문 근거를 실제 셀과 비교했다. 0과 null, 작업별 시간과 하루 전체, 다른 중량의 횟수/시간, 직접 USER 값, 과거 snapshot을 구분했다.',
      '- 사진 후보·연결 보조 메타데이터는 snapshot 보존 항목으로 표시했다. 수락한 조사값처럼 Excel에 표시됐다고 세지 않는다.',
      '', '## 증거 읽기','',
      '- summary.json: 단계별 회차/실제 외부 호출/판정 집계와 마지막 통과 근거 경로.',
      '- field-ledger-latest-passing.csv / .json: 입력 원문·AI 응답 ID·제안 결정·계산 입력 경로·최종 Excel 셀의 대조표. JSON에 원제안과 직접 수정 메시지까지 포함한다.',
      '- 각 원본 폴더의 actions.jsonl은 입력 전에 기록한 원장이다. 원장 순서는 파일 행 번호다. openai.jsonl은 응답을 바꾸지 않은 실제 SDK 기록이며 인증키를 기록하지 않는다.',
      '- *-db.json은 단계별 실제 SQL 조회 결과와 물리 열 정의다. databases/에는 원 DB의 일관된 SQLite backup을 별도로 넣었다.',
      '- 최초 30개 EXPORT_LOG snapshot을 새 파일로 다시 렌더링한 replay는 실제 재호출이 아니다. 저장됐던 값의 표시 보존만 검증하며, 과거에 저장되지 않은 값을 복구했다고 주장하지 않는다.',
      '', '## 시험 보정과 범위','',
      '- 최초 03의 누락 값 뒤 driver 직접 입력/화면 상태 동기화는 harness-recovery.json에 기록했다. 그때 앱 코드는 변경하지 않았으며 360분 추출 결함은 그대로 남겨 검출했다.',
      '- 최초 08의 load=UNLOADED 기대는 미는 힘까지 배제하지 않은 문장을 과도하게 해석한 시험 오류였다. 원본 입력/기대/파일은 보존하고 oracle-review.json에 정정했다.',
      '- 무하중 근거 시각 반례의 최종 집중 시험은 원문 08에 미는/당기는 힘도 없다는 문장을 명시적으로 추가했다. 실제 AI가 load=UNLOADED를 저장한 상태에서 반복 조회·분석·Excel·재시작을 검증하며 원래 08과 구분한다.',
      '- 수정 후 06은 추가 답변이 실제 AI 호출 전 거절되어 실패했다. 08은 조회에 의한 근거 시각/revision 변화를 검출했다. 이 실패를 보존하고 해당 사례를 수정 후 다시 실호출했다.',
      '- 추가 근거 없음/사진 소유권 불명/최신 USER 충돌은 원문·원제안·진단을 보존한다. 늦었다는 이유의 유효기간은 추가하지 않았다.',
      '- 화면 밖·초점 불가 Electron/실제 Python/격리 SQLite/실제 MediaPipe Heavy/실제 외부 AI/실제 Excel이다. 파일 선택/저장 dialog만 시험 경로로 대체했다. 사용자 마우스·키보드를 조작하지 않았다.',
      '- origin/main의 최신 Excel/크롭/질문 화면 통합, 배포본, 실제 현장 정확도는 이 결과에 포함하지 않는다. PR·push·main merge·배포는 수행하지 않았다.', '']
    (destination/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    with zipfile.ZipFile(destination/'final-excel-10-cases.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for case,entry in sorted(latest.items()):bundle.write(Path(entry['path'])/'final-output.xlsx',case+'.xlsx')
        bundle.write(destination/'field-ledger-latest-passing.csv','field-ledger.csv')
        bundle.writestr('README.txt','Ten case types, latest passing final exports. Evidence spans the patch versions and explicit unloaded variant described in REPORT.md. See the full evidence archive for original failures, DB backups and raw AI traces.')
    # Include source runs without Chromium caches or unrelated local data.
    archive=destination/'live-output-evidence.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for campaign in [ROOT/'.local'/name for name in (*CAMPAIGNS,'live-output-ten-replayed-20261023')]:
            for file in campaign.rglob('*'):
                if file.is_file() and 'profile' not in file.relative_to(campaign).parts and file.suffix in ('.json','.jsonl','.xlsx','.png'):
                    bundle.write(file,Path('runs')/file.relative_to(ROOT/'.local'))
        for file in destination.rglob('*'):
            if file.is_file() and file!=archive and file.name!='archive-sha256.json':bundle.write(file,Path('evidence')/file.relative_to(destination))
        for file in (ROOT.parent/'origin-main-audit').glob('live-output*.log'):bundle.write(file,Path('checks')/file.name)
    write(destination/'archive-sha256.json',dict(file=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    print(json.dumps(dict(campaigns=len(campaigns),journeys=sum(c['completed'] for c in campaigns),last_passing=10,checks=result['latest_passing_audit_checks'],mismatches=0,archive=str(archive)),ensure_ascii=False))

if __name__=='__main__':main()
