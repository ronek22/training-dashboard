import unittest
from unittest.mock import patch

from app.services.session_comparisons import endurance_comparison, pace_seconds, strength_comparisons


def activity(id, day, **changes):
    return dict(id=id, date=day, type='Run', name=id, avg_hr=140, avg_pace='5:00',
                avg_watts=200, duration_min=40, elevation_m=0, workout_intent=None) | changes


class ComparisonTests(unittest.TestCase):
    def test_run_selects_control_match_not_best_outcome(self):
        rows = [activity('new', '2026-09-01', avg_pace='5:10'),
                activity('close', '2026-08-01', avg_pace='5:00'),
                activity('favorable', '2026-08-20', avg_hr=144, avg_pace='6:00')]
        result = endurance_comparison(rows, 'running')['comparison']
        self.assertEqual(result['earlier']['activity_id'], 'close')
        self.assertEqual(result['delta'], 10)
        self.assertTrue(any('intent is missing' in f for f in result['flags']))

    def test_cycling_rejects_environment_intent_and_duration_mismatches(self):
        recent = activity('new', '2026-09-01', type='Ride', workout_intent='easy')
        for changes in ({'type': 'VirtualRide'}, {'workout_intent': 'intervals'}, {'duration_min': 80}, {'avg_watts': 230}):
            old = activity('old', '2026-08-01', type='Ride', workout_intent='easy') | changes
            self.assertIsNone(endurance_comparison([recent, old], 'cycling')['comparison'])
        old = activity('old', '2026-08-01', type='Ride', avg_hr=145, avg_watts=205)
        self.assertEqual(endurance_comparison([recent, old], 'cycling')['comparison']['delta'], -5)

    def test_invalid_metrics_and_same_day_never_match(self):
        rows = [activity('a', '2026-09-01'), activity('b', '2026-09-01'),
                activity('c', '2026-08-01', avg_hr=0), activity('d', '2026-08-02', avg_pace='5:99')]
        result = endurance_comparison(rows, 'running')
        self.assertIsNone(result['comparison'])
        self.assertEqual(result['excluded'], 2)
        self.assertIsNone(pace_seconds('nan'))

    @patch('app.services.session_comparisons._load_strength_rows')
    def test_strength_exact_weight_best_work_set_and_count_warning(self, loader):
        sessions = [dict(id=i, workout_date=f'2026-08-0{i}', activity_id=str(i), title='Lift', activity_name='Lift', source='trainlog') for i in (1, 2)]
        exercises = [dict(id=i, session_id=i, exercise_name='Bench Press') for i in (1, 2)]
        sets = [dict(exercise_id=1, weight_kg=60, reps=8, is_warmup=0),
                dict(exercise_id=2, weight_kg=60, reps=10, is_warmup=0),
                dict(exercise_id=2, weight_kg=60, reps=7, is_warmup=0),
                dict(exercise_id=2, weight_kg=60, reps=20, is_warmup=1),
                dict(exercise_id=2, weight_kg=61, reps=15, is_warmup=0),
                dict(exercise_id=2, weight_kg=None, reps=10, is_warmup=0)]
        loader.return_value = sessions, exercises, sets
        result = strength_comparisons(None, '2026-01-01', '2026-09-01')
        self.assertEqual(len(result['items']), 1)
        comparison = result['items'][0]['comparison']
        self.assertEqual(comparison['delta'], 2)
        self.assertTrue(any('count differs' in f for f in comparison['flags']))
        self.assertEqual(result['excluded_sets'], 1)
