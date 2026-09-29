import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.adapters.mcp import build_mcp_router_dependencies
from backend.app.repositories.settings import set_setting_value
from backend.app.routers.goals import router as goals_router
from backend.app.routers.weekly_reviews import router as weekly_router
from backend.app.services import goal_outcomes
from backend.app.services.goal_portfolio import OVER_COMMIT_RATIO, build_portfolio_check, portfolio_conflict
from backend.app.services.mcp import call_mcp_tool
from backend.app.services.plans import _build_goal_conflicts
from backend.app.services.weekly_reviews import is_monthly_goal_review_week

TODAY = date(2026, 9, 28)  # a Monday
LAST_MONDAY = TODAY - timedelta(days=7)


def goal(goal_id=1, title='Ride 90 km weekly', **changes):
    return {
        'id': goal_id, 'title': title, 'metric_type': 'ride_km', 'period_type': 'week', 'target_value': 90.0,
        'current_value': 0.0, 'commitment': 'flexible', 'is_active': True, 'season_ended': False,
        'activity_type': None, 'end_date': '2026-09-28', **changes,
    }


def anchor_lift():
    return goal(2, 'Lift 3x/week', metric_type='strength_sessions', target_value=3.0, commitment='anchor')


def add_week(conn, monday, ride_hours=2.0, ride_km=60.0, lift_hours=1.0):
    rows = [(f'r{monday}', (monday + timedelta(days=1)).isoformat(), 'Ride', ride_km, ride_hours * 60)]
    if lift_hours:
        rows.append((f'w{monday}', (monday + timedelta(days=3)).isoformat(), 'WeightTraining', None, lift_hours * 60))
    conn.executemany(
        'INSERT INTO activities (id, date, type, name, distance_km, duration_min) VALUES (?, ?, ?, ?, ?, ?)',
        [(a, d, t, t, km, mins) for a, d, t, km, mins in rows],
    )


class PortfolioTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'portfolio.db'))
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def train(self, weeks=12, **kwargs):
        for index in range(1, weeks + 1):
            add_week(self.conn, TODAY - timedelta(days=7 * index), **kwargs)
        self.conn.commit()

    def check(self, goals, off_months=None):
        return build_portfolio_check(self.conn, goals, today=TODAY, off_season_months=off_months or [])


class PortfolioBudgetTests(PortfolioTestCase):
    def test_over_commitment_names_biggest_goals_and_spares_the_anchor(self):
        self.train()  # 3 h/week: 2 h riding at 30 km/h plus 1 h lifting
        result = self.check([goal(), anchor_lift()])
        self.assertEqual(result['status'], 'over_committed')
        self.assertEqual(result['actual_weekly_hours'], 3.0)
        self.assertEqual(result['implied_weekly_hours'], 6.0)  # 90 km / 30 = 3 h, 3 lifts x 1 h = 3 h
        self.assertGreater(result['ratio'], OVER_COMMIT_RATIO)
        self.assertEqual([item['title'] for item in result['contributors']], ['Ride 90 km weekly', 'Lift 3x/week'])
        self.assertEqual([item['title'] for item in result['reduction_candidates']], ['Ride 90 km weekly'])
        self.assertIn('Anchor goals (Lift 3x/week)', result['summary'])

    def test_budget_that_fits_is_not_flagged(self):
        self.train()
        result = self.check([goal(target_value=45.0), goal(2, 'Lift 1x', metric_type='strength_sessions', target_value=1.0)])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['reduction_candidates'], [])
        self.assertIsNone(portfolio_conflict(result))

    def test_anchor_alone_over_budget_offers_nothing_to_reduce(self):
        self.train(lift_hours=0.5, ride_hours=0.6)
        result = self.check([anchor_lift()])
        self.assertEqual(result['status'], 'over_committed')
        self.assertEqual(result['reduction_candidates'], [])

    def test_zone2_and_quality_share_riding_time_with_a_ride_distance_goal(self):
        self.train()
        zone2 = goal(3, 'Zone 2', metric_type='zone2_hours', target_value=2.0)
        result = self.check([goal(target_value=60.0), zone2])
        self.assertEqual(result['implied_weekly_hours'], 2.0)
        self.assertEqual(next(item for item in result['goals'] if item['goal_id'] == 3)['counted_hours'], 0.0)

    def test_yearly_goal_uses_remaining_work_over_remaining_weeks(self):
        self.train()
        yearly = goal(period_type='year', target_value=3000.0, current_value=2700.0, end_date='2026-12-21')
        result = self.check([yearly])
        # 300 km over 12 weeks at 30 km/h
        self.assertEqual(result['goals'][0]['weekly_hours'], 0.8)
        done = goal(period_type='year', target_value=3000.0, current_value=3100.0, end_date='2026-12-21')
        self.assertEqual(self.check([done])['goals'][0]['weekly_hours'], 0.0)

    def test_paused_and_ended_season_goals_are_ignored(self):
        self.train()
        result = self.check([goal(is_active=False), goal(2, 'Old season', season_ended=True)])
        self.assertEqual(result['status'], 'no_estimate')

    def test_sparse_history_is_insufficient_evidence(self):
        self.assertEqual(self.check([goal()])['status'], 'insufficient_evidence')
        self.train(weeks=2)
        self.assertEqual(self.check([goal()])['status'], 'insufficient_evidence')

    def test_off_season_budget_uses_same_season_history(self):
        # Winter weeks are light (2 h), summer weeks heavy (6 h).
        monday = TODAY - timedelta(days=7 * 50)
        while monday < TODAY:
            winter = monday.month in (10, 11, 12, 1, 2, 3)
            add_week(self.conn, monday, ride_hours=1.0 if winter else 5.0, ride_km=25.0 if winter else 150.0)
            monday += timedelta(days=7)
        self.conn.commit()
        off = [10, 11, 12, 1, 2, 3]
        seasonal = self.check([goal()], off)
        self.assertEqual(seasonal['basis']['kind'], 'season')
        self.assertEqual(seasonal['actual_weekly_hours'], 2.0)
        self.assertEqual(seasonal['goals'][0]['weekly_hours'], 3.6)  # winter speed 25 km/h
        self.assertEqual(self.check([goal()], [])['basis']['kind'], 'recent')

    def test_time_budget_conflict_uses_the_plan_conflict_format(self):
        self.train()
        conflict = portfolio_conflict(self.check([goal(), anchor_lift()]))
        self.assertEqual(set(conflict), {'type', 'label', 'summary', 'goal_titles'})
        self.assertEqual(conflict['goal_titles'], ['Ride 90 km weekly'])
        conflicts = _build_goal_conflicts([], self.check([goal(), anchor_lift()]))
        self.assertEqual([item['type'] for item in conflicts], ['time_budget'])
        self.assertEqual(_build_goal_conflicts([], None), [])


