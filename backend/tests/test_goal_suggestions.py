import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.tests.test_quality_sessions import QualitySessionTests
from backend.app import db
from backend.app.repositories.settings import set_setting_value
from backend.app.routers.goals import router
from backend.app.services import goal_outcomes, goal_suggestions as suggestions
from backend.app.services.goals import create_goal_data

TODAY = date(2026, 9, 28)
YEAR_END = date(2026, 11, 15)
OFF_MONTHS = [10, 11, 12, 1, 2, 3]


class PinnedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 28)


def goal(**changes):
    return {'id': 1, 'title': 'Ride yearly', 'goal_family': 'accumulation', 'metric_type': 'ride_km',
            'period_type': 'year', 'target_value': 3500, 'activity_type': 'Ride', 'commitment': 'flexible',
            'lifecycle_status': 'completed', 'end_date': '2026-12-31',
            'history': {'stats': {'year_to_date': 4875, 'projected_total': 6300, 'projection_basis': 'seasonal'}}, **changes}


def candidate(metric='ride_km', period='week', key='season_template:test', **changes):
    return {'key': key, 'draft': {'metric_type': metric, 'period_type': period, 'activity_type': 'Ride', **changes}}


class SuggestionRuleTests(unittest.TestCase):
    def test_next_year_goal_waits_for_the_end_of_the_year(self):
        self.assertIsNone(suggestions.replace_completed(goal(), TODAY))
        self.assertIsNone(suggestions.replace_completed(goal(), date(2026, 10, 31)))
        self.assertIsNotNone(suggestions.replace_completed(goal(), date(2026, 11, 1)))

    def test_completed_year_uses_seasonal_projection(self):
        item = suggestions.replace_completed(goal(), YEAR_END)
        self.assertEqual(item['draft']['target_value'], 6600)
        self.assertEqual(item['draft']['start_date'], '2027-01-01')
        self.assertIn('Season-aware', item['evidence'][1])
        self.assertIsNone(suggestions.replace_completed(goal(commitment='anchor'), YEAR_END))
        self.assertIsNone(suggestions.replace_completed(goal(end_date='2025-12-31'), YEAR_END))
        self.assertIsNone(suggestions.replace_completed(goal(lifecycle_status='active'), YEAR_END))

    def test_profile_weakness_is_measured_benchmark_with_history_calibration(self):
        profile = {'category_levels': {
            'Sprint': {'level': 4, 'name': 'Strong', 'limiting_duration_seconds': 30},
            'Climb': {'level': 1, 'name': 'Aspiring', 'limiting_duration_seconds': 1200},
        }, 'monthly': [{'month': f'2026-{month:02}', 'efforts': [
            {'duration_seconds': 1200, 'watts': watts, 'date': f'2026-{month:02}-10'}
        ]} for month, watts in [(7, 225), (8, 230), (9, 230)]]}
        item = suggestions.profile_weakness(profile, TODAY)
        self.assertEqual(item['draft']['target_config'], {'duration_min': 20, 'target_watts': 240, 'measurement': 'power_stream'})
        self.assertIn('no dedicated FTP test', item['rationale'])
        profile['monthly'] = profile['monthly'][:1]
        self.assertIsNone(suggestions.profile_weakness(profile, TODAY))
        self.assertIsNone(suggestions.profile_weakness({'category_levels': {'Climb': None}}, TODAY))

    def test_max_three_and_metric_period_dedup_including_scheduled_goals(self):
        candidates = [candidate(), candidate(key='season_template:duplicate'), candidate('run_km'),
                      candidate('strength_sessions'), candidate('quality_sessions')]
        selected = suggestions.select_suggestions(candidates, [], {}, {}, TODAY)
        self.assertEqual(len(selected), 3)
        active = [goal(metric_type='ride_km', period_type='week', lifecycle_status='active'),
                  goal(metric_type='run_km', period_type='week', lifecycle_status='paused')]
        selected = suggestions.select_suggestions(candidates, active, {}, {}, TODAY)
        self.assertEqual([x['draft']['metric_type'] for x in selected], ['strength_sessions', 'quality_sessions'])

    def test_blocked_and_limited_modalities_filter_all_sources(self):
        candidates = [candidate(), candidate('quality_sessions'), candidate('benchmark_power'),
                      candidate('run_km', activity_type='Run')]
        for status in ['blocked', 'limited']:
            selected = suggestions.select_suggestions(candidates, [], {'modalities': {'ride': {'status': status}}}, {}, TODAY)
            self.assertEqual([x['draft']['metric_type'] for x in selected], ['run_km'])

    def test_dismissed_expiry_and_accepted_suppression(self):
        item = candidate()
        for decision in [{'decision': 'dismissed', 'until': '2026-09-29'}, {'decision': 'accepted', 'until': None}]:
            self.assertEqual(suggestions.select_suggestions([item], [], {}, {item['key']: decision}, TODAY), [])
        decision = {'decision': 'dismissed', 'until': TODAY.isoformat()}
        self.assertEqual(suggestions.select_suggestions([item], [], {}, {item['key']: decision}, TODAY), [item])


class GoalSuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.directory.name) / 'suggestions.db'))
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()
        set_setting_value(self.conn, 'athlete_profile', json.dumps({'off_season_months': OFF_MONTHS}))
        self.conn.commit()
        self.next_id = 0
        self.patches = [patch.object(suggestions, 'datetime', PinnedDatetime),
                        patch.object(goal_outcomes, '_health_history', return_value=[])]
        for item in self.patches:
            item.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        for item in self.patches:
            item.stop()
        self.conn.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def add(self, day, activity='Ride', distance=30, intent=None):
        self.next_id += 1
        self.conn.execute('INSERT INTO activities (id, date, type, name, distance_km, duration_min, workout_intent) VALUES (?, ?, ?, ?, ?, 60, ?)',
                          (str(self.next_id), day.isoformat(), activity, 'Fixture', distance, intent))
        self.conn.commit()

    def winter(self):
        for week in range(13):
            self.add(date(2026, 1, 5) + timedelta(weeks=week), distance=100, intent='tempo')
        for week in range(12):
            self.add(date(2026, 7, 6) + timedelta(weeks=week), distance=220)

    def test_quality_from_each_eligible_verdict_and_anchor_protection(self):
        self.winter()
        for verdict in suggestions.QUALITY_VERDICTS:
            item = suggestions.plateau_to_quality(self.conn, goal(review={'verdict': verdict}), TODAY, OFF_MONTHS)
            self.assertEqual(item['draft']['metric_type'], 'quality_sessions')
            self.assertEqual(item['draft']['target_value'], 2)
            self.assertEqual(item['draft']['start_date'], '2026-10-01')
            self.assertIn('Same-season', item['evidence'][1])
        self.assertIsNone(suggestions.plateau_to_quality(self.conn, goal(commitment='anchor', review={'verdict': 'too_easy'}), TODAY, OFF_MONTHS))
        self.assertIsNone(suggestions.plateau_to_quality(self.conn, goal(metric_type='run_km', review={'verdict': 'too_easy'}), TODAY, OFF_MONTHS))

    def test_season_template_uses_winter_not_summer_and_disables_cleanly(self):
        self.winter()
        items = suggestions.season_template(self.conn, TODAY, OFF_MONTHS)
        ride = next(x for x in items if x['draft']['metric_type'] == 'ride_km')
        self.assertEqual(ride['draft']['target_value'], 100)
        self.assertEqual(ride['draft']['season_end'], '2027-03-31')
        self.assertEqual(suggestions.season_template(self.conn, date(2026, 8, 1), OFF_MONTHS), [])
        self.assertEqual(suggestions.season_template(self.conn, TODAY, []), [])

    def test_season_without_same_season_history_is_silent(self):
        for week in range(12):
            self.add(date(2026, 7, 6) + timedelta(weeks=week), distance=220)
        self.assertEqual(suggestions.season_template(self.conn, TODAY, OFF_MONTHS), [])

    def test_neglected_modality_needs_regular_use_then_eight_weeks(self):
        for week in range(8):
            self.add(date(2026, 5, 4) + timedelta(weeks=week), 'Run', 5)
        items = suggestions.neglected_modality(self.conn, TODAY)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['draft']['target_value'], 1)
        self.assertEqual(items[0]['draft']['activity_type'], 'Run')
        self.add(TODAY - timedelta(weeks=7), 'Run', 5)
        self.assertEqual(suggestions.neglected_modality(self.conn, TODAY), [])

    def test_neglected_indoor_cycling_counts_regular_virtual_rides(self):
        for week in range(8):
            self.add(date(2026, 5, 4) + timedelta(weeks=week), 'VirtualRide', 30)
        items = suggestions.neglected_modality(self.conn, TODAY)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['draft']['activity_type'], 'Ride')

    def test_mcp_suggestions_are_read_only_and_match_api(self):
        from backend.app.adapters.mcp import build_mcp_router_dependencies
        from backend.app.services.mcp import call_mcp_tool
        self.winter()
        result = call_mcp_tool('get_goal_suggestions', {}, **build_mcp_router_dependencies())
        self.assertEqual(result['structuredContent']['suggestions'], self.client.get('/goals/suggestions').json()['suggestions'])

    def test_active_anchor_is_not_converted_and_existing_metric_is_not_duplicated(self):
        self.winter()
        create_goal_data(self.conn, title='Cycling standard', metric_type='ride_km',
                         goal_family='accumulation', period_type='week', target_value=50, commitment='anchor')
        items = suggestions.build_goal_suggestions(self.conn, TODAY)['suggestions']
        self.assertFalse(any(item['source'] == 'plateau_to_quality' for item in items))
        self.assertFalse(any(item['draft']['metric_type'] == 'ride_km' for item in items))

    def test_one_old_activity_does_not_imply_neglect(self):
        self.add(date(2026, 5, 4), 'Run', 5)
        self.assertEqual(suggestions.neglected_modality(self.conn, TODAY), [])

    def test_api_read_only_dismiss_persistence_expiry_and_restrictions(self):
        self.winter()
        before = self.conn.execute('SELECT COUNT(*) FROM goals').fetchone()[0]
        response = self.client.get('/goals/suggestions')
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()['suggestions']
        self.assertTrue(items)
        key = items[0]['key']
        response = self.client.post(f'/goals/suggestions/{key}/decision', json={'decision': 'dismissed', 'until': '2026-10-26'})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn(key, [x['key'] for x in self.client.get('/goals/suggestions').json()['suggestions']])
        fresh = db.get_db()
        self.assertEqual(fresh.execute('SELECT decision FROM goal_suggestion_decisions').fetchone()[0], 'dismissed')
        fresh.close()
        self.conn.execute('UPDATE goal_suggestion_decisions SET until = ?', (TODAY.isoformat(),))
        self.conn.commit()
        self.assertIn(key, [x['key'] for x in self.client.get('/goals/suggestions').json()['suggestions']])
        set_setting_value(self.conn, 'modality_restrictions', json.dumps({'modalities': {'ride': {'status': 'blocked'}}}))
        self.conn.commit()
        self.assertEqual(self.client.get('/goals/suggestions').json()['suggestions'], [])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM goals').fetchone()[0], before)

    def test_decision_validation_and_acceptance(self):
        key = 'plateau_to_quality:123'
        for payload in [{'decision': 'unknown'}, {'decision': 'dismissed', 'until': 'bad'},
                        {'decision': 'dismissed', 'until': TODAY.isoformat()}, {'decision': 'accepted', 'until': '2026-10-01'}]:
            self.assertEqual(self.client.post(f'/goals/suggestions/{key}/decision', json=payload).status_code, 400)
        response = self.client.post(f'/goals/suggestions/{key}/decision', json={'decision': 'accepted'})
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['until'])

    def test_generated_drafts_pass_goal_validation_without_saving_real_data(self):
        self.winter()
        for item in suggestions.build_goal_suggestions(self.conn, TODAY)['suggestions']:
            saved = create_goal_data(self.conn, **item['draft'])
            row = self.conn.execute('SELECT metric_type FROM goals WHERE id = ?', (saved['id'],)).fetchone()
            self.assertEqual(row['metric_type'], item['draft']['metric_type'])


if __name__ == '__main__':
    unittest.main()
