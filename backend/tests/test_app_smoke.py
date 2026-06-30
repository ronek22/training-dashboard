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

    def test_recovery_caution_deprioritizes_run_goal_pressure_in_weekly_coaching(self):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())

        restrictions = self.client.put(
            "/settings/modality-restrictions",
            json={
                "modalities": {
                    "run": {"status": "allowed"},
                    "ride": {"status": "allowed"},
                    "strength": {"status": "allowed"},
                }
            },
        )
        self.assertEqual(restrictions.status_code, 200)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Run 1000km in 2026",
                "period_type": "year",
                "metric_type": "run_km",
                "target_value": 1000,
            },
        )
        self.assertEqual(goal.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "recovery-caution-run-1",
                "date": yesterday.isoformat(),
                "type": "Run",
                "name": "Short run",
                "distance_km": 4.0,
                "duration_min": 24.0,
                "zone2": False,
            },
        )
        self.assertEqual(activity.status_code, 201)

        feedback = self.client.post(
            "/activities/recovery-caution-run-1/feedback",
            json={
                "rpe": 6,
                "energy": 2,
                "muscle_soreness": 3,
                "pain_level": 4,
                "note": "Feet still need caution",
            },
        )
        self.assertEqual(feedback.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Recovery-sensitive week",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Run",
                        "title": "Easy run",
                        "target_duration_min": 35,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        body = coaching.json()
        self.assertGreaterEqual(body["goal_assessment"]["deferred_goal_count"], 1)
        self.assertTrue(any(
            "Run-volume goals are temporarily backgrounded" in item
            for item in body["goal_assessment"]["key_observations"]
        ))
        self.assertFalse(any("Run 1000km in 2026" in item for item in body["recommendation"]["risks"]))

    def test_modality_restrictions_constrain_goals_and_coaching(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        target_day = today + timedelta(days=1)

        restrictions = self.client.put(
            "/settings/modality-restrictions",
            json={
                "modalities": {
                    "run": {
                        "status": "blocked",
                        "reason": "Foot flare-up",
                        "expected_end_date": (today + timedelta(days=10)).isoformat(),
                    },
                    "ride": {"status": "allowed"},
                    "strength": {"status": "allowed"},
                }
            },
        )
        self.assertEqual(restrictions.status_code, 200)
        self.assertEqual(restrictions.json()["summary"]["blocked_count"], 1)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Run 800km in 2026",
                "period_type": "year",
                "metric_type": "run_km",
                "target_value": 800,
            },
        )
        self.assertEqual(goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Restriction-aware week",
                "days": [
                    {
                        "date": target_day.isoformat(),
                        "label": target_day.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 45,
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        restricted_goal = next(item for item in goals.json() if item["title"] == "Run 800km in 2026")
        self.assertEqual(restricted_goal["risk_summary"]["status"], "constrained")

        plans = self.client.get("/plans/weekly?limit=4")
        self.assertEqual(plans.status_code, 200)
        self.assertEqual(plans.json()[0]["days"][0]["modality_restriction"]["status"], "blocked")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["modality_restrictions"]["summary"]["blocked_count"], 1)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        body = coaching.json()
        self.assertEqual(body["goal_assessment"]["constrained_goal_count"], 1)
        next_session = next(item for item in body["recommended_next_sessions"] if item["title"] == "Easy run")
        self.assertEqual(next_session["suggestion"], "substitute")
        self.assertEqual(body["proposed_adjustment"]["days"][0]["session_type"], "Ride")

    def test_plan_and_weekly_summary_routes(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        editable_day = today + timedelta(days=1)
        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Build Week",
                "focus": "Aerobic consistency",
                "overview": "Keep the week steady.",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "run",
                        "workout_intent": "easy",
                        "title": "Easy Run",
                        "details": "Keep it easy",
                        "target_duration_min": 45,
                    },
                    {
                        "date": editable_day.isoformat(),
                        "label": editable_day.strftime("%a"),
                        "session_type": "run",
                        "workout_intent": "easy",
                        "title": "Second Easy Run",
                        "details": "Keep it steady",
                        "target_duration_min": 40,
                    }
                ],
                "notes": "No changes",
            },
        )
        self.assertEqual(plan.status_code, 201)

        weekly = self.client.post(
            "/weekly",
            json={
                "week_start": week_start.isoformat(),
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
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        self.assertEqual(target_plan["revision_count"], 0)
        self.assertEqual(target_plan["days"][0]["workout_intent"], "easy")
        self.assertEqual(target_plan["days"][0]["workout_intent_label"], "Easy")

        adjusted = self.client.post(
            "/plans/weekly/adjust",
            json={
                "week_start": week_start.isoformat(),
                "effective_from": editable_day.isoformat(),
                "adaptation_reason": "Shift the opener later in the day",
                "days": [
                    {
                        "date": editable_day.isoformat(),
                        "label": editable_day.strftime("%a"),
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
        self.assertEqual(adjusted_body["latest_revision"]["effective_from"], editable_day.isoformat())
        self.assertEqual(adjusted_body["latest_revision"]["adaptation_reason"], "Shift the opener later in the day")
        self.assertEqual(adjusted_body["latest_revision"]["changed_dates"], [editable_day.isoformat()])

        updated_plans = self.client.get("/plans/weekly?limit=4")
        self.assertEqual(updated_plans.status_code, 200)
        updated_target_plan = next(item for item in updated_plans.json() if item["week_start"] == week_start.isoformat())
        self.assertEqual(updated_target_plan["revision_count"], 1)
        self.assertEqual(updated_target_plan["latest_revision"]["changed_dates"], [editable_day.isoformat()])
        self.assertEqual(len(updated_target_plan["revisions"]), 1)
        self.assertEqual(updated_target_plan["revisions"][0]["change_count"], 1)
        self.assertEqual(updated_target_plan["revisions"][0]["source"], "manual")

        weekly_list = self.client.get("/weekly?limit=4")
        self.assertEqual(weekly_list.status_code, 200)
        self.assertEqual(weekly_list.json()[0]["week_start"], week_start.isoformat())

    def test_dashboard_prefers_current_week_plan_over_next_week(self):
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        next_week_start = current_week_start + timedelta(days=7)
        tomorrow = today + timedelta(days=1)

        current_plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": current_week_start.isoformat(),
                "title": "Current Week Plan",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Ride",
                        "title": "Today ride",
                        "target_duration_min": 60,
                    },
                    {
                        "date": tomorrow.isoformat(),
                        "label": tomorrow.strftime("%a"),
                        "session_type": "Run",
                        "title": "Tomorrow run",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(current_plan.status_code, 201)

        next_plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": next_week_start.isoformat(),
                "title": "Next Week Plan",
                "days": [
                    {
                        "date": next_week_start.isoformat(),
                        "label": next_week_start.strftime("%a"),
                        "session_type": "Run",
                        "title": "Next week opener",
                        "target_duration_min": 35,
                    }
                ],
            },
        )
        self.assertEqual(next_plan.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "dashboard-current-week-match",
                "date": today.isoformat(),
                "type": "Ride",
                "name": "Completed today ride",
                "duration_min": 62,
                "distance_km": 24.0,
                "zone2": True,
            },
        )
        self.assertEqual(activity.status_code, 201)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        body = dashboard.json()
        self.assertEqual(body["weekly_plan"]["week_start"], current_week_start.isoformat())
        self.assertEqual(body["weekly_plan"]["days"][0]["comparison"]["status"], "matched")

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        coaching_body = coaching.json()
        self.assertEqual(coaching_body["week_start"], current_week_start.isoformat())
        self.assertIsInstance(coaching_body["recommended_next_sessions"], list)

    def test_zz_coaching_history_snapshot_route(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        second_day = week_start + timedelta(days=1)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Current Week",
                "focus": "Keep the structure visible",
                "days": [
                    {
                        "date": week_start.isoformat(),
                        "label": week_start.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy Run",
                        "target_duration_min": 45,
                    },
                    {
                        "date": second_day.isoformat(),
                        "label": second_day.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "Tempo Run",
                        "target_duration_min": 50,
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        coaching_body = coaching.json()
        self.assertIsNotNone(coaching_body["week_start"])

        history = self.client.get("/coaching/history?limit=4")
        self.assertEqual(history.status_code, 200)
        history_body = history.json()
        self.assertTrue(history_body)
        self.assertTrue(any(item["week_start"] == coaching_body["week_start"] for item in history_body))
        matching_entry = next(item for item in history_body if item["week_start"] == coaching_body["week_start"])
        self.assertIn(matching_entry["recommendation_status"], {"keep", "push", "reduce", "recover", "adjust"})
        self.assertIn("rationale_summary", matching_entry)

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

        goal_titles = [goal["title"] for goal in target_plan["goal_context"]["active_goals"]]
        self.assertIn("Run 40 km this week", goal_titles)
        run_day = next(day for day in target_plan["days"] if day["session_type"] == "Run")
        strength_day = next(day for day in target_plan["days"] if day["session_type"] == "WeightTraining")
        self.assertEqual(run_day["goal_links"][0]["support_reason"], "Builds run volume")
        self.assertEqual(strength_day["goal_links"], [])

    def test_plan_session_ids_and_manual_activity_linking(self):
        week_start = datetime.now().date() - timedelta(days=datetime.now().date().weekday()) - timedelta(days=70)
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
                    },
                    {
                        "date": moved_day.isoformat(),
                        "label": moved_day.strftime("%a"),
                        "session_type": "Rest",
                        "title": "Rest day",
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

        activities_after_link = self.client.get("/activities?limit=32")
        self.assertEqual(activities_after_link.status_code, 200)
        linked_activity = next(item for item in activities_after_link.json() if item["id"] == "linked-run-1")
        self.assertEqual(linked_activity["linked_planned_session_id"], day["session_id"])

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertGreaterEqual(recent_context.json()["workout_intent_summary"]["recent_activities"]["count"], 1)

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
        self.assertIsInstance(target_goal["planning_guidance"]["required_per_week"], float)
        self.assertTrue(target_goal["planning_guidance"]["summary"])
        self.assertIn("forecast", target_goal)
        self.assertIn(target_goal["forecast"]["projected_status"], {"completed", "ahead", "on_track", "behind", "at_risk"})
        self.assertIn("risk_summary", target_goal)
        self.assertIn(target_goal["risk_summary"]["status"], {"completed", "on_track", "watch", "under_pressure", "at_risk"})

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        self.assertIn("active_goals", recent_context.json())
        self.assertIn("goal_planning_summary", recent_context.json())
        self.assertIn("goal_risk_summary", recent_context.json())
        self.assertGreaterEqual(recent_context.json()["goal_planning_summary"]["count"], 1)
        self.assertTrue(recent_context.json()["goal_planning_summary"]["most_urgent"])

    def test_behind_goal_changes_visible_planning_guidance(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        second_day = week_start + timedelta(days=2)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 5000 km this year",
                "period_type": "year",
                "metric_type": "ride_km",
                "target_value": 5000,
            },
        )
        self.assertEqual(goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Pressure week",
                "days": [
                    {
                        "date": today.isoformat(),
                        "label": today.strftime("%a"),
                        "session_type": "Ride",
                        "title": "Endurance ride",
                        "target_duration_min": 90,
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

        goals = self.client.get("/goals?limit=24")
        self.assertEqual(goals.status_code, 200)
        target_goal = next(item for item in goals.json() if item["title"] == "Ride 5000 km this year")
        self.assertIn(target_goal["forecast"]["projected_status"], {"behind", "at_risk"})
        self.assertIn(target_goal["risk_summary"]["status"], {"under_pressure", "at_risk"})

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        ride_day = next(day for day in target_plan["days"] if day["session_type"] == "Ride")
        self.assertTrue(ride_day["goal_links"])
        self.assertEqual(ride_day["goal_links"][0]["goal_title"], "Ride 5000 km this year")
        self.assertIn(ride_day["goal_links"][0]["risk_status"], {"under_pressure", "at_risk"})

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(dashboard.json()["goal_risk_summary"]["status"], {"under_pressure", "at_risk"})

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        self.assertIn(coaching.json()["goal_assessment"]["status"], {"watch", "pressured"})
        self.assertTrue(any(
            "Ride 5000 km this year" in item
            for item in coaching.json()["goal_assessment"]["key_observations"]
        ))

    def test_plan_comparison_status_semantics(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday()) - timedelta(days=28)

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
        week_start = (today - timedelta(days=today.weekday())) + timedelta(days=7)
        yesterday = today - timedelta(days=1)
        second_day = week_start + timedelta(days=1)

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
                        "date": week_start.isoformat(),
                        "label": week_start.strftime("%a"),
                        "session_type": "Ride",
                        "workout_intent": "tempo",
                        "title": "Tempo ride",
                        "target_duration_min": 75,
                        "target_distance_km": 35,
                    },
                    {
                        "date": second_day.isoformat(),
                        "label": second_day.strftime("%a"),
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
        self.assertIsInstance(coaching_body["recommended_next_sessions"], list)
        if coaching_body["proposed_adjustment"] is not None:
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

    def test_weekly_coaching_exposes_recent_pattern_summary(self):
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        historical_weeks = [
            current_week_start - timedelta(days=14),
            current_week_start - timedelta(days=7),
        ]

        for index, week_start in enumerate(historical_weeks):
            monday = week_start
            tuesday = week_start + timedelta(days=1)
            plan = self.client.post(
                "/plans/weekly",
                json={
                    "week_start": week_start.isoformat(),
                    "title": f"Pattern week {index + 1}",
                    "days": [
                        {
                            "date": monday.isoformat(),
                            "label": monday.strftime("%a"),
                            "session_type": "Run",
                            "workout_intent": "tempo",
                            "title": "Tempo run",
                            "target_duration_min": 45,
                        },
                        {
                            "date": tuesday.isoformat(),
                            "label": tuesday.strftime("%a"),
                            "session_type": "Run",
                            "workout_intent": "easy",
                            "title": "Easy run",
                            "target_duration_min": 35,
                        },
                    ],
                },
            )
            self.assertEqual(plan.status_code, 201)

            matched = self.client.post(
                "/activities",
                json={
                    "id": f"pattern-match-{index}",
                    "date": monday.isoformat(),
                    "type": "Run",
                    "workout_intent": "tempo",
                    "name": "Tempo run done",
                    "duration_min": 44.0,
                },
            )
            self.assertEqual(matched.status_code, 201)

        tomorrow = today + timedelta(days=1)
        later_this_week = today + timedelta(days=2)
        current_plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": current_week_start.isoformat(),
                "title": "Current pattern-sensitive week",
                "days": [
                    {
                        "date": tomorrow.isoformat(),
                        "label": tomorrow.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "Tempo run",
                        "target_duration_min": 50,
                    },
                    {
                        "date": later_this_week.isoformat(),
                        "label": later_this_week.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 40,
                    },
                ],
            },
        )
        self.assertEqual(current_plan.status_code, 201)

        neutral_activity = self.client.post(
            "/activities",
            json={
                "id": "pattern-neutral-checkin",
                "date": today.isoformat(),
                "type": "Run",
                "workout_intent": "easy",
                "name": "Easy reset run",
                "duration_min": 30.0,
            },
        )
        self.assertEqual(neutral_activity.status_code, 201)

        neutral_feedback = self.client.post(
            "/activities/pattern-neutral-checkin/feedback",
            json={
                "rpe": 4,
                "energy": 4,
                "muscle_soreness": 2,
                "pain_level": 0,
                "note": "Felt normal again.",
            },
        )
        self.assertEqual(neutral_feedback.status_code, 201)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        body = coaching.json()
        self.assertIn(body["recommendation"]["status"], {"adjust", "reduce", "recover"})
        self.assertEqual(body["reasoning_signals"]["recent_pattern_summary"]["status"], "concerning")
        self.assertTrue(any(
            "Skipped sessions appeared" in item
            for item in body["reasoning_signals"]["recent_pattern_summary"]["key_observations"]
        ))

    def test_weekly_recommendation_push_is_suppressed_when_recent_patterns_are_not_stable(self):
        from backend.app.services.coaching import build_weekly_recommendation

        context = {"daily_recommendation": {"status": "push"}}
        execution = {
            "status": "on_track",
            "planned_sessions": 4,
            "fulfilled_sessions": 3,
            "modified_sessions": 0,
            "missed_sessions": 0,
            "intent_alignment": {"different": 0},
            "key_observations": ["Execution is lining up with the plan."],
        }
        recovery = {
            "status": "steady",
            "caution_score": 0,
            "key_reasons": ["Recovery signals are calm."],
            "caution_flags": [],
        }
        goals = {
            "status": "steady",
            "most_urgent": [],
            "key_observations": ["Goals are supported by the current week."],
        }
        next_sessions = [
            {
                "date": "2026-07-01",
                "title": "Quality ride",
                "suggestion": "keep",
            }
        ]

        stable_patterns = {
            "status": "stable",
            "current_week_revision_count": 0,
            "key_observations": ["Recent pattern signals are fairly stable."],
            "execution_trend": {
                "recurring_patterns": {
                    "weeks_with_skipped": 0,
                    "weeks_with_modified": 0,
                },
                "streaks": {"consecutive_weeks_with_skipped": 0},
            },
            "recent_feedback_patterns": {
                "high_rpe_count": 0,
                "low_energy_count": 0,
                "elevated_pain_count": 0,
            },
        }
        watch_patterns = {
            **stable_patterns,
            "status": "watch",
            "key_observations": ["Intent mismatches are repeating rather than looking like a one-off."],
            "recent_feedback_patterns": {
                "high_rpe_count": 2,
                "low_energy_count": 0,
                "elevated_pain_count": 0,
            },
        }

        stable = build_weekly_recommendation(context, execution, recovery, goals, next_sessions, stable_patterns)
        watch = build_weekly_recommendation(context, execution, recovery, goals, next_sessions, watch_patterns)

        self.assertEqual(stable["status"], "push")
        self.assertEqual(watch["status"], "keep")
        self.assertIn("Recent feedback includes repeated high-RPE sessions.", watch["rationale"])

    def test_weekly_recommendation_adjusts_for_recurring_skips_and_revision_churn(self):
        from backend.app.services.coaching import build_weekly_recommendation

        context = {"daily_recommendation": {"status": "keep"}}
        execution = {
            "status": "mixed",
            "planned_sessions": 4,
            "fulfilled_sessions": 2,
            "modified_sessions": 1,
            "missed_sessions": 0,
            "intent_alignment": {"different": 1},
            "key_observations": ["Execution has started to drift."],
        }
        recovery = {
            "status": "steady",
            "caution_score": 0,
            "key_reasons": ["Recovery signals are calm."],
            "caution_flags": [],
        }
        goals = {
            "status": "steady",
            "most_urgent": [],
            "key_observations": ["Goals are present but not driving the decision."],
        }
        next_sessions = [
            {
                "date": "2026-07-02",
                "title": "Threshold run",
                "suggestion": "review",
            }
        ]
        recent_patterns = {
            "status": "concerning",
            "current_week_revision_count": 3,
            "key_observations": [
                "Skipped sessions appeared in 2 recent planned weeks.",
                "This week has already been revised 3 times.",
            ],
            "execution_trend": {
                "recurring_patterns": {
                    "weeks_with_skipped": 2,
                    "weeks_with_modified": 1,
                },
                "streaks": {"consecutive_weeks_with_skipped": 2},
            },
            "recent_feedback_patterns": {
                "high_rpe_count": 0,
                "low_energy_count": 0,
                "elevated_pain_count": 0,
            },
        }

        recommendation = build_weekly_recommendation(context, execution, recovery, goals, next_sessions, recent_patterns)

        self.assertEqual(recommendation["status"], "adjust")
        self.assertIn("Skipped sessions have recurred in 2 recent weeks.", recommendation["risks"])
        self.assertIn("This week has already been revised 3 times.", recommendation["rationale"])

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
        self.assertEqual(planning_body["roadmap"]["completed_phases"], planning_body["roadmap"]["total_phases"])
        self.assertIsNone(planning_body["roadmap"]["current_phase"])
        self.assertIsNone(planning_body["sprints"]["next_recommended"])

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
                        "session_type": "Hike",
                        "workout_intent": "long",
                        "title": "Easy trail hike",
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
        self.assertNotEqual(comparison["status"], "skipped")

    def test_multi_week_execution_trend_exposes_recurring_patterns(self):
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        week_starts = [
            current_week_start - timedelta(days=21),
            current_week_start - timedelta(days=14),
            current_week_start - timedelta(days=7),
        ]

        for index, week_start in enumerate(week_starts):
            monday = week_start
            tuesday = week_start + timedelta(days=1)
            wednesday = week_start + timedelta(days=2)

            plan = self.client.post(
                "/plans/weekly",
                json={
                    "week_start": week_start.isoformat(),
                    "title": f"Trend week {index + 1}",
                    "days": [
                        {
                            "date": monday.isoformat(),
                            "label": monday.strftime("%a"),
                            "session_type": "Run",
                            "workout_intent": "tempo",
                            "title": "Tempo run",
                            "target_duration_min": 45,
                        },
                        {
                            "date": tuesday.isoformat(),
                            "label": tuesday.strftime("%a"),
                            "session_type": "Run",
                            "workout_intent": "easy",
                            "title": "Easy run",
                            "target_duration_min": 40,
                        },
                        {
                            "date": wednesday.isoformat(),
                            "label": wednesday.strftime("%a"),
                            "session_type": "Rest",
                            "title": "Rest day",
                        },
                    ],
                },
            )
            self.assertEqual(plan.status_code, 201)

        moved_activity_week_1 = self.client.post(
            "/activities",
            json={
                "id": "trend-moved-week-1",
                "date": (week_starts[0] + timedelta(days=2)).isoformat(),
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Moved tempo run",
                "duration_min": 46.0,
            },
        )
        self.assertEqual(moved_activity_week_1.status_code, 201)

        matched_activity_week_1 = self.client.post(
            "/activities",
            json={
                "id": "trend-matched-week-1",
                "date": (week_starts[0] + timedelta(days=1)).isoformat(),
                "type": "Run",
                "workout_intent": "easy",
                "name": "Matched easy run",
                "duration_min": 39.0,
            },
        )
        self.assertEqual(matched_activity_week_1.status_code, 201)

        moved_activity_week_2 = self.client.post(
            "/activities",
            json={
                "id": "trend-moved-week-2",
                "date": (week_starts[1] + timedelta(days=2)).isoformat(),
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Moved tempo run again",
                "duration_min": 47.0,
            },
        )
        self.assertEqual(moved_activity_week_2.status_code, 201)

        mismatched_activity_week_2 = self.client.post(
            "/activities",
            json={
                "id": "trend-partial-week-2",
                "date": (week_starts[1] + timedelta(days=1)).isoformat(),
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Harder than planned",
                "duration_min": 41.0,
            },
        )
        self.assertEqual(mismatched_activity_week_2.status_code, 201)

        matched_activity_week_3 = self.client.post(
            "/activities",
            json={
                "id": "trend-matched-week-3",
                "date": week_starts[2].isoformat(),
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Tempo run matched",
                "duration_min": 44.0,
            },
        )
        self.assertEqual(matched_activity_week_3.status_code, 201)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        dashboard_trend = dashboard.json()["execution_trend"]
        self.assertGreaterEqual(dashboard_trend["recurring_patterns"]["weeks_with_moved"], 2)
        self.assertGreaterEqual(dashboard_trend["recurring_patterns"]["weeks_with_intent_mismatch"], 1)
        self.assertGreaterEqual(dashboard_trend["totals"]["status_counts"]["moved"], 2)
        self.assertTrue(dashboard_trend["observations"])

        trends = self.client.get("/plans/weekly/trends?weeks=8")
        self.assertEqual(trends.status_code, 200)
        body = trends.json()
        self.assertGreaterEqual(body["weeks_considered"], 3)
        trend_weeks = {item["week_start"]: item for item in body["weeks"] if item["week_start"] in {week.isoformat() for week in week_starts}}
        self.assertEqual(len(trend_weeks), 3)
        self.assertEqual(trend_weeks[week_starts[0].isoformat()]["status_counts"]["moved"], 1)
        self.assertEqual(trend_weeks[week_starts[0].isoformat()]["status_counts"]["rest_day_changed"], 1)
        self.assertEqual(trend_weeks[week_starts[1].isoformat()]["intent_alignment"]["different"], 1)
        self.assertEqual(trend_weeks[week_starts[1].isoformat()]["status_counts"]["rest_day_changed"], 1)
        self.assertGreaterEqual(trend_weeks[week_starts[2].isoformat()]["fulfilled_sessions"], 1)
