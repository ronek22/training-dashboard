import json
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from scripts import sunday_review as review


class SundayReviewWorkerTests(unittest.TestCase):
    def test_sunday_end_boundary_and_monday_catchup(self):
        for value, expected in [
            ('2026-09-06T23:58:59', '2026-08-24'),
            ('2026-09-06T23:59:00', '2026-08-31'),
            ('2026-09-07T08:00:00', '2026-08-31'),
            ('2026-10-25T23:59:00', '2026-10-19'),
        ]:
            with self.subTest(value=value):
                self.assertEqual(review.due_week(datetime.fromisoformat(value).replace(tzinfo=review.ZONE)), expected)
        self.assertEqual(review.due_week(datetime(2026, 9, 6, 21, 59, tzinfo=ZoneInfo('UTC'))), '2026-08-31')

    @patch.object(review, 'request')
    def test_saved_review_skips_model_after_restart(self, request):
        request.return_value = [{'week_start': '2026-08-31', 'generator': 'codex-cli'}]
        model = Mock()
        self.assertFalse(review.run_once(model, datetime(2026, 9, 7, tzinfo=review.ZONE)))
        model.assert_not_called()

    @patch.object(review, 'request')
    def test_generation_uses_context_and_saves_structured_output(self, request):
        request.side_effect = [[], {'review_week': '2026-08-31', 'previous_change': None}, {}]
        payload = {'improved': 'Stable pacing', 'missed': 'No evidence of a miss',
                   'proposed_change': 'Keep easy rides easy', 'previous_change_outcome': 'not_assessed',
                   'outcome_reason': 'No prior review'}
        model = Mock(return_value=json.dumps(payload))
        self.assertTrue(review.run_once(model, datetime(2026, 9, 7, tzinfo=review.ZONE)))
        self.assertEqual(request.call_args.args, ('/reviews/weekly', {**payload, 'week_start': '2026-08-31'}))
        self.assertIn('Do not call tools', model.call_args.args[0])

    @patch.object(review, 'request')
    def test_invalid_model_output_is_not_saved(self, request):
        request.side_effect = [[], {}]
        with self.assertRaises(ValueError):
            review.run_once(Mock(return_value='Not JSON'), datetime(2026, 9, 7, tzinfo=review.ZONE))
        self.assertEqual(request.call_count, 2)

    @patch.object(review, 'run_once', side_effect=RuntimeError('offline'))
    def test_failure_retries_with_backoff(self, run_once):
        stopped = Mock()
        stopped.is_set.side_effect = [False, True]
        with self.assertLogs(level='ERROR'):
            review.run_loop(Mock(), stopped)
        stopped.wait.assert_called_once_with(900)
