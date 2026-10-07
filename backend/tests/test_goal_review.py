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
from backend.app.repositories.settings import set_setting_value
from backend.app.services.goal_history import _recurring_history, _yearly_history, recurring_period_windows
from backend.app.services.goal_review import build_goal_verdict, calibrated_target
from backend.app.services.mcp import call_mcp_tool

TODAY = date(2026, 9, 28)


def goal(**changes):
    return {
        'id': 1,
        'title': 'Ride 100km weekly',
        'goal_family': 'accumulation',
        'metric_type': 'ride_km',
        'period_type': 'week',
        'target_value': 100.0,
        'unit': 'km',
        'commitment': 'flexible',
        'purpose': None,
        'review_on': None,
        'season_end': None,
        'season_ended': False,
        'created_at': '2026-01-01 00:00:00',
        **changes,
    }


def weekly(item, values):
    windows, _ = recurring_period_windows('week', len(values), TODAY)
    lookup = {start.isoformat(): value for (start, _end), value in zip(windows, values)}
    return _recurring_history(item, lambda start, end: lookup.get(start, 0.0), len(values), TODAY, None)


def yearly(item, per_day):
    """per_day(day) -> value logged that day."""
    def value_fn(start, end):
        day, last, total = date.fromisoformat(start), date.fromisoformat(end), 0.0
        while day <= last:
            total += per_day(day)
            day += timedelta(days=1)
        return total
    return _yearly_history(item, value_fn, TODAY, None)


def outcomes(*signals):
    return {'signals': [
        {'key': key, 'label': key.replace('_', ' '), 'trend': trend, 'change_pct': change}
        for key, trend, change in signals
    ]}


def verdict(item, values=None, *, history=None, linked=None, others=None, costs=None, decision=None):
    item = {**item, 'history': history or weekly(item, values), 'outcomes': linked or outcomes()}
    return build_goal_verdict(item, others=others or [], costs=costs or [], decision=decision, today=TODAY)


