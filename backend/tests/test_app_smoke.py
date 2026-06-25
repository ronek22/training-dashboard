import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def import_fresh_app():
    for name in list(sys.modules):
        if name == "backend.app" or name.startswith("backend.app."):
            sys.modules.pop(name)

    import backend.app.main as main_module

    return main_module.app


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "training-test.db")
        cls.client = TestClient(import_fresh_app())

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("TRAINING_DB_PATH", None)
        cls.temp_dir.cleanup()

    def test_health_and_mcp_info(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        mcp = self.client.get("/mcp")
        self.assertEqual(mcp.status_code, 200)
        self.assertEqual(mcp.json()["name"], "training-dashboard")
        self.assertEqual(mcp.json()["endpoint"], "/mcp")

    def test_activity_crud_and_stats(self):
        create = self.client.post(
            "/activities",
            json={
                "id": "run-1",
                "date": "2026-06-24",
                "type": "Run",
                "name": "Easy Run",
                "distance_km": 8.2,
                "duration_min": 45.0,
                "avg_hr": 148,
                "zone2": True,
            },
        )
        self.assertEqual(create.status_code, 201)
        self.assertEqual(create.json()["status"], "ok")

        activities = self.client.get("/activities?limit=5")
        self.assertEqual(activities.status_code, 200)
        body = activities.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], "run-1")

        stats = self.client.get("/activities/stats?days=30")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()[0]["type"], "Run")
        self.assertEqual(stats.json()[0]["count"], 1)

    def test_plan_and_weekly_summary_routes(self):
        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": "2026-06-22",
                "title": "Build Week",
                "focus": "Aerobic consistency",
                "overview": "Keep the week steady.",
                "days": [
                    {
                        "date": "2026-06-22",
                        "label": "Mon",
                        "session_type": "run",
                        "title": "Easy Run",
                        "details": "Keep it easy",
                        "target_duration_min": 45,
                    }
                ],
                "notes": "No changes",
            },
        )
        self.assertEqual(plan.status_code, 201)

        weekly = self.client.post(
            "/weekly",
            json={
                "week_start": "2026-06-22",
                "run_km": 8.2,
                "ride_km": 0,
                "strength_sessions": 1,
                "total_elevation": 120,
                "avg_hr": 148,
                "notes": "Solid start",
            },
        )
        self.assertEqual(weekly.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=4")
        self.assertEqual(plans.status_code, 200)
        self.assertEqual(plans.json()[0]["week_start"], "2026-06-22")
        self.assertEqual(plans.json()[0]["revision_count"], 0)

        adjusted = self.client.post(
            "/plans/weekly/adjust",
            json={
                "week_start": "2026-06-22",
                "effective_from": "2026-06-22",
                "adaptation_reason": "Shift the opener later in the day",
                "days": [
                    {
                        "date": "2026-06-22",
                        "label": "Mon",
                        "session_type": "Run",
                        "title": "Easy Run Plus Strides",
                        "details": "Keep it easy",
                        "target_duration_min": 50,
                    }
                ],
            },
        )
        self.assertEqual(adjusted.status_code, 200)
        adjusted_body = adjusted.json()
        self.assertEqual(adjusted_body["latest_revision"]["effective_from"], "2026-06-22")
        self.assertEqual(adjusted_body["latest_revision"]["adaptation_reason"], "Shift the opener later in the day")
        self.assertEqual(adjusted_body["latest_revision"]["changed_dates"], ["2026-06-22"])

        updated_plans = self.client.get("/plans/weekly?limit=4")
        self.assertEqual(updated_plans.status_code, 200)
        self.assertEqual(updated_plans.json()[0]["revision_count"], 1)
        self.assertEqual(updated_plans.json()[0]["latest_revision"]["changed_dates"], ["2026-06-22"])

        weekly_list = self.client.get("/weekly?limit=4")
        self.assertEqual(weekly_list.status_code, 200)
        self.assertEqual(weekly_list.json()[0]["week_start"], "2026-06-22")

    def test_plan_comparison_status_semantics(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday()) - timedelta(days=7)

        monday = week_start
        tuesday = week_start + timedelta(days=1)
        wednesday = week_start + timedelta(days=2)
        friday = week_start + timedelta(days=4)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Status Semantics Week",
                "days": [
                    {
                        "date": monday.isoformat(),
                        "label": monday.strftime("%a"),
                        "session_type": "Run",
                        "title": "Run moved later",
                    },
                    {
                        "date": tuesday.isoformat(),
                        "label": tuesday.strftime("%a"),
                        "session_type": "Rest",
                        "title": "Rest day",
                    },
                    {
                        "date": wednesday.isoformat(),
                        "label": wednesday.strftime("%a"),
                        "session_type": "Ride",
                        "title": "Ride replaced",
                    },
                    {
                        "date": friday.isoformat(),
                        "label": friday.strftime("%a"),
                        "session_type": "Run",
                        "title": "Run skipped",
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        moved_activity = self.client.post(
            "/activities",
            json={
                "id": "status-run-moved",
                "date": tuesday.isoformat(),
                "type": "Run",
                "name": "Shifted run",
                "duration_min": 42.0,
                "zone2": True,
            },
        )
        self.assertEqual(moved_activity.status_code, 201)

        replaced_activity = self.client.post(
            "/activities",
            json={
                "id": "status-strength-replaced",
                "date": wednesday.isoformat(),
                "type": "WeightTraining",
                "name": "Gym session",
                "duration_min": 55.0,
                "zone2": False,
            },
        )
        self.assertEqual(replaced_activity.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        days = {day["date"]: day["comparison"] for day in target_plan["days"]}

        self.assertEqual(days[monday.isoformat()]["status"], "moved")
        self.assertEqual(days[monday.isoformat()]["moved_to_date"], tuesday.isoformat())
        self.assertEqual(days[wednesday.isoformat()]["status"], "replaced")
        self.assertEqual(days[friday.isoformat()]["status"], "skipped")
