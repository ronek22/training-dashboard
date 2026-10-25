"""App smoke tests: Goals, goal readiness and goal-aware coaching."""
import unittest
import json
from datetime import date, datetime, timedelta
from backend.tests import smoke_base


class GoalSmokeTests(smoke_base.SmokeTestCase):
    def test_goal_drafting_supports_high_confidence_and_warning_cases(self):
        ready_cases = [
            (
                "run 10k in under 40 minutes by October",
                {
                    "goal_family": "event_performance",
                    "activity_type": "Run",
                    "distance_km": 10.0,
                    "target_duration_min": 40.0,
                },
            ),
            (
                "hold 300W for 10 minutes",
                {
                    "goal_family": "benchmark",
                    "activity_type": "Ride",
                    "target_watts": 300.0,
                    "duration_min": 10.0,
                },
            ),
            (
                "ride 6 hours of zone 2 per week",
                {
                    "goal_family": "process",
                    "metric_type": "zone2_hours",
                    "target_value": 6.0,
                },
            ),
        ]

        for text, expected in ready_cases:
            with self.subTest(text=text):
                draft = self.client.post("/goals/draft", json={"text": text})
                self.assertEqual(draft.status_code, 200)
                body = draft.json()
                self.assertTrue(body["is_supported"])
                self.assertTrue(body["is_ready"])
                self.assertEqual(body["goal"]["goal_family"], expected["goal_family"])
                if "metric_type" in expected:
                    self.assertEqual(body["goal"]["metric_type"], expected["metric_type"])
                if "activity_type" in expected:
                    self.assertEqual(body["goal"]["activity_type"], expected["activity_type"])
                if "target_value" in expected:
                    self.assertEqual(body["goal"]["target_value"], expected["target_value"])
                if "distance_km" in expected:
                    self.assertEqual(body["goal"]["target_config"]["distance_km"], expected["distance_km"])
                if "target_duration_min" in expected:
                    self.assertEqual(body["goal"]["target_config"]["target_duration_min"], expected["target_duration_min"])
                if "target_watts" in expected:
                    self.assertEqual(body["goal"]["target_config"]["target_watts"], expected["target_watts"])
                if "duration_min" in expected:
                    self.assertEqual(body["goal"]["target_config"]["duration_min"], expected["duration_min"])

        saveable = self.client.post("/goals/draft", json={"text": "lift twice per week"})
        self.assertEqual(saveable.status_code, 200)
        saveable_body = saveable.json()
        self.assertTrue(saveable_body["is_ready"])

        created = self.client.post("/goals", json=saveable_body["goal"])
        self.assertEqual(created.status_code, 201)

        warning_case = self.client.post("/goals/draft", json={"text": "ride more zone 2"})
        self.assertEqual(warning_case.status_code, 200)
        warning_body = warning_case.json()
        self.assertTrue(warning_body["is_supported"])
        self.assertFalse(warning_body["is_ready"])
        self.assertIn("target_value", warning_body["missing_fields"])
        self.assertGreaterEqual(len(warning_body["warnings"]), 1)

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

    def test_richer_goal_families_surface_in_goals_dashboard_and_coaching(self):
        today = datetime.now().date()
        event_date = today + timedelta(days=45)

        run_activity = self.client.post(
            "/activities",
            json={
                "id": "goal-family-run-1",
                "date": (today - timedelta(days=3)).isoformat(),
                "type": "Run",
                "name": "10k tempo",
                "distance_km": 10.1,
                "duration_min": 42.5,
            },
        )
        self.assertEqual(run_activity.status_code, 201)

        ride_activity = self.client.post(
            "/activities",
            json={
                "id": "goal-family-ride-1",
                "date": (today - timedelta(days=2)).isoformat(),
                "type": "Ride",
                "name": "Threshold climb",
                "duration_min": 75,
                "avg_watts": 286,
            },
        )
        self.assertEqual(ride_activity.status_code, 201)

        event_goal = self.client.post(
            "/goals",
            json={
                "title": "Run autumn 10k under 40",
                "period_type": "year",
                "goal_family": "event_performance",
                "activity_type": "Run",
                "end_date": event_date.isoformat(),
                "target_config": {
                    "distance_km": 10,
                    "target_duration_min": 40,
                },
            },
        )
        self.assertEqual(event_goal.status_code, 201)

        benchmark_goal = self.client.post(
            "/goals",
            json={
                "title": "Hold 300W for 10 minutes",
                "period_type": "month",
                "goal_family": "benchmark",
                "activity_type": "Ride",
                "target_config": {
                    "duration_min": 10,
                    "target_watts": 300,
                },
            },
        )
        self.assertEqual(benchmark_goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        body = goals.json()
        event_item = next(item for item in body if item["title"] == "Run autumn 10k under 40")
        benchmark_item = next(item for item in body if item["title"] == "Hold 300W for 10 minutes")
        self.assertEqual(event_item["goal_family"], "event_performance")
        self.assertEqual(event_item["family_label"], "Event")
        self.assertEqual(event_item["display_mode"], "performance")
        self.assertIn("10 km", event_item["target_summary"])
        self.assertEqual(event_item["derived_foundation"]["status"], "available")
        self.assertEqual(benchmark_item["goal_family"], "benchmark")
        self.assertEqual(benchmark_item["performance_snapshot"]["recent_best_watts"], 286)
        self.assertEqual(benchmark_item["derived_foundation"]["status"], "available")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        dashboard_goals = dashboard.json()["active_goals"]
        self.assertTrue(any(item["goal_family"] == "event_performance" for item in dashboard_goals))
        self.assertTrue(any(item["goal_family"] == "benchmark" for item in dashboard_goals))

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        observations = coaching.json()["goal_assessment"]["key_observations"]
        self.assertTrue(any("event" in item.lower() or "benchmark" in item.lower() for item in observations))

    def test_weekly_goal_uses_current_week_window_not_creation_week(self):
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        previous_week_day = current_week_start - timedelta(days=2)

        previous_ride = self.client.post(
            "/activities",
            json={
                "id": "weekly-goal-window-ride-1",
                "date": previous_week_day.isoformat(),
                "type": "Ride",
                "name": "Previous week ride",
                "distance_km": 168.1,
                "duration_min": 300,
            },
        )
        self.assertEqual(previous_ride.status_code, 201)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 100km weekly",
                "period_type": "week",
                "goal_family": "accumulation",
                "metric_type": "ride_km",
                "target_value": 100,
            },
        )
        self.assertEqual(goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        weekly_goal = next(item for item in goals.json() if item["title"] == "Ride 100km weekly")
        self.assertEqual(weekly_goal["current_value"], 0.0)
        self.assertEqual(weekly_goal["remaining_value"], 100.0)

    def test_weekly_goal_ignores_stale_stored_dates_from_previous_week(self):
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        previous_week_start = current_week_start - timedelta(days=7)
        previous_week_day = previous_week_start + timedelta(days=2)

        previous_ride = self.client.post(
            "/activities",
            json={
                "id": "weekly-goal-stale-date-ride-1",
                "date": previous_week_day.isoformat(),
                "type": "Ride",
                "name": "Previous week big ride",
                "distance_km": 168.1,
                "duration_min": 300,
            },
        )
        self.assertEqual(previous_ride.status_code, 201)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 100km weekly stale dates",
                "period_type": "week",
                "goal_family": "accumulation",
                "metric_type": "ride_km",
                "target_value": 100,
                "start_date": previous_week_start.isoformat(),
                "end_date": (previous_week_start + timedelta(days=6)).isoformat(),
            },
        )
        self.assertEqual(goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        weekly_goal = next(item for item in goals.json() if item["title"] == "Ride 100km weekly stale dates")
        self.assertEqual(weekly_goal["start_date"], current_week_start.isoformat())
        self.assertEqual(weekly_goal["current_value"], 0.0)
        self.assertEqual(weekly_goal["remaining_value"], 100.0)

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
        self.assertEqual(run_day["goal_links"][0]["requirement_type"], "aerobic_volume")
        self.assertEqual(run_day["goal_links"][0]["support_level"], "strong")
        self.assertEqual(strength_day["goal_links"], [])

    def test_goal_requirements_surface_for_multiple_goal_families(self):
        today = datetime.now().date()
        event_date = today + timedelta(days=28)

        process_goal = self.client.post(
            "/goals",
            json={
                "title": "Keep two strength sessions weekly",
                "period_type": "week",
                "goal_family": "process",
                "metric_type": "strength_sessions",
                "target_value": 2,
            },
        )
        self.assertEqual(process_goal.status_code, 201)

        event_goal = self.client.post(
            "/goals",
            json={
                "title": "10k under 42",
                "period_type": "year",
                "goal_family": "event_performance",
                "activity_type": "Run",
                "end_date": event_date.isoformat(),
                "target_config": {
                    "distance_km": 10,
                    "target_duration_min": 42,
                },
            },
        )
        self.assertEqual(event_goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        body = goals.json()
        process_item = next(item for item in body if item["title"] == "Keep two strength sessions weekly")
        event_item = next(item for item in body if item["title"] == "10k under 42")

        self.assertEqual(process_item["weekly_requirements"][0]["type"], "strength_frequency")
        self.assertEqual(process_item["weekly_requirements"][0]["minimum_sessions"], 2)
        self.assertIn("strength sessions", process_item["weekly_requirement_summary"].lower())

        event_requirement_types = [item["type"] for item in event_item["weekly_requirements"]]
        self.assertIn("event_specific_quality", event_requirement_types)
        self.assertIn("long_aerobic_support", event_requirement_types)
        self.assertIn("event-specific", event_item["weekly_requirement_summary"].lower())

    def test_goal_readiness_surfaces_underprepared_stale_and_next_step_guidance(self):
        today = datetime.now().date()
        event_date = today + timedelta(days=28)

        self._create_activity(
            "goal-readiness-run-benchmark",
            (today - timedelta(days=50)).isoformat(),
            "Run",
            name="10k benchmark",
            distance_km=10.0,
            duration_min=42.5,
            avg_hr=168,
            zone2=False,
        )
        self._create_activity(
            "goal-readiness-ride-benchmark",
            (today - timedelta(days=40)).isoformat(),
            "Ride",
            name="Old power test",
            duration_min=12.0,
            avg_watts=288,
            avg_hr=164,
            zone2=False,
        )

        event_goal = self.client.post(
            "/goals",
            json={
                "title": "Autumn 10k under 40",
                "period_type": "year",
                "goal_family": "event_performance",
                "activity_type": "Run",
                "end_date": event_date.isoformat(),
                "target_config": {
                    "distance_km": 10,
                    "target_duration_min": 40,
                },
            },
        )
        self.assertEqual(event_goal.status_code, 201)

        benchmark_goal = self.client.post(
            "/goals",
            json={
                "title": "Hold 300W for 10 minutes",
                "period_type": "month",
                "goal_family": "benchmark",
                "activity_type": "Ride",
                "target_config": {
                    "duration_min": 10,
                    "target_watts": 300,
                },
            },
        )
        self.assertEqual(benchmark_goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        body = goals.json()
        event_item = next(item for item in body if item["title"] == "Autumn 10k under 40")
        benchmark_item = next(item for item in body if item["title"] == "Hold 300W for 10 minutes")

        self.assertEqual(event_item["goal_readiness"]["state"], "underprepared")
        self.assertEqual(event_item["goal_readiness"]["what_matters_next"]["code"], "event_specific_quality")
        self.assertEqual(benchmark_item["goal_readiness"]["state"], "stale")
        self.assertEqual(benchmark_item["goal_readiness"]["what_matters_next"]["code"], "benchmark_specific_quality")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["goal_readiness_summary"]["status"], "underprepared")
        self.assertEqual(dashboard.json()["goal_readiness_summary"]["focus_goal"]["title"], "Autumn 10k under 40")

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        observations = coaching.json()["goal_assessment"]["key_observations"]
        self.assertTrue(any("Autumn 10k under 40" in item for item in observations))

    def test_goal_readiness_distinguishes_consistent_and_inconsistent_process_support(self):
        today = datetime.now().date()
        self._create_activity(
            "goal-ready-strength-1",
            (today - timedelta(days=1)).isoformat(),
            "WeightTraining",
            name="Upper strength",
            workout_intent="strength_upper",
            duration_min=48.0,
            distance_km=None,
        )
        self._create_activity(
            "goal-ready-strength-2",
            (today - timedelta(days=4)).isoformat(),
            "WeightTraining",
            name="Lower strength",
            workout_intent="strength_lower",
            duration_min=52.0,
            distance_km=None,
        )

        ready_goal = self.client.post(
            "/goals",
            json={
                "title": "Strength twice weekly",
                "period_type": "week",
                "goal_family": "process",
                "metric_type": "strength_sessions",
                "target_value": 2,
            },
        )
        self.assertEqual(ready_goal.status_code, 201)

        inconsistent_goal = self.client.post(
            "/goals",
            json={
                "title": "Run three times weekly",
                "period_type": "week",
                "goal_family": "process",
                "metric_type": "activities_count",
                "target_value": 3,
                "activity_type": "Run",
            },
        )
        self.assertEqual(inconsistent_goal.status_code, 201)

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        body = goals.json()
        ready_item = next(item for item in body if item["title"] == "Strength twice weekly")
        inconsistent_item = next(item for item in body if item["title"] == "Run three times weekly")

        self.assertEqual(ready_item["goal_readiness"]["state"], "ready")
        self.assertEqual(inconsistent_item["goal_readiness"]["state"], "inconsistent")
        self.assertEqual(inconsistent_item["goal_readiness"]["what_matters_next"]["code"], "session_frequency")

    def test_plan_and_coaching_surface_requirement_gaps_and_goal_tradeoffs(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        second_day = week_start + timedelta(days=1)
        third_day = week_start + timedelta(days=2)
        week_end = week_start + timedelta(days=6)
        event_date = today + timedelta(days=35)

        run_goal = self.client.post(
            "/goals",
            json={
                "title": "Autumn 10k under 40",
                "period_type": "year",
                "goal_family": "event_performance",
                "activity_type": "Run",
                "end_date": event_date.isoformat(),
                "target_config": {
                    "distance_km": 10,
                    "target_duration_min": 40,
                },
            },
        )
        self.assertEqual(run_goal.status_code, 201)

        strength_goal = self.client.post(
            "/goals",
            json={
                "title": "Strength twice weekly",
                "period_type": "week",
                "goal_family": "process",
                "metric_type": "strength_sessions",
                "target_value": 2,
            },
        )
        self.assertEqual(strength_goal.status_code, 201)

        benchmark_goal = self.client.post(
            "/goals",
            json={
                "title": "Hold 300W for 10 minutes",
                "period_type": "month",
                "goal_family": "benchmark",
                "activity_type": "Ride",
                "target_config": {
                    "duration_min": 10,
                    "target_watts": 300,
                },
            },
        )
        self.assertEqual(benchmark_goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Competing goals week",
                "days": [
                    {
                        "date": week_start.isoformat(),
                        "label": week_start.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "tempo",
                        "title": "10k pace work",
                        "target_duration_min": 50,
                    },
                    {
                        "date": second_day.isoformat(),
                        "label": second_day.strftime("%a"),
                        "session_type": "Ride",
                        "workout_intent": "interval",
                        "title": "Threshold ride",
                        "target_duration_min": 70,
                    },
                    {
                        "date": third_day.isoformat(),
                        "label": third_day.strftime("%a"),
                        "session_type": "Run",
                        "workout_intent": "easy",
                        "title": "Easy run",
                        "target_duration_min": 40,
                    },
                    # Real plans cover the whole week; a goal created later in
                    # the week (today) must still fall inside the plan window.
                    {
                        "date": week_end.isoformat(),
                        "label": week_end.strftime("%a"),
                        "session_type": "Rest",
                        "title": "Rest",
                        "target_duration_min": 0,
                    },
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=4")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        goal_context = target_plan["goal_context"]
        self.assertGreaterEqual(len(goal_context["conflicts"]), 1)

        strength_item = next(item for item in goal_context["active_goals"] if item["title"] == "Strength twice weekly")
        self.assertEqual(strength_item["requirement_support_status"], "unsupported")
        self.assertEqual(strength_item["unsupported_requirements"][0]["type"], "strength_frequency")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertGreaterEqual(len(dashboard.json()["goal_planning_summary"]["conflicts"]), 1)

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        coaching_body = coaching.json()
        self.assertGreaterEqual(coaching_body["goal_assessment"]["unsupported_goal_count"], 1)
        self.assertGreaterEqual(coaching_body["goal_assessment"]["conflict_count"], 1)
        self.assertTrue(any("unsupported this week" in item.lower() or "tradeoff" in item.lower() for item in coaching_body["goal_assessment"]["key_observations"]))
        goal_support = [
            *coaching_body["recommendation"]["primary_support"],
            *coaching_body["recommendation"]["secondary_support"],
        ]
        self.assertTrue(any("Autumn 10k under 40" in item for item in goal_support))
        strength_guidance = [
            *coaching_body["recommendation"]["primary_support"],
            *coaching_body["recommendation"]["secondary_support"],
            *coaching_body["recommendation"]["deprioritized_work"],
        ]
        self.assertTrue(any("Strength twice weekly" in item for item in strength_guidance))
        recent_pattern_text = {
            item.strip().lower()
            for item in coaching_body["reasoning_signals"]["recent_pattern_summary"]["key_observations"]
        }
        rationale_text = {
            item.strip().lower()
            for item in coaching_body["recommendation"]["rationale"]
        }
        self.assertTrue(recent_pattern_text.isdisjoint(rationale_text))

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

    def test_benchmark_tagged_plan_sessions_surface_on_activities_and_goals(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        benchmark_day = week_start + timedelta(days=2)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Hold 300W for 10 minutes",
                "period_type": "month",
                "goal_family": "benchmark",
                "activity_type": "Ride",
                "target_config": {
                    "duration_min": 10,
                    "target_watts": 300,
                },
            },
        )
        self.assertEqual(goal.status_code, 201)

        plan = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start.isoformat(),
                "title": "Benchmark week",
                "days": [
                    {
                        "date": benchmark_day.isoformat(),
                        "label": benchmark_day.strftime("%a"),
                        "session_type": "Ride",
                        "workout_intent": "interval",
                        "benchmark_tag": "test",
                        "benchmark_label": "FTP check",
                        "title": "10-minute power test",
                        "target_duration_min": 60,
                        "details": "Warm up, then one clear 10-minute test effort.",
                    }
                ],
            },
        )
        self.assertEqual(plan.status_code, 201)

        plans = self.client.get("/plans/weekly?limit=8")
        self.assertEqual(plans.status_code, 200)
        target_plan = next(item for item in plans.json() if item["week_start"] == week_start.isoformat())
        plan_day = target_plan["days"][0]
        self.assertEqual(plan_day["benchmark_tag"], "test")
        self.assertEqual(plan_day["benchmark_label"], "FTP check")

        activity = self.client.post(
            "/activities",
            json={
                "id": "benchmark-ride-1",
                "date": benchmark_day.isoformat(),
                "type": "Ride",
                "name": "10-minute test",
                "duration_min": 62,
                "avg_watts": 295,
                "zone2": False,
            },
        )
        self.assertEqual(activity.status_code, 201)

        link = self.client.post(
            "/activities/benchmark-ride-1/link-plan",
            json={"planned_session_id": plan_day["session_id"]},
        )
        self.assertEqual(link.status_code, 200)

        activities = self.client.get("/activities?limit=32")
        self.assertEqual(activities.status_code, 200)
        linked_activity = next(item for item in activities.json() if item["id"] == "benchmark-ride-1")
        self.assertEqual(linked_activity["benchmark_tag"], "test")
        self.assertEqual(linked_activity["benchmark_label"], "FTP check")

        goals = self.client.get("/goals")
        self.assertEqual(goals.status_code, 200)
        benchmark_goal = next(item for item in goals.json() if item["title"] == "Hold 300W for 10 minutes")
        self.assertEqual(benchmark_goal["benchmark_history"]["status"], "available")
        self.assertEqual(benchmark_goal["benchmark_history"]["latest"]["benchmark_label"], "FTP check")
        self.assertTrue(benchmark_goal["benchmark_history"]["latest"]["is_tagged_benchmark"])

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


if __name__ == "__main__":
    unittest.main()
