-- =====================================================================
-- 근골격계 유해요인조사 보조 앱 · 내부 스키마 v1 (SQLite 3.45 이상)
-- 연결할 때마다:      PRAGMA foreign_keys = ON;
-- 파일을 만들 때 한 번: PRAGMA journal_mode = WAL;
-- 시각은 모두 로컬 시각 ISO 8601 문자열 'YYYY-MM-DDTHH:MM:SS'
-- =====================================================================

-- ---------------------------------------------------------------------
-- A. 기준 정보
-- ---------------------------------------------------------------------
CREATE TABLE criterion (
  criterion_no   INTEGER PRIMARY KEY CHECK (criterion_no BETWEEN 1 AND 11),
  short_name     TEXT    NOT NULL CHECK (length(trim(short_name)) > 0),
  legal_text     TEXT    NOT NULL,
  source_ref     TEXT    NOT NULL,
  note_ref       TEXT,
  basis_type_cd  TEXT    NOT NULL CHECK (basis_type_cd IN ('POSE','INPUT','MIXED'))
) STRICT;

CREATE TABLE threshold_default (
  threshold_cd   TEXT    PRIMARY KEY CHECK (threshold_cd IN
                   ('NECK_FLEX','WAIST_FLEX','WAIST_EXT','NECK_TWIST','WAIST_TWIST','UPPER_ARM_RAISE')),
  criterion_no   INTEGER NOT NULL REFERENCES criterion(criterion_no),
  value_deg      REAL    NOT NULL CHECK (value_deg > 0 AND value_deg < 180),
  measure_cd     TEXT    NOT NULL CHECK (measure_cd IN ('POSE','INVESTIGATOR')),
  source_ref     TEXT    NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE pose_model (
  model_id       INTEGER PRIMARY KEY,
  model_name     TEXT    NOT NULL,
  model_version  TEXT    NOT NULL,
  keypoint_cnt   INTEGER NOT NULL CHECK (keypoint_cnt >= 17),
  UNIQUE (model_name, model_version)
) STRICT;

-- ---------------------------------------------------------------------
-- B. 조사
-- ---------------------------------------------------------------------
CREATE TABLE survey (
  survey_id          INTEGER PRIMARY KEY,
  survey_type_cd     TEXT    NOT NULL CHECK (survey_type_cd IN ('REGULAR','OCCASIONAL','INITIAL')),
  survey_date        TEXT    NOT NULL CHECK (date(survey_date) IS survey_date),
  investigator_name  TEXT    NOT NULL CHECK (length(trim(investigator_name)) > 0),
  dept_name          TEXT    NOT NULL CHECK (length(trim(dept_name)) > 0),
  process_name       TEXT    NOT NULL CHECK (length(trim(process_name)) > 0),
  work_name          TEXT    NOT NULL CHECK (length(trim(work_name)) > 0),
  status_cd          TEXT    NOT NULL DEFAULT 'DRAFT' CHECK (status_cd IN ('DRAFT','CONFIRMED')),
  confirmed_at       TEXT    CHECK (confirmed_at IS NULL OR datetime(confirmed_at) IS NOT NULL),
  created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  updated_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  CHECK ((status_cd = 'CONFIRMED') = (confirmed_at IS NOT NULL))
) STRICT;

CREATE TABLE survey_reason (
  survey_id   INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  reason_cd   TEXT    NOT NULL CHECK (reason_cd IN ('MSD_CASE','NEW_TASK','ENV_CHANGE')),
  PRIMARY KEY (survey_id, reason_cd)
) STRICT, WITHOUT ROWID;

CREATE TABLE participant (
  participant_id       INTEGER PRIMARY KEY,
  survey_id            INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  participant_type_cd  TEXT    NOT NULL CHECK (participant_type_cd IN ('REPRESENTATIVE','WORKER')),
  display_name         TEXT    NOT NULL CHECK (length(trim(display_name)) > 0),
  created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT;

CREATE TABLE survey_threshold (
  survey_id     INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  threshold_cd  TEXT    NOT NULL REFERENCES threshold_default(threshold_cd),
  value_deg     REAL    NOT NULL CHECK (value_deg > 0 AND value_deg < 180),
  reason_text   TEXT    NOT NULL CHECK (length(trim(reason_text)) > 0),
  changed_by    TEXT    NOT NULL CHECK (length(trim(changed_by)) > 0),
  changed_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  PRIMARY KEY (survey_id, threshold_cd)
) STRICT, WITHOUT ROWID;

-- ---------------------------------------------------------------------
-- C. 단위작업과 입력
-- ---------------------------------------------------------------------
CREATE TABLE unit_task (
  unit_task_id    INTEGER PRIMARY KEY,
  survey_id       INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  task_name       TEXT    NOT NULL CHECK (length(trim(task_name)) > 0),
  task_desc       TEXT,
  worker_cnt      INTEGER NOT NULL CHECK (worker_cnt >= 1),
  period_type_cd  TEXT    NOT NULL CHECK (period_type_cd IN ('ONGOING','SHORT_TERM','INTERMITTENT')),
  sort_no         INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  UNIQUE (survey_id, task_name)
) STRICT;

CREATE TABLE task_input (
  unit_task_id            INTEGER PRIMARY KEY REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  daily_work_h            REAL    CHECK (daily_work_h BETWEEN 0 AND 24),
  unsupported_posture_yn  INTEGER CHECK (unsupported_posture_yn IN (0,1)),
  neck_twist_h            REAL    CHECK (neck_twist_h BETWEEN 0 AND 24),
  waist_twist_h           REAL    CHECK (waist_twist_h BETWEEN 0 AND 24),
  keyboard_h              REAL    CHECK (keyboard_h BETWEEN 0 AND 24),
  keyboard_self_paced_yn  INTEGER CHECK (keyboard_self_paced_yn IN (0,1)),
  finger_pinch_kg         REAL    CHECK (finger_pinch_kg >= 0),
  finger_grip_kg          REAL    CHECK (finger_grip_kg >= 0),
  finger_h                REAL    CHECK (finger_h BETWEEN 0 AND 24),
  finger_unsupported_yn   INTEGER CHECK (finger_unsupported_yn IN (0,1)),
  onehand_kg              REAL    CHECK (onehand_kg >= 0),
  onehand_h               REAL    CHECK (onehand_h BETWEEN 0 AND 24),
  onehand_unsupported_yn  INTEGER CHECK (onehand_unsupported_yn IN (0,1)),
  lift_kg                 REAL    CHECK (lift_kg >= 0),
  lift_people_cnt         INTEGER CHECK (lift_people_cnt >= 1),
  lift_cnt_per_day        INTEGER CHECK (lift_cnt_per_day >= 0),
  freq_lift_kg            REAL    CHECK (freq_lift_kg >= 0),
  freq_lift_per_min       REAL    CHECK (freq_lift_per_min >= 0),
  freq_lift_h             REAL    CHECK (freq_lift_h BETWEEN 0 AND 24),
  impact_h                REAL    CHECK (impact_h BETWEEN 0 AND 24),
  impact_per_hour         INTEGER CHECK (impact_per_hour >= 0),
  updated_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  CHECK (neck_twist_h  IS NULL OR daily_work_h IS NULL OR neck_twist_h  <= daily_work_h),
  CHECK (waist_twist_h IS NULL OR daily_work_h IS NULL OR waist_twist_h <= daily_work_h)
) STRICT;

CREATE TABLE repetition_input (
  unit_task_id  INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  body_part_cd  TEXT    NOT NULL CHECK (body_part_cd IN ('NECK','SHOULDER','ELBOW','WRIST','HAND')),
  repeat_h      REAL    NOT NULL CHECK (repeat_h BETWEEN 0 AND 24),
  PRIMARY KEY (unit_task_id, body_part_cd)
) STRICT, WITHOUT ROWID;

CREATE TABLE lift_position_input (
  unit_task_id      INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  position_cd       TEXT    NOT NULL CHECK (position_cd IN ('BELOW_KNEE','ABOVE_SHOULDER','ARM_EXTENDED')),
  lift_cnt_per_day  INTEGER NOT NULL CHECK (lift_cnt_per_day >= 0),
  weight_kg         REAL    NOT NULL CHECK (weight_kg >= 0),
  PRIMARY KEY (unit_task_id, position_cd)
) STRICT, WITHOUT ROWID;

CREATE TABLE reba_input (
  unit_task_id         INTEGER PRIMARY KEY REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  load_kg              REAL    CHECK (load_kg >= 0),
  shock_yn             INTEGER CHECK (shock_yn IN (0,1)),
  coupling_cd          TEXT    CHECK (coupling_cd IN ('GOOD','FAIR','POOR','UNACCEPTABLE')),
  wrist_flex_cd        TEXT    CHECK (wrist_flex_cd IN ('LE15','GT15')),
  wrist_twist_yn       INTEGER CHECK (wrist_twist_yn IN (0,1)),
  neck_twist_side_yn   INTEGER CHECK (neck_twist_side_yn IN (0,1)),
  trunk_twist_side_yn  INTEGER CHECK (trunk_twist_side_yn IN (0,1)),
  legs_support_cd      TEXT    CHECK (legs_support_cd IN ('BILATERAL','UNILATERAL')),
  shoulder_raised_yn   INTEGER CHECK (shoulder_raised_yn IN (0,1)),
  arm_abducted_yn      INTEGER CHECK (arm_abducted_yn IN (0,1)),
  arm_supported_yn     INTEGER CHECK (arm_supported_yn IN (0,1)),
  act_static_yn        INTEGER CHECK (act_static_yn IN (0,1)),
  act_repeat_yn        INTEGER CHECK (act_repeat_yn IN (0,1)),
  act_rapid_yn         INTEGER CHECK (act_rapid_yn IN (0,1)),
  updated_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT;

-- ---------------------------------------------------------------------
-- D. 사진과 분석  (MVP의 분석 입력은 사진이다. 기능정의서 D-MVP-01)
-- ---------------------------------------------------------------------
CREATE TABLE still (
  still_id       INTEGER PRIMARY KEY,
  unit_task_id   INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  still_no       INTEGER NOT NULL CHECK (still_no >= 1),          -- 단위작업 안의 순번 (뺀 사진의 번호는 다시 쓰지 않음)
  file_path      TEXT    NOT NULL,                                -- 원본은 복사하지 않고 위치만 저장한다 (BR-22)
  file_name      TEXT    NOT NULL,
  width_px       INTEGER NOT NULL CHECK (width_px > 0),
  height_px      INTEGER NOT NULL CHECK (height_px > 0),
  rotation_deg   INTEGER NOT NULL DEFAULT 0 CHECK (rotation_deg IN (0,90,180,270)),
  consent_yn     INTEGER NOT NULL DEFAULT 0 CHECK (consent_yn IN (0,1)),
  consent_at     TEXT    CHECK (consent_at IS NULL OR datetime(consent_at) IS NOT NULL),
  removed_yn     INTEGER NOT NULL DEFAULT 0 CHECK (removed_yn IN (0,1)),   -- 1 = 표본에서 뺌. 분석에 쓴 사진은 지우지 않는다
  registered_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  UNIQUE (unit_task_id, still_no),
  CHECK ((consent_yn = 1) = (consent_at IS NOT NULL))
) STRICT;

CREATE TABLE analysis_run (
  run_id            INTEGER PRIMARY KEY,
  unit_task_id      INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  model_id          INTEGER NOT NULL REFERENCES pose_model(model_id),
  status_cd         TEXT    NOT NULL CHECK (status_cd IN ('RUNNING','DONE','FAILED','CANCELED')),
  is_current_yn     INTEGER NOT NULL DEFAULT 0 CHECK (is_current_yn IN (0,1)),
  started_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  finished_at       TEXT,
  processing_s      REAL    CHECK (processing_s >= 0),
  still_total_cnt   INTEGER CHECK (still_total_cnt >= 0),
  still_valid_cnt   INTEGER CHECK (still_valid_cnt >= 0),
  invalid_ratio     REAL    CHECK (invalid_ratio BETWEEN 0 AND 1),
  legs_cut_yn       INTEGER NOT NULL DEFAULT 0 CHECK (legs_cut_yn IN (0,1)),
  error_cd          TEXT,
  jitter_deg        REAL    NOT NULL DEFAULT 5   CHECK (jitter_deg >= 0),
  conf_min          REAL    NOT NULL DEFAULT 0.5 CHECK (conf_min BETWEEN 0 AND 1),
  min_sample_cnt    INTEGER NOT NULL DEFAULT 5   CHECK (min_sample_cnt >= 1),
  CHECK (is_current_yn = 0 OR status_cd = 'DONE'),
  CHECK (status_cd = 'RUNNING' OR finished_at IS NOT NULL),
  CHECK (still_valid_cnt IS NULL OR still_total_cnt IS NULL OR still_valid_cnt <= still_total_cnt)
) STRICT;

CREATE TABLE still_angle (
  run_id                   INTEGER NOT NULL REFERENCES analysis_run(run_id) ON DELETE CASCADE,
  still_id                 INTEGER NOT NULL REFERENCES still(still_id),
  valid_yn                 INTEGER NOT NULL CHECK (valid_yn IN (0,1)),
  trunk_tilt_deg           REAL    CHECK (trunk_tilt_deg      BETWEEN -180 AND 180),
  neck_tilt_vert_deg       REAL    CHECK (neck_tilt_vert_deg  BETWEEN -180 AND 180),
  neck_flex_trunk_deg      REAL    CHECK (neck_flex_trunk_deg BETWEEN -180 AND 180),
  upper_arm_raise_l_deg    REAL    CHECK (upper_arm_raise_l_deg BETWEEN 0 AND 180),
  upper_arm_raise_r_deg    REAL    CHECK (upper_arm_raise_r_deg BETWEEN 0 AND 180),
  upper_arm_flex_l_deg     REAL    CHECK (upper_arm_flex_l_deg BETWEEN -180 AND 180),
  upper_arm_flex_r_deg     REAL    CHECK (upper_arm_flex_r_deg BETWEEN -180 AND 180),
  elbow_flex_l_deg         REAL    CHECK (elbow_flex_l_deg BETWEEN 0 AND 180),
  elbow_flex_r_deg         REAL    CHECK (elbow_flex_r_deg BETWEEN 0 AND 180),
  knee_flex_l_deg          REAL    CHECK (knee_flex_l_deg BETWEEN 0 AND 180),
  knee_flex_r_deg          REAL    CHECK (knee_flex_r_deg BETWEEN 0 AND 180),
  hand_above_head_yn       INTEGER CHECK (hand_above_head_yn IN (0,1)),
  elbow_above_shoulder_yn  INTEGER CHECK (elbow_above_shoulder_yn IN (0,1)),
  elbow_behind_trunk_yn    INTEGER CHECK (elbow_behind_trunk_yn IN (0,1)),
  squat_yn                 INTEGER CHECK (squat_yn IN (0,1)),
  kneeling_yn              INTEGER CHECK (kneeling_yn IN (0,1)),
  knee_on_floor_yn         INTEGER CHECK (knee_on_floor_yn IN (0,1)),
  PRIMARY KEY (run_id, still_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE reba_result (
  run_id           INTEGER PRIMARY KEY REFERENCES analysis_run(run_id) ON DELETE CASCADE,
  key_still_id     INTEGER NOT NULL,
  key_still_by_cd  TEXT    NOT NULL DEFAULT 'AUTO' CHECK (key_still_by_cd IN ('AUTO','INVESTIGATOR')),
  side_cd          TEXT    NOT NULL CHECK (side_cd IN ('L','R')),
  neck_score       INTEGER NOT NULL CHECK (neck_score      BETWEEN 1 AND 3),
  trunk_score      INTEGER NOT NULL CHECK (trunk_score     BETWEEN 1 AND 5),
  legs_score       INTEGER NOT NULL CHECK (legs_score      BETWEEN 1 AND 4),
  table_a_score    INTEGER NOT NULL CHECK (table_a_score   BETWEEN 1 AND 9),
  load_score       INTEGER NOT NULL CHECK (load_score      BETWEEN 0 AND 3),
  score_a          INTEGER NOT NULL CHECK (score_a         BETWEEN 1 AND 12),
  upper_arm_score  INTEGER NOT NULL CHECK (upper_arm_score BETWEEN 1 AND 6),
  lower_arm_score  INTEGER NOT NULL CHECK (lower_arm_score BETWEEN 1 AND 2),
  wrist_score      INTEGER NOT NULL CHECK (wrist_score     BETWEEN 1 AND 3),
  table_b_score    INTEGER NOT NULL CHECK (table_b_score   BETWEEN 1 AND 9),
  coupling_score   INTEGER NOT NULL CHECK (coupling_score  BETWEEN 0 AND 3),
  score_b          INTEGER NOT NULL CHECK (score_b         BETWEEN 1 AND 12),
  table_c_score    INTEGER NOT NULL CHECK (table_c_score   BETWEEN 1 AND 12),
  activity_score   INTEGER NOT NULL CHECK (activity_score  BETWEEN 0 AND 3),
  reba_score       INTEGER NOT NULL CHECK (reba_score      BETWEEN 1 AND 15),
  risk_level_cd    TEXT    NOT NULL CHECK (risk_level_cd IN ('NEGLIGIBLE','LOW','MEDIUM','HIGH','VERY_HIGH')),
  provisional_yn   INTEGER NOT NULL CHECK (provisional_yn IN (0,1)),
  FOREIGN KEY (run_id, key_still_id) REFERENCES still_angle(run_id, still_id),   -- 대표 사진은 그 분석에 쓴 사진
  CHECK (score_a    = table_a_score + load_score),
  CHECK (score_b    = table_b_score + coupling_score),
  CHECK (reba_score = table_c_score + activity_score),
  CHECK (risk_level_cd = CASE WHEN reba_score = 1   THEN 'NEGLIGIBLE'
                              WHEN reba_score <= 3  THEN 'LOW'
                              WHEN reba_score <= 7  THEN 'MEDIUM'
                              WHEN reba_score <= 10 THEN 'HIGH'
                              ELSE 'VERY_HIGH' END)
) STRICT;

CREATE TABLE key_still_image (
  run_id      INTEGER PRIMARY KEY REFERENCES reba_result(run_id) ON DELETE CASCADE,
  still_id    INTEGER NOT NULL REFERENCES still(still_id),
  image_jpeg  BLOB    NOT NULL CHECK (length(image_jpeg) > 0),
  masked_yn   INTEGER NOT NULL CHECK (masked_yn = 1),
  created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT;

-- ---------------------------------------------------------------------
-- E. 판정·경고·AI 문장
-- ---------------------------------------------------------------------
CREATE TABLE judgment (
  judgment_id          INTEGER PRIMARY KEY,
  unit_task_id         INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  criterion_no         INTEGER NOT NULL REFERENCES criterion(criterion_no),
  run_id               INTEGER REFERENCES analysis_run(run_id),
  computed_status_cd   TEXT    NOT NULL CHECK (computed_status_cd IN
                         ('APPLICABLE','NOT_APPLICABLE','NEEDS_REVIEW','NEEDS_INPUT')),
  review_reason_cd     TEXT    CHECK (review_reason_cd IN
                         ('JITTER','INVALID_STILLS','INTERPRETATION','LEGS_CUT','KNEE_ON_FLOOR','SMALL_SAMPLE')),
  exclusion_cd         TEXT    CHECK (exclusion_cd IN ('SHORT_TERM','INTERMITTENT')),
  final_status_cd      TEXT    CHECK (final_status_cd IN ('APPLICABLE','NOT_APPLICABLE')),
  confirmed_yn         INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_yn IN (0,1)),
  confirmed_by         TEXT,
  confirmed_at         TEXT    CHECK (confirmed_at IS NULL OR datetime(confirmed_at) IS NOT NULL),
  confirm_reason_text  TEXT,
  basis_text           TEXT    NOT NULL,
  source_text          TEXT    NOT NULL,
  computed_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  UNIQUE (unit_task_id, criterion_no),
  CHECK ((computed_status_cd = 'NEEDS_REVIEW') = (review_reason_cd IS NOT NULL)),
  CHECK (exclusion_cd IS NULL OR computed_status_cd = 'NOT_APPLICABLE'),
  CHECK ((confirmed_yn = 1) = (final_status_cd IS NOT NULL)),
  CHECK (confirmed_yn = 0 OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)),
  CHECK (NOT (confirmed_yn = 1 AND computed_status_cd = 'NEEDS_INPUT')),
  CHECK (confirmed_yn = 0
         OR (computed_status_cd <> 'NEEDS_REVIEW' AND final_status_cd = computed_status_cd)
         OR length(trim(coalesce(confirm_reason_text, ''))) > 0)
) STRICT;

CREATE TABLE judgment_basis (
  basis_id             INTEGER PRIMARY KEY,
  judgment_id          INTEGER NOT NULL REFERENCES judgment(judgment_id) ON DELETE CASCADE,
  item_cd              TEXT    NOT NULL,
  share_ratio          REAL    CHECK (share_ratio BETWEEN 0 AND 1),
  exposure_h           REAL    CHECK (exposure_h  BETWEEN 0 AND 24),
  input_value          REAL,
  unit_cd              TEXT    CHECK (unit_cd IN ('H','KG','CNT_DAY','CNT_MIN','CNT_HOUR','PERSON','RATIO','DEG','YN')),
  threshold_value      REAL,
  threshold_source_cd  TEXT    CHECK (threshold_source_cd IN ('NOTICE','MOEL_NOTE','INVESTIGATOR')),
  UNIQUE (judgment_id, item_cd)
) STRICT;

CREATE TABLE warning (
  warning_id     INTEGER PRIMARY KEY,
  unit_task_id   INTEGER NOT NULL REFERENCES unit_task(unit_task_id) ON DELETE CASCADE,
  criterion_no   INTEGER NOT NULL REFERENCES criterion(criterion_no),
  judgment_id    INTEGER REFERENCES judgment(judgment_id) ON DELETE SET NULL,
  message_text   TEXT    NOT NULL,
  basis_text     TEXT    NOT NULL,
  raised_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  cleared_at     TEXT,
  CHECK (cleared_at IS NULL OR cleared_at >= raised_at)
) STRICT;

CREATE TABLE ai_text (
  ai_text_id      INTEGER PRIMARY KEY,
  purpose_cd      TEXT    NOT NULL CHECK (purpose_cd IN ('WARNING_ADVICE','REPORT_SUMMARY')),
  warning_id      INTEGER REFERENCES warning(warning_id) ON DELETE CASCADE,
  survey_id       INTEGER REFERENCES survey(survey_id) ON DELETE CASCADE,
  model_name      TEXT    NOT NULL,
  prompt_version  TEXT    NOT NULL,
  request_json    TEXT    NOT NULL CHECK (json_valid(request_json)),
  response_text   TEXT,
  result_cd       TEXT    NOT NULL CHECK (result_cd IN ('OK','DISABLED','NO_WARNING','FALLBACK_NO_KEY','FALLBACK_OFFLINE',
                                                         'FALLBACK_TIMEOUT','FALLBACK_ERROR','FALLBACK_NUMBER_MISMATCH')),
  edited_text     TEXT,
  created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  CHECK ((purpose_cd = 'WARNING_ADVICE' AND warning_id IS NOT NULL AND survey_id IS NULL)
      OR (purpose_cd = 'REPORT_SUMMARY' AND survey_id IS NOT NULL AND warning_id IS NULL)),
  CHECK (result_cd <> 'OK' OR response_text IS NOT NULL)
) STRICT;

-- ---------------------------------------------------------------------
-- F. 이력·내보내기·설정
-- ---------------------------------------------------------------------
CREATE TABLE edit_log (
  log_id        INTEGER PRIMARY KEY,
  survey_id     INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  unit_task_id  INTEGER,   -- 외래키를 걸지 않음: 단위작업을 지워도 이력은 남긴다
  target_cd     TEXT    NOT NULL CHECK (target_cd IN ('SURVEY','TASK_INPUT','REBA_INPUT','THRESHOLD','KEY_STILL','JUDGMENT')),
  target_key    TEXT    NOT NULL,
  action_cd     TEXT    NOT NULL CHECK (action_cd IN ('SET','CHANGE','CONFIRM','UNCONFIRM','RESET')),
  old_value     TEXT,
  new_value     TEXT,
  reason_text   TEXT,
  actor_name    TEXT    NOT NULL CHECK (length(trim(actor_name)) > 0),
  logged_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  CHECK (action_cd <> 'CHANGE' OR length(trim(coalesce(reason_text, ''))) > 0)
) STRICT;

CREATE TABLE export_log (
  export_id       INTEGER PRIMARY KEY,
  survey_id       INTEGER NOT NULL REFERENCES survey(survey_id) ON DELETE CASCADE,
  file_path       TEXT    NOT NULL,
  draft_cell_cnt  INTEGER NOT NULL CHECK (draft_cell_cnt >= 0),
  exported_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT;

CREATE TABLE app_setting (
  setting_key    TEXT PRIMARY KEY CHECK (setting_key IN ('POSE_MODEL_ID','GPT_ENABLED','GPT_MODEL','LAST_EXPORT_DIR')),
  setting_value  TEXT NOT NULL,
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT, WITHOUT ROWID;

CREATE TABLE schema_version (
  version_no   INTEGER PRIMARY KEY,
  description  TEXT    NOT NULL,
  applied_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
) STRICT;

-- ---------------------------------------------------------------------
-- 인덱스 (외래키 열 + 조회 경로). 복합 UNIQUE의 첫 열은 별도 인덱스가 필요 없다.
-- ---------------------------------------------------------------------
CREATE INDEX ix_participant_survey  ON participant(survey_id);
CREATE INDEX ix_still_task          ON still(unit_task_id);
CREATE INDEX ix_run_task            ON analysis_run(unit_task_id);
CREATE INDEX ix_run_model           ON analysis_run(model_id);
CREATE INDEX ix_angle_still         ON still_angle(still_id);
CREATE UNIQUE INDEX ux_run_current  ON analysis_run(unit_task_id) WHERE is_current_yn = 1;
CREATE INDEX ix_judgment_run        ON judgment(run_id);
CREATE INDEX ix_judgment_criterion  ON judgment(criterion_no);
CREATE INDEX ix_warning_task        ON warning(unit_task_id);
CREATE INDEX ix_warning_judgment    ON warning(judgment_id);
CREATE INDEX ix_ai_text_warning     ON ai_text(warning_id);
CREATE INDEX ix_ai_text_survey      ON ai_text(survey_id);
CREATE INDEX ix_edit_log_survey     ON edit_log(survey_id, logged_at);
CREATE INDEX ix_export_log_survey   ON export_log(survey_id);

-- ---------------------------------------------------------------------
-- 트리거 (행 하나의 CHECK로는 못 거는 업무 규칙)
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_survey_reason_occasional BEFORE INSERT ON survey_reason
WHEN (SELECT survey_type_cd FROM survey WHERE survey_id = NEW.survey_id) IS NOT 'OCCASIONAL'
BEGIN SELECT RAISE(ABORT, 'survey_reason: 수시조사에만 사유를 넣을 수 있습니다'); END;

CREATE TRIGGER trg_run_has_stills BEFORE INSERT ON analysis_run
WHEN NOT EXISTS (SELECT 1 FROM still WHERE unit_task_id = NEW.unit_task_id AND removed_yn = 0)
BEGIN SELECT RAISE(ABORT, 'analysis_run: 분석할 사진이 없습니다'); END;

CREATE TRIGGER trg_run_consent BEFORE INSERT ON analysis_run
WHEN EXISTS (SELECT 1 FROM still WHERE unit_task_id = NEW.unit_task_id AND removed_yn = 0 AND consent_yn = 0)
BEGIN SELECT RAISE(ABORT, 'analysis_run: 촬영 동의 확인 전에는 분석할 수 없습니다'); END;

CREATE TRIGGER trg_angle_same_task BEFORE INSERT ON still_angle
WHEN (SELECT unit_task_id FROM still WHERE still_id = NEW.still_id)
     IS NOT (SELECT unit_task_id FROM analysis_run WHERE run_id = NEW.run_id)
BEGIN SELECT RAISE(ABORT, 'still_angle: 다른 단위작업의 사진입니다'); END;

CREATE TRIGGER trg_judgment_run_task_ins BEFORE INSERT ON judgment
WHEN NEW.run_id IS NOT NULL
 AND (SELECT unit_task_id FROM analysis_run WHERE run_id = NEW.run_id) IS NOT NEW.unit_task_id
BEGIN SELECT RAISE(ABORT, 'judgment: 다른 단위작업의 분석 결과입니다'); END;

CREATE TRIGGER trg_judgment_run_task_upd BEFORE UPDATE OF run_id ON judgment
WHEN NEW.run_id IS NOT NULL
 AND (SELECT unit_task_id FROM analysis_run WHERE run_id = NEW.run_id) IS NOT NEW.unit_task_id
BEGIN SELECT RAISE(ABORT, 'judgment: 다른 단위작업의 분석 결과입니다'); END;

CREATE TRIGGER trg_edit_log_no_update BEFORE UPDATE ON edit_log
BEGIN SELECT RAISE(ABORT, 'edit_log: 수정 이력은 고칠 수 없습니다'); END;

CREATE TRIGGER trg_edit_log_no_delete BEFORE DELETE ON edit_log
WHEN EXISTS (SELECT 1 FROM survey WHERE survey_id = OLD.survey_id)
BEGIN SELECT RAISE(ABORT, 'edit_log: 수정 이력은 지울 수 없습니다 (조사 전체를 지울 때만 함께 지워집니다)'); END;

-- ---------------------------------------------------------------------
-- 외부 스키마: 뷰
-- ---------------------------------------------------------------------
-- 조사별로 실제 쓰는 각도 기준 (기본값 + 조사자 변경)
CREATE VIEW v_effective_threshold AS
SELECT s.survey_id, d.threshold_cd, d.criterion_no, d.measure_cd,
       COALESCE(o.value_deg, d.value_deg)                    AS value_deg,
       CASE WHEN o.threshold_cd IS NULL THEN 0 ELSE 1 END    AS overridden_yn,
       CASE WHEN o.threshold_cd IS NULL THEN d.source_ref
            ELSE '조사자 변경: ' || o.reason_text END        AS source_label
FROM survey s
CROSS JOIN threshold_default d
LEFT JOIN survey_threshold o ON o.survey_id = s.survey_id AND o.threshold_cd = d.threshold_cd;

-- S01 조사 목록
CREATE VIEW v_survey_list AS
SELECT s.survey_id, s.survey_date, s.survey_type_cd, s.process_name, s.work_name, s.status_cd,
       (SELECT COUNT(*) FROM unit_task t WHERE t.survey_id = s.survey_id) AS task_cnt,
       (SELECT COUNT(*) FROM judgment j JOIN unit_task t ON t.unit_task_id = j.unit_task_id
         WHERE t.survey_id = s.survey_id AND j.confirmed_yn = 0)           AS draft_judgment_cnt,
       CASE WHEN s.survey_type_cd IN ('REGULAR','INITIAL') AND s.confirmed_at IS NOT NULL
            THEN date(s.confirmed_at, '+3 years') END                       AS next_regular_due_date
FROM survey s;

-- S06 분석 결과 · 엑셀 '작업별 결과'
CREATE VIEW v_task_result AS
SELECT t.unit_task_id, t.survey_id, t.task_name, t.period_type_cd, i.daily_work_h,
       r.run_id, r.status_cd AS run_status_cd, r.still_total_cnt, r.still_valid_cnt, r.invalid_ratio,
       m.model_name, m.model_version,
       rb.reba_score, rb.risk_level_cd, rb.key_still_id, rb.provisional_yn,
       (SELECT COUNT(*) FROM warning w WHERE w.unit_task_id = t.unit_task_id AND w.cleared_at IS NULL) AS open_warning_cnt
FROM unit_task t
LEFT JOIN task_input   i  ON i.unit_task_id = t.unit_task_id
LEFT JOIN analysis_run r  ON r.unit_task_id = t.unit_task_id AND r.is_current_yn = 1
LEFT JOIN pose_model   m  ON m.model_id = r.model_id
LEFT JOIN reba_result  rb ON rb.run_id = r.run_id;

-- S07 판정 · 엑셀 '판정 초안'
CREATE VIEW v_judgment_sheet AS
SELECT t.survey_id, j.unit_task_id, t.task_name, j.criterion_no, c.short_name,
       COALESCE(j.final_status_cd, j.computed_status_cd)       AS status_cd,
       CASE WHEN j.confirmed_yn = 1 THEN '확정' ELSE '초안' END AS draft_label,
       j.review_reason_cd, j.exclusion_cd, j.basis_text, j.source_text,
       j.confirmed_by, j.confirmed_at, j.confirm_reason_text
FROM judgment j
JOIN unit_task t ON t.unit_task_id = j.unit_task_id
JOIN criterion c ON c.criterion_no = j.criterion_no;

-- 엑셀 '요약'의 단위작업별 결론
CREATE VIEW v_excel_summary AS
SELECT t.survey_id, t.unit_task_id, t.task_name,
       (SELECT group_concat(j.criterion_no || '호', ', ' ORDER BY j.criterion_no)
          FROM judgment j
         WHERE j.unit_task_id = t.unit_task_id
           AND COALESCE(j.final_status_cd, j.computed_status_cd) = 'APPLICABLE') AS applicable_criteria,
       (SELECT COUNT(*) FROM judgment j WHERE j.unit_task_id = t.unit_task_id AND j.confirmed_yn = 0) AS draft_cnt,
       tr.reba_score, tr.risk_level_cd
FROM unit_task t
LEFT JOIN v_task_result tr ON tr.unit_task_id = t.unit_task_id;

-- 엑셀 '경고 기록'
CREATE VIEW v_warning_log AS
SELECT t.survey_id, w.warning_id, t.task_name, w.criterion_no, w.message_text, w.basis_text,
       w.raised_at, w.cleared_at,
       (SELECT a.result_cd FROM ai_text a WHERE a.warning_id = w.warning_id
         ORDER BY a.ai_text_id DESC LIMIT 1) AS latest_ai_result_cd
FROM warning w
JOIN unit_task t ON t.unit_task_id = w.unit_task_id;

-- GPT 어댑터가 읽을 수 있는 유일한 뷰: 이름·경로·자유 입력 글은 담지 않는다
-- warning_id · survey_id · unit_task_id는 거르고 묶는 데만 쓰고 GPT에 보내지 않는다
CREATE VIEW v_gpt_payload AS
SELECT w.warning_id, t.survey_id, w.unit_task_id,
       (SELECT COUNT(*) FROM unit_task t2 WHERE t2.survey_id = t.survey_id) AS survey_task_cnt,
       w.criterion_no, c.short_name AS criterion_summary,
       c.legal_text AS criterion_legal_text,      -- 공개 법령 문구 (숫자 검증용)
       i.daily_work_h,
       (SELECT MAX(b.share_ratio) FROM judgment_basis b WHERE b.judgment_id = w.judgment_id) AS max_share_ratio,
       (SELECT MAX(b.exposure_h)  FROM judgment_basis b WHERE b.judgment_id = w.judgment_id) AS max_exposure_h,
       rb.reba_score, rb.risk_level_cd
FROM warning w
JOIN unit_task t          ON t.unit_task_id = w.unit_task_id
JOIN criterion c          ON c.criterion_no = w.criterion_no
LEFT JOIN task_input i    ON i.unit_task_id = w.unit_task_id
LEFT JOIN analysis_run r  ON r.unit_task_id = w.unit_task_id AND r.is_current_yn = 1
LEFT JOIN reba_result rb  ON rb.run_id = r.run_id
WHERE w.cleared_at IS NULL;

-- S07 수정 이력
CREATE VIEW v_edit_log AS
SELECT survey_id, unit_task_id, logged_at, actor_name, target_cd, target_key, action_cd,
       old_value, new_value, reason_text
FROM edit_log;

-- 검증용: 저장된 사진별 각도로 자세 비율과 하루 노출 시간을 다시 계산한다.
-- 앱의 판정에는 쓰지 않고, 분석 엔진의 결과와 대조하는 데만 쓴다.
CREATE VIEW v_posture_exposure_check AS
SELECT r.run_id, r.unit_task_id, t.survey_id, i.daily_work_h,
       SUM(f.valid_yn) AS valid_still_cnt,
       AVG(CASE WHEN f.valid_yn = 1 THEN (f.trunk_tilt_deg >= wf.value_deg AND COALESCE(f.knee_on_floor_yn, 0) = 0) END) AS waist_flex_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN (f.trunk_tilt_deg <= -we.value_deg) END)                                    AS waist_ext_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN (f.neck_tilt_vert_deg >= nf.value_deg) END)                                 AS neck_flex_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN (f.hand_above_head_yn = 1 OR f.elbow_above_shoulder_yn = 1
                                          OR f.elbow_behind_trunk_yn = 1
                                          OR MAX(COALESCE(f.upper_arm_raise_l_deg, -1), COALESCE(f.upper_arm_raise_r_deg, -1)) >= ua.value_deg) END) AS p3_union_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN f.squat_yn END)    AS squat_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN f.kneeling_yn END) AS kneeling_ratio,
       AVG(CASE WHEN f.valid_yn = 1 THEN (f.trunk_tilt_deg >= wf.value_deg AND COALESCE(f.knee_on_floor_yn, 0) = 0) END) * i.daily_work_h AS waist_flex_h
FROM analysis_run r
JOIN unit_task t   ON t.unit_task_id = r.unit_task_id
JOIN still_angle f ON f.run_id = r.run_id
LEFT JOIN task_input i ON i.unit_task_id = r.unit_task_id
JOIN v_effective_threshold wf ON wf.survey_id = t.survey_id AND wf.threshold_cd = 'WAIST_FLEX'
JOIN v_effective_threshold we ON we.survey_id = t.survey_id AND we.threshold_cd = 'WAIST_EXT'
JOIN v_effective_threshold nf ON nf.survey_id = t.survey_id AND nf.threshold_cd = 'NECK_FLEX'
JOIN v_effective_threshold ua ON ua.survey_id = t.survey_id AND ua.threshold_cd = 'UPPER_ARM_RAISE'
GROUP BY r.run_id;