class MonthlyReviewRhythmTests(unittest.TestCase):
    def test_first_review_of_the_month_is_the_week_ending_in_days_1_to_7(self):
        # Sunday 6 Sep 2026 ends the week of Monday 31 Aug.
        self.assertTrue(is_monthly_goal_review_week(date(2026, 8, 31)))
        self.assertTrue(is_monthly_goal_review_week(date(2026, 9, 1)))
        self.assertFalse(is_monthly_goal_review_week(date(2026, 9, 7)))
        self.assertFalse(is_monthly_goal_review_week(date(2026, 9, 21)))


class PortfolioApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'api.db'))
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(goals_router)
        app.include_router(weekly_router)
        self.client = TestClient(app)
        self.patches = [
            patch.object(goal_outcomes, 'get_cycling_power_trends_data', return_value={'monthly': [], 'efforts': [], 'coverage': {}}),
            patch.object(goal_outcomes, 'get_strength_overview_data', return_value={'sessions': []}),
            patch.object(goal_outcomes, '_health_history', return_value=[]),
            patch('backend.app.services.goal_suggestions.get_cycling_power_trends_data', return_value={'monthly': [], 'efforts': [], 'coverage': {}}),
        ]
        for item in self.patches:
            item.start()
        conn = db.get_db()
        set_setting_value(conn, 'athlete_profile', '{"off_season_months": []}')
        today = date.today()
        for index in range(1, 11):
            add_week(conn, today - timedelta(days=today.weekday() + 7 * index))
        conn.commit()
        conn.close()
        self.client.post('/goals', json={
            'title': 'Ride 300 km weekly', 'period_type': 'week', 'goal_family': 'accumulation',
            'metric_type': 'ride_km', 'target_value': 300,
        })
        self.client.post('/goals', json={
            'title': 'Lift 3x/week', 'period_type': 'week', 'goal_family': 'process',
            'metric_type': 'strength_sessions', 'target_value': 3, 'commitment': 'anchor',
        })

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def test_goal_review_includes_the_portfolio_block(self):
        portfolio = self.client.get('/goals/review').json()['portfolio']
        self.assertEqual(portfolio['status'], 'over_committed')
        self.assertEqual([item['title'] for item in portfolio['reduction_candidates']], ['Ride 300 km weekly'])

    def test_mcp_goal_review_carries_the_portfolio(self):
        result = call_mcp_tool('get_goal_review', {}, **build_mcp_router_dependencies())
        self.assertEqual(result['structuredContent']['portfolio']['status'], 'over_committed')

    def test_weekly_review_goals_section_only_in_first_review_of_month(self):
        first = self.client.get('/reviews/weekly/goals', params={'week_start': '2026-08-31'}).json()['goals']
        self.assertEqual(first['month'], '2026-09')
        self.assertEqual(first['link'], '/goals')
        self.assertEqual(first['portfolio']['status'], 'over_committed')
        self.assertGreaterEqual(first['attention_count'], 0)
        self.assertEqual(len(first['decisions']), first['attention_count'])
        self.assertIsNone(self.client.get('/reviews/weekly/goals', params={'week_start': '2026-09-14'}).json()['goals'])
        self.assertEqual(self.client.get('/reviews/weekly/goals', params={'week_start': '2026-09-15'}).status_code, 422)

    def test_goals_section_does_not_change_goals(self):
        before = self.client.get('/goals').json()
        self.client.get('/reviews/weekly/goals', params={'week_start': '2026-08-31'})
        self.assertEqual(self.client.get('/goals').json(), before)


if __name__ == '__main__':
    unittest.main()