class VerdictTests(unittest.TestCase):
    def test_too_easy_raises_to_calibrated_target(self):
        review = verdict(goal(), [180, 170, 200, 190, 160, 210, 185, 175, 195, 90, 205, 180])
        self.assertEqual(review['verdict'], 'too_easy')
        self.assertTrue(review['needs_attention'])
        raise_action = review['actions'][0]
        self.assertEqual(raise_action['type'], 'raise_target')
        self.assertEqual(raise_action['body'], {'target_value': 210.0})
        self.assertIn('set_season', [action['type'] for action in review['actions']])

    def test_out_of_reach_recurring(self):
        review = verdict(goal(title='Lift 4x', metric_type='strength_sessions', target_value=4, unit='sessions'),
                         [1, 2, 1, 1, 2, 4, 1, 2, 1, 2, 1, 2])
        self.assertEqual(review['verdict'], 'out_of_reach')
        self.assertEqual(review['actions'][0]['body'], {'target_value': 2.0})

    def test_inconsistent_between_out_of_reach_and_on_track(self):
        review = verdict(goal(), [120, 80, 110, 90, 70, 130, 60, 105, 95, 115, 85, 100])
        self.assertEqual(review['verdict'], 'inconsistent')

    def test_inconsistent_never_offers_a_token_target(self):
        review = verdict(goal(), [120, 0, 0, 110, 0, 0, 130, 0, 0, 105, 0, 0])
        self.assertEqual(review['verdict'], 'inconsistent')
        self.assertNotIn('lower_target', [action['type'] for action in review['actions']])

    def test_future_review_date_quiets_the_card(self):
        review = verdict(goal(review_on='2026-10-26'), [120, 80, 110, 90, 70, 130, 60, 105, 95, 115, 85, 100])
        self.assertEqual(review['verdict'], 'inconsistent')
        self.assertFalse(review['needs_attention'])
        self.assertEqual(review['snoozed_until'], '2026-10-26')

    def test_productive_when_outcome_improves(self):
        linked = outcomes(('cycling_power_20m', 'improving', 4.0))
        review = verdict(goal(target_value=150), [160, 150, 170, 140, 155, 165, 150, 160, 158, 152, 149, 162], linked=linked)
        self.assertEqual(review['verdict'], 'productive')
        self.assertEqual(review['confidence'], 'high')

    def test_plateaued_when_hit_but_outcome_flat(self):
        linked = outcomes(('cycling_power_20m', 'flat', 0.5))
        review = verdict(goal(target_value=150), [160, 150, 170, 140, 155, 165, 150, 160, 158, 152, 149, 162], linked=linked)
        self.assertEqual(review['verdict'], 'plateaued')

    def test_holding_counts_as_productive_for_maintenance_purpose(self):
        linked = outcomes(('strength_maintenance', 'flat', 0.0))
        item = goal(title='Lift 2x', metric_type='strength_sessions', target_value=2, unit='sessions', purpose='Keep my strength')
        review = verdict(item, [2, 2, 3, 2, 2, 2, 1, 2, 2, 3, 2, 2], linked=linked)
        self.assertEqual(review['verdict'], 'productive')

    def test_unproven_when_outcome_data_is_missing(self):
        linked = outcomes(('cycling_power_20m', 'insufficient', None))
        review = verdict(goal(target_value=150), [160, 150, 170, 140, 155, 165, 150, 160, 158, 152, 149, 162], linked=linked)
        self.assertEqual(review['verdict'], 'on_track_unproven')
        self.assertFalse(review['needs_attention'])

    def test_too_few_periods(self):
        self.assertEqual(verdict(goal(), [150, 160])['verdict'], 'insufficient_evidence')

    def test_crowding_out_other_goal(self):
        lift = goal(id=2, title='Lift 3x', metric_type='strength_sessions', target_value=3, unit='sessions')
        lift['history'] = weekly(lift, [3, 3, 3, 3, 3, 3, 1, 2, 1, 2, 1, 1])
        ride = goal(target_value=120)
        review = verdict(ride, [110, 115, 120, 125, 130, 140, 150, 170, 180, 200, 210, 230], others=[lift])
        self.assertEqual(review['verdict'], 'crowding_out')
        self.assertTrue(any('Lift 3x' in line for line in review['evidence']))

    def test_crowding_out_from_worsening_costs(self):
        costs = [{'key': 'hrv', 'label': 'HRV', 'trend': 'declining', 'stale': False, 'change_pct': -9.0}]
        review = verdict(goal(target_value=120), [110, 115, 120, 125, 130, 140, 150, 170, 180, 200, 210, 230], costs=costs)
        self.assertEqual(review['verdict'], 'crowding_out')

    def test_stale_costs_are_ignored(self):
        costs = [{'key': 'hrv', 'label': 'HRV', 'trend': 'declining', 'stale': True, 'change_pct': -9.0}]
        review = verdict(goal(target_value=120), [110, 115, 120, 125, 130, 140, 150, 170, 180, 200, 210, 230], costs=costs)
        self.assertNotEqual(review['verdict'], 'crowding_out')
        self.assertFalse(any('Recovery cost' in line for line in review['evidence']))

    def test_review_due_after_review_date(self):
        review = verdict(goal(review_on='2026-09-01'), [180] * 12)
        self.assertEqual(review['verdict'], 'review_due')
        self.assertEqual(review['actions'][0]['body'], {'review_on': None, 'season_end': None})

    def test_ended_season_is_review_due(self):
        self.assertEqual(verdict(goal(season_end='2026-09-01', season_ended=True), [150] * 12)['verdict'], 'review_due')

    def test_benchmark_goals_are_not_applicable(self):
        item = goal(goal_family='benchmark', metric_type='benchmark_power')
        review = verdict(item, history={'available': False, 'reason': 'benchmark goals use benchmark history'})
        self.assertEqual(review['verdict'], 'not_applicable')


class NewGoalTests(unittest.TestCase):
    def quality(self, created_at):
        return goal(title='1 quality ride per week', metric_type='quality_sessions', target_value=1.0, created_at=created_at)

    def test_brand_new_goal_is_not_called_out_of_reach_from_pre_goal_weeks(self):
        result = verdict(self.quality('2026-09-26 10:00:00'), [0] * 12)
        self.assertEqual(result['verdict'], 'insufficient_evidence')
        self.assertFalse(result['needs_attention'])
        self.assertIn('Just started', ' '.join(result['evidence']))

    def test_low_hit_rate_becomes_inconsistent_only_after_a_few_own_weeks(self):
        values = [0] * 6 + [1, 0, 1, 0, 0, 1]
        self.assertEqual(verdict(self.quality('2026-09-12 10:00:00'), values)['verdict'], 'insufficient_evidence')
        self.assertEqual(verdict(self.quality('2026-08-15 10:00:00'), values)['verdict'], 'inconsistent')

    def test_out_of_reach_needs_eight_weeks_of_the_goals_own_history(self):
        self.assertEqual(verdict(self.quality('2026-08-10 10:00:00'), [0] * 12)['verdict'], 'insufficient_evidence')
        self.assertEqual(verdict(self.quality('2026-07-20 10:00:00'), [0] * 12)['verdict'], 'out_of_reach')


