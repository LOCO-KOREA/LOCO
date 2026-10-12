"""서비스 계약 시험 (API 계약서 10절). 스텁도, 진짜 서비스도 이 시험을 통과해야 한다.

쓰는 법
    class MyServiceContract(ServiceContractTests, unittest.TestCase):
        def make_service(self, progress_delay_s=0.0):
            return MyService(...)        # 아래 '시험용 데이터'를 담고 있어야 한다

시험용 데이터 (ERD 시험 데이터와 화면설계서의 예시와 같다)
    조사 1: 2026-10-23 정기조사, 포장공정. 확정된 판정 없음, 수정 이력 약간
    단위작업 10 '상자 들어 옮기기' (상시): 하루 6시간, 15kg · 1명 · 하루 300회, 분석 결과가 있음 (허리 굽힘 35%)
        판정 초안: 1호 입력 필요 · 3호 사람 확인 · 4호 해당 · 9호 해당 · 2·5호 확정(비해당)
        경고: 4호 (AI 문장이 이미 있음), 9호 (문장 없음)
    단위작업 11 '선반 정리' (상시): 입력 없음, 분석 없음
    단위작업 12 '수레 밀기' (단기간작업)
    영상 100: 단위작업 10의 영상, 촬영 동의함

각 시험은 기능정의서의 수용 기준(AC)이나 API 계약서 8절의 오류 코드를 이름에 쓴다.
"""
from __future__ import annotations

import collections.abc
import inspect
import threading
import typing
from dataclasses import replace
from pathlib import Path

from ergo import contracts as C
from ergo.contracts import ErgoError

SURVEY, TASK, TASK_SHORT, TASK_EMPTY, VIDEO = 1, 10, 12, 11, 100
BY = "홍길동"
S = C.JudgmentStatus


def _matches(value, ann) -> bool:
    if ann is typing.Any:
        return True
    if ann is None or ann is type(None):
        return value is None
    origin = typing.get_origin(ann)
    args = typing.get_args(ann)
    if origin is typing.Union:
        return any(_matches(value, a) for a in args)
    if origin in (collections.abc.Sequence, list, tuple):
        if not isinstance(value, (list, tuple)):
            return False
        elem = args[0] if args else typing.Any
        return all(_matches(v, elem) for v in value)
    if isinstance(ann, type):
        return isinstance(value, ann)
    return True


