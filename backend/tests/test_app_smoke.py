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
                "workout_intent": "easy",
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
        self.assertEqual(body[0]["workout_intent"], "easy")

        updated_intent = self.client.post(
            "/activities/run-1/intent",
            json={"workout_intent": "tempo"},
        )
        self.assertEqual(updated_intent.status_code, 200)
        self.assertEqual(updated_intent.json()["workout_intent"], "tempo")
        self.assertEqual(updated_intent.json()["workout_intent_label"], "Tempo")

        stats = self.client.get("/activities/stats?days=30")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()[0]["type"], "Run")
        self.assertEqual(stats.json()[0]["count"], 1)

    def test_activity_feedback_and_recommendation_context(self):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())

        create = self.client.post(
            "/activities",
            json={
                "id": "feedback-run-1",
                "date": yesterday.isoformat(),
                "type": "Run",
                "name": "Threshold Run",
                "distance_km": 10.0,
                "duration_min": 52.0,
                "avg_hr": 171,
                "zone2": False,
            },
        )
        self.assertEqual(create.status_code, 201)

        feedback = self.client.post(
            "/activities/feedback-run-1/feedback",
            json={
                "rpe": 9,
                "energy": 2,
                "muscle_soreness": 4,
                "pain_level": 5,
                "note": "Felt heavy on the last reps",
            },
        )
        self.assertEqual(feedback.status_code, 201)
        self.assertEqual(feedback.json()["pain_level"], 5)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Feedback Week",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Run",
                        "title": "Steady Run",
                        "target_duration_min": 45,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        activity_list = self.client.get("/activities?limit=5")
        self.assertEqual(activity_list.status_code, 200)
        self.assertEqual(activity_list.json()[0]["feedback"]["rpe"], 9)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(dashboard.json()["daily_recommendation"]["status"], {"reduce", "recover"})
        self.assertEqual(dashboard.json()["latest_subjective_state"]["pain_level"], 5)

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertEqual(recent_context.json()["recent_feedback"][0]["activity_id"], "feedback-run-1")
        self.assertIn("daily_recommendation", recent_context.json())

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
                        "workout_intent": "easy",
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
        self.assertEqual(plans.json()[0]["days"][0]["workout_intent"], "easy")
        self.assertEqual(plans.json()[0]["days"][0]["workout_intent_label"], "Easy")

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

    def test_weekly_plan_includes_goal_context(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        second_day = week_start + timedelta(days=1)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Run 40 km this week",
                "period_type": "week",
                "metric_type": "run_km",
                "target_value": 40,
            },
        )
        self.assertEqual(goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Goal-aligned week",
                "days": [
                    {
                        "date": week_start.isoformat(),
                        "label": week_start.strftime("%a"),
                        "session_type": "Run",
                        "title": "Easy run",
                        "target_duration_min": 45,
                    },
                    {
                        "date": second_day.isoformat(),
                        "label": second_day.strftime("%a"),
                        "session_type": "WeightTraining",
                        "title": "Gym",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())

        self.assertEqual(target_plan["goal_context"]["active_goals"][0]["title"], "Run 40 km this week")
        run_day = next(day for day in target_plan["days"] if day["session_type"] == "Run")
        strength_day = next(day for day in target_plan["days"] if day["session_type"] == "WeightTraining")
        self.assertEqual(run_day["goal_links"][0]["support_reason"], "Builds run volume")
        self.assertEqual(strength_day["goal_links"], [])

    def test_plan_session_ids_and_manual_activity_linking(self):
        week_start = datetime.now().date() - timedelta(days=datetime.now().date().weekday())
        planned_day = week_start + timedelta(days=1)
        moved_day = planned_day + timedelta(days=1)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Link test week",
                "days": [
                    {
                        "date": planned_day.isoformat(),
                        "label": planned_day.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "Tempo run",
                        "target_duration_min": 50,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "linked-run-1",
                "date": moved_day.isoformat(),
                "type": "Run",
                "workout_intent": "easy",
                "name": "Moved tempo run",
                "distance_km": 9.5,
                "duration_min": 51,
                "zone2": False,
            },
        )
        self.assertEqual(activity.status_code, 201)

        plans_before_link = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans_before_link.status_code, 200)
        target_plan = next(item for item in plans_before_link.json() if item["week_start"] == week_start.isoformat())
        day = target_plan["days"][0]
        self.assertTrue(day["session_id"].startswith("plan-"))
        self.assertEqual(day["comparison"]["status"], "moved")
        self.assertEqual(day["workout_intent"], "tempo")
        self.assertEqual(day["comparison"]["planned_intent"], "tempo")

        link = self.client.post(
            "/activities/linked-run-1/link-plan",
            json={"planned_session_id": day["session_id"]},
        )
        self.assertEqual(link.status_code, 200)
        self.assertEqual(link.json()["linked_planned_session_id"], day["session_id"])

        plans_after_link = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans_after_link.status_code, 200)
        linked_plan = next(item for item in plans_after_link.json() if item["week_start"] == week_start.isoformat())
        linked_day = linked_plan["days"][0]
        self.assertEqual(linked_day["comparison"]["status"], "linked")
        self.assertEqual(linked_day["comparison"]["matching_strategy"], "explicit")
        self.assertEqual(linked_day["comparison"]["completed_activities"][0]["id"], "linked-run-1")
        self.assertEqual(linked_day["comparison"]["intent_alignment"], "different")
        self.assertEqual(linked_day["comparison"]["completed_activities"][0]["workout_intent"], "easy")

        activities_after_link = self.client.get("/activities?limit=8")
        self.assertEqual(activities_after_link.status_code, 200)
        linked_activity = next(item for item in activities_after_link.json() if item["id"] == "linked-run-1")
        self.assertEqual(linked_activity["linked_planned_session_id"], day["session_id"])

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertEqual(
            recent_context.json()["active_plan"]["days"][0]["comparison"]["matching_strategy"],
            "explicit",
        )
        self.assertGreaterEqual(recent_context.json()["workout_intent_summary"]["recent_activities"]["count"], 1)
        self.assertGreaterEqual(recent_context.json()["workout_intent_summary"]["active_plan"]["count"], 1)

    def test_goal_planning_guidance_fields(self):
        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 200 km this month",
                "period_type": "month",
                "metric_type": "ride_km",
                "target_value": 200,
            },
        )
        self.assertEqual(goal.status_code, 201)

        goals = self.client.get("/goals?limit=8")
        self.assertEqual(goals.status_code, 200)
        target_goal = next(item for item in goals.json() if item["title"] == "Ride 200 km this month")

        self.assertIn("planning_guidance", target_goal)
        self.assertIn(target_goal["planning_guidance"]["status"], {"completed", "comfortable", "steady", "pressured", "urgent"})
        self.assertIsInstance(target_goal["planning_guidance"]["required_per_day"], float)
        self.assertTrue(target_goal["planning_guidance"]["summary"])

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertIn("active_goals", recent_context.json())
        self.assertIn("goal_planning_summary", recent_context.json())
        self.assertGreaterEqual(recent_context.json()["goal_planning_summary"]["count"], 1)
        self.assertTrue(recent_context.json()["goal_planning_summary"]["most_urgent"])

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

    def test_intent_mismatch_becomes_partially_matched(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday()) - timedelta(days=7)
        monday = week_start

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Intent mismatch week",
                "days": [
                    {
                        "date": monday.isoformat(),
                        "label": monday.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "Tempo run",
                        "target_duration_min": 45,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "intent-mismatch-run",
                "date": monday.isoformat(),
                "type": "Run",
                "workout_intent": "easy",
                "name": "Easy run instead",
                "duration_min": 47.0,
                "zone2": True,
            },
        )
        self.assertEqual(activity.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        comparison = target_plan["days"][0]["comparison"]
        self.assertEqual(comparison["status"], "partially_matched")
        self.assertEqual(comparison["intent_alignment"], "different")
        self.assertEqual(comparison["planned_intent_label"], "Tempo")

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertIn("workout_intent_summary", recent_context.json())
        self.assertTrue(recent_context.json()["workout_intent_summary"]["recent_activities"]["top"])

    def test_weekly_coaching_route_and_mcp_tool(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 120 km this week",
                "period_type": "week",
                "metric_type": "ride_km",
                "target_value": 120,
            },
        )
        self.assertEqual(goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Coaching week",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Ride",
                        "workout_intent": "tempo",
                        "title": "Tempo ride",
                        "target_duration_min": 75,
                        "target_distance_km": 35,
                    },
                    {
                        "date": tomorrow.isoformat(),
                        "label": tomorrow.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "coaching-ride-yesterday",
                "date": yesterday.isoformat(),
                "type": "Ride",
                "workout_intent": "tempo",
                "name": "Hard ride",
                "distance_km": 42.0,
                "duration_min": 96.0,
                "avg_hr": 167,
                "avg_watts": 228,
                "zone2": False,
            },
        )
        self.assertEqual(activity.status_code, 201)

        feedback = self.client.post(
            "/activities/coaching-ride-yesterday/feedback",
            json={
                "rpe": 8,
                "energy": 2,
                "muscle_soreness": 4,
                "pain_level": 5,
                "note": "Legs still heavy the next day.",
            },
        )
        self.assertEqual(feedback.status_code, 201)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        coaching_body = coaching.json()
        self.assertIn("summary", coaching_body)
        self.assertIn("execution_assessment", coaching_body)
        self.assertIn("recovery_assessment", coaching_body)
        self.assertIn("goal_assessment", coaching_body)
        self.assertIn("recommendation", coaching_body)
        self.assertIn("recommended_next_sessions", coaching_body)
        self.assertIn("reasoning_signals", coaching_body)
        self.assertIn(coaching_body["recommendation"]["status"], {"reduce", "recover", "adjust"})
        self.assertTrue(coaching_body["recommended_next_sessions"])
        self.assertEqual(coaching_body["recommended_next_sessions"][0]["date"], today.isoformat())
        self.assertIsNotNone(coaching_body["proposed_adjustment"])
        self.assertIn("diff", coaching_body["proposed_adjustment"])
        self.assertTrue(coaching_body["proposed_adjustment"]["diff"]["changed_dates"])

        mcp = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "coach_this_week",
                    "arguments": {},
                },
            },
        )
        self.assertEqual(mcp.status_code, 200)
        mcp_body = mcp.json()
        self.assertEqual(mcp_body["id"], 7)
        structured = mcp_body["result"]["structuredContent"]
        self.assertIn("recommendation", structured)
        self.assertIn("summary", structured)
        self.assertIn(structured["recommendation"]["status"], {"reduce", "recover", "adjust"})

    def test_adjustment_preview_and_planning_status_routes(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        tomorrow = today + timedelta(days=1)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Preview week",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "Tempo run",
                        "target_duration_min": 50,
                    },
                    {
                        "date": tomorrow.isoformat(),
                        "label": tomorrow.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        preview = self.client.post(
            "/plans/weekly/adjust/preview",
            json={
                "week_start": week_start.isoformat(),
                "effective_from": today.isoformat(),
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Recovery",
                        "workout_intent": "recovery",
                        "title": "Recovery spin",
                        "target_duration_min": 30,
                    },
                    {
                        "date": tomorrow.isoformat(),
                        "label": tomorrow.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(preview.status_code, 200)
        preview_body = preview.json()
        self.assertTrue(preview_body["preview_only"])
        self.assertEqual(preview_body["diff"]["summary"]["edited"], 1)
        self.assertEqual(preview_body["diff"]["days"][0]["status"], "edited")
        self.assertTrue(preview_body["diff"]["days"][0]["changes"])

        planning_status = self.client.get("/planning/status")
        self.assertEqual(planning_status.status_code, 200)
        planning_body = planning_status.json()
        self.assertEqual(planning_body["roadmap"]["title"], "Training Dashboard Roadmap")
        self.assertTrue(planning_body["roadmap"]["phases"])
        self.assertTrue(planning_body["sprints"]["items"])
        self.assertEqual(planning_body["sprints"]["next_recommended"]["label"], "Sprint 8")

    def test_today_session_is_not_skipped_before_day_is_over(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Today stays open",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Ride",
                        "workout_intent": "easy",
                        "title": "Zone 2 Endurance Ride",
                        "target_duration_min": 75,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        comparison = target_plan["days"][0]["comparison"]
        self.assertEqual(comparison["status"], "not_completed_yet")
        self.assertEqual(comparison["label"], "Not completed yet")
