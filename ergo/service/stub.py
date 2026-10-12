"""ServiceAPI의 가짜 구현 (스텁). 진짜 서비스가 나오기 전에 화면을 만들 수 있게 한다.

- 값은 화면설계서의 예시와 같다: 2026-10-23 정기조사, 포장공정, '상자 들어 옮기기',
  허리 굽힘 35% × 하루 6시간 = 2.10시간, REBA 9 (표 C 8 + 활동 1).
- 판정과 점수를 제대로 계산하지 않는다. 그래도 화면의 '다시 계산' 흐름을 볼 수 있도록 몇 가지만 흉내 낸다:
  1호 (키보드 시간), 4호 (허리 굽힘 비율 × 하루 작업시간), 8호 (무게 ÷ 인원), 9호 (위치별 횟수).
  나머지 호는 입력해도 바뀌지 않는다. 진짜 계산은 ergo/engine/ 에서 만든다.
- 오류는 API 계약서 8절의 코드로 던진다. 진짜 서비스도 tests/contract_suite.py를 통과해야 한다.
- 분석은 백그라운드 스레드에서 진행률을 0.2초마다 보낸다 (API 계약서 4.3절). 화면은 이 콜백을
  자기 스레드로 넘겨서 그려야 한다.
"""
from __future__ import annotations

import base64
import itertools
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from .. import contracts as C
from ..contracts import ErgoError

# 96×60 단색 JPEG (미리보기, 대표 장면 자리표시자). Pillow로 만든 진짜 JPEG
_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkz"
    "ODdASFxOQERXRTc4UG1RV19iZ2hnPk1xeXBkeFxlZ2P/2wBDARESEhgVGC8aGi9jQjhCY2NjY2Nj"
    "Y2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2P/wAARCAA8AGADASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDlqKKK"
    "1MwooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKK"
    "ACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP/Z"
)

_CRITERIA = {
    1: "키보드·마우스 집중 입력", 2: "같은 동작 반복", 3: "팔을 들거나 뒤로 한 자세", 4: "목·허리 굽힘·비틀림",
    5: "쪼그림·무릎 굽힘", 6: "손가락 집기·쥐기", 7: "한 손 들기·쥐기", 8: "25kg 이상 들기",
    9: "불편한 위치에서 10kg 들기", 10: "자주 드는 작업", 11: "손·무릎 충격",
}
# 각도 기준 기본값 (시드의 threshold_default와 같아야 한다 — tests/test_stub_contract.py가 대조한다)
_THRESHOLDS = {
    C.ThresholdCode.NECK_FLEX: (4, "VIDEO", 20.0, "해설 4호 주3"),
    C.ThresholdCode.WAIST_FLEX: (4, "VIDEO", 20.0, "해설 4호 주3"),
    C.ThresholdCode.WAIST_EXT: (4, "VIDEO", 20.0, "해설 4호 주3"),
    C.ThresholdCode.NECK_TWIST: (4, "INVESTIGATOR", 5.0, "해설 4호 주4"),
    C.ThresholdCode.WAIST_TWIST: (4, "INVESTIGATOR", 20.0, "해설 4호 주4"),
    C.ThresholdCode.UPPER_ARM_RAISE: (3, "VIDEO", 45.0, "해설 3호 주1"),
}
_MODELS = (
    C.PoseModel(1, "MoveNet Lightning", "pose2 sample", 17),
    C.PoseModel(2, "MoveNet Thunder", "pose2 sample", 17),
    C.PoseModel(3, "MediaPipe Pose Lite", "1.1.0", 33),
    C.PoseModel(4, "MediaPipe Pose Full", "1.1.0", 33),
    C.PoseModel(5, "MediaPipe Pose Heavy", "1.1.0", 33),
)
_TABLE_C_ROW_A8 = (8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11)   # REBA 표 C에서 점수 A = 8인 줄
_SHARE_BY_THRESHOLD = ((20.0, 0.35), (30.0, 0.20), (999.0, 0.05))   # 허리 굽힘 기준을 올리면 비율이 줄어드는 것을 흉내 냄


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _need(cond: bool, code: str, message: str):
    if not cond:
        raise ErgoError(code, message)


