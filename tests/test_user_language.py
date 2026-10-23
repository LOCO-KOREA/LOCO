import copy
import unittest
from ergo.user_language import user_text
from ergo.report.plain import _explanations


class UserLanguage(unittest.TestCase):
    def test_codes_adjacent_to_korean_and_numeric_units(self):
        self.assertEqual(user_text('NEEDS_INPUT입니다. NOT_APPLICABLE입니다. YES NO UNKNOWN 20kg 0분'),
                         '추가 정보 필요입니다. 해당하지 않음입니다. 예 아니오 모름 20kg 0분')
        self.assertEqual(user_text('UNKNOWN_FIELD YESMAN C01-B01'),'UNKNOWN_FIELD YESMAN C01-B01')

    def test_old_explanation_is_localized_for_excel_without_rewriting_history(self):
        data={'tasks':[{'name':'작업','analysis':{'ai':[{'is_active':True,'applied_text':'NEEDS_INPUT입니다. 20kg','applied_kind':'GENERATED'}]}}]}
        before=copy.deepcopy(data)
        sheet=_explanations(data)
        self.assertIn('추가 정보 필요입니다. 20kg',str(sheet));self.assertNotIn('NEEDS_INPUT',str(sheet))
        self.assertEqual(data,before)