class YearlyVerdictTests(unittest.TestCase):
    def test_done_only_completes_until_the_year_is_nearly_over(self):
        item = goal(title='Ride 3500km in 2026', period_type='year', target_value=3500)
        review = verdict(item, history=yearly(item, lambda day: 18.0))
        self.assertEqual(review['verdict'], 'done')
        self.assertEqual([action['type'] for action in review['actions']], ['complete'])

    def test_done_offers_completion_and_next_year_draft(self):
        item = goal(title='Ride 3500km in 2026', period_type='year', target_value=3500)
        review = build_goal_verdict(
            {**item, 'history': yearly(item, lambda day: 18.0), 'outcomes': outcomes()},
            others=[], costs=[], today=date(2026, 11, 15),
        )
        self.assertEqual(review['verdict'], 'done')
        create_next, complete = review['actions']
        self.assertEqual(complete['body']['status'], 'completed')
        self.assertEqual(create_next['body']['start_date'], '2027-01-01')
        self.assertTrue(create_next['body']['title'].startswith('Ride '))
        self.assertTrue(create_next['body']['title'].endswith(' km in 2027'))

    def test_out_of_reach_when_needed_pace_dwarfs_best_weeks(self):
        item = goal(title='Run 1000km in 2026', metric_type='run_km', period_type='year', target_value=1000)
        review = verdict(item, history=yearly(item, lambda day: 1.0 if day.month <= 4 else 0.25))
        self.assertEqual(review['verdict'], 'out_of_reach')
        self.assertEqual([action['type'] for action in review['actions']], ['lower_target', 'retire'])

    def test_anchor_yearly_goal_can_still_be_done(self):
        item = goal(period_type='year', target_value=1000, commitment='anchor')
        self.assertEqual(verdict(item, history=yearly(item, lambda day: 10.0))['verdict'], 'done')


class AnchorVerdictTests(unittest.TestCase):
    def lift(self, **changes):
        return goal(title='Lift three times per week', goal_family='process', metric_type='strength_sessions',
                    target_value=3, unit='sessions', commitment='anchor', purpose='Maintain muscle alongside heavy cardio',
                    **changes)

    def test_anchor_is_never_lowered_or_retired(self):
        linked = outcomes(('strength_maintenance', 'flat', 0.0))
        review = verdict(self.lift(), [2, 0, 3, 2, 3, 1, 2, 0, 4, 2, 3, 3], linked=linked)
        self.assertEqual(review['verdict'], 'anchor_under_pressure')
        self.assertEqual(review['purpose_status'], 'served')
        self.assertFalse(review['needs_attention'])
        action_types = {action['type'] for action in review['actions']}
        self.assertTrue(action_types.isdisjoint({'lower_target', 'retire', 'pause'}))
        self.assertIn('plan_support', action_types)
        self.assertIn('purpose is served', review['headline'])

    def test_anchor_steady_even_when_too_easy(self):
        review = verdict(self.lift(), [4, 4, 5, 4, 4, 5, 4, 4, 4, 5, 4, 4], linked=outcomes(('strength_maintenance', 'improving', 4.0)))
        self.assertEqual(review['verdict'], 'anchor_steady')
        self.assertNotIn('raise_target', {action['type'] for action in review['actions']})

    def test_anchor_purpose_at_risk_when_outcome_declines(self):
        review = verdict(self.lift(), [2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1], linked=outcomes(('strength_maintenance', 'declining', -6.0)))
        self.assertEqual(review['purpose_status'], 'at_risk')

    def test_anchor_with_unknown_outcome(self):
        review = verdict(self.lift(), [3] * 12, linked=outcomes(('strength_maintenance', 'insufficient', None)))
        self.assertEqual(review['purpose_status'], 'unknown')


OFF_SEASON = [10, 11, 12, 1, 2, 3]


def seasonal_weekly(item, summer_value, winter_value):
    """52 weeks back from TODAY: winter weeks log winter_value, the rest summer_value."""
    def value_fn(start, end):
        return winter_value if date.fromisoformat(start).month in OFF_SEASON else summer_value
    return _recurring_history(item, value_fn, 12, TODAY, date(2025, 12, 29), OFF_SEASON)


