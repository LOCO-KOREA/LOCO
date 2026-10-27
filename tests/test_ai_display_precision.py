"""Display precision and discarded model comparisons do not reject valid AI text."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from ergo.gpt import client,payload
from test_gpt_input_linkage import source_analysis
from test_v2_gpt import content_fixture,summary_fixture


def measured_summary():
    source=source_analysis()
    source['snapshot']['capture']['slots']=source['snapshot']['capture']['slots'][:1]
    source['snapshot']['capture']['slots'][0]['observation']['measured_load_kg']=20.34
    source['pose']=dict(slots=[dict(slot_no=17,photo_id=7711,points=[dict(name='nose',x_px=10,y_px=20,confidence=.87654)],
        angles=[dict(side='LEFT',angle_code='TRUNK_TILT_VERT',value_deg=33.7139484,min_confidence=.87654)],
        world_angles=[dict(side='LEFT',angle_code='REFERENCE_3D',value_deg=53.51234,min_confidence=.87654)])])
    before=copy.deepcopy(source)
    summary=payload.build_numeric_summary(source)
    assert source==before
    return summary


class AiDisplayPrecision(unittest.TestCase):
    def generate(self,summary,content):
        response=SimpleNamespace(status='completed',output_text=json.dumps(content,ensure_ascii=False),id='fixture')
        with patch('ergo.gpt.client.create_response',return_value=response):
            return client.generate(summary,'fixture','fixture-key')

    def test_model_comparison_is_normalized_before_validating_the_discarded_field(self):
        summary=summary_fixture();content=content_fixture(summary)
        content['reba_comparison']='미완성 1차 정보에서 작성한 비교 999점'
        result,error=self.generate(summary,content)
        self.assertIsNone(error)
        self.assertEqual(result['reba_comparison'],'')

    def test_missing_or_wrong_comparison_types_and_other_invalid_numbers_stay_rejected(self):
        summary=summary_fixture()
        for value in ('missing',None,False,{}):
            content=content_fixture(summary)
            if value=='missing':content.pop('reba_comparison')
            else:content['reba_comparison']=value
            result,error=self.generate(summary,content)
            self.assertIsNone(result)
            self.assertEqual(error,'INVALID_STRUCTURED_CONTENT')
        content=content_fixture(summary);content['summary']='알 수 없는 999점'
        self.assertEqual(self.generate(summary,content),(None,'INVALID_STRUCTURED_CONTENT'))

    def test_only_declared_angle_and_confidence_display_precision_is_accepted(self):
        summary=measured_summary();photo=summary['posture_results'][0]
        self.assertEqual(photo['angles'][0]['value_deg'],33.7139484)
        self.assertEqual(photo['angles'][0]['display_value_deg'],33.7)
        self.assertEqual(photo['inferred_world_angles'][0]['display_value_deg'],53.5)
        self.assertEqual(photo['measurement_quality']['display_confidence_percent'],88)
        self.assertEqual(summary['pose_quality']['display_confidence_percent'],88)
        content=content_fixture(summary)
        content['posture_explanations'][0]['explanation']='몸통 33.7도, 참고 53.5도, 관절 신뢰도 88%입니다.'
        self.assertTrue(payload.validate_content(content,summary))
        content['summary']='사진 중량은 20.3kg입니다.'
        self.assertFalse(payload.validate_content(content,summary),'display precision must not allow rounding a recorded mass20.34')
        content['summary']='근거 없는 999점입니다.'
        self.assertFalse(payload.validate_content(content,summary))
        content['summary']='근거 없는 신뢰도 999%입니다.'
        self.assertFalse(payload.validate_content(content,summary),'percent signs must not bypass numeric provenance')


if __name__=='__main__':unittest.main()
