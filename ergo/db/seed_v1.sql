-- 기준 정보 초기 데이터 v1
INSERT INTO criterion (criterion_no, short_name, legal_text, source_ref, note_ref, basis_type_cd) VALUES
 (1,  '키보드·마우스 집중 입력', '하루에 4시간 이상 집중적으로 자료입력 등을 위해 키보드 또는 마우스를 조작하는 작업', '고시 제3조 제1호', '해설 1호 주1~4, 각주 3·4', 'INPUT'),
 (2,  '같은 동작 반복', '하루에 총 2시간 이상 목, 어깨, 팔꿈치, 손목 또는 손을 사용하여 같은 동작을 반복하는 작업', '고시 제3조 제2호', '해설 2호 주1·2', 'INPUT'),
 (3,  '팔을 들거나 뒤로 한 자세', '하루에 총 2시간 이상 머리 위에 손이 있거나, 팔꿈치가 어깨위에 있거나, 팔꿈치를 몸통으로부터 들거나, 팔꿈치를 몸통뒤쪽에 위치하도록 하는 상태에서 이루어지는 작업', '고시 제3조 제3호', '해설 3호 주1·2', 'VIDEO'),
 (4,  '목·허리 굽힘·비틀림', '지지되지 않은 상태이거나 임의로 자세를 바꿀 수 없는 조건에서, 하루에 총 2시간 이상 목이나 허리를 구부리거나 트는 상태에서 이루어지는 작업', '고시 제3조 제4호', '해설 4호 주1~4', 'MIXED'),
 (5,  '쪼그림·무릎 굽힘', '하루에 총 2시간 이상 쪼그리고 앉거나 무릎을 굽힌 자세에서 이루어지는 작업', '고시 제3조 제5호', '해설 5호 주1·2', 'VIDEO'),
 (6,  '손가락 집기·쥐기', '하루에 총 2시간 이상 지지되지 않은 상태에서 1kg 이상의 물건을 한손의 손가락으로 집어 옮기거나, 2kg 이상에 상응하는 힘을 가하여 한손의 손가락으로 물건을 쥐는 작업', '고시 제3조 제6호', '해설 6호 주1·2', 'INPUT'),
 (7,  '한 손 들기·쥐기', '하루에 총 2시간 이상 지지되지 않은 상태에서 4.5kg 이상의 물건을 한 손으로 들거나 동일한 힘으로 쥐는 작업', '고시 제3조 제7호', '해설 7호 주1·2', 'INPUT'),
 (8,  '25kg 이상 들기', '하루에 10회 이상 25kg 이상의 물체를 드는 작업', '고시 제3조 제8호', '해설 8호 주1~3', 'INPUT'),
 (9,  '불편한 위치에서 10kg 들기', '하루에 25회 이상 10kg 이상의 물체를 무릎 아래에서 들거나, 어깨 위에서 들거나, 팔을 뻗은 상태에서 드는 작업', '고시 제3조 제9호', '해설 9호 주1·2', 'INPUT'),
 (10, '자주 드는 작업', '하루에 총 2시간 이상, 분당 2회 이상 4.5kg 이상의 물체를 드는 작업', '고시 제3조 제10호', NULL, 'INPUT'),
 (11, '손·무릎 충격', '하루에 총 2시간 이상 시간당 10회 이상 손 또는 무릎을 사용하여 반복적으로 충격을 가하는 작업', '고시 제3조 제11호', '해설 11호 주', 'INPUT');

INSERT INTO threshold_default (threshold_cd, criterion_no, value_deg, measure_cd, source_ref) VALUES
 ('NECK_FLEX',       4, 20, 'VIDEO',        '해설 4호 주3'),
 ('WAIST_FLEX',      4, 20, 'VIDEO',        '해설 4호 주3'),
 ('WAIST_EXT',       4, 20, 'VIDEO',        '해설 4호 주3'),
 ('NECK_TWIST',      4,  5, 'INVESTIGATOR', '해설 4호 주4'),
 ('WAIST_TWIST',     4, 20, 'INVESTIGATOR', '해설 4호 주4'),
 ('UPPER_ARM_RAISE', 3, 45, 'VIDEO',        '해설 3호 주1');

INSERT INTO pose_model (model_id, model_name, model_version, keypoint_cnt) VALUES
 (1, 'MoveNet Lightning',    'pose2 sample', 17),
 (2, 'MoveNet Thunder',      'pose2 sample', 17),
 (3, 'MediaPipe Pose Lite',  '1.1.0',        33),
 (4, 'MediaPipe Pose Full',  '1.1.0',        33),
 (5, 'MediaPipe Pose Heavy', '1.1.0',        33);

INSERT INTO app_setting (setting_key, setting_value) VALUES
 ('POSE_MODEL_ID', '4'),
 ('GPT_ENABLED',   '0');

INSERT INTO schema_version (version_no, description) VALUES (1, 'v1 초안 (2026-10-12)');
