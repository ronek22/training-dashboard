import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.routers.goals import router
from backend.app.services.goal_history import build_goal_period_history, recurring_period_windows

TODAY = date(2026, 9, 28)  # a Monday


def ride_goal(**changes):
    return {
        'goal_family': 'accumulation',
        'metric_type': 'ride_km',
        'period_type': 'week',
        'target_value': 100,
        'activity_type': None,
        'created_at': '2026-06-22 10:00:00',
        **changes,
    }


class GoalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'history.db')
        self.db_patch = patch.object(db, 'DB_PATH', self.path)
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()
        self.next_id = 1

    def tearDown(self):
        self.conn.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def add(self, day, activity_type='Ride', distance_km=0.0):
        self.conn.execute(
            'INSERT INTO activities (id, date, type, name, distance_km, duration_min) VALUES (?, ?, ?, ?, ?, 60)',
            (str(self.next_id), day.isoformat(), activity_type, 'Test', distance_km),
        )
        self.next_id += 1
        self.conn.commit()

    def history(self, goal, **kwargs):
        return build_goal_period_history(self.conn, goal, today=TODAY, **kwargs)

    def test_recurring_windows_exclude_current_period(self):
        windows, current = recurring_period_windows('week', 3, TODAY)
        self.assertEqual(windows[-1], (date(2026, 9, 21), date(2026, 9, 27)))
        self.assertEqual(windows[0], (date(2026, 9, 7), date(2026, 9, 13)))
        self.assertEqual(current, (date(2026, 9, 28), date(2026, 10, 4)))

        months, current_month = recurring_period_windows('month', 2, date(2026, 3, 15))
        self.assertEqual(months, [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28))])
        self.assertEqual(current_month, (date(2026, 3, 1), date(2026, 3, 31)))

    def test_weekly_goal_stats(self):
        # Eight completed weeks: six clear the target comfortably, two miss.
        weekly_km = [150, 180, 60, 200, 170, 90, 190, 160]
        first_week = date(2026, 8, 3)
        for index, km in enumerate(weekly_km):
            self.add(first_week + timedelta(days=7 * index + 2), distance_km=km)
        self.add(TODAY, distance_km=40)

        history = self.history(ride_goal(), periods=8)
        stats = history['stats']
        self.assertTrue(history['available'])
        self.assertEqual(stats['periods'], 8)
        self.assertEqual(stats['hit_count'], 6)
        self.assertEqual(stats['hit_rate'], 0.75)
        self.assertEqual(stats['median'], 165.0)
        self.assertEqual(stats['current_streak'], 2)
        self.assertEqual(stats['best'], 200)
        self.assertEqual(stats['margin'], 1.65)

        current = history['entries'][-1]
        self.assertTrue(current['partial'])
        self.assertEqual(current['value'], 40)
        self.assertEqual(len(history['entries']), 9)

    def test_periods_before_first_activity_are_not_counted_as_misses(self):
        self.add(date(2026, 9, 16), distance_km=120)
        stats = self.history(ride_goal())['stats']
        self.assertEqual(stats['periods'], 2)  # weeks of 14 and 21 Sep only
        self.assertEqual(stats['hit_count'], 1)

    def test_periods_before_goal_creation_are_flagged(self):
        self.add(date(2026, 8, 1), distance_km=120)
        history = self.history(ride_goal(created_at='2026-09-01 08:00:00'))
        flagged = [entry['before_goal'] for entry in history['entries'] if not entry['partial']]
        self.assertTrue(flagged[0])
        self.assertFalse(flagged[-1])
        self.assertLess(history['stats']['periods_since_created'], history['stats']['periods'])

    def test_count_median_is_not_rounded_up(self):
        for offset in (0, 7, 8, 14, 15, 21, 22, 23):
            self.add(date(2026, 9, 1) + timedelta(days=offset), activity_type='WeightTraining')
        goal = ride_goal(goal_family='process', metric_type='strength_sessions', target_value=3)
        history = self.history(goal, periods=4)
        self.assertEqual([entry['value'] for entry in history['entries'][:-1]], [1, 2, 2, 3])
        self.assertEqual(history['stats']['median'], 2.0)

    def test_yearly_goal_reports_required_versus_recent_rate(self):
        self.add(date(2026, 1, 10), activity_type='Run', distance_km=200)
        for week in range(8):
            self.add(date(2026, 8, 3) + timedelta(days=7 * week), activity_type='Run', distance_km=5)
        goal = ride_goal(metric_type='run_km', period_type='year', target_value=1000)

        history = self.history(goal)
        stats = history['stats']
        self.assertEqual(history['kind'], 'yearly')
        self.assertEqual(stats['year_to_date'], 240)
        self.assertEqual(stats['remaining'], 760)
        self.assertEqual(stats['recent_rate_per_week'], 5.0)
        self.assertGreater(stats['required_rate_ratio'], 10)
        self.assertIsNone(stats['reached_in'])
        self.assertEqual([entry['label'] for entry in history['entries']][:2], ['Jan', 'Feb'])
        self.assertTrue(history['entries'][-1]['partial'])

    def test_yearly_goal_records_month_target_was_reached(self):
        for month in range(1, 9):
            self.add(date(2026, month, 15), distance_km=500)
        stats = self.history(ride_goal(period_type='year', target_value=3500))['stats']
        self.assertEqual(stats['reached_in'], '2026-07')
        self.assertEqual(stats['remaining'], 0)
        self.assertEqual(stats['required_rate_ratio'], 0.0)

    def test_benchmark_goals_are_unavailable(self):
        history = self.history({'goal_family': 'benchmark', 'metric_type': 'benchmark_power', 'period_type': 'year'})
        self.assertFalse(history['available'])
        self.assertIn('benchmark', history['reason'])


class GoalHistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'api.db'))
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def test_history_is_opt_in_on_list_and_available_per_goal(self):
        goal_id = self.client.post('/goals', json={
            'title': 'Ride 100km weekly', 'period_type': 'week', 'goal_family': 'accumulation',
            'metric_type': 'ride_km', 'target_value': 100,
        }).json()['id']
        self.assertNotIn('history', self.client.get('/goals').json()[0])
        self.assertIn('history', self.client.get('/goals', params={'include_history': True}).json()[0])

        response = self.client.get(f'/goals/{goal_id}/history', params={'periods': 4})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['kind'], 'recurring')
        self.assertEqual(self.client.get('/goals/999/history').status_code, 404)


if __name__ == '__main__':
    unittest.main()
