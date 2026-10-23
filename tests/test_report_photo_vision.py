"""Photo observations reach output from the chosen snapshot with exact ownership."""
import copy
import unittest

from ergo.intake.contract import SESSION_KEY
from ergo.report.photo_vision import observation_rows, observation_sheet
from ergo.report.plain import _context, note


def source(value='허리를 앞으로 굽힌 모습', owner=11):
    return dict(task_id=1, conditions={SESSION_KEY: dict(photo_vision=dict(photos=[
        dict(photo_id=owner, view='LEFT', status='OBSERVED',
             source_sha256='not-for-display', connection=dict(response_id='private-response'),
             observations=dict(trunk=dict(status='OBSERVED', value=value,
                 evidence='상체가 앞으로 기울어져 있어요.', reason='', confidence=0.93))),
        dict(photo_id=99, view='RIGHT', observations=dict(trunk=dict(
             status='OBSERVED', value='제거된 사진의 내용', evidence='이전 사진', reason='')))
    ]))}, capture=dict(slots=[dict(photo_id=owner, slot_no=1, analysis_target=True)]))


class VisionOutput(unittest.TestCase):
    def test_exact_photo_row_keeps_observation_and_evidence_without_private_metadata(self):
        saved = source(); before = copy.deepcopy(saved)
        rows = observation_rows('물건 정리', saved)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], '왼쪽에서 찍은 사진')
        self.assertEqual(rows[0][3], '허리를 앞으로 굽힌 모습')
        self.assertEqual(rows[0][5], '상체가 앞으로 기울어져 있어요.')
        self.assertNotIn('private-response', str(rows))
        self.assertNotIn('not-for-display', str(rows))
        self.assertNotIn('제거된 사진의 내용', str(rows))
        self.assertEqual(saved, before)

    def test_selected_analysis_stays_immutable_when_the_live_task_changes(self):
        selected = source(); live = source('나중에 바뀐 현재 작업')
        snapshot = dict(survey={}, tasks=[live], analyses=[dict(task_id=1, snapshot=selected)])
        context = _context(snapshot, dict(tasks=[dict(task_id=1, task_name='작업')]))
        sheet = observation_sheet(context)
        self.assertEqual(sheet['name'], 'AI 사진 관찰')
        self.assertEqual(sheet['tables'][0]['rows'][0][3], '허리를 앞으로 굽힌 모습')
        self.assertNotIn('나중에 바뀐 현재 작업', str(sheet))
        self.assertIsNone(observation_sheet(dict(tasks=[dict(name='옛 작업', source={})])))

    def test_uncertain_is_not_converted_to_no_and_vision_evidence_stays_readable(self):
        saved = source(); item = saved['conditions'][SESSION_KEY]['photo_vision']['photos'][0]
        item['observations']['trunk'] = dict(status='NOT_VISIBLE', value='',
            evidence='상체가 가려져 있어요.', reason='다른 각도에서 확인이 필요해요.')
        row = observation_rows('작업', saved)[0]
        self.assertNotIn('아니오', row)
        self.assertIn('가려져', row[5])
        self.assertIn('다른 각도', row[5])
        self.assertEqual(note('{"photo_vision":true,"quote":"허리를 굽힌 모습"}'),
                         'AI 사진 관찰: 허리를 굽힌 모습')


if __name__ == '__main__':
    unittest.main()
