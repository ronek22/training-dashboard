import sqlite3
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
from backend.app.services.mcp import call_mcp_tool
from backend.app.services.plans import build_plan_goal_context


class GoalLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'goals.db')
        self.db_patch = patch.object(db, 'DB_PATH', self.path)
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def create(self, **changes):
        payload = {
            'title': 'Lift three times per week',
            'period_type': 'week',
            'goal_family': 'process',
            'metric_type': 'strength_sessions',
            'target_value': 3,
            **changes,
        }
        response = self.client.post('/goals', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def goal(self, goal_id):
        goals = self.client.get('/goals').json()
        return next(goal for goal in goals if goal['id'] == goal_id)

    def test_new_goal_defaults_to_active_flexible(self):
        goal = self.goal(self.create())
        self.assertEqual(goal['lifecycle_status'], 'active')
        self.assertEqual(goal['commitment'], 'flexible')
        self.assertTrue(goal['is_active'])
        self.assertIsNone(goal['purpose'])

    def test_create_accepts_anchor_and_purpose(self):
        goal = self.goal(self.create(commitment='anchor', purpose=' Maintain muscle alongside cardio '))
        self.assertEqual(goal['commitment'], 'anchor')
        self.assertEqual(goal['purpose'], 'Maintain muscle alongside cardio')

    def test_patch_changes_only_provided_fields(self):
        goal_id = self.create(purpose='Maintain muscle')
        response = self.client.patch(f'/goals/{goal_id}', json={'commitment': 'anchor', 'review_on': '2026-11-01'})
        self.assertEqual(response.status_code, 200, response.text)
        goal = response.json()
        self.assertEqual(goal['commitment'], 'anchor')
        self.assertEqual(goal['review_on'], '2026-11-01')
        self.assertEqual(goal['purpose'], 'Maintain muscle')
        self.assertEqual(goal['target_value'], 3)

    def test_patch_null_clears_optional_field(self):
        goal_id = self.create(purpose='Maintain muscle')
        goal = self.client.patch(f'/goals/{goal_id}', json={'purpose': None}).json()
        self.assertIsNone(goal['purpose'])

    def test_patch_target_revalidates_goal(self):
        goal_id = self.create()
        self.assertEqual(self.client.patch(f'/goals/{goal_id}', json={'target_value': 0}).status_code, 400)
        goal = self.client.patch(f'/goals/{goal_id}', json={'target_value': 4, 'title': 'Lift four times'}).json()
        self.assertEqual(goal['target_value'], 4)
        self.assertEqual(goal['title'], 'Lift four times')

    def test_patch_rejects_bad_lifecycle_values(self):
        goal_id = self.create()
        self.assertEqual(self.client.patch(f'/goals/{goal_id}', json={'commitment': 'forever'}).status_code, 400)
        self.assertEqual(self.client.patch(f'/goals/{goal_id}', json={'season_end': '28/02/2027'}).status_code, 400)
        self.assertEqual(self.client.patch(f'/goals/{goal_id}', json={'title': '  '}).status_code, 400)

    def test_missing_goal_returns_404(self):
        self.assertEqual(self.client.patch('/goals/999', json={'title': 'x'}).status_code, 404)
        self.assertEqual(self.client.post('/goals/999/status', json={'status': 'paused'}).status_code, 404)

    def test_status_change_records_reason_and_syncs_is_active(self):
        goal_id = self.create(title='Run 1000km in 2026', period_type='year', goal_family='accumulation',
                              metric_type='run_km', target_value=1000)
        response = self.client.post(f'/goals/{goal_id}/status', json={'status': 'retired', 'reason': 'Running paused since May'})
        self.assertEqual(response.status_code, 200, response.text)
        goal = response.json()
        self.assertEqual(goal['lifecycle_status'], 'retired')
        self.assertEqual(goal['status_reason'], 'Running paused since May')
        self.assertIsNotNone(goal['status_changed_at'])
        self.assertFalse(goal['is_active'])

        goal = self.client.post(f'/goals/{goal_id}/status', json={'status': 'active'}).json()
        self.assertEqual(goal['lifecycle_status'], 'active')
        self.assertTrue(goal['is_active'])

    def test_invalid_status_is_rejected(self):
        goal_id = self.create()
        self.assertEqual(self.client.post(f'/goals/{goal_id}/status', json={'status': 'deleted'}).status_code, 400)

    def test_list_filters_by_status_and_active_only(self):
        active_id = self.create()
        completed_id = self.create(title='Ride 3500km in 2026', period_type='year', goal_family='accumulation',
                                   metric_type='ride_km', target_value=3500)
        self.client.post(f'/goals/{completed_id}/status', json={'status': 'completed'})

        completed = self.client.get('/goals', params={'status': 'completed'}).json()
        self.assertEqual([goal['id'] for goal in completed], [completed_id])
        active = self.client.get('/goals', params={'active_only': True}).json()
        self.assertEqual([goal['id'] for goal in active], [active_id])
        self.assertEqual(len(self.client.get('/goals').json()), 2)
        self.assertEqual(self.client.get('/goals', params={'status': 'gone'}).status_code, 400)

    def test_ended_season_leaves_goal_active_but_out_of_planning(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        goal_id = self.create(title='Ride 100km weekly', goal_family='accumulation', metric_type='ride_km',
                              target_value=100, season_end=yesterday)
        goal = self.goal(goal_id)
        self.assertEqual(goal['lifecycle_status'], 'active')
        self.assertTrue(goal['season_ended'])
        self.assertFalse(goal['is_active'])
        self.assertEqual(self.client.get('/goals', params={'active_only': True}).json(), [])

        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        conn = db.get_db()
        try:
            context = build_plan_goal_context(conn, [{'date': today.isoformat(), 'session_type': 'ride'}], week_start)
        finally:
            conn.close()
        self.assertNotIn(goal_id, context['goal_ids'])

    def test_mcp_goal_tools_round_trip(self):
        goal_id = self.create()
        deps = build_mcp_router_dependencies()
        updated = call_mcp_tool('update_goal', {'goal_id': goal_id, 'commitment': 'anchor', 'purpose': 'Keep muscle'}, **deps)
        self.assertEqual(updated['structuredContent']['commitment'], 'anchor')
        paused = call_mcp_tool('set_goal_status', {'goal_id': goal_id, 'status': 'paused', 'reason': 'Travel'}, **deps)
        self.assertEqual(paused['structuredContent']['lifecycle_status'], 'paused')
        listed = call_mcp_tool('get_goals', {'status': 'paused'}, **deps)
        self.assertEqual([goal['id'] for goal in listed['structuredContent']['goals']], [goal_id])
        with_history = call_mcp_tool('get_goals', {'include_history': True}, **deps)['structuredContent']['goals'][0]
        self.assertIn('stats', with_history['history'])
        self.assertNotIn('entries', with_history['history'])


class GoalMigrationTests(unittest.TestCase):
    def test_existing_inactive_goals_backfill_to_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'legacy.db')
            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    period_type TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    target_value REAL NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    activity_type TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.executemany(
                "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active) VALUES (?, 'week', 'ride_km', 100, '2026-01-01', '2026-01-07', ?)",
                [('Active goal', 1), ('Old goal', 0)],
            )
            conn.commit()
            conn.close()

            with patch.object(db, 'DB_PATH', path):
                db.init_db()
                conn = db.get_db()
                try:
                    rows = conn.execute('SELECT title, lifecycle_status, commitment FROM goals ORDER BY id').fetchall()
                finally:
                    conn.close()
            self.assertEqual([tuple(row) for row in rows], [('Active goal', 'active', 'flexible'), ('Old goal', 'paused', 'flexible')])


if __name__ == '__main__':
    unittest.main()
