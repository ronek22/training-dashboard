import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.routers.coaching import router
from backend.app.services.coaches import build_team_coaching
from backend.app.services.coaches import running, strength
from backend.app.services.coaches.head import coordinate
from backend.app.services.coaches.presentation import session_action
from backend.app.services.weekly_reviews import review_context


def activity(identifier, day, sport='Run', intent='easy', duration=30, distance=5):
    return {'id': identifier, 'date': day, 'type': sport, 'workout_intent': intent,
            'duration_min': duration, 'distance_km': distance}


class SpecialistTests(unittest.TestCase):
    def test_adjusted_session_does_not_show_original_prescription(self):
        session = {'date': '2026-09-12', 'title': 'Long ride', 'session_type': 'Ride',
                   'suggestion': 'lighten', 'target_duration_min': 180, 'target_distance_km': 70}
        result = session_action(session)
        self.assertIsNone(result['duration_min'])
        self.assertIsNone(result['distance_km'])
        self.assertIn('easy', result['instruction'])
        self.assertEqual(session_action({**session, 'suggestion': 'keep'})['duration_min'], 180)

    def test_takeaway_does_not_call_a_single_long_run_light(self):
        start = date(2026, 9, 7)
        report = running.analyze([activity('long', start.isoformat(), intent='long', duration=240, distance=40)], start, start)
        head = coordinate({'running': report})
        self.assertNotIn('light', report['takeaway'])
        self.assertNotIn('planned', head['headline'])

    def test_matching_weekdays_not_full_prior_weeks(self):
        start = date(2026, 9, 7)
        rows = [activity('current', '2026-09-07', duration=60)]
        for offset in range(1, 5):
            monday = start - timedelta(weeks=offset)
            rows += [activity(f'mon-{offset}', monday.isoformat()),
                     activity(f'sun-{offset}', (monday + timedelta(days=6)).isoformat(), duration=300)]
        report = running.analyze(rows, start, start + timedelta(days=1))
        self.assertEqual(report['baseline']['matching_weekday_duration_min'], 30)
        self.assertEqual(report['baseline']['change_pct'], 100)
        self.assertEqual(report['status'], 'review')

    def test_missing_measurements_not_zero_or_easy(self):
        start = date(2026, 9, 7)
        result = running.analyze([activity('unknown', start.isoformat(), intent=None, duration=None, distance=None)], start, start)
        self.assertIsNone(result['totals']['duration_min']['value'])
        self.assertIsNone(result['totals']['distance_km']['value'])
        self.assertEqual(result['totals']['easy_sessions'], 0)
        self.assertEqual(result['totals']['unknown_intent_sessions'], 1)
        self.assertIsNone(result['baseline']['change_pct'])
        self.assertEqual(result['data_quality'], 'partial')

    def test_strength_uses_work_sets_not_warmups_and_identifies_lower_body(self):
        start = date(2026, 9, 7)
        rows = [activity('lift', start.isoformat(), 'WeightTraining', None),
                activity('generic', start.isoformat(), 'WeightTraining', None)]
        detail = [{'matched_activity': {'id': 'lift'}, 'exercises': [
            {'work_set_count': 3, 'warmup_set_count': 2, 'body_part': 'lower'},
            {'work_set_count': 4, 'warmup_set_count': 1, 'body_part': 'push'},
        ]}]
        result = strength.analyze(rows, start, start, detail)
        self.assertEqual(result['totals']['work_sets'], 7)
        self.assertEqual(result['totals']['lower_body_work_sets'], 3)
        self.assertEqual(result['totals']['demanding_sessions'], 1)
        self.assertEqual(result['data_quality'], 'partial')
        self.assertTrue(result['evidence'][0]['demanding'])

    def test_upper_only_strength_is_not_a_lower_body_conflict(self):
        start = date(2026, 9, 7)
        result = strength.analyze([activity('upper', start.isoformat(), 'WeightTraining', 'strength_upper')], start, start)
        self.assertFalse(result['evidence'][0]['demanding'])


class TeamCoachingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.temp.name) / 'team.db'))
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.conn.close()
        self.db_patch.stop()
        self.temp.cleanup()

    def insert(self, identifier, day, sport='Run', intent='easy', duration=30):
        self.conn.execute('INSERT INTO activities (id,date,type,workout_intent,duration_min) VALUES (?,?,?,?,?)',
                          (identifier, day, sport, intent, duration))
        self.conn.commit()

    def test_empty_week_has_all_specialists_without_training_claims(self):
        report = build_team_coaching(self.conn, today=date(2026, 9, 7))
        self.assertEqual(set(report['specialists']), {'running', 'cycling', 'strength'})
        self.assertEqual(report['head_coach']['status'], 'insufficient_data')
        self.assertTrue(all(item['status'] == 'no_data' for item in report['specialists'].values()))
        self.assertEqual(report['window']['week_start'], '2026-09-07')

    def test_complete_range_future_exclusion_and_indoor_cycling(self):
        for index in range(18):
            self.insert(f'run-{index}', '2026-09-07')
        self.insert('ride', '2026-09-08', 'VirtualRide')
        self.insert('future', '2026-09-10')
        self.insert('old', '2026-08-01')
        result = build_team_coaching(self.conn, today=date(2026, 9, 9))
        self.assertEqual(result['specialists']['running']['totals']['sessions'], 18)
        self.assertEqual(result['specialists']['cycling']['totals']['indoor_sessions'], 1)
        self.assertEqual(result['window']['through_date'], '2026-09-09')

    def test_head_arbitrates_conflicts_and_recovery(self):
        self.insert('run', '2026-09-07', intent='interval')
        self.insert('ride', '2026-09-08', 'Ride', 'tempo')
        self.insert('lift', '2026-09-08', 'WeightTraining', 'strength_lower')
        context = {'daily_recommendation': {'status': 'recover', 'action': 'Recovery is the priority.'},
                   'modality_restrictions': {'active': [{'modality': 'run', 'status': 'blocked'}]}}
        result = build_team_coaching(self.conn, today=date(2026, 9, 9), context=context)
        head = result['head_coach']
        self.assertEqual(head['status'], 'review')
        self.assertEqual(head['priorities'][0], 'Recovery is the priority.')
        self.assertEqual(len(head['conflicts']), 3)
        self.assertEqual({s['activity_id'] for c in head['conflicts'] for s in c['sessions']}, {'run', 'ride', 'lift'})

    def test_easy_sessions_do_not_trigger_demanding_conflicts(self):
        self.insert('run', '2026-09-07')
        self.insert('ride', '2026-09-08', 'Ride')
        report = build_team_coaching(self.conn, today=date(2026, 9, 9))
        self.assertEqual(report['head_coach']['conflicts'], [])

    def test_historical_context_never_uses_current_recovery(self):
        self.insert('past', '2026-08-25')
        self.insert('later', '2026-09-07')
        report = build_team_coaching(self.conn, week_start=date(2026, 8, 24), today=date(2026, 9, 9),
            context={'daily_recommendation': {'status': 'recover', 'action': 'Current illness'}})
        self.assertFalse(report['head_coach']['context_used']['recovery'])
        self.assertEqual(report['specialists']['running']['totals']['sessions'], 1)
        context = review_context(self.conn, date(2026, 8, 24))
        self.assertEqual(context['team_coaching']['window']['week_end'], '2026-08-30')
        self.assertEqual(context['team_coaching']['specialists']['running']['evidence'][0]['activity_id'], 'past')

    def test_http_additive_contract_and_no_plan_or_review_writes(self):
        today = datetime.now(ZoneInfo('Europe/Warsaw')).date()
        for index in range(18):
            self.insert(f'run-{index}', today.isoformat())
        self.conn.execute("INSERT INTO weekly_plans (week_start,title,days_json) VALUES ('2026-01-05','Preserved plan','[]')")
        self.conn.execute("INSERT INTO weekly_reviews (week_start,improved,missed,proposed_change) VALUES ('2026-01-05','Preserved','Preserved','Preserved')")
        self.conn.commit()
        before = {table: [tuple(row) for row in self.conn.execute(f'SELECT * FROM {table}')] for table in ('weekly_plans', 'plan_revisions', 'weekly_reviews')}
        response = self.client.get('/coaching/weekly?recent_activity_limit=1&include_proposed_adjustment=false')
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertIn('recommendation', result)
        self.assertIn('execution_assessment', result)
        self.assertIsNone(result['proposed_adjustment'])
        self.assertEqual(result['team_coaching']['specialists']['running']['totals']['sessions'], 18)
        for table, rows in before.items():
            self.assertEqual(rows, [tuple(row) for row in self.conn.execute(f'SELECT * FROM {table}')])

    def test_mcp_uses_same_weekly_team_contract(self):
        from backend.app.adapters.mcp import build_mcp_router_dependencies
        from backend.app.services.mcp import call_mcp_tool
        result = call_mcp_tool('coach_this_week', {'include_proposed_adjustment': False}, **build_mcp_router_dependencies())
        team = result['structuredContent']['team_coaching']
        self.assertEqual(set(team['specialists']), {'running', 'cycling', 'strength'})
        self.assertIn('action', team['head_coach'])


if __name__ == '__main__':
    unittest.main()