class SeasonTests(unittest.TestCase):
    def seasonal(self, item, history, linked=None):
        item = {**item, 'history': history, 'outcomes': linked or outcomes()}
        return build_goal_verdict(item, others=[], costs=[], today=TODAY, off_season_months=OFF_SEASON)

    def test_summer_history_is_not_used_to_judge_the_winter(self):
        history = seasonal_weekly(goal(), summer_value=180, winter_value=105)
        self.assertTrue(history['season']['shift'])
        self.assertEqual(history['season']['reference']['median'], 105)

        review = self.seasonal(goal(), history)
        self.assertNotEqual(review['verdict'], 'too_easy')
        self.assertNotIn('raise_target', [action['type'] for action in review['actions']])
        self.assertTrue(any('last off season' in line for line in review['evidence']))

    def test_winter_reference_can_still_say_too_easy(self):
        review = self.seasonal(goal(target_value=50), seasonal_weekly(goal(target_value=50), 180, 110))
        self.assertEqual(review['verdict'], 'too_easy')
        # Calibrated from the winter reference (p75 110 km), not the summer.
        self.assertEqual(review['actions'][0]['body'], {'target_value': 120.0})

    def test_no_reference_season_is_season_change(self):
        item = goal()
        history = _recurring_history(item, lambda start, end: 180.0, 12, TODAY, date(2026, 6, 1), OFF_SEASON)
        self.assertIsNone(history['season']['reference'])
        review = self.seasonal(item, history)
        self.assertEqual(review['verdict'], 'season_change')
        self.assertFalse(review['needs_attention'])
        self.assertEqual(review['actions'][0]['type'], 'set_review')

    def test_strength_goals_ignore_seasons(self):
        item = goal(metric_type='strength_sessions', target_value=3, unit='sessions')
        history = _recurring_history(item, lambda start, end: 3.0, 12, TODAY, None, OFF_SEASON)
        self.assertIsNone(history['season'])

    def test_season_action_uses_profile_months(self):
        item = goal(target_value=50)
        review = build_goal_verdict(
            {**item, 'history': weekly(item, [180] * 12), 'outcomes': outcomes()},
            others=[], costs=[], today=TODAY, off_season_months=OFF_SEASON,
        )
        season = next(action for action in review['actions'] if action['type'] == 'set_season')
        self.assertEqual(season['body'], {'season_end': '2027-03-31'})
        self.assertIn('31 Mar', season['label'])

    def test_yearly_projection_uses_each_seasons_pace(self):
        item = goal(title='Ride 3500km in 2026', period_type='year', target_value=3500)

        def value_fn(start, end):
            day, last, total = date.fromisoformat(start), date.fromisoformat(end), 0.0
            while day <= last:
                total += 15.0 if day.month in OFF_SEASON else 30.0
                day += timedelta(days=1)
            return total

        seasonal = _yearly_history(item, value_fn, TODAY, date(2026, 1, 1), OFF_SEASON)
        naive = _yearly_history(item, value_fn, TODAY, date(2026, 1, 1), None)
        self.assertEqual(seasonal['stats']['projection_basis'], 'seasonal')
        # Oct–Dec at the winter pace (15/day) instead of the summer pace (30/day).
        self.assertLess(seasonal['stats']['projected_total'], naive['stats']['projected_total'] - 1000)


class SnoozeTests(unittest.TestCase):
    def test_snooze_hides_same_verdict_until_expiry(self):
        values = [180, 170, 200, 190, 160, 210, 185, 175, 195, 90, 205, 180]
        snoozed = {'verdict': 'too_easy', 'until': '2026-10-20', 'decision': 'snoozed'}
        review = verdict(goal(), values, decision=snoozed)
        self.assertFalse(review['needs_attention'])
        self.assertEqual(review['snoozed_until'], '2026-10-20')

        expired = {**snoozed, 'until': '2026-09-20'}
        self.assertTrue(verdict(goal(), values, decision=expired)['needs_attention'])

    def test_snooze_does_not_hide_a_new_verdict(self):
        snoozed = {'verdict': 'too_easy', 'until': '2026-12-01', 'decision': 'snoozed'}
        review = verdict(goal(), [1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1], decision=snoozed)
        self.assertEqual(review['verdict'], 'out_of_reach')
        self.assertTrue(review['needs_attention'])


