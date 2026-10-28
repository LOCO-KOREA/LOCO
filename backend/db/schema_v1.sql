-- Canonical six-table demo schema from docs/ERD_데이터설계서.md.
-- JSON DTOs are stored as UTF-8 text. Business calculations stay in Python modules.

CREATE TABLE IF NOT EXISTS SURVEY (
  survey_id INTEGER PRIMARY KEY,
  metadata_revision INTEGER,
  metadata_json TEXT,
  review_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS TASK (
  task_id INTEGER PRIMARY KEY,
  survey_id INTEGER,
  input_revision INTEGER,
  latest_analysis_id INTEGER,
  input_json TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS PHOTO (
  photo_id INTEGER PRIMARY KEY,
  task_id INTEGER,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS ANALYSIS (
  analysis_id INTEGER PRIMARY KEY,
  task_id INTEGER,
  input_revision INTEGER,
  status TEXT,
  snapshot_json TEXT,
  result_json TEXT,
  created_at TEXT,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS APP_SETTINGS (
  settings_id INTEGER PRIMARY KEY,
  settings_json TEXT
);

CREATE TABLE IF NOT EXISTS EXPORT_LOG (
  export_id INTEGER PRIMARY KEY,
  survey_id INTEGER,
  file_path TEXT,
  snapshot_json TEXT,
  receipt_json TEXT,
  created_at TEXT
);
