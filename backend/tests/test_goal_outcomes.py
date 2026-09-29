import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.adapters.mcp import build_mcp_router_dependencies
from backend.app.routers.goals import router
from backend.app.services import goal_outcomes
from backend.app.services.goal_outcomes import (
    _cost_signal,
    build_outcome_signals,
    classify_trend,
    outcome_keys_for_goal,
)
from backend.app.services.mcp import call_mcp_tool

TODAY = date(2026, 9, 28)


def power_profile(monthly_20m):
    """Minimal power-trends payload: {month: watts} for 20-minute bests."""
    efforts = []
    monthly = []
    for month, watts in monthly_20m.items():
        month_efforts = [
            {'duration_seconds': 1200, 'watts': watts - offset, 'activity_id': f'{month}-{offset}', 'date': f'{month}-1{offset}'}
            for offset in range(3)
        ]
        efforts.extend(month_efforts)
        monthly.append({'month': month, 'efforts': [month_efforts[0]]})
    return {
        'monthly': monthly,
        'efforts': efforts,
        'coverage': {'measured_power_activities': len(efforts), 'cycling_activities': 40},
    }


def strength_session(day, lifts):
    return {
        'workout_date': day.isoformat(),
        'exercises': [
            {'exercise_name': name, 'sets': [{'weight_kg': weight, 'reps': reps, 'is_warmup': False}]}
            for name, weight, reps in lifts
        ],
    }


def daily_history(start, values):
    return [{'date': (start + timedelta(days=index)).isoformat(), 'value': value} for index, value in enumerate(values)]


class ClassifyTrendTests(unittest.TestCase):
    def test_needs_three_months_and_six_points(self):
        self.assertEqual(classify_trend([('a', 1), ('b', 2)], evidence_count=20), ('insufficient', None))
        self.assertEqual(classify_trend([('a', 1), ('b', 2), ('c', 3)], evidence_count=5), ('insufficient', None))

    def test_directions(self):
        rising = [('a', 200), ('b', 205), ('c', 215), ('d', 220)]
        self.assertEqual(classify_trend(rising, evidence_count=10)[0], 'improving')
        self.assertEqual(classify_trend(rising, evidence_count=10, higher_is_better=False)[0], 'declining')
        steady = [('a', 200), ('b', 201), ('c', 199), ('d', 202)]
        self.assertEqual(classify_trend(steady, evidence_count=10)[0], 'flat')


class OutcomeSignalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'signals.db'))
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def signal(self, key, profile=None, sessions=None):
        with patch.object(goal_outcomes, 'get_cycling_power_trends_data', return_value=profile or power_profile({})), \
                patch.object(goal_outcomes, 'get_strength_overview_data', return_value={'sessions': sessions or []}):
            return build_outcome_signals(self.conn, [key], today=TODAY)[key]

    def test_power_gap_months_are_insufficient_not_zero(self):
        signal = self.signal('cycling_power_20m', power_profile({'2026-08': 160, '2026-09': 200}))
        self.assertEqual(signal['trend'], 'insufficient')
        self.assertEqual([item['value'] for item in signal['series']], [None, None, None, None, 160, 200])
        self.assertIn('verified power', signal['note'])

    def test_power_trend_with_enough_months(self):
        profile = power_profile({'2026-05': 200, '2026-06': 205, '2026-07': 215, '2026-08': 222})
        signal = self.signal('cycling_power_20m', profile)
        self.assertEqual(signal['trend'], 'improving')
        self.assertGreater(signal['change_pct'], 2)

    def test_strength_uses_recent_typical_level_not_peak_months(self):
        sessions = []
        # Established level: 100 kg bench, with one peak day in May that should not set the bar.
        for week in range(18):
            day = date(2026, 4, 6) + timedelta(days=7 * week)
            weight = 110 if day == date(2026, 5, 11) else 100
            sessions.append(strength_session(day, [('Bench', weight, 1), ('Row', 80, 1)]))
        for day in (date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 22)):
            sessions.append(strength_session(day, [('Bench', 100, 1), ('Row', 81, 1)]))

        signal = self.signal('strength_maintenance', sessions=sessions)
        self.assertEqual(signal['trend'], 'flat')
        bench = next(item for item in signal['detail'] if item['exercise'] == 'Bench')
        self.assertEqual(bench['change_pct'], 0.0)

    def test_strength_decline_is_detected(self):
        sessions = [strength_session(date(2026, 4, 6) + timedelta(days=7 * week), [('Bench', 100, 1)]) for week in range(18)]
        sessions += [strength_session(day, [('Bench', 90, 1)]) for day in (date(2026, 9, 8), date(2026, 9, 22))]
        signal = self.signal('strength_maintenance', sessions=sessions)
        self.assertEqual(signal['trend'], 'declining')
        self.assertEqual(signal['change_pct'], -10.0)

    def test_strength_ignores_warmups_and_high_rep_sets(self):
        session = {
            'workout_date': '2026-09-20',
            'exercises': [{'exercise_name': 'Bench', 'sets': [
                {'weight_kg': 200, 'reps': 1, 'is_warmup': True},
                {'weight_kg': 60, 'reps': 20, 'is_warmup': False},
            ]}],
        }
        signal = self.signal('strength_maintenance', sessions=[session])
        self.assertEqual(signal['detail'], [])
        self.assertEqual(signal['trend'], 'insufficient')

    def test_cycling_efficiency_uses_verified_steady_rides(self):
        profile = power_profile({'2026-06': 200, '2026-07': 200, '2026-08': 200})
        rows = []
        for month, efficiency in (('2026-06', 1.0), ('2026-07', 1.05), ('2026-08', 1.1)):
            for offset in range(3):
                rows.append((f'{month}-{offset}', f'{month}-1{offset}', 'VirtualRide', 60, efficiency * 140, 140, None))
        rows.append(('unverified', '2026-08-20', 'Ride', 60, 500, 100, None))
        rows.append(('2026-08-9', '2026-08-21', 'VirtualRide', 60, 300, 150, 'interval'))
        self.conn.executemany(
            'INSERT INTO activities (id, date, type, duration_min, avg_watts, avg_hr, workout_intent) VALUES (?, ?, ?, ?, ?, ?, ?)',
            rows,
        )
        self.conn.commit()
        signal = self.signal('cycling_efficiency', profile)
        self.assertEqual(signal['evidence_count'], 9)
        self.assertEqual(signal['trend'], 'improving')

    def test_goal_links_default_and_override(self):
        self.assertEqual(outcome_keys_for_goal({'metric_type': 'strength_sessions'}), ['strength_maintenance'])
        self.assertEqual(outcome_keys_for_goal({'metric_type': 'ride_km'}), ['cycling_efficiency', 'cycling_power_20m'])
        self.assertEqual(outcome_keys_for_goal({'metric_type': 'ride_km', 'outcome_signal': 'cycling_power_5m'}), ['cycling_power_5m'])
        self.assertEqual(outcome_keys_for_goal({'metric_type': 'ride_km', 'outcome_signal': 'nonsense'}), ['cycling_efficiency', 'cycling_power_20m'])
        self.assertEqual(outcome_keys_for_goal({'metric_type': 'benchmark_power'}), [])


