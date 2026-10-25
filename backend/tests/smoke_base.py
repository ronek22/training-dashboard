"""Shared setup for the app smoke tests (test_smoke_*.py).

Each smoke test file gets its own temporary database and a freshly imported app; setUp clears
the common tables before every test.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
import json
from datetime import date, datetime

from fastapi.testclient import TestClient


def _is_app_module(name):
    return name == "backend.app" or name.startswith("backend.app.")


def import_fresh_app():
    """Re-import the app so DB_PATH picks up the test database; returns the app and the modules it replaced."""
    replaced = {name: sys.modules.pop(name) for name in list(sys.modules) if _is_app_module(name)}

    import backend.app.main as main_module

    return main_module.app, replaced


def restore_app_modules(replaced):
    # Put back the modules other test files imported, so their patches and lazy imports agree.
    for name in [name for name in sys.modules if _is_app_module(name)]:
        sys.modules.pop(name)
    sys.modules.update(replaced)


class SmokeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "training-test.db")
        app, cls.replaced_modules = import_fresh_app()
        cls.client = TestClient(
            app,
            base_url="http://localhost:8000",
            headers={"Accept": "application/json, text/event-stream"},
        )
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        os.environ.pop("TRAINING_DB_PATH", None)
        restore_app_modules(cls.replaced_modules)
        cls.temp_dir.cleanup()

    def _find_plan(self, week_start: str):
        plans = self.client.get("/plans/weekly?limit=24")
        self.assertEqual(plans.status_code, 200)
        return next((plan for plan in plans.json() if plan["week_start"] == week_start), None)

    def _insert_activity_detail_streams(self, activity_id: str, streams: dict):
        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        try:
            conn.execute(
                """
                INSERT INTO activity_details
                (activity_id, fetched_at, source_status, detail_json, streams_json, charts_json, best_efforts_json, derived_version, route_polyline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    fetched_at=excluded.fetched_at,
                    source_status=excluded.source_status,
                    detail_json=excluded.detail_json,
                    streams_json=excluded.streams_json,
                    charts_json=excluded.charts_json,
                    best_efforts_json=excluded.best_efforts_json,
                    derived_version=excluded.derived_version,
                    route_polyline=excluded.route_polyline
                """,
                (
                    activity_id,
                    datetime.now().isoformat(),
                    "cached",
                    None,
                    json.dumps(streams),
                    json.dumps([]),
                    None,
                    "v1",
                    None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _create_activity(self, activity_id: str, date: str, activity_type: str, **overrides):
        payload = {
            "id": activity_id,
            "date": date,
            "type": activity_type,
            "name": overrides.pop("name", activity_id),
            "duration_min": overrides.pop("duration_min", 45.0),
            "distance_km": overrides.pop("distance_km", 8.0 if activity_type == "Run" else None),
            "workout_intent": overrides.pop("workout_intent", None),
            "avg_hr": overrides.pop("avg_hr", 145 if activity_type in {"Run", "Ride", "VirtualRide"} else None),
            "avg_watts": overrides.pop("avg_watts", 190 if activity_type in {"Ride", "VirtualRide"} else None),
            "zone2": overrides.pop("zone2", True if activity_type in {"Run", "Ride", "VirtualRide"} else None),
        }
        payload.update(overrides)
        response = self.client.post("/activities", json=payload)
        self.assertEqual(response.status_code, 201)
        return response

    def _save_feedback(self, activity_id: str, **payload):
        response = self.client.post(f"/activities/{activity_id}/feedback", json=payload)
        self.assertEqual(response.status_code, 201)
        return response

    def setUp(self):
        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        try:
            for table in [
                "activities",
                "coach_notes",
                "coach_chat_messages",
                "coach_chat_conversations",
                "weekly_summary",
                "metrics",
                "app_settings",
                "weekly_plans",
                "plan_revisions",
                "coaching_snapshots",
                "activity_stream_summaries",
                "activity_details",
                "activity_analyses",
                "goals",
                "activity_feedback",
                "fitbod_workout_sets",
                "fitbod_workout_exercises",
                "fitbod_workout_sessions",
                "fitbod_session_decisions",
                "fitbod_import_rows",
                "fitbod_import_batches",
                "life_load_days",
                "daily_checkins",
                "sick_session_completions",
                "sick_periods",
            ]:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
        finally:
            conn.close()

    def call_tool(self, name, arguments):
        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        self.assertEqual(response.status_code, 200)
        return response.json()["result"]
