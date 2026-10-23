# 실제 사진 관찰 계약

`ergo.vision.contract`의 VERSION/PROMPT_VERSION/RESPONSE_FORMAT_NAME/SOURCE, policy(), CATALOGUE, OBSERVATION_LABELS, OBSERVATION_STATUS_LABELS가 공통 계약이다. `intake_contract.photo_vision`에 동일한 공개 계약을 제공한다. 기본은 기존 gpt-6-luna/xhigh 설정, image detail high, 긴 변 1280, JPEG 품질 88, 자동 입력에 필요한 관찰 확신도 0.9, 사진 동시 요청 3개다. 환경변수 LOCO_VISION_DETAIL/MAX_EDGE/JPEG_QUALITY/MIN_CONFIDENCE/PARALLELISM으로 조정한다.

Responses user content에 input_text(사진 방향·ID)와 실제 input_image(data:image/jpeg;base64,...)를 넣는다. 등록한 크롭 파일의 바이트를 읽고 EXIF 방향을 반영한 RGB JPEG를 전송한다. 원본은 바꾸지 않고 인코딩된 이미지에서 EXIF를 제거한다. key/이미지 base64를 저장하지 않는다. 공식 근거: https://developers.openai.com/api/docs/models/gpt-6-luna 및 https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses .

공개 응답과 TASK/분석 snapshot의 conditions.intake_session.photo_vision 형태는 {version,catalogue,photos:[현재 유효 record],history:[이전/지연 record]}다. record는 photo_id, view, photo_label, owner{task_id,task_created_at,photo_id}, source_sha256, encoded_sha256, signature, configuration, context, request_id, requested_at, completed_at, image 메타데이터, status, summary, observations, raw_response, connection, diagnostics를 포함한다. state는 OBSERVED/UNCERTAIN/ERROR이며 사진 소유 문맥이 바뀐 지연 자료는 history에 STALE로 남긴다. task가 삭제/재생성되면 원래 자료를 새 소유자에게 저장하지 않는다.

observations는 activity,trunk,neck,knees,arm_left,arm_right,wrist_left,wrist_right,holding 9개 고정 키다. 각각 {status:OBSERVED|UNCERTAIN|NOT_VISIBLE,value:한국어,evidence:한국어,confidence:number|null,reason:한국어}이며 좌우는 작업자의 신체 좌우다. 확신도는 측정 정확도가 아니다.

별도 manual_candidates의 scope/field/observation/value/status/confidence/evidence를 검증해 seated, 몸통/목 비틀림·옆굽힘, 좌우 손목 편위의 boolean만 재사용한다. 동일 관찰에 근거하고 확신도가 문턱 이상이어야 한다. work_candidates는 keyboard,arm_over,trunk_neck,knee의 YES만 허용한다. 반복/들기/중량/힘/노출/완전함을 사진으로 채우지 않는다. 후보의 사용자 인용 검증과 사진 관찰 검증을 섞지 않는다. 충돌은 관찰 및 진단으로 보존하고 기존 직접·텍스트·유효 POSE 값을 덮지 않는다.

원본SHA/view/owner/모델/추론/프롬프트/인코딩 정책에 따른 캐시는 시간으로 만료하지 않는다. 같은 turn 텍스트 추출이 만든 context=YES 때문에 이미지 결과가 즉시 무효화되지 않도록 텍스트 추출값은 이미지 캐시 키에서 제외한다. 무효화된 VISION 소유 입력은 UNKNOWN tombstone을 거쳐 투영한 이전 값도 해제하고, 다른 현재 사진의 분명한 양성 근거가 있으면 그 사진으로 소유권을 다시 연결한다. JSON에 쓸 수 없는 비정상 provider 수치는 유효한 문자열 표식으로 격리해 IPC를 깨지 않고 원문 output_text/진단을 보존한다.

실행 검증: tests/test_photo_vision.py 12개 회귀 통과. 실제 현재 크롭 사진1장을 unpatched MediaPipe와 함께 분석하고, 실제 gpt-6-luna/xhigh의 input_image 송신 SHA와 저장 SHA를 대조했다. .local/vision-first-live-20261023/actual-request-proof.json와receipt.json에 증거가 있다. 이 1회는 이미지 경계를 분리하기 위해 텍스트 추출 응답만 제어했으며 전체 실앱/실텍스트/Excel 통합 검증은 별도 수행한다.

사진 삭제 후 암묵적 복원은 현재 등록 사진만 선택한다. 명시적으로 삭제된 photo_id를 다시 선택하는 요청은 계속 거절한다. 삭제 중 지연 응답은 원래 사진의 history에 남고 사진/값을 복구하지 않는다.