class ServiceContractTests:
    def make_service(self, progress_delay_s: float = 0.0):
        raise NotImplementedError

    def setUp(self):
        self.svc = self.make_service()

    # ---------------------------------------------------------------- 도우미
    def raises(self, code, fn, *args, **kwargs):
        with self.assertRaises(ErgoError) as cm:
            fn(*args, **kwargs)
        self.assertEqual(cm.exception.code, code)
        self.assertIn(code, C.ERROR_CODES, "계약(8절)에 없는 오류 코드")
        return cm.exception

    def judgment(self, result, no):
        return next(j for j in result.judgments if j.criterion_no == no)

    def wait(self, event, seconds=10):
        self.assertTrue(event.wait(seconds), "분석이 끝나지 않음")

    # ---------------------------------------------------------------- 계약 모양
    def test_every_method_exists_with_the_same_parameters(self):
        for name, proto in vars(C.ServiceAPI).items():
            if name.startswith("_") or not callable(proto):
                continue
            impl = getattr(self.svc, name, None)
            self.assertTrue(callable(impl), f"{name}이(가) 없음")
            want = list(inspect.signature(proto).parameters)[1:]
            got = list(inspect.signature(impl).parameters)
            self.assertEqual(want, got, f"{name}의 매개변수가 계약과 다름")

    def test_read_functions_return_the_contract_types(self):
        calls = {"list_surveys": (), "get_survey": (SURVEY,), "get_task_inputs": (TASK,), "get_reba_inputs": (TASK,),
                 "list_videos": (TASK,), "get_task_result": (TASK,), "get_posture_timeline": (TASK,),
                 "list_edit_log": (SURVEY,), "get_thresholds": (SURVEY,), "get_settings": (), "list_models": ()}
        for name, args in calls.items():
            value = getattr(self.svc, name)(*args)
            ret = typing.get_type_hints(getattr(C.ServiceAPI, name), vars(C))["return"]
            self.assertTrue(_matches(value, ret), f"{name}이(가) {ret}이(가) 아닌 값을 돌려줌: {type(value)}")

    def test_frame_preview_is_a_jpeg(self):
        run = self.svc.get_task_result(TASK).run
        data = self.svc.get_frame_preview(run.run_id, 0)
        self.assertIsInstance(data, bytes)
        self.assertEqual(data[:3], b"\xff\xd8\xff")

    def test_every_notice_code_is_in_the_contract(self):
        notices = []
        for t in (TASK, TASK_EMPTY, TASK_SHORT):
            notices += list(self.svc.get_task_result(t).notices)
        for v in self.svc.list_videos(TASK):
            notices += list(v.notices)
        for n in notices:
            self.assertIn(n.code, C.ERROR_CODES)

    # ---------------------------------------------------------------- 조사 · 단위작업
    def test_not_found(self):
        self.raises("E-NOTFOUND-001", self.svc.get_survey, 9999)
        self.raises("E-NOTFOUND-001", self.svc.get_task_result, 9999)

    def test_occasional_survey_needs_a_reason(self):
        data = C.SurveyCreate(C.SurveyType.OCCASIONAL, "2026-10-24", BY, "포장부", "포장공정", "상자 포장")
        self.raises("E-INPUT-002", self.svc.create_survey, data)
        ok = self.svc.create_survey(replace(data, occasional_reasons=(C.OccasionalReason.NEW_TASK,)))
        self.assertEqual(ok.survey_type_cd, C.SurveyType.OCCASIONAL)
        self.assertEqual(ok.occasional_reasons, (C.OccasionalReason.NEW_TASK,))

    def test_AC01_saved_survey_comes_back_the_same(self):
        data = C.SurveyCreate(C.SurveyType.REGULAR, "2026-11-02", "김나리", "물류부", "출하공정", "팔레트 적재")
        made = self.svc.create_survey(data)
        again = self.svc.get_survey(made.survey_id)
        self.assertEqual((again.survey_date, again.investigator_name, again.dept_name, again.process_name, again.work_name),
                         ("2026-11-02", "김나리", "물류부", "출하공정", "팔레트 적재"))
        self.assertEqual(again.status_cd, C.SurveyStatus.DRAFT)

    def test_AC02_list_is_newest_first(self):
        self.svc.create_survey(C.SurveyCreate(C.SurveyType.REGULAR, "2027-01-05", BY, "a", "b", "c"))
        dates = [s.survey_date for s in self.svc.list_surveys()]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(dates[0], "2027-01-05")

    def test_duplicate_unit_task_name(self):
        self.raises("E-INPUT-003", self.svc.create_unit_task, SURVEY,
                    C.UnitTaskCreate("상자 들어 옮기기", 1, C.PeriodType.ONGOING))

    def test_unit_task_validation(self):
        self.raises("E-INPUT-001", self.svc.create_unit_task, SURVEY, C.UnitTaskCreate("새 작업", 0, C.PeriodType.ONGOING))
        self.raises("E-INPUT-002", self.svc.create_unit_task, SURVEY, C.UnitTaskCreate("  ", 1, C.PeriodType.ONGOING))

    def test_new_unit_task_starts_with_all_criteria_needing_input(self):
        t = self.svc.create_unit_task(SURVEY, C.UnitTaskCreate("새 작업", 1, C.PeriodType.ONGOING))
        res = self.svc.get_task_result(t.unit_task_id)
        self.assertIsNone(res.run)
        self.assertEqual(sorted(j.criterion_no for j in res.judgments), list(range(1, 12)))
        self.assertTrue(all(j.computed_status_cd == S.NEEDS_INPUT for j in res.judgments))

    def test_AC04_short_term_task_is_all_not_applicable(self):
        res = self.svc.get_task_result(TASK_SHORT)
        self.assertEqual(len(res.judgments), 11)
        for j in res.judgments:
            self.assertEqual(j.computed_status_cd, S.NOT_APPLICABLE)
            self.assertEqual(j.exclusion_cd, C.Exclusion.SHORT_TERM)

    def test_AC06_participants(self):
        n = len(self.svc.get_survey(SURVEY).participants)
        p = self.svc.add_participant(SURVEY, C.ParticipantType.WORKER, "근로자 B")
        self.assertEqual(len(self.svc.get_survey(SURVEY).participants), n + 1)
        self.svc.remove_participant(p.participant_id)
        self.assertEqual(len(self.svc.get_survey(SURVEY).participants), n)

    # ---------------------------------------------------------------- 입력과 다시 계산
    def test_AC05_hours_out_of_range_are_not_saved(self):
        before = self.svc.get_task_inputs(TASK).inputs
        self.raises("E-INPUT-001", self.svc.save_task_inputs, TASK, replace(before, daily_work_h=25.0), BY)
        self.assertEqual(self.svc.get_task_inputs(TASK).inputs, before)

    def test_twist_hours_cannot_exceed_daily_hours(self):
        before = self.svc.get_task_inputs(TASK).inputs
        self.raises("E-INPUT-001", self.svc.save_task_inputs, TASK, replace(before, waist_twist_h=7.0), BY)

    def test_AC26_changing_daily_hours_recalculates_criterion_4(self):
        inp = self.svc.get_task_inputs(TASK).inputs
        self.assertEqual(self.judgment(self.svc.get_task_result(TASK), 4).computed_status_cd, S.APPLICABLE)
        r = self.svc.save_task_inputs(TASK, replace(inp, daily_work_h=5.0), BY)
        self.assertEqual(self.judgment(r.result, 4).computed_status_cd, S.NOT_APPLICABLE)
        change = [c for c in r.changes if c.criterion_no == 4]
        self.assertTrue(change and (change[0].before, change[0].after) == (S.APPLICABLE, S.NOT_APPLICABLE))
        self.assertIn(4, r.warnings_cleared)
        r = self.svc.save_task_inputs(TASK, replace(inp, daily_work_h=6.0), BY)
        self.assertIn(4, r.warnings_raised)

    def test_AC22_two_people_share_the_weight(self):
        inp = self.svc.get_task_inputs(TASK).inputs
        r = self.svc.save_task_inputs(TASK, replace(inp, lift_kg=30.0, lift_people_cnt=2, lift_cnt_per_day=12), BY)
        self.assertEqual(self.judgment(r.result, 8).computed_status_cd, S.NOT_APPLICABLE)

    def test_AC23_precondition_no_means_not_applicable(self):
        inp = self.svc.get_task_inputs(TASK).inputs
        r = self.svc.save_task_inputs(TASK, replace(inp, unsupported_posture_yn=False), BY)
        self.assertEqual(self.judgment(r.result, 4).computed_status_cd, S.NOT_APPLICABLE)

    def test_missing_hours_make_criterion_4_need_input(self):
        inp = self.svc.get_task_inputs(TASK).inputs
        r = self.svc.save_task_inputs(TASK, replace(inp, daily_work_h=None), BY)
        self.assertEqual(self.judgment(r.result, 4).computed_status_cd, S.NEEDS_INPUT)

    def test_confirmed_criterion_is_unconfirmed_when_its_input_changes(self):
        self.svc.confirm_judgment(TASK, 4, C.FinalStatus.APPLICABLE, None, BY)
        inp = self.svc.get_task_inputs(TASK).inputs
        r = self.svc.save_task_inputs(TASK, replace(inp, daily_work_h=5.0), BY)
        j4 = self.judgment(r.result, 4)
        self.assertFalse(j4.confirmed_yn)
        self.assertTrue(any(c.criterion_no == 4 and c.unconfirmed for c in r.changes))

    # ---------------------------------------------------------------- 확정과 이력
    def test_AC27_cannot_confirm_when_input_is_missing(self):
        self.raises("E-CONFIRM-001", self.svc.confirm_judgment, TASK, 1, C.FinalStatus.NOT_APPLICABLE, None, BY)

    def test_AC27_review_needs_a_reason(self):
        self.raises("E-CONFIRM-002", self.svc.confirm_judgment, TASK, 3, C.FinalStatus.APPLICABLE, None, BY)
        j = self.svc.confirm_judgment(TASK, 3, C.FinalStatus.APPLICABLE, "영상에서 직접 확인함", BY)
        self.assertTrue(j.confirmed_yn)
        self.assertEqual(j.confirmed_by, BY)
        self.assertEqual(j.confirm_reason_text, "영상에서 직접 확인함")

    def test_a_different_result_than_the_draft_needs_a_reason(self):
        self.raises("E-CONFIRM-002", self.svc.confirm_judgment, TASK, 4, C.FinalStatus.NOT_APPLICABLE, None, BY)

    def test_AC28_confirm_leaves_an_edit_log_line_and_the_log_only_grows(self):
        n = len(self.svc.list_edit_log(SURVEY))
        self.svc.confirm_judgment(TASK, 4, C.FinalStatus.APPLICABLE, None, BY)
        log = self.svc.list_edit_log(SURVEY)
        self.assertEqual(len(log), n + 1)
        last = log[-1]
        self.assertEqual((last.target_cd, last.action_cd, last.actor_name, last.unit_task_id), ("JUDGMENT", "CONFIRM", BY, TASK))
        self.svc.unconfirm_judgment(TASK, 4, "입력값을 다시 확인하려고", BY)
        self.assertEqual(len(self.svc.list_edit_log(SURVEY)), n + 2)

    def test_unconfirm_needs_a_reason(self):
        self.svc.confirm_judgment(TASK, 4, C.FinalStatus.APPLICABLE, None, BY)
        self.raises("E-CONFIRM-002", self.svc.unconfirm_judgment, TASK, 4, " ", BY)

    def test_confirm_all_skips_review_and_input(self):
        r = self.svc.confirm_all(TASK, BY)
        self.assertIn(3, r.needs_decision)
        self.assertIn(1, r.blocked)
        self.assertIn(4, r.confirmed)

    def test_survey_cannot_be_confirmed_while_drafts_remain(self):
        self.raises("E-CONFIRM-003", self.svc.confirm_survey, SURVEY, BY)

    # ---------------------------------------------------------------- 각도 기준
    def test_AC34_threshold_change_needs_a_reason(self):
        before = self.svc.get_thresholds(SURVEY)
        self.raises("E-THRESHOLD-001", self.svc.set_threshold, SURVEY, C.ThresholdCode.WAIST_FLEX, 30.0, "", BY)
        self.assertEqual(self.svc.get_thresholds(SURVEY), before)
        n_tasks = len(self.svc.get_survey(SURVEY).unit_tasks)
        results = self.svc.set_threshold(SURVEY, C.ThresholdCode.WAIST_FLEX, 30.0, "허리를 받치는 지지대가 있음", BY)
        self.assertEqual(len(results), n_tasks)
        now = {t.threshold_cd: t for t in self.svc.get_thresholds(SURVEY)}
        w = now[C.ThresholdCode.WAIST_FLEX]
        self.assertTrue(w.overridden_yn)
        self.assertEqual(w.value_deg, 30.0)
        self.assertIn("허리를 받치는 지지대가 있음", w.source_label)
        last = self.svc.list_edit_log(SURVEY)[-1]
        self.assertEqual((last.target_cd, last.action_cd), ("THRESHOLD", "CHANGE"))
        self.assertEqual(last.reason_text, "허리를 받치는 지지대가 있음")
        self.svc.reset_threshold(SURVEY, C.ThresholdCode.WAIST_FLEX, BY)
        back = {t.threshold_cd: t for t in self.svc.get_thresholds(SURVEY)}[C.ThresholdCode.WAIST_FLEX]
        self.assertFalse(back.overridden_yn)
        self.assertEqual(back.value_deg, 20.0)
        self.assertEqual(self.svc.list_edit_log(SURVEY)[-1].action_cd, "RESET")

    def test_other_surveys_are_not_affected_by_a_threshold_change(self):
        other = self.svc.create_survey(C.SurveyCreate(C.SurveyType.REGULAR, "2027-02-01", BY, "a", "b", "c"))
        self.svc.set_threshold(SURVEY, C.ThresholdCode.NECK_FLEX, 25.0, "사유", BY)
        theirs = {t.threshold_cd: t for t in self.svc.get_thresholds(other.survey_id)}
        self.assertEqual(theirs[C.ThresholdCode.NECK_FLEX].value_deg, 20.0)
        self.assertFalse(theirs[C.ThresholdCode.NECK_FLEX].overridden_yn)

    # ---------------------------------------------------------------- 영상과 분석
    def test_inspect_video_rejects_unknown_formats(self):
        self.raises("E-VIDEO-001", self.svc.inspect_video, Path("D:/영상/메모.txt"))

    def test_AC09_consent_is_required_before_analysis(self):
        info = self.svc.attach_video(TASK, Path("D:/영상/새영상.mp4"), False, BY)
        self.assertFalse(info.consent_yn)
        self.raises("E-VIDEO-003", self.svc.start_analysis, TASK, info.video_id, lambda p: None)
        self.assertTrue(self.svc.confirm_consent(info.video_id, BY).consent_yn)

    def test_AC10_progress_never_goes_back_and_ends_with_done(self):
        events, done = [], threading.Event()

        def cb(p):
            events.append(p)
            if p.stage in (C.Stage.DONE, C.Stage.FAILED, C.Stage.CANCELED):
                done.set()

        handle = self.svc.start_analysis(TASK, VIDEO, cb)
        self.assertEqual((handle.unit_task_id, handle.video_id), (TASK, VIDEO))
        self.wait(done)
        self.assertEqual(events[-1].stage, C.Stage.DONE)
        self.assertEqual(events[-1].percent, 100.0)
        pct = [e.percent for e in events]
        self.assertEqual(pct, sorted(pct))
        self.assertTrue(all(e.run_id == handle.run_id for e in events))

    def test_AC10_cancel_stops_without_a_new_result(self):
        svc = self.make_service(progress_delay_s=0.1)
        before = svc.get_task_result(TASK).run
        events, done = [], threading.Event()

        def cb(p):
            events.append(p)
            if p.stage in (C.Stage.DONE, C.Stage.FAILED, C.Stage.CANCELED):
                done.set()

        handle = svc.start_analysis(TASK, VIDEO, cb)
        svc.cancel_analysis(handle.run_id)
        self.wait(done)
        self.assertEqual(events[-1].stage, C.Stage.CANCELED)
        self.assertEqual(svc.get_task_result(TASK).run.run_id, before.run_id)

    def test_only_one_analysis_at_a_time(self):
        svc = self.make_service(progress_delay_s=0.1)
        done = threading.Event()
        h = svc.start_analysis(TASK, VIDEO, lambda p: done.set() if p.stage in (C.Stage.DONE, C.Stage.CANCELED, C.Stage.FAILED) else None)
        self.raises("E-ANALYSIS-004", svc.start_analysis, TASK, VIDEO, lambda p: None)
        svc.cancel_analysis(h.run_id)
        self.wait(done)

    # ---------------------------------------------------------------- 대표 장면
    def test_AC20_key_frame_change_leaves_a_log_line(self):
        res = self.svc.get_task_result(TASK)
        n = len(self.svc.list_edit_log(SURVEY))
        frame = 100 if res.key_frame_no != 100 else 101
        after = self.svc.set_key_frame(TASK, frame, BY)
        self.assertEqual(after.key_frame_no, frame)
        log = self.svc.list_edit_log(SURVEY)
        self.assertEqual(len(log), n + 1)
        self.assertEqual(log[-1].target_cd, "KEY_FRAME")
        self.raises("E-INPUT-001", self.svc.set_key_frame, TASK, 10 ** 9, BY)

    # ---------------------------------------------------------------- GPT와 설정
    def test_AC33_settings_persist(self):
        self.svc.save_settings(3, False, None)
        self.assertEqual(self.svc.get_settings().pose_model_id, 3)
        self.raises("E-INPUT-001", self.svc.save_settings, 999, False, None)

    def test_api_key_is_never_returned(self):
        self.svc.set_gpt_api_key("dummy-key-for-test")
        s = self.svc.get_settings()
        self.assertTrue(s.has_gpt_key)
        self.assertNotIn("dummy-key-for-test", repr(s))
        self.svc.delete_gpt_api_key()
        self.assertFalse(self.svc.get_settings().has_gpt_key)
        self.raises("E-INPUT-002", self.svc.set_gpt_api_key, "  ")

    def test_AC35_gpt_off_gives_the_default_sentence_only(self):
        """GPT를 끄면 새 문장을 요청하지 않고 기본 문구만 나온다 (API 계약서 6.6절)."""
        self.svc.save_settings(4, False, None)
        warn = next(w for w in self.svc.get_task_result(TASK).warnings if w.ai_text is None)
        res = self.svc.request_warning_advice(warn.warning_id)
        self.assertFalse(res.is_ai)
        self.assertNotEqual(res.result_cd, C.AiResult.OK)
        self.assertTrue(res.text)

    def test_stored_ai_sentence_stays_when_gpt_is_turned_off(self):
        """이미 저장된 문장(조사자가 고친 것 포함)은 GPT를 꺼도 사라지지 않는다 (API 계약서 6.6절)."""
        warn = next(w for w in self.svc.get_task_result(TASK).warnings if w.ai_text is not None)
        self.svc.save_settings(4, False, None)
        again = next(w for w in self.svc.get_task_result(TASK).warnings if w.warning_id == warn.warning_id)
        self.assertEqual(again.ai_text, warn.ai_text)
        self.assertEqual(self.svc.request_warning_advice(warn.warning_id).text, warn.ai_text)

    def test_ai_text_can_be_edited(self):
        warn = self.svc.get_task_result(TASK).warnings[0]
        res = self.svc.request_warning_advice(warn.warning_id)
        edited = self.svc.edit_ai_text(res.ai_text_id, "상자를 허리 높이에 두세요.", BY)
        self.assertEqual(edited.text, "상자를 허리 높이에 두세요.")
        self.raises("E-INPUT-002", self.svc.edit_ai_text, res.ai_text_id, " ", BY)

    def test_export_to_a_missing_folder_fails_cleanly(self):
        self.raises("E-EXPORT-001", self.svc.export_excel, SURVEY, Path("Z:/없는폴더/보고서.xlsx"), BY)
