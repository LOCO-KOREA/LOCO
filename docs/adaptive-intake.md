# 적응형 추가 확인 계약 · 2026-10-22

사진·작업 설명 → 자동 정리·1차 점수 → 부족한 정보만 추가 확인 → 결과 → 검토·설명 → Excel 순서다. 확보한 값은 입력으로 저장하며, 계산과 최종 조사자 결론은 기존 규칙 엔진과 검토 흐름을 따른다. 새 운영 승인·배포 차단·AI 성공 필수 절차를 추가하지 않는다.

## 공통 계약과 모듈

`ergo/intake/contract.py`의 `VERSION`, `METHODS`, `POLICY`, 필드 catalogue가 기준이다. 항목·단위·선택지는 기존 질문 정의와 조건 행 매핑에서 조립한다. 프론트는 `intake_contract`를 한 번 조회하고 반환된 메서드 이름·저장 키·필드·정책으로 화면과 요청을 구성한다. 필드 경로나 AI 질문 문구를 프론트에서 새로 판정하지 않는다.

| 모듈 | 책임 |
|---|---|
| `ergo/intake/contract.py` | 공통 변수, 대상 필드, 조건 행 연결, strict 응답 schema |
| `ergo/intake/facts.py` | 값·단위·근거 검증, 사용자 우선 병합, 기존 TaskInput으로 투영 |
| `ergo/intake/planner.py` | 실제 11개 규칙/REBA의 누락 항목과 후보 연결, 중복·해결된 항목 제외 |
| `ergo/gpt/intake.py` | 현재 값·누락 후보·현재 질문을 받아 자연어 추출과 추가 질문 선택 |
| `ergo/service/intake.py` | 사진 추론, 회차 저장, revision 충돌, 서비스 조정 |
| `frontend/intake/client.js` | 계약 조회, 입력 자동 저장, 응답 순서·화면 수명 관리 |
| `frontend/intake/view.js`, `intake.css` | 저장된 정보/수정, 추가 질문, 자연어 답변 화면 |

## 서비스 DTO

- `intake_contract {}` → `{version,session_key,methods,policy,states,sources,fields}`.
- `intake_session {task_id,views?}` → 세션 복원/생성, 사진 측정 저장, 현재 상태. `views`는 방향→같은 작업 사진 ID이며 빈 객체도 가능하다.
- `intake_turn {task_id,text?,answers?,expected_revision?,plan?,focus?,task_created_at?}` → 직접 답변을 우선 저장하고, `plan`이 참이면 실제 AI로 설명 추출과 다음 질문을 요청한다. `plan=false`는 선택/숫자 입력 자동 저장 경로다. AI 실패 시에도 직접 답변과 기존 값은 유지한다.

직접 답변은 `{target,condition,value,quote?}`, 현재 질문 문맥은 `{target,condition}`이다. 회차 응답은 `{task,contract,facts,questions,remaining_count,complete,judgments,reba,preview,reason,dropped,messages}`다. `complete=false`여도 현재 정보로 결과를 생성할 수 있다.

각 fact는 `{target,condition,value,state,source,quote,updated_at,conflict?,angles?,origin?}`다. 상태는 KNOWN(사용 가능), ESTIMATED(사진에서 읽었으나 낮은 신뢰도/경계), UNKNOWN(모름·재확인), CONFLICT(서로 다른 진술)다. 출처는 USER/AI/MOVENET/SAVED다. 대상 항목의 type과 choices에서 모델 응답의 항목별 schema를 생성해 숫자/선택 값이 섞이지 않게 한다. 낮은 신뢰도 추정은 후보로 저장하고 한 번의 사용 선택으로 반영할 수 있다. 실제 관측값으로 몰래 승격하지 않는다.

AI 응답은 `answers:[{target,condition,number,text,quote}], questions:[{target,condition,text,reason}]`다. 답변 근거는 이번 문장이나 최근 저장된 사용자 진술에 실제로 있어야 하며 숫자와 단위도 일치해야 한다. 과거 진술은 더 최신 값이나 직접 입력을 덮어쓰지 못한다. 질문 문구는 바꿀 수 있지만 target·condition·입력 선택지와 계산값은 모델이 변경하지 않는다. 점수·해당 여부·조사자 결론은 AI 출력 대상이 아니다.

## 중복 제거와 의미

- 이미 사용 가능한 필드는 다시 묻지 않는다. 질문 카드 일부만 채워져도 필드별로 제외한다.
- USER가 모름으로 답한 항목도 자동 반복하지 않는다. 결과에는 입력 필요를 유지한다. 수정은 정보 요약에서 가능하다.
- 다른 무게·작업 조건은 서로 다른 condition/row_id로 유지한다. 최대 중량에 전체 횟수를 붙이지 않는다.
- 일반 작업의 무게를 사진 속 하중으로 복사하려면 같은 물건/무게라는 진술이나 추가 답변이 있어야 한다.
- 전체 하루 시간과 특정 동작 노출시간을 구별한다. 사진 비율로 노출량을 만들지 않는다.
- 말하지 않은 작업 특징은 UNKNOWN이다. 같은 작업에도 여러 부담 특성이 겹치므로 ‘다른 작업 없음’을 다른 특성의 NO로 확대하지 않는다. 화면에 열거한 미확인 특징을 ‘아래 특징은 모두 없음’으로 직접 선택했을 때만 묶어 NO로 기록한다. 이 묶음 선택은 AI 쓰기 대상에서 제외하며 결과 진행을 막지 않는다. 이 답변을 조건 행 전체를 기록했다는 답으로 쓰지 않는다. 행 전체 여부는 별도 `complete.<gate>` 항목이다.
- 같은 사진의 반대쪽 팔이나 다른 사진의 관찰을 현재 대표 사진의 사실로 복사하지 않는다. 현재 빠른 계산의 대표 사진은 계약의 방향 순서에서 먼저 등록된 사진이며, 다른 사진·행의 상세 계산은 고급 편집에서 조정한다.

## 저장·재실행

기존 `TASK.input_json.conditions`의 선택 키에 세션을 보관한다. 실제 값은 기존 conditions/legal/capture/manual에도 저장하므로 결과·Excel·고급 편집이 같은 값을 사용한다. 물리 여섯 테이블, 기존 분석/출력 snapshot, 이전 자료는 유지한다. 값이 없는 이전 자료는 기존 계약대로 읽는다.

선택은 즉시, 숫자·텍스트 칸은 입력 중 짧은 지연 후 또는 필드를 떠날 때 저장한다. 결과 생성 전에 저장 요청을 기다린다. AI 네트워크 대기 중에는 DB 트랜잭션을 잡지 않는다. 입력 revision이 바뀐 뒤 도착한 AI 응답은 최신 사용자 값을 덮어쓰지 않는다. 삭제한 작업을 복원하지 않는다.

사진/모델 변경 시 영향을 받는 사진 추정만 재평가하며 작업 전체의 시간·횟수는 유지한다. 고급 편집에서 바뀐 실제 값은 세션보다 우선한다. 세션 이력은 작업 입력 변경으로서 snapshot에 보존하지만 전후 비교의 작업 조건 변화 목록에는 보조 세션 메타데이터를 펼쳐 쓰지 않는다.

기존 `quick_preview`와 `quick_interpret`는 호환 호출로 남는다. 새 간편 흐름은 위 세 서비스와 모듈을 사용한다. 과거 localStorage 초안은 호환 경로로 열 수 있으며 새 자동 저장 값의 정본은 SQLite다.
