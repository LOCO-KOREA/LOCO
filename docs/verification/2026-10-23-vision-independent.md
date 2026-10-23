# 사진 실호출과 저장·출력 독립 검증 · 2026-10-23

## 검증 범위

기존 12개 작업 조합과 새 이미지 관찰은 별개 실행이다. c886과 같은 앱 내용의 기존 실제 12사례는 최초 선언값 115개, DB/Excel 30,176개, 회차 확장 원장 1,626개, 조건 결합 114개, 종료 물리 DB 36개를 대조해 불일치가 없었다. 실제 Luna 요청/응답은 84/84, xhigh이며 실패한 환경 시도는 통과로 세지 않았다. 자세한 경계는 `2026-10-23-final12-independent.md`와 그 원본 증거를 따른다. 이 12개는 새 이미지 관찰을 포함한 실행이 아니다.

새 사진 관찰은 실제 작업 사진을 UI에서 선택·크롭하고 실제 Luna 이미지 입력을 호출한다. 관절 측정은 unpatched MediaPipe Heavy, 데이터는 격리 SQLite, 창은 화면 밖이며 focusable=false다. OS 마우스·키보드는 사용하지 않았다. test provider로 대체한 단위 반례와 실제 외부 호출을 구분한다.

## f909714 실제 3사진 실행

`LOCO-vision-e2e-20261023/.local/vision-live-f909714-r1`에 원본 증거를 보존했다. 감사 tree의 merge HEAD는 81a1ec2지만 ergo/frontend 내용은 f909714와 Git diff 0이며 시작/종료 manifest가 같다. 이 소스를 마지막 후속 소스로 표현하지 않는다.

| 실제 사진 | 실제 반환된 관찰 |
|---|---|
| 정면에서 상자를 잡은 모습 | 몸통 앞숙임, 상자가 가린 무릎은 NOT_VISIBLE |
| 측면에서 상자를 잡고 몸통·무릎을 굽힌 모습 | 몸통 앞기울임과 두 무릎 굽힘 OBSERVED |
| 같은 측면 원본의 상체 크롭 | 몸통 앞숙임, 프레임 밖/가린 무릎은 UNCERTAIN |

이는 해당 세 사진에서 반환한 관찰이다. 확신도를 측정 정확도로 표현하거나 정밀 각도·무게·힘·하루 노출시간·횟수를 사진에서 추정한 결과가 아니다.

실제 SDK 요청/응답은 5/5, 오류 0이며 사진 요청 3개와 기존 텍스트 처리 2개다. 모두 gpt-6-luna/xhigh였다. 각 등록 크롭 PNG의 SHA256, 인코딩 JPEG SHA256, 실제 `input_image` data URI의 SHA256·바이트 수, 실제 응답 ID가 연결된다. SDK의 원래 kwargs는 그대로 전송했고 기록기만 이미지 bytes 대신 해시를 남겼다. base64를 로그나 DB에 복제하지 않았다.

- 실제 UI 등록·크롭→관찰→반복 조회→불변 분석→간편 Excel→재시작: 34개 검사 통과.
- 물리 TASK/ANALYSIS/EXPORT_LOG와 실제 ‘AI 사진 관찰’ 27행의 사진·항목·값·근거·확인할 부분: 142개 검사 통과.
- 저장된 결과 화면을 다시 열어 27개 관찰 항목을 전부 펼쳐 표시·원문 일치를 확인했으며 추가 AI 호출은 0이다.
- 3회 조회와 재시작에서 관찰/입력 revision을 보존했다. 사용자 출력에 내부 status/source, 응답 ID와 image data URI가 없었다.

증거 파일은 `receipt.json`, `output-audit.json`, `external-image-audit.json`, `sdk.jsonl`, `expanded-render-audit.json`, `observations.png`, `expanded-stored-observations.png`, `vision.xlsx`다. `sdk.jsonl`은 이미지 바이트를 제외한 실제 SDK 기록이며 인위적으로 만든 응답이 아니다.

## 후속 소유권 회귀

c4217e9의 등록 UUID·사용자 context=NO 우선권을 별도 적용한 감사 tree에서 backend vision 13개, 등록 세대 3개, 독립 소유권 5개가 통과했다. 독립 5개는 pending 중 USER 모름, 같은 photo_id의 파일 교체, 사진 삭제, 같은 SQLite ID/경로/바이트/view의 재등록, context NO→YES 캐시 재사용과 USER 모름 보존이다. 지연된 원 관찰은 history에 남기고 현재 사진·사람의 값을 덮지 않았다. 이 회귀의 사진/모델 응답은 합성 fixture이며 외부 Luna 5회 요청에 합산하지 않는다.

