# 실제 사진 관찰 계약

`ergo.vision.contract`의 VERSION/PROMPT_VERSION/RESPONSE_FORMAT_NAME/SOURCE, policy(), CATALOGUE, OBSERVATION_LABELS, OBSERVATION_STATUS_LABELS가 공통 계약이다. `intake_contract.photo_vision`에 동일한 공개 계약을 제공한다. 기본은 기존 gpt-6-luna/xhigh 설정, image detail high, 긴 변 1280, JPEG 품질 88, 자동 입력에 필요한 관찰 확신도 0.9, 사진 동시 요청 3개다. 환경변수 LOCO_VISION_DETAIL/MAX_EDGE/JPEG_QUALITY/MIN_CONFIDENCE/PARALLELISM으로 조정한다.

Responses user content에 input_text(사진 방향·ID)와 실제 input_image(data:image/jpeg;base64,...)를 넣는다. 등록한 크롭 파일의 바이트를 읽고 EXIF 방향을 반영한 RGB JPEG를 전송한다. 원본은 바꾸지 않고 인코딩된 이미지에서 EXIF를 제거한다. key/이미지 base64를 저장하지 않는다. 공식 근거: https://developers.openai.com/api/docs/models/gpt-6-luna 및 https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses .

공개 응답과 TASK/분석 snapshot의 conditions.intake_session.photo_vision 형태는 {version,catalogue,photos:[현재 유효 record],history:[이전/지연 record]}다. record는 photo_id, view, photo_label, owner{task_id,task_created_at,photo_id}, source_sha256, encoded_sha256, signature, configuration, context, request_id, requested_at, completed_at, image 메타데이터, status, summary, observations, raw_response, connection, diagnostics를 포함한다. state는 OBSERVED/UNCERTAIN/ERROR이며 사진 소유 문맥이 바뀐 지연 자료는 history에 STALE로 남긴다. task가 삭제/재생성되면 원래 자료를 새 소유자에게 저장하지 않는다.

observations는 activity,trunk,neck,knees,arm_left,arm_right,wrist_left,wrist_right,holding 9개 고정 키다. 각각 {status:OBSERVED|UNCERTAIN|NOT_VISIBLE,value:한국어,evidence:한국어,confidence:number|null,reason:한국어}이며 좌우는 작업자의 신체 좌우다. 확신도는 측정 정확도가 아니다.

별도 manual_candidates의 scope/field/observation/value/status/confidence/evidence를 검증해 seated, 몸통/목 비틀림·옆굽힘, 좌우 손목 편위의 boolean만 재사용한다. 동일 관찰에 근거하고 확신도가 문턱 이상이어야 한다. work_candidates는 keyboard,arm_over,trunk_neck,knee의 YES만 허용한다. 반복/들기/중량/힘/노출/완전함을 사진으로 채우지 않는다. 후보의 사용자 인용 검증과 사진 관찰 검증을 섞지 않는다. 충돌은 관찰 및 진단으로 보존하고 기존 직접·텍스트·유효 POSE 값을 덮지 않는다.

원본SHA/view/owner/모델/추론/프롬프트/인코딩 정책에 따른 캐시는 시간으로 만료하지 않는다. 같은 turn 텍스트 추출이 만든 context=YES 때문에 이미지 결과가 즉시 무효화되지 않도록 텍스트 추출값은 이미지 캐시 키에서 제외한다. 무효화된 VISION 소유 입력은 UNKNOWN tombstone을 거쳐 투영한 이전 값도 해제하고, 다른 현재 사진의 분명한 양성 근거가 있으면 그 사진으로 소유권을 다시 연결한다. JSON에 쓸 수 없는 비정상 provider 수치는 유효한 문자열 표식으로 격리해 IPC를 깨지 않고 원문 output_text/진단을 보존한다.

실행 검증: tests/test_photo_vision.py 12개 회귀 통과. 실제 현재 크롭 사진1장을 unpatched MediaPipe와 함께 분석하고, 실제 gpt-6-luna/xhigh의 input_image 송신 SHA와 저장 SHA를 대조했다. .local/vision-first-live-20261023/actual-request-proof.json와receipt.json에 증거가 있다. 이 1회는 이미지 경계를 분리하기 위해 텍스트 추출 응답만 제어했으며 전체 실앱/실텍스트/Excel 통합 검증은 별도 수행한다.

사진 삭제 후 암묵적 복원은 현재 등록 사진만 선택한다. 명시적으로 삭제된 photo_id를 다시 선택하는 요청은 계속 거절한다. 삭제 중 지연 응답은 원래 사진의 history에 남고 사진/값을 복구하지 않는다.


## 화면·Excel과 원본 근거

