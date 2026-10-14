import unittest
from scripts import cycling_power_helper as helper


class CyclingPowerHelperTests(unittest.TestCase):
    def test_normalize_fits_reply_to_save_schema(self):
        focus = {'title': 'T' * 150, 'reason': 'r', 'action': 'a', 'success_check': 's', 'extra': 'x'}
        result = helper.normalize({'context_key': 'other', 'headline': 'H' * 200, 'assessment': 'a',
                                   'focus': [focus] * 5, 'uncertainty': None, 'evidence_ids': [42, '', 'abc'],
                                   'notes': 'dropped'}, 'k')
        self.assertEqual(result['context_key'], 'k')
        self.assertEqual(len(result['headline']), 120)
        self.assertEqual(len(result['focus']), 3)
        self.assertEqual(set(result['focus'][0]), {'title', 'reason', 'action', 'success_check'})
        self.assertEqual(len(result['focus'][0]['title']), 100)
        self.assertEqual(result['uncertainty'], '')
        self.assertEqual(result['evidence_ids'], ['42', 'abc'])
        self.assertNotIn('notes', result)


if __name__ == '__main__':
    unittest.main()