독립 반례에서 발견한 비정상 provider 수치(inf)의 IPC 직렬화 실패와 삭제된 저장 view의 암묵 복원 실패는 backend99a5b38에서 수리했고 실제 서비스 회귀로 재확인했다.

## 최종 e8ded39 실제 3사진 재검증

등록 세대 UUID, 현재 사용자 원문 우선권, 작업과 무관하다는 답변의 계산 제외, 해당 상태의 화면 안내까지 반영한 `e8ded39bc2cadd909c9f0c3aef520fdf7a85f610` 앱 내용으로 새 DB·프로필에서 다시 실행했다. 증거는 `LOCO-vision-e2e-20261023/.local/vision-live-final-e8ded39-r1`이며 앞선 f909714 실행을 덮어쓰지 않았다.

실행 tree HEAD는 부모 소스를 병합한 `ceb9d8fba306d9b84f1d378f027a130a19e50afb`다. 시작 manifest의 앱 파일 168개와 종료 파일 SHA256이 전부 같고, 실행한 168개 파일은 Git e8ded39 원본 bytes와 전부 같다. 부모 통합 tree(02de7d3)의 앱 내용도 같다. 부모 디스크 파일과는 164개 bytes가 같고 4개 파일만 LF/CRLF 직렬화 차이가 있다. 차이 목록은 `external-image-audit.json`에 남겼고 개행을 제외한 내용 차이는 0개다. 따라서 서로 다른 HEAD 이름을 근거로 소스가 같다고 가정하지 않았다.

최신 main `a7ba406` 계열의 `frontend/photo-crop.js`와 `frontend/photo-workspace.js`는 최종 Git 소스와 bytes가 같다. 실제 UI에서 정면·측면 원본과 상체 부분 크롭을 각각 등록했고 원본 이미지 파일 SHA256은 보존됐다. 등록된 크롭 bytes의 SHA256 → 이미지 인코딩 JPEG SHA256 → 실제 SDK `input_image` SHA256 → 해당 응답 ID → 사진별 저장 기록을 모두 대조했다.

| 최종 실행 검사 | 실제 결과 |
|---|---|
| UI 등록·크롭·관찰·반복 조회·분석·Excel·재시작 | 34/34 통과 |
| 실제 외부 SDK 요청 / 응답 / 오류 | 5 / 5 / 0 |
| 실제 이미지 입력 | 서로 다른 JPEG payload 3개 |
| 호출 모델 / 추론 설정 | 모두 gpt-6-luna / xhigh |
| 물리 DB·불변 분석·Excel 사진 관찰 대조 | 27행, 136개 검사, 불일치 0 |
| 저장 결과 27개 항목 전체 펼침 | 전부 원문 일치, 추가 AI 호출 0 |
| SDK·원본/등록사진·source manifest 독립 감사 | 14개 검사, 불일치 0 |

검사 수는 이번 실제 응답의 근거·이유 항목 수를 따른다. 이전 실행의 142개를 이번 136개에 재사용하지 않았다. 정면 사진의 상자에 가린 무릎과 상체 크롭의 무릎은 이번 응답 모두 ‘사진에서 확인할 수 없음’으로 저장됐고, 측면에서 보이는 무릎 굽힘과 몸통 앞기울임은 관찰 결과로 저장됐다. 실제 반환값·근거·확인할 부분이 사진별 DB/분석/Excel에 그대로 이어졌다. 정밀 각도·힘·무게·작업시간·횟수를 이미지에서 산출했다는 의미는 아니다.

최종 e8ded39에서 독립 소유권 반례 5개, 현재 원문 우선권 반례 9개, 사진 관찰 frontend 시험도 다시 통과했다. 이는 합성 provider를 사용한 회귀이며 위 5개 실제 외부 호출에 합산하지 않는다. 전체 통합 Python 결과는 441개, skip 0, 성공이고 frontend 시험 24개 및 build도 성공했다. 부모 실행 로그 `.local/vision-final-python.log`, `vision-final-frontend.log`, `vision-final-build.log`의 마지막 성공 결과를 별도로 확인했다.

최종 근거 파일은 `receipt.json`, `output-audit.json`, `external-image-audit.json`, `application-source-manifest.json`, `sdk.jsonl`, `expanded-render-audit.json`, `vision.xlsx`와 단계별 JSON이다. 관찰 사진 3장에 대한 실호출 증거와 기존 12개 텍스트·수치 조합 검증은 범위와 소스 버전을 계속 구분한다. 사용자의 원본 DB나 과거 분석 snapshot을 변경한 검증은 아니다.
