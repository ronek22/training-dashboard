import unittest
from datetime import date, timedelta
from unittest.mock import patch

from app.services.strength import get_strength_overview_data


class StrengthRangeTests(unittest.TestCase):
    @patch('app.services.strength._filtered_sessions', return_value=([], []))
    def test_extended_ranges_cover_every_week(self, filtered):
        for weeks in (26, 52):
            with self.subTest(weeks=weeks):
                result = get_strength_overview_data(None, weeks=weeks)
                self.assertEqual(result['window']['weeks'], weeks)
                self.assertEqual(len(result['weekly']), weeks)
                start = date.fromisoformat(result['window']['start_date'])
                self.assertEqual(filtered.call_args.kwargs['window_start'], start)
                self.assertEqual(result['weekly'][0]['week_start'], start.isoformat())
                self.assertEqual(result['weekly'][-1]['week_start'], (start + timedelta(weeks=weeks - 1)).isoformat())
                self.assertLessEqual(start + timedelta(weeks=weeks - 1), date.today())

    @patch('app.services.strength._filtered_sessions', return_value=([], []))
    def test_invalid_range_keeps_default(self, _filtered):
        result = get_strength_overview_data(None, weeks=999)
        self.assertEqual(result['window']['weeks'], 8)
        self.assertEqual(len(result['weekly']), 8)