class CostSignalTests(unittest.TestCase):
    def test_hrv_drop_is_declining(self):
        history = daily_history(TODAY - timedelta(days=34), [60] * 28 + [52] * 7)
        signal = _cost_signal('hrv', history, TODAY)
        self.assertEqual(signal['trend'], 'declining')
        self.assertFalse(signal['stale'])
        self.assertEqual(signal['baseline_mean'], 60)

    def test_resting_hr_rise_is_declining(self):
        history = daily_history(TODAY - timedelta(days=34), [60] * 28 + [64] * 7)
        self.assertEqual(_cost_signal('resting_hr', history, TODAY)['trend'], 'declining')

    def test_small_change_is_flat(self):
        history = daily_history(TODAY - timedelta(days=34), [60] * 28 + [61] * 7)
        self.assertEqual(_cost_signal('hrv', history, TODAY)['trend'], 'flat')

    def test_old_data_is_stale(self):
        history = daily_history(TODAY - timedelta(days=46), [60] * 35)
        signal = _cost_signal('hrv', history, TODAY)
        self.assertTrue(signal['stale'])
        self.assertIn('stale', signal['note'])

    def test_missing_and_thin_data(self):
        self.assertEqual(_cost_signal('sleep', [], TODAY)['trend'], 'insufficient')
        thin = daily_history(TODAY - timedelta(days=3), [7.5] * 4)
        self.assertEqual(_cost_signal('sleep', thin, TODAY)['trend'], 'insufficient')


class GoalSignalApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'api.db'))
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.patches = [
            patch.object(goal_outcomes, 'get_cycling_power_trends_data', return_value=power_profile({})),
            patch.object(goal_outcomes, 'get_strength_overview_data', return_value={'sessions': []}),
            patch.object(goal_outcomes, '_health_history', return_value=[]),
        ]
        for item in self.patches:
            item.start()
        self.goal_id = self.client.post('/goals', json={
            'title': 'Lift three times per week', 'period_type': 'week', 'goal_family': 'process',
            'metric_type': 'strength_sessions', 'target_value': 3,
        }).json()['id']

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def test_goal_outcomes_endpoint(self):
        body = self.client.get(f'/goals/{self.goal_id}/outcomes').json()
        self.assertEqual(body['linked'], ['strength_maintenance'])
        self.assertEqual(body['signals'][0]['trend'], 'insufficient')
        self.assertEqual({signal['key'] for signal in body['costs']}, {'hrv', 'resting_hr', 'sleep'})
        self.assertEqual(self.client.get('/goals/999/outcomes').status_code, 404)

    def test_outcomes_are_opt_in_on_list(self):
        self.assertNotIn('outcomes', self.client.get('/goals').json()[0])
        goal = self.client.get('/goals', params={'include_outcomes': True}).json()[0]
        self.assertEqual(goal['outcomes']['linked'], ['strength_maintenance'])

    def test_signals_endpoint_and_mcp_tool(self):
        body = self.client.get('/goals/signals').json()
        self.assertIn('strength_maintenance', {signal['key'] for signal in body['outcomes']})

        result = call_mcp_tool('get_goal_signals', {'goal_id': self.goal_id}, **build_mcp_router_dependencies())
        content = result['structuredContent']
        self.assertEqual(content['linked'], ['strength_maintenance'])
        self.assertNotIn('series', content['outcomes'][0])
        self.assertEqual(len(content['costs']), 3)


if __name__ == '__main__':
    unittest.main()
