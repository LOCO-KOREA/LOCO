# LOCO 데스크톱 프로그램 샘플

> 안내 개정 2.0 · 2026-10-15 · 정식 앱 완성 목표 2026-10-23(Asia/Seoul)

이 폴더는 이전 문서 1.5를 바탕으로 만든 독립 샘플이며 계산 DTO·보고서는 1.3이다. 새로운 정본은 [요구사항](../../docs/requirements.md), [기능정의서](../../docs/기능정의서.md), [API 계약서](../../docs/API_계약서.md)다. 이 안내는 샘플을 일반 작업 2.0으로 개조했다는 뜻이 아니다.

정식 앱에서는 상자 들기도 다른 작업과 같은 직접입력·가변 사진·관찰 하중 흐름을 사용한다. 샘플에 남은 15슬롯·3회차·5순간·사건별 하중·20종 시간·영문 1.3 출력은 이전 동작을 읽는 참고용이며 새 구현의 요구사항이 아니다.

## 기존 샘플 실행

Node.js 22.12 이상/npm과 CPython 3.12 x64가 있는 Windows PowerShell에서 저장소 루트 기준으로 실행한다.

~~~powershell
cd samples/desktop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-inference.txt
.\start.ps1 -ModelPath "C:\models\movenet_lightning_float16_v4.tflite"
~~~

모델은 실제 경로로 바꾸고 Git에 포함하지 않는다. start.ps1은 필요하면 Electron 의존성을 설치하고 이 폴더의 .venv를 우선 사용한다. -PythonPath/LOCO_PYTHON으로 Python을, -ModelPath/LOCO_MOVENET_MODEL로 모델을 지정할 수 있다.

샘플 DB 기본은 이 폴더의 loco_sample.db이며 LOCO_SAMPLE_DB로 변경한다. 정식 사용 자료와 섞지 않는다. 원본 사진은 경로만 참조하고 수정·삭제하지 않는다. Excel은 선택한 경로에 만든다.

정식 공통 서비스의 개발 실행은 저장소 루트 [README](../../README.md)의 run-integrated.ps1 안내를 따른다. 이 샘플의 backend/server.py와 공통 ergo/service/json_lines.py를 같은 구현으로 간주하지 않는다.

## 코드에서 확인할 수 있는 범위와 한계

| 영역 | 이전 샘플 코드 | 2.0에서 바꿀 부분 |
|---|---|---|
| 조사/작업 | CRUD·기존 조건·11개 기준 | 일반 작업·조건별 행·15종 시간 |
| 사진 | EXIF 미리보기·고정 15슬롯·관찰·진행/취소 | 가변 대상·사진별 일반 촬영조건/하중 |
| 자세/REBA | 관절·각도·6후보·수동입력·표 A/B/C | 범위/분모·불명 하중·상태 계약 대조 |
| 기준/검토 | 초안·근거·조사자 결론 | 적격 행·망라성·합집합·해석 사유 |
| 출력 | 1.3의 SUMMARY 등 4시트 | 2.0 한글 4시트·전후 비교 |
| GPT | 고정 대체 설명·수정·적용 | 실제 API·허용 요약·실패 처리·현재성 |
| 안내 위젯 | docs/ui/loco-guide.js 로드 | 다음 입력 연결과 상태 일치 |

위 표는 소스 구성 설명이며 동작 정확성·완성의 증거가 아니다. 이전 보고의 한 장 추론 결과나 실행 기록은 해당 환경의 제한된 주장으로 보고, 이번 문서 개정에서 재현·수용한 것으로 표현하지 않는다.

## MoveNet와 데이터

전처리 EXIF_OPENCV_LETTERBOX_V2는 Pillow EXIF/RGB → 원본 크기 검정 정방형 패딩 → OpenCV INTER_LINEAR 192×192 → 원본 픽셀 좌표 역변환이다. 홀수 여분은 아래/오른쪽에 둔다. 모델은 singlepose Lightning TFLite float16 v4 계열의 192×192 입력을 사용한다.

requirements-inference.txt는 기본 이미지/Excel 패키지와 LiteRT 2.3.0·OpenCV를 설치한다. 모델·런타임이 없으면 MODEL_ERROR이며 임의 좌표를 성공값으로 만들지 않는다. 좌표가 나와도 촬영조건·법적 해당·목/손목 각도 정확성이 확인된 것은 아니다.

이전 분석은 당시 전처리·규칙으로 읽는다. 새 분석에서 모델/전처리를 바꾸면 자동 후보 적용값만 재확인하고 직접 관찰값은 보존하는 것이 2.0 계약이다. 샘플의 실제 동작도 별도 검증 없이 이 계약을 만족한다고 주장하지 않는다.

DB는 기존 ergo/db의 여섯 테이블 구조를 사용한다. 모델·가상환경·DB·사진·출력물을 Git에 추가하지 않는다. 통합 시 샘플 backend에 대한 공통 모듈의 의존성을 만들지 않는다.

## 정식 앱으로 가져올 때

소스의 필요한 부분만 base/ancestry·변경 범위·의존성을 확인해 포팅한다. 특히 혼합 중량, 합집합 누락, null/0, 사진 재연결 보존, 계산과 AI 편집의 부분 저장, 지연 완료, 출력 snapshot 일치를 독립 검증한다.

이전 테스트 금지 문구는 폐기했다. 현재 [AGENTS.md](../../AGENTS.md)와 요구사항의 정상·실패·경계·반례 검증을 따른다. 샘플의 초록 시험이나 완료 보고만으로 수용하지 않는다. 2.0 구현·검증·배포의 담당과 10월 23일 일정은 정본을 따른다.
