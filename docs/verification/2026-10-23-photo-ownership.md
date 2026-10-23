# 사진별 자세 관측 연결 검증 · 2026-10-23

기준 소스는 `696f457`와 손목 측정 수리 위의 `ead6230`이다. 최신 통합 후보 전체의 실호출 검증을 대신하지 않는다. 원래 main의 Excel·사진 크롭, 대표 사진 선택·양팔 REBA 완성/최댓값 점수 의미를 바꾸지 않았다.

| 관측 | 저장·자동 반영 | 확인이 남는 경계 |
|---|---|---|
| 몸통 기울기·위팔·팔꿈치·무릎 2D 각도 | 원 사진·좌우·각도·quality를 저장하고 같은 사진의 manual에만 반영 | 낮은 신뢰도, 점수 경계, 원 사진의 반대쪽 |
| 목 기울기 두 참고 각도 | 원 각도 보존 | 대체 지표이므로 목 REBA 확정값으로 변환하지 않음 |
| 손목 사진 평면 굽힘 | wrist 정책을 만족하는 원 사진/신체 쪽만 반영 | 손 가림·손바닥면·짧은 선분·경계; 편위·비틀림은 별도 |
| 정면 몸통/목 기울임·좌우 팔 벌림 | 실제 해당 측면의 양성값만 변환, 원 사진별 근거 보존 | 작은 각도에서 NO 생성 금지; 한 팔 최댓값 양팔 복사 금지 |
| 앉음·머리 위 손·무릎 등의 신호 | 원 사진 관측 저장; 앉음은 같은 사진에만 조건부 반영 | 신호만으로 하루 노출시간·힘·회수 추정 금지 |
| 추정 3D | 원 관측 별도 보존 | 기존 2D REBA 산식에 혼합하지 않음 |

`tests/test_photo_fact_ownership.py`의 독립 반례 11개가 통과했다. 다른 사진 값이 대표를 채우는 오류, 같은 범주 두 사진의 출처 복제, legacy 추정값의 USER/모름 덮어쓰기, 대표 교체·다른 사진 삭제, 실제 서비스 지연 응답과 직접 모름 경합, 잘못된 앉음 인용, 반복 조회 변경, 좌우 팔 각도 복제, 이미 알려진 값의 재질문을 검사했다.

`tests/per_photo_e2e.py`는 제공된 실제 3장과 unpatched MediaPipe Heavy로 서비스→SQLite→재시작→분석→실제 Excel을 실행했다. `.local/per-photo-actual-r1/receipt.json`에 10개 canonical 자세 fact와 3개 사용 가능한 manual 행, 원 사진·각도·사진 해시, Excel 셀을 보존했다. usable 3행은 모두 두 번째 사진에만 들어갔으며 대표 사진의 빈 자세로 복사되지 않았다. 나머지 낮은 신뢰도·경계·손목 미측정은 확정되지 않았다. 같은 경로 세 번 조회와 재시작에서 TASK JSON/revision이 같았다. 기존 3사진 DB를 read-only backup하여 원본 TASK/ANALYSIS/EXPORT_LOG와 과거 snapshot 불변도 확인했다. 이 시험은 외부 Luna 호출과 frontend 전체 동작을 포함하지 않는다.

Python 전체는 369개 통과, fixture/model 경로 조건으로 8개를 건너뛴 실행이었다. 이는 skip 없는 통과로 보고하지 않는다. frontend 전체 기존 시험은 통과했다. 실제 외부 Luna 12개 캠페인의 전후 독립 감사 및 31초 지연 crop 시험은 별도 [출력 감사](2026-10-23-export-independent-audit.md)와 부모 통합 보고서에 구분한다.

후속 소스 `c66d698`의 `tests/frontend-photo-ownership.cjs`는 사진/신체 좌우 표시, 손 가림 사유, 화면 내부 식별자 숨김, 별칭·삭제사진 중복 요약과 확인횟수 제외, 이미 확인한 항목의 접힌 수정 영역, 손목 각도 한국어를 검사해 통과했다.

`tests/per_photo_quote_e2e.py`는 위 실사진 DB를 read-only backup하여 두 사진의 같은 몸통 범주 3에 서로 다른 직접 USER 시험 근거 35도/50도를 입력했다. 실제 미패치 서비스·Heavy·SQLite·새 분석·Excel로 `입력한 값!C24/F24`에는 왼쪽 사진/35도 원문, `C25/F25`에는 오른쪽 사진/50도 원문이 정확히 들어갔다. 재시작 후 DB의 사진·값·출처·원문이 같고 원 DB와 과거 분석 행은 불변이었다. 입력한 각도는 합성 직접 입력 시험값이며 실제 사진의 측정 결과라는 주장이 아니다. 산출물은 `.local/per-photo-distinct-quotes-r1/receipt.json`이다.

이어 `tests/per-photo-electron-replay.cjs`가 그 저장된 분석을 다시 read-only backup해 실제 Electron/Python/SQLite로 열었다. 간편 Excel 미리보기의 두 사진별 근거와 실제 Excel 저장 버튼 산출물을 대조해 9개 검사를 통과했다. 창은 좌표 -12000/-12000, focusable=false이고 native 마우스·키보드를 사용하지 않았다. 새 AI·분석을 실행하지 않았으며 `.local/per-photo-hidden-electron-r1/receipt.json`에 창 속성·실제 IPC 목록·미리보기 텍스트·화면·workbook을 기록했다. 이 시험은 저장된 per-photo 분석의 화면/출력 경로 검증이며 최신 통합 후보의 새 사용자 원문 Luna E2E 검증과 구분한다.
