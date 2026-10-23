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

독립 반례에서 발견한 비정상 provider 수치(inf)의 IPC 직렬화 실패와 삭제된 저장 view의 암묵 복원 실패는 backend99a5b38에서 수리했고 실제 서비스 회귀로 재확인했다. 추가 사용자 원문 우선권 후속이 진행 중이므로 최종 소스의 실제 3사진 재실행 결과는 별도 추가해야 한다.