class StubService:
    def __init__(self, progress_delay_s: float = 0.2):
        self._delay = progress_delay_s
        self._lock = threading.RLock()
        self._id = {k: itertools.count(v) for k, v in dict(
            survey=2, task=13, participant=3, video=102, run=1001, warning=1, ai=2, log=1).items()}
        self._surveys: dict[int, dict] = {1: dict(
            type=C.SurveyType.REGULAR, date="2026-10-23", investigator="홍길동", dept="포장부",
            process="포장공정", work="상자 포장 및 운반", status=C.SurveyStatus.DRAFT, confirmed_at=None, reasons=())}
        self._participants: dict[int, dict] = {
            1: dict(survey=1, type=C.ParticipantType.REPRESENTATIVE, name="김OO"),
            2: dict(survey=1, type=C.ParticipantType.WORKER, name="근로자 A")}
        self._tasks: dict[int, dict] = {
            10: dict(survey=1, name="상자 들어 옮기기", desc="상자를 바닥에서 들어 수레에 옮김", workers=2, period=C.PeriodType.ONGOING, sort=1),
            11: dict(survey=1, name="선반 정리", desc=None, workers=1, period=C.PeriodType.ONGOING, sort=2),
            12: dict(survey=1, name="수레 밀기", desc=None, workers=1, period=C.PeriodType.SHORT_TERM, sort=3)}
        self._inputs: dict[int, C.TaskInputs] = {
            10: C.TaskInputs(daily_work_h=6.0, unsupported_posture_yn=True, neck_twist_h=0.5, lift_kg=15.0,
                             lift_people_cnt=1, lift_cnt_per_day=300),
            11: C.TaskInputs(), 12: C.TaskInputs()}
        self._reps: dict[int, tuple] = {10: (C.RepetitionInput(C.BodyPart.HAND, 1.5),), 11: (), 12: ()}
        self._lifts: dict[int, tuple] = {10: (C.LiftPositionInput(C.LiftPosition.BELOW_KNEE, 300, 15.0),
                                              C.LiftPositionInput(C.LiftPosition.ARM_EXTENDED, 20, 15.0)), 11: (), 12: ()}
        self._reba_in: dict[int, C.RebaInputs] = {
            10: C.RebaInputs(load_kg=15.0, shock_yn=False, coupling_cd=C.Coupling.GOOD, trunk_twist_side_yn=True,
                             act_repeat_yn=True), 11: C.RebaInputs(), 12: C.RebaInputs()}
        self._videos: dict[int, dict] = {100: dict(
            task=10, path="D:/영상/상자옮기기_측면.mp4", name="상자옮기기_측면.mp4", dur=32.0, fps=30.0, frames=960,
            w=1080, h=1920, rot=90, consent=True)}
        self._runs: dict[int, dict] = {10: dict(run_id=1000, video=100, model=4, key_frame=216, status=C.RunStatus.DONE)}
        self._running: dict[int, dict] = {}
        self._judg: dict[int, dict[int, dict]] = {}
        self._warn: dict[int, dict] = {}
        self._ai: dict[int, dict] = {}
        self._log: list[tuple[int, C.EditLogEntry]] = []
        self._thr: dict[int, dict[C.ThresholdCode, tuple[float, str]]] = {1: {}}
        self._settings = dict(pose_model_id=4, gpt_enabled=False, gpt_model=None, has_key=False, last_dir=None)
        for tid in self._tasks:
            self._judg[tid] = {n: self._blank(tid, n) for n in _CRITERIA}
        self._recalc(10, log=False)
        self._judg[10][2].update(final=C.FinalStatus.NOT_APPLICABLE, confirmed=True, by="홍길동", at="2026-10-23T14:02:00")
        self._judg[10][5].update(final=C.FinalStatus.NOT_APPLICABLE, confirmed=True, by="홍길동", at="2026-10-23T14:03:00")
        self._judg[10][3].update(status=C.JudgmentStatus.NEEDS_REVIEW, reason=C.ReviewReason.JITTER,
                                 basis="30% × 6시간 = 1.80시간 · 각도를 ±5° 바꾸면 1.50~2.28시간 (기준 2시간 근처)")
        self._judg[10][2].update(status=C.JudgmentStatus.NOT_APPLICABLE, basis="부위별 반복 시간 중 가장 긴 것 1.5시간 < 2시간")
        self._judg[10][5].update(status=C.JudgmentStatus.NOT_APPLICABLE, basis="쪼그림 5% × 6시간 = 0.30시간")
        self._ensure_warnings(10)
        w4 = next(wid for wid, w in self._warn.items() if w["task"] == 10 and w["criterion"] == 4)
        self._ai[1] = dict(purpose=C.AiPurpose.WARNING_ADVICE, warning=w4, survey=None,
                           text="상자를 허리 높이 선반에 두면 굽힘을 줄일 수 있어요.", result=C.AiResult.OK, is_ai=True)
        self._warn[w4]["ai"] = 1

    # ------------------------------------------------------------ 내부 도우미
    def _survey(self, sid: int) -> dict:
        _need(sid in self._surveys, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
        return self._surveys[sid]

    def _task(self, tid: int) -> dict:
        _need(tid in self._tasks, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
        return self._tasks[tid]

    def _blank(self, tid: int, no: int) -> dict:
        period = self._tasks[tid]["period"]
        if period in (C.PeriodType.SHORT_TERM, C.PeriodType.INTERMITTENT):
            excl = C.Exclusion.SHORT_TERM if period == C.PeriodType.SHORT_TERM else C.Exclusion.INTERMITTENT
            return dict(status=C.JudgmentStatus.NOT_APPLICABLE, final=None, confirmed=False, reason=None, excl=excl,
                        basis="단기간·간헐 작업이라 부담작업에서 제외", by=None, at=None, why=None)
        return dict(status=C.JudgmentStatus.NEEDS_INPUT, final=None, confirmed=False, reason=None, excl=None,
                    basis="필요한 값을 넣어 주세요", by=None, at=None, why=None)

    def _threshold_value(self, sid: int, code: C.ThresholdCode) -> tuple[float, bool, str]:
        over = self._thr.get(sid, {}).get(code)
        base = _THRESHOLDS[code]
        if over:
            return over[0], True, "조사자 변경: " + over[1]
        return base[2], False, base[3]

    def _waist_share(self, sid: int) -> float:
        value = self._threshold_value(sid, C.ThresholdCode.WAIST_FLEX)[0]
        return next(r for limit, r in _SHARE_BY_THRESHOLD if value <= limit)

    def _entry(self, sid: int, tid: Optional[int], target: str, key: str, action: str, old, new, reason, actor):
        e = C.EditLogEntry(_now(), actor, target, key, action, None if old is None else str(old),
                           None if new is None else str(new), reason, tid)
        self._log.append((sid, e))

    def _set_judgment(self, tid: int, no: int, status: C.JudgmentStatus, basis: str, actor: str, sid: int,
                      changes: list, reason_text: str):
        j = self._judg[tid][no]
        if j["excl"] is not None:
            return
        if j["status"] == status and j["basis"] == basis:
            return
        unconfirmed = False
        if j["confirmed"]:
            j.update(confirmed=False, final=None, by=None, at=None, why=None)
            unconfirmed = True
            self._entry(sid, tid, "JUDGMENT", f"criterion={no}", "UNCONFIRM", "확정", "초안", reason_text, actor)
        changes.append(C.JudgmentChange(no, j["status"], status, unconfirmed))
        j.update(status=status, basis=basis, reason=None)

    def _recalc(self, tid: int, actor: str = "시스템", log: bool = True):
        """바뀐 입력으로 1·4·8·9호만 다시 계산하는 흉내. 바뀐 내용을 RecalcResult 재료로 돌려준다."""
        task = self._tasks[tid]
        sid = task["survey"]
        inp = self._inputs[tid]
        changes: list[C.JudgmentChange] = []
        S = C.JudgmentStatus
        reason = "입력값 변경으로 확정 해제"
        # 1호
        if inp.keyboard_h is None:
            self._set_judgment(tid, 1, S.NEEDS_INPUT, "키보드·마우스 작업 시간을 넣어 주세요", actor, sid, changes, reason)
        else:
            hit = inp.keyboard_h >= 4 and not inp.keyboard_self_paced_yn
            self._set_judgment(tid, 1, S.APPLICABLE if hit else S.NOT_APPLICABLE,
                               f"집중 입력 {inp.keyboard_h:g}시간 {'≥' if hit else '<'} 4시간", actor, sid, changes, reason)
        # 4호 (비율은 영상에서 잰 값이라 분석이 있는 단위작업에만)
        if tid in self._runs:
            share = self._waist_share(sid)
            if inp.daily_work_h is None or inp.unsupported_posture_yn is None:
                self._set_judgment(tid, 4, S.NEEDS_INPUT, "하루 작업시간과 4호 전제를 넣어 주세요", actor, sid, changes, reason)
            elif not inp.unsupported_posture_yn:
                self._set_judgment(tid, 4, S.NOT_APPLICABLE, "4호 전제가 '아니오'라 해당하지 않음", actor, sid, changes, reason)
            else:
                hours = share * inp.daily_work_h
                hit = hours >= 2.0
                self._set_judgment(tid, 4, S.APPLICABLE if hit else S.NOT_APPLICABLE,
                                   f"허리 굽힘 {share:.0%} × 하루 {inp.daily_work_h:g}시간 = {hours:.2f}시간 {'≥' if hit else '<'} 2시간",
                                   actor, sid, changes, reason)
        # 8호
        if inp.lift_kg is None or inp.lift_cnt_per_day is None:
            self._set_judgment(tid, 8, S.NEEDS_INPUT, "드는 무게와 횟수를 넣어 주세요", actor, sid, changes, reason)
        else:
            people = inp.lift_people_cnt or 1
            per = inp.lift_kg / people
            hit = per >= 25 and inp.lift_cnt_per_day >= 10
            self._set_judgment(tid, 8, S.APPLICABLE if hit else S.NOT_APPLICABLE,
                               f"{inp.lift_kg:g}kg ÷ {people}명 = {per:g}kg {'≥' if per >= 25 else '<'} 25kg", actor, sid, changes, reason)
        # 9호
        lifts = self._lifts[tid]
        if not lifts:
            self._set_judgment(tid, 9, S.NEEDS_INPUT, "위치별 들기 횟수와 무게를 넣어 주세요", actor, sid, changes, reason)
        else:
            hits = [x for x in lifts if x.weight_kg >= 10 and x.lift_cnt_per_day >= 25]
            names = {C.LiftPosition.BELOW_KNEE: "무릎 아래", C.LiftPosition.ABOVE_SHOULDER: "어깨 위",
                     C.LiftPosition.ARM_EXTENDED: "팔을 뻗은 상태"}
            if hits:
                h = hits[0]
                self._set_judgment(tid, 9, S.APPLICABLE, f"{names[h.position_cd]} {h.weight_kg:g}kg · 하루 {h.lift_cnt_per_day}회 ≥ 25회",
                                   actor, sid, changes, reason)
            else:
                self._set_judgment(tid, 9, S.NOT_APPLICABLE, "위치별 횟수 25회 미만이거나 10kg 미만", actor, sid, changes, reason)
        raised, cleared = self._ensure_warnings(tid)
        return changes, raised, cleared

    def _ensure_warnings(self, tid: int):
        raised, cleared = [], []
        open_by_no = {w["criterion"]: wid for wid, w in self._warn.items() if w["task"] == tid and w["cleared"] is None}
        for no, j in self._judg[tid].items():
            applicable = j["status"] == C.JudgmentStatus.APPLICABLE
            if applicable and no not in open_by_no:
                wid = next(self._id["warning"])
                self._warn[wid] = dict(task=tid, criterion=no, raised=_now(), cleared=None, ai=None,
                                       message=f"부담작업 {no}호 기준({_CRITERIA[no]})을 넘습니다.", basis=j["basis"])
                raised.append(no)
            elif not applicable and no in open_by_no:
                self._warn[open_by_no[no]]["cleared"] = _now()
                cleared.append(no)
        for wid, w in self._warn.items():
            if w["task"] == tid and w["cleared"] is None:
                w["basis"] = self._judg[tid][w["criterion"]]["basis"]
        return raised, cleared

    def _judgment_dto(self, tid: int, no: int) -> C.Judgment:
        j = self._judg[tid][no]
        basis: tuple = ()
        if no == 4 and tid in self._runs:
            sid = self._tasks[tid]["survey"]
            v, over, _ = self._threshold_value(sid, C.ThresholdCode.WAIST_FLEX)
            share = self._waist_share(sid)
            daily = self._inputs[tid].daily_work_h
            basis = (C.JudgmentBasis("WAIST_FLEX", share_ratio=share, exposure_h=None if daily is None else share * daily,
                                     threshold_value=v,
                                     threshold_source_cd=C.ThresholdSource.INVESTIGATOR if over else C.ThresholdSource.MOEL_NOTE),)
        return C.Judgment(
            unit_task_id=tid, criterion_no=no, short_name=_CRITERIA[no], computed_status_cd=j["status"],
            final_status_cd=j["final"], confirmed_yn=j["confirmed"], review_reason_cd=j["reason"], exclusion_cd=j["excl"],
            basis_text=j["basis"], source_text=f"고시 제3조 제{no}호", basis=basis, confirmed_by=j["by"],
            confirmed_at=j["at"], confirm_reason_text=j["why"])

    def _reba(self, tid: int) -> C.RebaScore:
        r = self._reba_in[tid]
        wrist = 1 if r.wrist_flex_cd in (None, C.WristFlex.LE15) else 2
        wrist += 1 if r.wrist_twist_yn else 0
        table_b = 3 + (wrist - 1)
        coupling = {None: 0, C.Coupling.GOOD: 0, C.Coupling.FAIR: 1, C.Coupling.POOR: 2, C.Coupling.UNACCEPTABLE: 3}[r.coupling_cd]
        score_b = table_b + coupling
        table_c = _TABLE_C_ROW_A8[min(score_b, 12) - 1]
        activity = sum(bool(x) for x in (r.act_static_yn, r.act_repeat_yn, r.act_rapid_yn))
        total = table_c + activity
        level = (C.RiskLevel.NEGLIGIBLE if total == 1 else C.RiskLevel.LOW if total <= 3 else C.RiskLevel.MEDIUM if total <= 7
                 else C.RiskLevel.HIGH if total <= 10 else C.RiskLevel.VERY_HIGH)
        return C.RebaScore(
            side_cd="R", neck_score=2, trunk_score=4, legs_score=2, table_a_score=6, load_score=2, score_a=8,
            upper_arm_score=3, lower_arm_score=1, wrist_score=wrist, table_b_score=table_b, coupling_score=coupling,
            score_b=score_b, table_c_score=table_c, activity_score=activity, reba_score=total, risk_level_cd=level,
            provisional_yn=r.wrist_flex_cd is None, needs_review_items=("wrist",) if r.wrist_flex_cd is None else ())

    def _result(self, tid: int) -> C.TaskResult:
        self._task(tid)
        run = self._runs.get(tid)
        sid = self._tasks[tid]["survey"]
        judgments = tuple(self._judgment_dto(tid, no) for no in sorted(self._judg[tid]))
        warnings = tuple(self._warning_dto(wid) for wid, w in sorted(self._warn.items())
                         if w["task"] == tid and w["cleared"] is None)
        if run is None:
            return C.TaskResult(tid, None, None, None, None, None, None, (), judgments, warnings)
        daily = self._inputs[tid].daily_work_h
        v, over, label = self._threshold_value(sid, C.ThresholdCode.WAIST_FLEX)
        src = C.ThresholdSource.INVESTIGATOR if over else C.ThresholdSource.MOEL_NOTE
        waist = self._waist_share(sid)
        shares = (
            C.PostureShare("WAIST_FLEX", waist, None if daily is None else waist * daily, v, src),
            C.PostureShare("NECK_FLEX", 0.12, None if daily is None else 0.12 * daily, 20.0, C.ThresholdSource.MOEL_NOTE),
            C.PostureShare("P3_UNION", 0.30, None if daily is None else 0.30 * daily, 45.0, C.ThresholdSource.MOEL_NOTE),
            C.PostureShare("SQUAT", 0.05, None if daily is None else 0.05 * daily, None, None),
        )
        notices = (C.Notice("W-ANALYSIS-003", "다리가 보이지 않아 쪼그림·무릎 자세는 확인이 필요합니다."),) if tid == 11 else ()
        return C.TaskResult(
            unit_task_id=tid, run=C.RunHandle(run["run_id"], tid, run["video"], run["model"]),
            run_status_cd=run["status"], invalid_ratio=0.03, reba=self._reba(tid), key_frame_no=run["key_frame"],
            key_frame_jpeg=_JPEG, shares=shares, judgments=judgments, warnings=warnings, notices=notices)

    def _warning_dto(self, wid: int) -> C.WarningItem:
        w = self._warn[wid]
        ai = self._ai.get(w["ai"]) if w["ai"] else None
        return C.WarningItem(wid, w["criterion"], w["message"], w["basis"], w["raised"],
                             None if ai is None else ai["text"], None if ai is None else ai["result"])

    def _recalc_result(self, tid: int, actor: str) -> C.RecalcResult:
        changes, raised, cleared = self._recalc(tid, actor)
        return C.RecalcResult(tuple(changes), tuple(raised), tuple(cleared), self._result(tid))

    def _log_input_changes(self, tid: int, old, new, actor: str, target: str):
        sid = self._tasks[tid]["survey"]
        if not any(j["confirmed"] for j in self._judg[tid].values()):
            return                                         # 확정된 호가 없으면 남기지 않는다 (API 2.1절 ⑦)
        for f in old.__dataclass_fields__:
            a, b = getattr(old, f), getattr(new, f)
            if a != b:
                self._entry(sid, tid, target, f, "SET", a, b, None, actor)

    # ------------------------------------------------------------ 4.1 조사
    def create_survey(self, data: C.SurveyCreate) -> C.SurveyDetail:
        with self._lock:
            for v in (data.investigator_name, data.dept_name, data.process_name, data.work_name, data.survey_date):
                _need(bool(v and v.strip()), "E-INPUT-002", "필수 항목을 입력해 주세요.")
            if data.survey_type_cd == C.SurveyType.OCCASIONAL:
                _need(len(data.occasional_reasons) > 0, "E-INPUT-002", "수시조사 사유를 하나 이상 고르세요.")
            else:
                _need(len(data.occasional_reasons) == 0, "E-INPUT-001", "수시 사유는 수시조사에만 넣을 수 있습니다.")
            sid = next(self._id["survey"])
            self._surveys[sid] = dict(type=data.survey_type_cd, date=data.survey_date, investigator=data.investigator_name,
                                      dept=data.dept_name, process=data.process_name, work=data.work_name,
                                      status=C.SurveyStatus.DRAFT, confirmed_at=None, reasons=tuple(data.occasional_reasons))
            self._thr[sid] = {}
            return self.get_survey(sid)

    def list_surveys(self) -> Sequence[C.SurveySummary]:
        with self._lock:
            out = []
            for sid, s in sorted(self._surveys.items(), key=lambda kv: kv[1]["date"], reverse=True):
                tids = [t for t, x in self._tasks.items() if x["survey"] == sid]
                drafts = sum(1 for t in tids for j in self._judg[t].values() if not j["confirmed"])
                due = None
                if s["status"] == C.SurveyStatus.CONFIRMED and s["type"] != C.SurveyType.OCCASIONAL and s["confirmed_at"]:
                    due = f"{int(s['confirmed_at'][:4]) + 3}{s['confirmed_at'][4:10]}"
                out.append(C.SurveySummary(sid, s["date"], s["type"], s["process"], s["work"], s["status"], len(tids), drafts, due))
            return out

    def get_survey(self, survey_id: int) -> C.SurveyDetail:
        with self._lock:
            s = self._survey(survey_id)
            parts = tuple(C.Participant(pid, p["type"], p["name"]) for pid, p in sorted(self._participants.items())
                          if p["survey"] == survey_id)
            tasks = tuple(C.UnitTask(tid, t["name"], t["desc"], t["workers"], t["period"], t["sort"])
                          for tid, t in sorted(self._tasks.items(), key=lambda kv: kv[1]["sort"]) if t["survey"] == survey_id)
            return C.SurveyDetail(survey_id, s["type"], s["date"], s["investigator"], s["dept"], s["process"], s["work"],
                                  s["status"], s["confirmed_at"], tuple(s["reasons"]), parts, tasks)

    def update_survey(self, survey_id: int, data: C.SurveyUpdate, actor: str) -> C.SurveyDetail:
        with self._lock:
            s = self._survey(survey_id)
            mapping = dict(survey_date="date", investigator_name="investigator", dept_name="dept", process_name="process", work_name="work")
            for f, key in mapping.items():
                v = getattr(data, f)
                if v is not None:
                    _need(bool(v.strip()), "E-INPUT-002", "필수 항목을 입력해 주세요.")
                    s[key] = v
            if data.occasional_reasons is not None:
                s["reasons"] = tuple(data.occasional_reasons)
            if s["status"] == C.SurveyStatus.CONFIRMED:
                s.update(status=C.SurveyStatus.DRAFT, confirmed_at=None)
                self._entry(survey_id, None, "SURVEY", "status", "UNCONFIRM", "확정", "작성 중", "확정 뒤 수정", actor)
            return self.get_survey(survey_id)

    def delete_survey(self, survey_id: int, actor: str) -> None:
        with self._lock:
            self._survey(survey_id)
            for tid in [t for t, x in self._tasks.items() if x["survey"] == survey_id]:
                self._drop_task(tid)
            for pid in [p for p, x in self._participants.items() if x["survey"] == survey_id]:
                del self._participants[pid]
            self._log = [(s, e) for s, e in self._log if s != survey_id]
            del self._surveys[survey_id]

    def add_participant(self, survey_id: int, participant_type_cd: C.ParticipantType, display_name: str) -> C.Participant:
        with self._lock:
            self._survey(survey_id)
            _need(bool(display_name and display_name.strip()), "E-INPUT-002", "이름을 입력해 주세요.")
            pid = next(self._id["participant"])
            self._participants[pid] = dict(survey=survey_id, type=participant_type_cd, name=display_name.strip())
            return C.Participant(pid, participant_type_cd, display_name.strip())

    def remove_participant(self, participant_id: int) -> None:
        with self._lock:
            _need(participant_id in self._participants, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            del self._participants[participant_id]

    def confirm_survey(self, survey_id: int, actor: str) -> C.SurveyDetail:
        with self._lock:
            s = self._survey(survey_id)
            tids = [t for t, x in self._tasks.items() if x["survey"] == survey_id]
            _need(bool(tids) and all(j["confirmed"] for t in tids for j in self._judg[t].values()), "E-CONFIRM-003",
                  "확정하지 않은 판정이 있어 조사를 확정할 수 없습니다.")
            s.update(status=C.SurveyStatus.CONFIRMED, confirmed_at=_now())
            self._entry(survey_id, None, "SURVEY", "status", "CONFIRM", "작성 중", "확정", None, actor)
            return self.get_survey(survey_id)

    # ------------------------------------------------------------ 4.2 단위작업과 입력
    def create_unit_task(self, survey_id: int, data: C.UnitTaskCreate) -> C.UnitTask:
        with self._lock:
            self._survey(survey_id)
            _need(bool(data.task_name and data.task_name.strip()), "E-INPUT-002", "단위작업명을 입력해 주세요.")
            _need(data.worker_cnt >= 1, "E-INPUT-001", "작업 인원은 1명 이상이어야 합니다.")
            _need(all(t["name"] != data.task_name.strip() for t in self._tasks.values() if t["survey"] == survey_id),
                  "E-INPUT-003", "같은 이름의 단위작업이 이미 있습니다.")
            tid = next(self._id["task"])
            sort = 1 + max([t["sort"] for t in self._tasks.values() if t["survey"] == survey_id], default=0)
            self._tasks[tid] = dict(survey=survey_id, name=data.task_name.strip(), desc=data.task_desc, workers=data.worker_cnt,
                                    period=data.period_type_cd, sort=sort)
            self._inputs[tid], self._reps[tid], self._lifts[tid], self._reba_in[tid] = C.TaskInputs(), (), (), C.RebaInputs()
            self._judg[tid] = {n: self._blank(tid, n) for n in _CRITERIA}
            t = self._tasks[tid]
            return C.UnitTask(tid, t["name"], t["desc"], t["workers"], t["period"], t["sort"])

    def update_unit_task(self, unit_task_id: int, data: C.UnitTaskCreate, actor: str) -> C.RecalcResult:
        with self._lock:
            t = self._task(unit_task_id)
            _need(bool(data.task_name.strip()), "E-INPUT-002", "단위작업명을 입력해 주세요.")
            _need(data.worker_cnt >= 1, "E-INPUT-001", "작업 인원은 1명 이상이어야 합니다.")
            _need(all(x["name"] != data.task_name.strip() for k, x in self._tasks.items()
                      if x["survey"] == t["survey"] and k != unit_task_id), "E-INPUT-003", "같은 이름의 단위작업이 이미 있습니다.")
            changed_period = t["period"] != data.period_type_cd
            t.update(name=data.task_name.strip(), desc=data.task_desc, workers=data.worker_cnt, period=data.period_type_cd)
            if changed_period:
                before = {n: j["status"] for n, j in self._judg[unit_task_id].items()}
                self._judg[unit_task_id] = {n: self._blank(unit_task_id, n) for n in _CRITERIA}
                self._recalc(unit_task_id, actor)
                changes = tuple(C.JudgmentChange(n, before[n], j["status"], False)
                                for n, j in self._judg[unit_task_id].items() if before[n] != j["status"])
                return C.RecalcResult(changes, (), (), self._result(unit_task_id))
            return C.RecalcResult((), (), (), self._result(unit_task_id))

    def _drop_task(self, tid: int):
        for d in (self._tasks, self._inputs, self._reps, self._lifts, self._reba_in, self._runs, self._judg):
            d.pop(tid, None)
        for vid in [v for v, x in self._videos.items() if x["task"] == tid]:
            del self._videos[vid]
        for wid in [w for w, x in self._warn.items() if x["task"] == tid]:
            del self._warn[wid]

    def delete_unit_task(self, unit_task_id: int, actor: str) -> None:
        with self._lock:
            self._task(unit_task_id)
            self._drop_task(unit_task_id)

    def save_task_inputs(self, unit_task_id: int, inputs: C.TaskInputs, actor: str) -> C.RecalcResult:
        with self._lock:
            self._task(unit_task_id)
            _need(bool(actor and actor.strip()), "E-INPUT-002", "조사자 이름을 입력해 주세요.")
            for f in inputs.__dataclass_fields__:
                v = getattr(inputs, f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    _need(v >= 0, "E-INPUT-001", "0 이상으로 입력해 주세요.")
            if inputs.daily_work_h is not None:
                _need(inputs.daily_work_h <= 24, "E-INPUT-001", "하루 작업시간은 0~24 사이로 입력해 주세요.")
                for f in ("neck_twist_h", "waist_twist_h", "keyboard_h", "finger_h", "onehand_h", "freq_lift_h", "impact_h"):
                    v = getattr(inputs, f)
                    _need(v is None or v <= inputs.daily_work_h, "E-INPUT-001", "하루 작업시간보다 클 수 없습니다.")
            old = self._inputs[unit_task_id]
            self._inputs[unit_task_id] = inputs
            self._log_input_changes(unit_task_id, old, inputs, actor, "TASK_INPUT")
            return self._recalc_result(unit_task_id, actor)

    def save_repetition_inputs(self, unit_task_id: int, items: Sequence[C.RepetitionInput], actor: str) -> C.RecalcResult:
        with self._lock:
            self._task(unit_task_id)
            _need(all(i.repeat_h >= 0 for i in items), "E-INPUT-001", "0 이상으로 입력해 주세요.")
            self._reps[unit_task_id] = tuple(items)
            return self._recalc_result(unit_task_id, actor)

    def save_lift_position_inputs(self, unit_task_id: int, items: Sequence[C.LiftPositionInput], actor: str) -> C.RecalcResult:
        with self._lock:
            self._task(unit_task_id)
            _need(all(i.lift_cnt_per_day >= 0 and i.weight_kg >= 0 for i in items), "E-INPUT-001", "0 이상으로 입력해 주세요.")
            self._lifts[unit_task_id] = tuple(items)
            return self._recalc_result(unit_task_id, actor)

    def save_reba_inputs(self, unit_task_id: int, inputs: C.RebaInputs, actor: str) -> C.RecalcResult:
        with self._lock:
            self._task(unit_task_id)
            if inputs.load_kg is not None:
                _need(inputs.load_kg >= 0, "E-INPUT-001", "0 이상으로 입력해 주세요.")
            old = self._reba_in[unit_task_id]
            self._reba_in[unit_task_id] = inputs
            self._log_input_changes(unit_task_id, old, inputs, actor, "REBA_INPUT")
            return C.RecalcResult((), (), (), self._result(unit_task_id))     # REBA만 다시 계산한다. 판정은 그대로 (BR-15)

    def get_task_inputs(self, unit_task_id: int) -> C.TaskInputBundle:
        with self._lock:
            self._task(unit_task_id)
            return C.TaskInputBundle(unit_task_id, self._inputs[unit_task_id], self._reps[unit_task_id], self._lifts[unit_task_id])

    def get_reba_inputs(self, unit_task_id: int) -> C.RebaInputs:
        with self._lock:
            self._task(unit_task_id)
            return self._reba_in[unit_task_id]

    # ------------------------------------------------------------ 4.3 영상과 분석
    def _video_info(self, vid: int) -> C.VideoInfo:
        v = self._videos[vid]
        notices = (C.Notice("W-VIDEO-002", "작업 한 사이클 이상 찍었는지 확인해 주세요."),) if v["dur"] < 10 else ()
        return C.VideoInfo(vid, v["path"], v["name"], v["dur"], v["fps"], v["frames"], v["w"], v["h"], v["rot"], v["consent"], notices)

    def inspect_video(self, path: Path) -> C.VideoInfo:
        p = Path(path)
        _need(p.suffix.lower() in (".mp4", ".mov"), "E-VIDEO-001", "이 파일을 열 수 없습니다. mp4나 mov 파일을 골라 주세요.")
        short = "short" in p.stem.lower()
        dur = 8.0 if short else 32.0
        notices = (C.Notice("W-VIDEO-002", "작업 한 사이클 이상 찍었는지 확인해 주세요."),) if dur < 10 else ()
        return C.VideoInfo(None, str(p), p.name, dur, 30.0, int(dur * 30), 1080, 1920, 90, False, notices)

    def list_videos(self, unit_task_id: int) -> Sequence[C.VideoInfo]:
        with self._lock:
            self._task(unit_task_id)
            return tuple(self._video_info(v) for v, x in sorted(self._videos.items()) if x["task"] == unit_task_id)

    def attach_video(self, unit_task_id: int, path: Path, consent: bool, actor: str) -> C.VideoInfo:
        with self._lock:
            self._task(unit_task_id)
            info = self.inspect_video(path)
            vid = next(self._id["video"])
            self._videos[vid] = dict(task=unit_task_id, path=info.file_path, name=info.file_name, dur=info.duration_s,
                                     fps=info.fps, frames=info.frame_cnt, w=info.width_px, h=info.height_px,
                                     rot=info.rotation_deg, consent=bool(consent))
            return self._video_info(vid)

    def confirm_consent(self, video_id: int, actor: str) -> C.VideoInfo:
        with self._lock:
            _need(video_id in self._videos, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            self._videos[video_id]["consent"] = True
            return self._video_info(video_id)

    def start_analysis(self, unit_task_id: int, video_id: int, on_progress: C.ProgressCallback) -> C.RunHandle:
        with self._lock:
            self._task(unit_task_id)
            _need(video_id in self._videos and self._videos[video_id]["task"] == unit_task_id, "E-NOTFOUND-001",
                  "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            _need(self._videos[video_id]["consent"], "E-VIDEO-003", "촬영 동의를 먼저 확인해 주세요.")
            _need(not self._running, "E-ANALYSIS-004", "다른 분석이 끝난 뒤 시작해 주세요.")
            run_id = next(self._id["run"])
            handle = C.RunHandle(run_id, unit_task_id, video_id, self._settings["pose_model_id"])
            self._running[run_id] = dict(task=unit_task_id, cancel=threading.Event())
        threading.Thread(target=self._run, args=(handle, on_progress), daemon=True).start()
        return handle

    def _run(self, h: C.RunHandle, on_progress: C.ProgressCallback):
        total = self._videos[h.video_id]["frames"]
        cancel = self._running[h.run_id]["cancel"]
        steps = ((C.Stage.DECODE, 3), (C.Stage.KEYPOINT, 25), (C.Stage.KEYPOINT, 50), (C.Stage.KEYPOINT, 75),
                 (C.Stage.ANGLE, 88), (C.Stage.JUDGE, 95), (C.Stage.SAVE, 99))
        try:
            for stage, pct in steps:
                if self._delay:
                    time.sleep(self._delay)
                if cancel.is_set():
                    on_progress(C.Progress(h.run_id, C.Stage.CANCELED, int(total * pct / 100), total, float(pct),
                                           error_code="I-ANALYSIS-005", error_message="분석을 취소했습니다."))
                    return
                on_progress(C.Progress(h.run_id, stage, int(total * pct / 100), total, float(pct), eta_s=max(0.0, (100 - pct) / 10)))
            with self._lock:
                self._runs[h.unit_task_id] = dict(run_id=h.run_id, video=h.video_id, model=h.model_id, key_frame=216,
                                                  status=C.RunStatus.DONE)
                self._recalc(h.unit_task_id, "시스템")
            on_progress(C.Progress(h.run_id, C.Stage.DONE, total, total, 100.0))
        except Exception as e:                                      # 스텁도 실패를 같은 방식으로 알린다
            on_progress(C.Progress(h.run_id, C.Stage.FAILED, 0, total, 0.0, error_code="E-ANALYSIS-009", error_message=str(e)))
        finally:
            with self._lock:
                self._running.pop(h.run_id, None)

    def cancel_analysis(self, run_id: int) -> None:
        with self._lock:
            r = self._running.get(run_id)
            if r:
                r["cancel"].set()

    # ------------------------------------------------------------ 4.4 결과와 판정
    def get_task_result(self, unit_task_id: int) -> C.TaskResult:
        with self._lock:
            return self._result(unit_task_id)

    def get_frame_preview(self, run_id: int, frame_no: int) -> bytes:
        with self._lock:
            run = next((r for r in self._runs.values() if r["run_id"] == run_id), None)
            _need(run is not None, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            _need(0 <= frame_no < self._videos[run["video"]]["frames"], "E-INPUT-001", "프레임 번호가 범위를 벗어났습니다.")
            return _JPEG

    def get_posture_timeline(self, unit_task_id: int) -> C.PostureTimeline:
        with self._lock:
            self._task(unit_task_id)
            run = self._runs.get(unit_task_id)
            _need(run is not None, "E-NOTFOUND-001", "분석 결과가 없습니다.")
            v = self._videos[run["video"]]
            n = v["frames"]
            cut = lambda a, b: (int(n * a), int(n * b) - 1)
            segs = tuple(C.PostureSegment("WAIST_FLEX", *cut(a, b)) for a, b in ((0.08, 0.20), (0.40, 0.52), (0.72, 0.83))) \
                + (C.PostureSegment("INVALID", *cut(0.58, 0.61)),)
            return C.PostureTimeline(run["run_id"], v["fps"], n, segs)

    def set_key_frame(self, unit_task_id: int, frame_no: int, actor: str) -> C.TaskResult:
        with self._lock:
            self._task(unit_task_id)
            run = self._runs.get(unit_task_id)
            _need(run is not None, "E-NOTFOUND-001", "분석 결과가 없습니다.")
            _need(0 <= frame_no < self._videos[run["video"]]["frames"], "E-INPUT-001", "프레임 번호가 범위를 벗어났습니다.")
            old = run["key_frame"]
            run["key_frame"] = frame_no
            if old != frame_no:
                self._entry(self._tasks[unit_task_id]["survey"], unit_task_id, "KEY_FRAME", "key_frame_no", "SET", old, frame_no, None, actor)
            return self._result(unit_task_id)

    def confirm_judgment(self, unit_task_id: int, criterion_no: int, final_status: C.FinalStatus,
                         reason: Optional[str], actor: str) -> C.Judgment:
        with self._lock:
            self._task(unit_task_id)
            _need(criterion_no in _CRITERIA, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            j = self._judg[unit_task_id][criterion_no]
            _need(j["status"] != C.JudgmentStatus.NEEDS_INPUT, "E-CONFIRM-001", "입력이 필요한 기준이 있어 확정할 수 없습니다.")
            same = j["status"].value == final_status.value
            had_reason = bool(reason and reason.strip())
            _need((same and j["status"] != C.JudgmentStatus.NEEDS_REVIEW) or had_reason, "E-CONFIRM-002", "확정하는 이유를 입력해 주세요.")
            action = "CHANGE" if j["confirmed"] and j["final"] != final_status else "CONFIRM"
            old = j["final"].value if j["final"] else j["status"].value
            j.update(final=final_status, confirmed=True, by=actor, at=_now(), why=reason.strip() if had_reason else None)
            self._entry(self._tasks[unit_task_id]["survey"], unit_task_id, "JUDGMENT", f"criterion={criterion_no}", action,
                        old, final_status.value, j["why"], actor)
            return self._judgment_dto(unit_task_id, criterion_no)

    def confirm_all(self, unit_task_id: int, actor: str) -> C.ConfirmAllResult:
        with self._lock:
            self._task(unit_task_id)
            done, review, blocked = [], [], []
            for no, j in sorted(self._judg[unit_task_id].items()):
                if j["confirmed"]:
                    continue
                if j["status"] == C.JudgmentStatus.NEEDS_INPUT:
                    blocked.append(no)
                elif j["status"] == C.JudgmentStatus.NEEDS_REVIEW:
                    review.append(no)
                else:
                    self.confirm_judgment(unit_task_id, no, C.FinalStatus(j["status"].value), None, actor)
                    done.append(no)
            return C.ConfirmAllResult(tuple(done), tuple(review), tuple(blocked))

    def unconfirm_judgment(self, unit_task_id: int, criterion_no: int, reason: str, actor: str) -> C.Judgment:
        with self._lock:
            self._task(unit_task_id)
            _need(bool(reason and reason.strip()), "E-CONFIRM-002", "확정하는 이유를 입력해 주세요.")
            j = self._judg[unit_task_id][criterion_no]
            if j["confirmed"]:
                j.update(confirmed=False, final=None, by=None, at=None, why=None)
                self._entry(self._tasks[unit_task_id]["survey"], unit_task_id, "JUDGMENT", f"criterion={criterion_no}",
                            "UNCONFIRM", "확정", "초안", reason.strip(), actor)
            return self._judgment_dto(unit_task_id, criterion_no)

    def list_edit_log(self, survey_id: int) -> Sequence[C.EditLogEntry]:
        with self._lock:
            self._survey(survey_id)
            return tuple(e for s, e in self._log if s == survey_id)

    # ------------------------------------------------------------ 4.5 각도 기준
    def get_thresholds(self, survey_id: int) -> Sequence[C.Threshold]:
        with self._lock:
            self._survey(survey_id)
            out = []
            for code, (no, measure, _, _) in _THRESHOLDS.items():
                v, over, label = self._threshold_value(survey_id, code)
                out.append(C.Threshold(code, no, measure, v, over, label))
            return tuple(out)

    def _recalc_survey(self, survey_id: int, actor: str) -> tuple:
        return tuple(self._recalc_result(t, actor) for t, x in sorted(self._tasks.items()) if x["survey"] == survey_id)

    def set_threshold(self, survey_id: int, threshold_cd: C.ThresholdCode, value_deg: float, reason: str, actor: str):
        with self._lock:
            self._survey(survey_id)
            _need(bool(reason and reason.strip()), "E-THRESHOLD-001", "바꾸는 이유를 입력해 주세요.")
            _need(0 < value_deg <= 180, "E-INPUT-001", "각도는 0보다 크고 180 이하로 입력해 주세요.")
            old = self._threshold_value(survey_id, threshold_cd)[0]
            self._thr.setdefault(survey_id, {})[threshold_cd] = (float(value_deg), reason.strip())
            self._entry(survey_id, None, "THRESHOLD", threshold_cd.value, "CHANGE", old, value_deg, reason.strip(), actor)
            return self._recalc_survey(survey_id, actor)

    def reset_threshold(self, survey_id: int, threshold_cd: C.ThresholdCode, actor: str):
        with self._lock:
            self._survey(survey_id)
            old = self._threshold_value(survey_id, threshold_cd)[0]
            self._thr.setdefault(survey_id, {}).pop(threshold_cd, None)
            self._entry(survey_id, None, "THRESHOLD", threshold_cd.value, "RESET", old, _THRESHOLDS[threshold_cd][2], None, actor)
            return self._recalc_survey(survey_id, actor)

    # ------------------------------------------------------------ 4.6 보고서와 AI 문장
    def export_excel(self, survey_id: int, path: Path, actor: str, with_db_backup: bool = True) -> C.ExportResult:
        with self._lock:
            self._survey(survey_id)
            p = Path(path)
            _need(p.suffix.lower() == ".xlsx" and p.parent.exists(), "E-EXPORT-001",
                  "엑셀 파일이 열려 있습니다. 닫고 다시 저장하거나 다른 이름으로 저장해 주세요.")
            tids = [t for t, x in self._tasks.items() if x["survey"] == survey_id]
            drafts = sum(1 for t in tids for j in self._judg[t].values() if not j["confirmed"])
            backup = str(p.with_name("ergo_assist_backup_스텁.db")) if with_db_backup else None
            return C.ExportResult(str(p), drafts, backup)          # 스텁: 파일을 실제로 만들지는 않는다

    def _ai_result(self, ai_id: int) -> C.AiTextResult:
        a = self._ai[ai_id]
        return C.AiTextResult(ai_id, a["purpose"], a["text"], a["result"], a["is_ai"])

    def request_warning_advice(self, warning_id: int) -> C.AiTextResult:
        with self._lock:
            _need(warning_id in self._warn, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            w = self._warn[warning_id]
            if w["ai"] is None:
                ai_id = next(self._id["ai"])
                use = self._settings["gpt_enabled"] and self._settings["has_key"]
                self._ai[ai_id] = dict(
                    purpose=C.AiPurpose.WARNING_ADVICE, warning=warning_id, survey=None, is_ai=bool(use),
                    result=C.AiResult.OK if use else (C.AiResult.DISABLED if not self._settings["gpt_enabled"] else C.AiResult.FALLBACK_NO_KEY),
                    text="작업 방법이나 높이를 바꿔 해당 자세를 줄일 수 있는지 살펴보세요." if use else
                         f"부담작업 {w['criterion']}호 기준을 넘습니다. 작업 방법이나 높이를 바꿔 해당 자세를 줄여 보세요.")
                w["ai"] = ai_id
            return self._ai_result(w["ai"])

    def request_report_summary(self, survey_id: int) -> C.AiTextResult:
        with self._lock:
            self._survey(survey_id)
            tids = [t for t, x in self._tasks.items() if x["survey"] == survey_id]
            open_w = [w for w in self._warn.values() if w["task"] in tids and w["cleared"] is None]
            ai_id = next(self._id["ai"])
            if not open_w:
                self._ai[ai_id] = dict(purpose=C.AiPurpose.REPORT_SUMMARY, warning=None, survey=survey_id, is_ai=False,
                                       result=C.AiResult.NO_WARNING, text="법 기준(고시 제3조)을 넘는 작업이 없습니다.")
            else:
                nos = sorted({w["criterion"] for w in open_w})
                self._ai[ai_id] = dict(purpose=C.AiPurpose.REPORT_SUMMARY, warning=None, survey=survey_id, is_ai=False,
                                       result=C.AiResult.DISABLED,
                                       text=f"조사한 작업 {len(tids)}개 중 {len({w['task'] for w in open_w})}개가 부담작업 기준({', '.join(f'{n}호' for n in nos)})을 넘었습니다.")
            return self._ai_result(ai_id)

    def edit_ai_text(self, ai_text_id: int, text: str, actor: str) -> C.AiTextResult:
        with self._lock:
            _need(ai_text_id in self._ai, "E-NOTFOUND-001", "찾을 수 없습니다. 목록을 새로 고쳐 주세요.")
            _need(bool(text and text.strip()), "E-INPUT-002", "문장을 입력해 주세요.")
            self._ai[ai_text_id]["text"] = text.strip()
            return self._ai_result(ai_text_id)

    # ------------------------------------------------------------ 4.7 설정
    def get_settings(self) -> C.Settings:
        with self._lock:
            s = self._settings
            return C.Settings(s["pose_model_id"], s["gpt_enabled"], s["gpt_model"], s["has_key"], s["last_dir"])

    def save_settings(self, pose_model_id: int, gpt_enabled: bool, gpt_model: Optional[str]) -> C.Settings:
        with self._lock:
            _need(any(m.model_id == pose_model_id for m in _MODELS), "E-INPUT-001", "고를 수 없는 모델입니다.")
            self._settings.update(pose_model_id=pose_model_id, gpt_enabled=bool(gpt_enabled), gpt_model=gpt_model)
            return self.get_settings()

    def set_gpt_api_key(self, key: str) -> None:
        with self._lock:
            _need(bool(key and key.strip()), "E-INPUT-002", "API 키를 입력해 주세요.")
            self._settings["has_key"] = True                       # 키 자체는 보관하지 않는다 (스텁)

    def delete_gpt_api_key(self) -> None:
        with self._lock:
            self._settings["has_key"] = False

    def list_models(self) -> Sequence[C.PoseModel]:
        return _MODELS
