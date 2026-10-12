"""ergo.contracts — 화면 ↔ 앱 코어 계약 v0.2 (API 계약서 ERGO-API-001)

규칙
- 값(Enum)은 ERD(ERGO-DD-001)의 코드값과 같다.
- 필드 이름은 ERD의 컬럼 이름과 같다.
- None은 '아직 입력하지 않음'이다. 0으로 채우지 않는다 (기능정의서 F02-02).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

CONTRACT_VERSION = "0.2"


# ---------------------------------------------------------------- 코드 (ERD 4.4)
class SurveyType(str, Enum):
    REGULAR = "REGULAR"
    OCCASIONAL = "OCCASIONAL"
    INITIAL = "INITIAL"


class OccasionalReason(str, Enum):
    MSD_CASE = "MSD_CASE"
    NEW_TASK = "NEW_TASK"
    ENV_CHANGE = "ENV_CHANGE"


class SurveyStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"


class ParticipantType(str, Enum):
    REPRESENTATIVE = "REPRESENTATIVE"
    WORKER = "WORKER"


class PeriodType(str, Enum):
    ONGOING = "ONGOING"
    SHORT_TERM = "SHORT_TERM"
    INTERMITTENT = "INTERMITTENT"


class BodyPart(str, Enum):
    NECK = "NECK"
    SHOULDER = "SHOULDER"
    ELBOW = "ELBOW"
    WRIST = "WRIST"
    HAND = "HAND"


class LiftPosition(str, Enum):
    BELOW_KNEE = "BELOW_KNEE"
    ABOVE_SHOULDER = "ABOVE_SHOULDER"
    ARM_EXTENDED = "ARM_EXTENDED"


class Coupling(str, Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    UNACCEPTABLE = "UNACCEPTABLE"


class WristFlex(str, Enum):
    LE15 = "LE15"
    GT15 = "GT15"


class LegsSupport(str, Enum):
    BILATERAL = "BILATERAL"
    UNILATERAL = "UNILATERAL"


class ThresholdCode(str, Enum):
    NECK_FLEX = "NECK_FLEX"
    WAIST_FLEX = "WAIST_FLEX"
    WAIST_EXT = "WAIST_EXT"
    NECK_TWIST = "NECK_TWIST"
    WAIST_TWIST = "WAIST_TWIST"
    UPPER_ARM_RAISE = "UPPER_ARM_RAISE"


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class Stage(str, Enum):
    DECODE = "DECODE"
    KEYPOINT = "KEYPOINT"
    ANGLE = "ANGLE"
    JUDGE = "JUDGE"
    SAVE = "SAVE"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class RiskLevel(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class JudgmentStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NEEDS_INPUT = "NEEDS_INPUT"


class FinalStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewReason(str, Enum):
    JITTER = "JITTER"
    INVALID_FRAMES = "INVALID_FRAMES"
    INTERPRETATION = "INTERPRETATION"
    MULTI_PERSON = "MULTI_PERSON"
    LEGS_CUT = "LEGS_CUT"
    KNEE_ON_FLOOR = "KNEE_ON_FLOOR"


class Exclusion(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    INTERMITTENT = "INTERMITTENT"


class ThresholdSource(str, Enum):
    NOTICE = "NOTICE"
    MOEL_NOTE = "MOEL_NOTE"
    INVESTIGATOR = "INVESTIGATOR"


class AiPurpose(str, Enum):
    WARNING_ADVICE = "WARNING_ADVICE"
    REPORT_SUMMARY = "REPORT_SUMMARY"


class AiResult(str, Enum):
    OK = "OK"
    DISABLED = "DISABLED"
    NO_WARNING = "NO_WARNING"            # 보고서 요약: 열린 경고가 없어 GPT를 부르지 않음
    FALLBACK_NO_KEY = "FALLBACK_NO_KEY"
    FALLBACK_OFFLINE = "FALLBACK_OFFLINE"
    FALLBACK_TIMEOUT = "FALLBACK_TIMEOUT"
    FALLBACK_ERROR = "FALLBACK_ERROR"
    FALLBACK_NUMBER_MISMATCH = "FALLBACK_NUMBER_MISMATCH"


# ---------------------------------------------------------------- 오류와 알림 (8절)
# API 계약서 8절의 오류·알림 코드 (E 오류 · W 경고 알림 · I 안내). 8절 표와 같아야 한다 (docs_src가 자동으로 대조한다)
ERROR_CODES = frozenset({
    "E-INPUT-001", "E-INPUT-002", "E-INPUT-003", "E-NOTFOUND-001",
    "E-VIDEO-001", "W-VIDEO-002", "E-VIDEO-003", "E-VIDEO-004",
    "E-ANALYSIS-001", "W-ANALYSIS-002", "W-ANALYSIS-003", "E-ANALYSIS-004", "I-ANALYSIS-005", "E-ANALYSIS-009",
    "E-CONFIRM-001", "E-CONFIRM-002", "E-CONFIRM-003", "E-THRESHOLD-001",
    "E-EXPORT-001", "E-DB-001", "E-DB-002", "W-GPT-001",
})


class ErgoError(Exception):
    """처리를 멈추는 오류. code는 8절 오류 코드 (E-…)."""

    def __init__(self, code: str, message: str, detail: Optional[dict] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.detail = detail or {}


@dataclass(frozen=True)
class Notice:
    """처리는 계속하되 화면에 알릴 것 (W-…, I-…)."""
    code: str
    message: str


# ---------------------------------------------------------------- 조사
@dataclass(frozen=True)
class SurveyCreate:
    survey_type_cd: SurveyType
    survey_date: str                      # YYYY-MM-DD
    investigator_name: str
    dept_name: str
    process_name: str
    work_name: str
    occasional_reasons: tuple[OccasionalReason, ...] = ()


@dataclass(frozen=True)
class SurveyUpdate:
    survey_date: Optional[str] = None
    investigator_name: Optional[str] = None
    dept_name: Optional[str] = None
    process_name: Optional[str] = None
    work_name: Optional[str] = None
    occasional_reasons: Optional[tuple[OccasionalReason, ...]] = None


@dataclass(frozen=True)
class SurveySummary:                      # v_survey_list
    survey_id: int
    survey_date: str
    survey_type_cd: SurveyType
    process_name: str
    work_name: str
    status_cd: SurveyStatus
    task_cnt: int
    draft_judgment_cnt: int
    next_regular_due_date: Optional[str]


@dataclass(frozen=True)
class Participant:
    participant_id: int
    participant_type_cd: ParticipantType
    display_name: str


@dataclass(frozen=True)
class UnitTask:
    unit_task_id: int
    task_name: str
    task_desc: Optional[str]
    worker_cnt: int
    period_type_cd: PeriodType
    sort_no: int


@dataclass(frozen=True)
class SurveyDetail:
    survey_id: int
    survey_type_cd: SurveyType
    survey_date: str
    investigator_name: str
    dept_name: str
    process_name: str
    work_name: str
    status_cd: SurveyStatus
    confirmed_at: Optional[str]
    occasional_reasons: tuple[OccasionalReason, ...]
    participants: tuple[Participant, ...]
    unit_tasks: tuple[UnitTask, ...]


# ---------------------------------------------------------------- 단위작업과 입력
@dataclass(frozen=True)
class UnitTaskCreate:
    task_name: str
    worker_cnt: int
    period_type_cd: PeriodType
    task_desc: Optional[str] = None


@dataclass(frozen=True)
class TaskInputs:                         # task_input
    daily_work_h: Optional[float] = None
    unsupported_posture_yn: Optional[bool] = None
    neck_twist_h: Optional[float] = None
    waist_twist_h: Optional[float] = None
    keyboard_h: Optional[float] = None
    keyboard_self_paced_yn: Optional[bool] = None
    finger_pinch_kg: Optional[float] = None
    finger_grip_kg: Optional[float] = None
    finger_h: Optional[float] = None
    finger_unsupported_yn: Optional[bool] = None
    onehand_kg: Optional[float] = None
    onehand_h: Optional[float] = None
    onehand_unsupported_yn: Optional[bool] = None
    lift_kg: Optional[float] = None
    lift_people_cnt: Optional[int] = None
    lift_cnt_per_day: Optional[int] = None
    freq_lift_kg: Optional[float] = None
    freq_lift_per_min: Optional[float] = None
    freq_lift_h: Optional[float] = None
    impact_h: Optional[float] = None
    impact_per_hour: Optional[int] = None


@dataclass(frozen=True)
class RepetitionInput:                    # repetition_input (2호)
    body_part_cd: BodyPart
    repeat_h: float


@dataclass(frozen=True)
class LiftPositionInput:                  # lift_position_input (9호)
    position_cd: LiftPosition
    lift_cnt_per_day: int
    weight_kg: float


@dataclass(frozen=True)
class RebaInputs:                         # reba_input. None = '사람 확인'
    load_kg: Optional[float] = None
    shock_yn: Optional[bool] = None
    coupling_cd: Optional[Coupling] = None
    wrist_flex_cd: Optional[WristFlex] = None
    wrist_twist_yn: Optional[bool] = None
    neck_twist_side_yn: Optional[bool] = None
    trunk_twist_side_yn: Optional[bool] = None
    legs_support_cd: Optional[LegsSupport] = None
    shoulder_raised_yn: Optional[bool] = None
    arm_abducted_yn: Optional[bool] = None
    arm_supported_yn: Optional[bool] = None
    act_static_yn: Optional[bool] = None
    act_repeat_yn: Optional[bool] = None
    act_rapid_yn: Optional[bool] = None


@dataclass(frozen=True)
class TaskInputBundle:                    # S03 화면을 채우는 값 (get_task_inputs)
    unit_task_id: int
    inputs: TaskInputs
    repetitions: tuple[RepetitionInput, ...]
    lift_positions: tuple[LiftPositionInput, ...]


# ---------------------------------------------------------------- 영상과 분석
@dataclass(frozen=True)
class VideoInfo:
    video_id: Optional[int]               # inspect_video는 None (아직 저장 전)
    file_path: str
    file_name: str
    duration_s: float
    fps: float
    frame_cnt: int
    width_px: int
    height_px: int
    rotation_deg: int
    consent_yn: bool
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class RunHandle:
    run_id: int
    unit_task_id: int
    video_id: int
    model_id: int


@dataclass(frozen=True)
class Progress:
    run_id: int
    stage: Stage
    processed_frames: int
    total_frames: int
    percent: float                        # 0 ~ 100
    eta_s: Optional[float] = None
    error_code: Optional[str] = None      # stage == FAILED일 때
    error_message: Optional[str] = None


ProgressCallback = Callable[[Progress], None]


@dataclass(frozen=True)
class PostureSegment:                     # S06 시간 막대의 한 구간
    item_cd: str                          # 예: WAIST_FLEX, NECK_FLEX, P3_UNION, SQUAT, INVALID(판별 불가)
    start_frame_no: int
    end_frame_no: int                     # 이 프레임까지 포함


@dataclass(frozen=True)
class PostureTimeline:                    # S06 시간 막대 (get_posture_timeline). 저장하지 않고 계산한다
    run_id: int
    fps: float
    frame_cnt: int
    segments: tuple[PostureSegment, ...]


# ---------------------------------------------------------------- 결과와 판정
@dataclass(frozen=True)
class RebaScore:                          # reba_result
    side_cd: str
    neck_score: int
    trunk_score: int
    legs_score: int
    table_a_score: int
    load_score: int
    score_a: int
    upper_arm_score: int
    lower_arm_score: int
    wrist_score: int
    table_b_score: int
    coupling_score: int
    score_b: int
    table_c_score: int
    activity_score: int
    reba_score: int
    risk_level_cd: RiskLevel
    provisional_yn: bool
    needs_review_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class PostureShare:
    item_cd: str                          # 예: WAIST_FLEX, P3_UNION, SQUAT
    share_ratio: float
    exposure_h: Optional[float]           # 하루 작업시간이 없으면 None
    threshold_value: Optional[float]
    threshold_source_cd: Optional[ThresholdSource]


@dataclass(frozen=True)
class JudgmentBasis:                      # judgment_basis
    item_cd: str
    share_ratio: Optional[float] = None
    exposure_h: Optional[float] = None
    input_value: Optional[float] = None
    unit_cd: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_source_cd: Optional[ThresholdSource] = None


@dataclass(frozen=True)
class Judgment:                           # v_judgment_sheet + judgment_basis
    unit_task_id: int
    criterion_no: int
    short_name: str
    computed_status_cd: JudgmentStatus
    final_status_cd: Optional[FinalStatus]
    confirmed_yn: bool
    review_reason_cd: Optional[ReviewReason]
    exclusion_cd: Optional[Exclusion]
    basis_text: str
    source_text: str
    basis: tuple[JudgmentBasis, ...]
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirm_reason_text: Optional[str] = None


@dataclass(frozen=True)
class WarningItem:                        # warning + 최신 ai_text
    warning_id: int
    criterion_no: int
    message_text: str
    basis_text: str
    raised_at: str
    ai_text: Optional[str] = None
    ai_result_cd: Optional[AiResult] = None


@dataclass(frozen=True)
class TaskResult:                         # S06
    unit_task_id: int
    run: Optional[RunHandle]
    run_status_cd: Optional[RunStatus]
    invalid_ratio: Optional[float]
    reba: Optional[RebaScore]
    key_frame_no: Optional[int]
    key_frame_jpeg: Optional[bytes]       # 얼굴을 가린 JPEG만
    shares: tuple[PostureShare, ...]
    judgments: tuple[Judgment, ...]
    warnings: tuple[WarningItem, ...]
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class JudgmentChange:
    criterion_no: int
    before: JudgmentStatus
    after: JudgmentStatus
    unconfirmed: bool                     # 확정이 풀렸는지 (기능정의서 3.2절 규칙 3)


@dataclass(frozen=True)
class RecalcResult:
    changes: tuple[JudgmentChange, ...]
    warnings_raised: tuple[int, ...]      # criterion_no
    warnings_cleared: tuple[int, ...]
    result: TaskResult


@dataclass(frozen=True)
class ConfirmAllResult:
    confirmed: tuple[int, ...]            # criterion_no
    needs_decision: tuple[int, ...]       # '사람 확인'이라 조사자 결정이 필요
    blocked: tuple[int, ...]              # '입력 필요'라 확정할 수 없음


@dataclass(frozen=True)
class Threshold:                          # v_effective_threshold
    threshold_cd: ThresholdCode
    criterion_no: int
    measure_cd: str
    value_deg: float
    overridden_yn: bool
    source_label: str


@dataclass(frozen=True)
class EditLogEntry:                       # v_edit_log
    logged_at: str
    actor_name: str
    target_cd: str
    target_key: str
    action_cd: str
    old_value: Optional[str]
    new_value: Optional[str]
    reason_text: Optional[str]
    unit_task_id: Optional[int]


# ---------------------------------------------------------------- 보고서, AI, 설정
@dataclass(frozen=True)
class ExportResult:
    file_path: str
    draft_cell_cnt: int
    backup_path: Optional[str]
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class AiTextResult:
    ai_text_id: int
    purpose_cd: AiPurpose
    text: str                             # GPT 문장 또는 기본 문구
    result_cd: AiResult
    is_ai: bool                           # True면 화면에 'AI 작성' 표시


@dataclass(frozen=True)
class PoseModel:
    model_id: int
    model_name: str
    model_version: str
    keypoint_cnt: int


@dataclass(frozen=True)
class Settings:
    pose_model_id: int
    gpt_enabled: bool
    gpt_model: Optional[str]
    has_gpt_key: bool                     # 키 자체는 돌려주지 않는다
    last_export_dir: Optional[str]


# ---------------------------------------------------------------- 서비스 API (4절)
class ServiceAPI(Protocol):
    # 4.1 조사
    def create_survey(self, data: SurveyCreate) -> SurveyDetail: ...
    def list_surveys(self) -> Sequence[SurveySummary]: ...
    def get_survey(self, survey_id: int) -> SurveyDetail: ...
    def update_survey(self, survey_id: int, data: SurveyUpdate, actor: str) -> SurveyDetail: ...
    def delete_survey(self, survey_id: int, actor: str) -> None: ...
    def add_participant(self, survey_id: int, participant_type_cd: ParticipantType, display_name: str) -> Participant: ...
    def remove_participant(self, participant_id: int) -> None: ...
    def confirm_survey(self, survey_id: int, actor: str) -> SurveyDetail: ...

    # 4.2 단위작업과 입력
    def create_unit_task(self, survey_id: int, data: UnitTaskCreate) -> UnitTask: ...
    def update_unit_task(self, unit_task_id: int, data: UnitTaskCreate, actor: str) -> RecalcResult: ...
    def delete_unit_task(self, unit_task_id: int, actor: str) -> None: ...
    def save_task_inputs(self, unit_task_id: int, inputs: TaskInputs, actor: str) -> RecalcResult: ...
    def save_repetition_inputs(self, unit_task_id: int, items: Sequence[RepetitionInput], actor: str) -> RecalcResult: ...
    def save_lift_position_inputs(self, unit_task_id: int, items: Sequence[LiftPositionInput], actor: str) -> RecalcResult: ...
    def save_reba_inputs(self, unit_task_id: int, inputs: RebaInputs, actor: str) -> RecalcResult: ...
    def get_task_inputs(self, unit_task_id: int) -> TaskInputBundle: ...
    def get_reba_inputs(self, unit_task_id: int) -> RebaInputs: ...

    # 4.3 영상과 분석
    def inspect_video(self, path: Path) -> VideoInfo: ...
    def list_videos(self, unit_task_id: int) -> Sequence[VideoInfo]: ...
    def attach_video(self, unit_task_id: int, path: Path, consent: bool, actor: str) -> VideoInfo: ...
    def confirm_consent(self, video_id: int, actor: str) -> VideoInfo: ...
    def start_analysis(self, unit_task_id: int, video_id: int, on_progress: ProgressCallback) -> RunHandle: ...
    def cancel_analysis(self, run_id: int) -> None: ...

    # 4.4 결과와 판정
    def get_task_result(self, unit_task_id: int) -> TaskResult: ...
    def get_frame_preview(self, run_id: int, frame_no: int) -> bytes: ...
    def get_posture_timeline(self, unit_task_id: int) -> PostureTimeline: ...
    def set_key_frame(self, unit_task_id: int, frame_no: int, actor: str) -> TaskResult: ...
    def confirm_judgment(self, unit_task_id: int, criterion_no: int, final_status: FinalStatus,
                         reason: Optional[str], actor: str) -> Judgment: ...
    def confirm_all(self, unit_task_id: int, actor: str) -> ConfirmAllResult: ...
    def unconfirm_judgment(self, unit_task_id: int, criterion_no: int, reason: str, actor: str) -> Judgment: ...
    def list_edit_log(self, survey_id: int) -> Sequence[EditLogEntry]: ...

    # 4.5 각도 기준
    def get_thresholds(self, survey_id: int) -> Sequence[Threshold]: ...
    def set_threshold(self, survey_id: int, threshold_cd: ThresholdCode, value_deg: float,
                      reason: str, actor: str) -> Sequence[RecalcResult]: ...
    def reset_threshold(self, survey_id: int, threshold_cd: ThresholdCode, actor: str) -> Sequence[RecalcResult]: ...

    # 4.6 보고서와 AI 문장
    def export_excel(self, survey_id: int, path: Path, actor: str, with_db_backup: bool = True) -> ExportResult: ...
    def request_warning_advice(self, warning_id: int) -> AiTextResult: ...
    def request_report_summary(self, survey_id: int) -> AiTextResult: ...
    def edit_ai_text(self, ai_text_id: int, text: str, actor: str) -> AiTextResult: ...

    # 4.7 설정
    def get_settings(self) -> Settings: ...
    def save_settings(self, pose_model_id: int, gpt_enabled: bool, gpt_model: Optional[str]) -> Settings: ...
    def set_gpt_api_key(self, key: str) -> None: ...
    def delete_gpt_api_key(self) -> None: ...
    def list_models(self) -> Sequence[PoseModel]: ...