화면에는 동작·허리·무릎 관찰을 먼저 보여 주고 목·양팔·양손목·잡는 모습은 펼쳐 확인한다. 저장된 분석 결과 화면과 출력은 해당 분석의 snapshot에 저장된 photo_vision만 사용한다. 현재 Task의 나중 관찰이나 제거된 사진으로 과거 결과를 바꾸지 않는다.

기존 Excel 시트·형식·입력값 셀은 유지하고, 관찰이 있는 경우에만 마지막에 ‘AI 사진 관찰’ 시트를 추가한다. 작업/사진 방향/관찰 항목/사진에서 본 모습/확인 상태/근거·확인할 부분의 여섯 열이며 사진별 9개 관찰을 같은 행의 value/evidence/reason과 대조한다. 확신도·모델·내부 사진 ID·요청 ID·파일 경로·원본 image bytes는 사용자 출력에 노출하지 않는다. 기존 근거 접두사 USER/POSE/SAVED도 직접 입력/사진 자동 측정/저장된 입력으로 표시하며 원문과 저장 코드는 보존한다.

VISION의 계산 입력 근거는 면담이 아닌 OTHER이며, 허용된 관찰 후보의 manual.source는 AUTO_ACCEPTED다. photo_id·vision_signature·관찰·원제안 근거를 전용 JSON으로 보존한다. 숫자 각도 후보나 MediaPipe angles로 위장하지 않는다. 나중에 신뢰도·경계 검사를 통과한 MediaPipe 측정이 생기면 시각 관찰의 대체값을 측정값으로 바꿀 수 있다. 낮은 신뢰도나 경계 관측은 유효한 시각 관찰을 지우지 않는다.

사진 또는 설정의 변경으로 시각 관찰 사실이 무효화되면 해당 사실이 소유한 계산 DTO 값도 함께 비운다. 동일한 값을 사람이 따로 확인한 근거는 지우지 않는다. 과거 분석·출력은 변경하지 않는다.
### 사진 등록 세대와 사용자 사진 상황 우선권 (2026-10-23)

`photo_identity.REGISTRATION_KEY`는 새 PHOTO.metadata_json 행에 UUID를 부여하며 update로 교체하지 않는다. 물리 스키마는 유지한다. legacy 행은 경로/소유 ID로 결정되는 토큰을 읽고 조회 중 metadata를 쓰지 않는다. 사진 signature는 [view,photo_id,원본SHA,등록세대]이며 과거 triple을 호환한다. 같은 SQLite ID·파일경로·바이트·view로 재등록해도 이전 이미지 및 텍스트 사진 응답이 새 등록에 적용되지 않는다.

사용자가 context=NO로 사진 상황을 부정하면 raw 관찰과 캐시는 보존하되 VISION 소유 manual/작업특징 입력은 UNKNOWN으로 돌려 실제 투영값도 해제한다. USER·텍스트 AI·SAVED·POSE 소유 값은 건드리지 않는다. context=YES로 직접 정정하면 같은 이미지 관찰을 재사용하며 추가 이미지 API를 호출하지 않는다. 같은 turn의 텍스트 추출 뒤 저장에도 이 우선권을 적용한다.

### 현재 원문이 사진 AI 추정을 정정하는 경우 (2026-10-23)

원문 인용·대상·단위·사진 소유권 검증을 통과한 현재 텍스트 제안은 이전 source=VISION의 KNOWN/CONFLICT 추정보다 우선해 source=AI,state=KNOWN으로 저장한다. 다른 값은 충돌 재질문으로 만들지 않고, 같은 값도 텍스트 근거로 승격하여 사진 삭제 때 명시한 작업 특징이 사라지지 않게 한다. 과거 원문 인용만으로는 이 승격을 하지 않는다. USER(직접 모름 포함), 기존 텍스트 AI/SAVED/유효 POSE 값과 사진 변경·지연 보호는 유지한다. 사진별 manual 정식 조건과 대표 호환 alias는 같은 사진의 AI 근거를 가리키며 원래 사진 관찰 raw/cache는 수정하지 않는다.

context=NO이면 public 사진 관찰은 계속 보관·표시하되 계산·추출용 known_visual_observations는 빈 목록이다. YES로 직접 정정하면 기존 사진 캐시를 다시 사용할 수 있다. 사진과 무관한 직접 설명값은 유지한다.

사진 관찰 요청은 적응형 입력·GPT 설명과 같은 프로세스 공유 OpenAI client/HTTP 연결 풀을 사용하며, 앱 요청 제한시간과 자동 재시도는 없다. 이는 응답 속도 보장이 아니며 네트워크·서비스 오류는 기존 실패 경로로 표시한다.