class CalibrationTests(unittest.TestCase):
    def test_round_targets(self):
        self.assertEqual(calibrated_target('ride_km', 218.1), 220.0)
        self.assertEqual(calibrated_target('ride_km', 7336), 7300.0)
        self.assertEqual(calibrated_target('run_km', 23), 25.0)
        self.assertEqual(calibrated_target('zone2_hours', 3.3), 3.5)
        self.assertEqual(calibrated_target('strength_sessions', 2.1), 3.0)
        self.assertEqual(calibrated_target('strength_sessions', 2.0), 2.0)
        self.assertEqual(calibrated_target('strength_sessions', 0), 1.0)


class GoalReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'review.db'))
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.patches = [
            patch.object(goal_outcomes, 'get_cycling_power_trends_data', return_value={'monthly': [], 'efforts': [], 'coverage': {}}),
            patch.object(goal_outcomes, 'get_strength_overview_data', return_value={'sessions': []}),
            patch.object(goal_outcomes, '_health_history', return_value=[]),
        ]
        for item in self.patches:
            item.start()
        conn = db.get_db()
        # These tests run on the real calendar; seasons get their own date-pinned tests.
        set_setting_value(conn, 'athlete_profile', '{"off_season_months": []}')
        start = date.today() - timedelta(days=date.today().weekday() + 7 * 12)
        conn.executemany(
            "INSERT INTO activities (id, date, type, name, distance_km, duration_min) VALUES (?, ?, 'Ride', 'Ride', ?, 90)",
            [(str(week), (start + timedelta(days=7 * week + 2)).isoformat(), 180.0) for week in range(12)],
        )
        conn.commit()
        conn.close()
        self.goal_id = self.client.post('/goals', json={
            'title': 'Ride 100km weekly', 'period_type': 'week', 'goal_family': 'accumulation',
            'metric_type': 'ride_km', 'target_value': 100,
        }).json()['id']

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def test_review_lists_active_goals_and_decisions_snooze(self):
        body = self.client.get('/goals/review').json()
        self.assertEqual(body['attention_count'], 1)
        self.assertEqual(body['goals'][0]['review']['verdict'], 'too_easy')

        response = self.client.post(f'/goals/{self.goal_id}/review-decision', json={'verdict': 'too_easy', 'decision': 'snoozed'})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['until'], (date.today() + timedelta(days=28)).isoformat())

        body = self.client.get('/goals/review').json()
        self.assertEqual(body['attention_count'], 0)
        self.assertEqual(body['goals'][0]['review']['last_decision']['decision'], 'snoozed')

    def test_review_excludes_inactive_goals(self):
        self.client.post(f'/goals/{self.goal_id}/status', json={'status': 'paused'})
        self.assertEqual(self.client.get('/goals/review').json()['goals'], [])

    def test_decision_validation(self):
        self.assertEqual(self.client.post(f'/goals/{self.goal_id}/review-decision', json={'verdict': 'meh', 'decision': 'snoozed'}).status_code, 400)
        self.assertEqual(self.client.post(f'/goals/{self.goal_id}/review-decision', json={'verdict': 'too_easy', 'decision': 'ignored'}).status_code, 400)
        self.assertEqual(self.client.post('/goals/999/review-decision', json={'verdict': 'too_easy', 'decision': 'kept'}).status_code, 404)

    def test_paused_goal_scheduled_to_start_becomes_review_due(self):
        next_id = self.client.post('/goals', json={
            'title': 'Ride 7700 km in 2027', 'period_type': 'year', 'goal_family': 'accumulation',
            'metric_type': 'ride_km', 'target_value': 7700, 'is_active': False,
            'review_on': (date.today() + timedelta(days=30)).isoformat(),
        }).json()['id']
        ids = [item['goal_id'] for item in self.client.get('/goals/review').json()['goals']]
        self.assertNotIn(next_id, ids)

        self.client.patch(f'/goals/{next_id}', json={'review_on': date.today().isoformat()})
        item = next(item for item in self.client.get('/goals/review').json()['goals'] if item['goal_id'] == next_id)
        self.assertEqual(item['review']['verdict'], 'review_due')
        start = item['review']['actions'][0]
        self.assertEqual(start['body']['status'], 'active')

        started = self.client.post(start['path'], json=start['body']).json()
        self.assertEqual(started['lifecycle_status'], 'active')
        self.assertIsNone(started['review_on'])

    def test_mcp_review_tool(self):
        result = call_mcp_tool('get_goal_review', {}, **build_mcp_router_dependencies())
        goal_review = result['structuredContent']['goals'][0]
        self.assertEqual(goal_review['verdict'], 'too_easy')
        self.assertIn('raise_target', [action['type'] for action in goal_review['actions']])


if __name__ == '__main__':
    unittest.main()
