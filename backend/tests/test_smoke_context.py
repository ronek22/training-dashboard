"""App smoke tests: Readiness, athlete profile, life load, sick mode and other daily context."""
import os
import sqlite3
import unittest
import json
from datetime import date, datetime, timedelta
from backend.tests import smoke_base


class ContextSmokeTests(smoke_base.SmokeTestCase):
    def test_readiness_strained_state_surfaces_when_feedback_and_load_stack(self):
        today = datetime.now().date()
        self._create_activity(
            "strained-run-1",
            today.isoformat(),
            "Run",
            name="Threshold Run",
            workout_intent="tempo",
            duration_min=58.0,
            distance_km=11.2,
            avg_hr=171,
            zone2=False,
        )
        self._create_activity(
            "strained-run-2",
            (today - timedelta(days=1)).isoformat(),
            "Run",
            name="Intervals",
            workout_intent="interval",
            duration_min=54.0,
            distance_km=9.6,
            avg_hr=174,
            zone2=False,
        )
        self._create_activity(
            "strained-strength",
            (today - timedelta(days=3)).isoformat(),
            "WeightTraining",
            name="Heavy Lower",
            workout_intent="strength_lower",
            duration_min=52.0,
            distance_km=None,
        )
        self._save_feedback(
            "strained-run-1",
            rpe=9,
            energy=2,
            muscle_soreness=4,
            pain_level=5,
            note="Legs were cooked.",
        )
        self._save_feedback(
            "strained-run-2",
            rpe=8,
            energy=2,
            muscle_soreness=4,
            pain_level=4,
            note="Could not lift the pace late.",
        )

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        readiness = dashboard.json()["readiness"]
        self.assertEqual(readiness["state"], "strained")
        self.assertTrue(readiness["reasons"])

        coaching = self.client.get("/coaching/weekly")
        self.assertEqual(coaching.status_code, 200)
        self.assertEqual(coaching.json()["readiness_assessment"]["state"], "strained")
        self.assertIn(coaching.json()["recommendation"]["status"], {"reduce", "recover"})

    def test_readiness_insufficient_data_is_explicit(self):
        today = datetime.now().date()
        self._create_activity(
            "insufficient-walk",
            (today - timedelta(days=1)).isoformat(),
            "Walk",
            name="Short Walk",
            duration_min=24.0,
            distance_km=2.1,
            avg_hr=None,
            avg_watts=None,
            zone2=None,
        )

        recent_context = self.client.get("/context/recent")
        self.assertEqual(recent_context.status_code, 200)
        readiness = recent_context.json()["readiness"]
        self.assertEqual(readiness["state"], "insufficient_data")
        self.assertFalse(readiness["available"])
        self.assertTrue(readiness["guidance_48h"])

    def test_athlete_profile_can_be_read_back_after_persisting_normalized_shape(self):
        initial = self.client.put(
            "/settings/athlete-profile",
            json={
                "primary_focus": "hybrid",
                "modality_preferences": ["ride", "strength", "run"],
                "current_block": "Cycling-first rebuild",
                "preferred_long_session_days": ["sat", "sun"],
                "weekly_availability_notes": "Weekdays are short.",
                "planning_notes": "Avoid stacking run progression and hard strength on the same day.",
                "bar_weight_kg": 15,
                "plates": [{"kg": 20, "count": 4}, {"kg": 10, "count": 2}, {"kg": 2.5, "count": 3}],
            },
        )
        self.assertEqual(initial.status_code, 200)

        reread = self.client.get("/settings/athlete-profile")
        self.assertEqual(reread.status_code, 200)
        body = reread.json()
        self.assertEqual(body["primary_focus"], "hybrid")
        self.assertEqual(body["bar_weight_kg"], 15)
        self.assertEqual(body["plates"], [{"kg": 20, "count": 4}, {"kg": 10, "count": 2}, {"kg": 2.5, "count": 3}])
        self.assertEqual(body["athlete_brief"]["modality_priority"], ["ride", "strength", "run"])
        self.assertEqual(body["athlete_brief"]["preferred_long_session_days"], ["sat", "sun"])

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["athlete_brief"]["modality_priority"], ["ride", "strength", "run"])

    def test_recent_context_mcp_tool_is_compact_by_default(self):
        compact = self.call_tool("get_recent_context", {})
        self.assertFalse(compact.get("isError"))
        self.assertEqual(compact["structuredContent"]["detail"], "compact")
        self.assertNotIn("workout_template_settings", compact["structuredContent"])
        full = self.call_tool("get_recent_context", {"detail": "full"})
        self.assertNotIn("detail", full["structuredContent"])
        self.assertIn("workout_template_settings", full["structuredContent"])
        self.assertLess(len(compact["content"][0]["text"]), len(full["content"][0]["text"]))

    def test_aerobic_fitness_trend_endpoint_and_mcp_tool(self):
        response = self.client.get("/metrics/aerobic-decoupling", params={"weeks": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["window"]["weeks"], 8)
        self.assertIn(response.json()["status"], {"available", "unavailable"})
        self.assertEqual(self.client.get("/metrics/aerobic-decoupling", params={"weeks": 2}).status_code, 422)
        result = self.call_tool("get_aerobic_fitness_trend", {"weeks": 12})
        self.assertFalse(result.get("isError"))
        self.assertEqual(result["structuredContent"]["window"]["weeks"], 12)

    def test_life_load_and_minimum_week_mcp_tools(self):
        names = {tool["name"] for tool in self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]}
        self.assertTrue({"get_life_load", "set_life_load_day", "preview_minimum_week", "set_minimum_week"} <= names)

        today = date.today()
        week_start = today + timedelta(days=7 - today.weekday())
        thursday = (week_start + timedelta(days=3)).isoformat()
        saved = self.call_tool("set_life_load_day", {"date": thursday, "tags": ["travel"], "note": "Berlin"})
        self.assertEqual(saved["structuredContent"]["day"]["labels"], ["Travel"])
        self.assertIn("Travel", saved["content"][0]["text"])
        self.assertTrue(self.call_tool("set_life_load_day", {"date": thursday, "tags": ["vacation"]})["isError"])
        listed = self.call_tool("get_life_load", {"start": week_start.isoformat(), "end": thursday})["structuredContent"]
        self.assertEqual([(day["date"], day["note"]) for day in listed["days"]], [(thursday, "Berlin")])

        days = [
            {"date": (week_start + timedelta(days=index)).isoformat(), "label": (week_start + timedelta(days=index)).strftime("%a"),
             "session_type": kind, "workout_intent": "interval" if kind == "Ride" else None,
             "title": "Strength" if kind == "WeightTraining" else "Ride session", "target_duration_min": 70}
            for index, kind in enumerate(["WeightTraining", "Ride", "WeightTraining", "Ride", "Ride", "WeightTraining", "Ride"])
        ]
        self.assertEqual(self.client.post("/plans/weekly", json={"week_start": week_start.isoformat(), "title": "Full", "days": days}).status_code, 201)
        preview = self.call_tool("preview_minimum_week", {"week_start": week_start.isoformat()})["structuredContent"]
        self.assertEqual(next(day for day in preview["days"] if day["date"] == thursday)["session_type"], "Rest")

        shrunk = self.call_tool("set_minimum_week", {"active": True, "week_start": week_start.isoformat()})
        self.assertFalse(shrunk.get("isError"))
        self.assertIn("Minimum viable week on", shrunk["content"][0]["text"])
        self.assertTrue(next(plan for plan in self.client.get("/plans/weekly").json() if plan["week_start"] == week_start.isoformat())["minimum_week"]["active"])
        restored = self.call_tool("set_minimum_week", {"active": False, "week_start": week_start.isoformat()})
        self.assertIn("restored", restored["content"][0]["text"])
        again = self.call_tool("set_minimum_week", {"active": False, "week_start": week_start.isoformat()})
        self.assertTrue(again["isError"])
        self.assertIn("not a minimum viable week", again["content"][0]["text"])

    def test_minimum_viable_week_round_trip(self):
        today = date.today()
        week_start = today + timedelta(days=7 - today.weekday())
        kinds = ["WeightTraining", "Ride", "WeightTraining", "Ride", "Run", "WeightTraining", "Ride"]
        days = [
            {
                "date": (week_start + timedelta(days=index)).isoformat(),
                "label": (week_start + timedelta(days=index)).strftime("%a"),
                "session_type": kind,
                "workout_intent": {"Ride": "interval", "Run": "easy"}.get(kind),
                "title": "Strength" if kind == "WeightTraining" else f"{kind} session",
                "target_duration_min": 75,
            }
            for index, kind in enumerate(kinds)
        ]
        self.assertEqual(self.client.post("/plans/weekly", json={"week_start": week_start.isoformat(), "title": "Full week", "days": days}).status_code, 201)
        self.assertEqual(self.client.post(f"/plans/weekly/{week_start + timedelta(days=7)}/minimum-week/preview").status_code, 404)

        preview = self.client.post(f"/plans/weekly/{week_start}/minimum-week/preview").json()
        self.assertEqual(preview["targets"], {"lifts": 2, "rides": 2})
        self.assertTrue(preview["diff"])
        plan = next(item for item in self.client.get("/plans/weekly").json() if item["week_start"] == week_start.isoformat())
        self.assertIsNone(plan["minimum_week"])

        applied = self.client.post(f"/plans/weekly/{week_start}/minimum-week").json()
        plan_days = applied["plan"]["days"]
        lifts = [day for day in plan_days if day["session_type"] == "WeightTraining"]
        self.assertEqual(len(lifts), 2)
        self.assertTrue(all(day["template_id"] and day["target_duration_min"] == 30 for day in lifts))
        self.assertEqual(sum(1 for day in plan_days if day["session_type"] == "Ride" and day["workout_intent"] == "easy"), 2)
        self.assertTrue(applied["plan"]["minimum_week"]["active"])
        self.assertIn("2 short lifts", applied["plan"]["minimum_week"]["summary"])

        restored = self.client.post(f"/plans/weekly/{week_start}/minimum-week/restore").json()
        self.assertIsNone(restored["plan"]["minimum_week"])
        self.assertEqual([day["session_type"] for day in restored["plan"]["days"]], kinds)
        self.assertEqual(self.client.post(f"/plans/weekly/{week_start}/minimum-week/restore").status_code, 400)

    def test_downshift_offer_and_streak(self):
        self.assertFalse(self.client.get("/downshift").json()["downshift"]["offer"])
        checkin = {"energy": 3, "muscle_soreness": 2, "stress": 5, "sleep_quality": 3}
        self.assertEqual(self.client.post("/checkins", json=checkin).status_code, 201)
        downshift = self.client.get("/dashboard").json()["downshift"]
        self.assertEqual(downshift["reasons"], ["stress 5/5 in today's check-in"])
        session = self.client.get("/guided-sessions/two_minute_downshift").json()["session"]
        self.assertEqual((session["duration_min"], session["context"]), (2, "stress"))

        self.assertEqual(self.client.get("/dashboard").json()["computed_streak"]["value"], 0)
        done = self.client.post("/guided-sessions/complete", json={"session_key": "two_minute_downshift", "started_at": f"{date.today()}T12:00:00Z", "elapsed_seconds": 125})
        self.assertEqual(done.json()["completed_today"][0]["title"], "Two-minute downshift")
        self.assertEqual(self.client.get("/dashboard").json()["computed_streak"]["value"], 1)
        self.assertEqual(self.client.post("/sick-mode/log", json={"session_key": "two_minute_downshift"}).status_code, 404)

    def test_sick_mode_endpoints_round_trip(self):
        self.assertEqual(self.client.get("/guided-sessions/sprints").status_code, 404)
        self.assertEqual(self.client.get("/guided-sessions/light_circuit").json()["session"]["duration_min"], 12)
        started = self.client.post("/sick-mode", json={"severity": "above_neck"})
        self.assertTrue(started.json()["sick_mode"]["active"])
        completion = {"session_key": "light_circuit", "started_at": "2026-10-01T18:06:00.000Z", "elapsed_seconds": 370, "extras": ["Pull-ups ×5"]}
        done = self.client.post("/guided-sessions/complete", json=completion)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(self.client.post("/guided-sessions/complete", json={**completion, "session_key": "sprints"}).status_code, 404)

        # A synced watch workout on the same day picks up the guided session.
        today = date.today().isoformat()
        watch = {"id": "watch-core", "date": today, "type": "WeightTraining", "name": "Evening Workout", "duration_min": 10.1, "avg_hr": 119, "max_hr": 142}
        self.assertEqual(self.client.post("/activities", json=watch).status_code, 201)
        with sqlite3.connect(os.environ["TRAINING_DB_PATH"]) as conn:
            conn.execute(
                "INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'watch-core', 'watch-core', ?)",
                (f"{today}T18:07:34+00:00",),
            )
        guided = {**completion, "started_at": f"{today}T18:06:00Z"}
        self.client.post("/guided-sessions/complete", json=guided)
        detail = self.client.get("/activities/watch-core").json()
        self.assertIsNone(detail["strength_detail"])
        self.assertEqual(detail["sick_session"]["extras"], ["Pull-ups ×5"])
        context = self.client.get("/activities/watch-core/analysis/context").json()
        self.assertTrue(context["available"])
        self.assertEqual(context["context"]["sick_session"]["title"], "Light bodyweight circuit")
        self.assertIn(today, self.client.get("/sick-mode/dates").json()["dates"])
        self.assertFalse(self.client.post("/sick-mode/end").json()["sick_mode"]["active"])

    def test_performance_settings_and_zone_foundation_surface_available_and_missing_states(self):
        today = datetime.now().date()
        zone_activity = self.client.post(
            "/activities",
            json={
                "id": "zone-foundation-ride-1",
                # Today, not yesterday: on a Monday yesterday is last week, outside the weekly goal.
                "date": today.isoformat(),
                "type": "Ride",
                "name": "Aerobic ride",
                "duration_min": 90,
                "avg_watts": 170,
            },
        )
        self.assertEqual(zone_activity.status_code, 201)

        goal = self.client.post(
            "/goals",
            json={
                "title": "Ride 4 hours of zone 2 per week",
                "period_type": "week",
                "goal_family": "process",
                "metric_type": "zone2_hours",
                "target_value": 4,
                "activity_type": "Ride",
            },
        )
        self.assertEqual(goal.status_code, 201)

        performance_summary = self.client.get("/metrics/performance-summary")
        self.assertEqual(performance_summary.status_code, 200)
        self.assertFalse(performance_summary.json()["derived"]["zone2_foundation"]["available"])

        goals_without_anchor = self.client.get("/goals")
        self.assertEqual(goals_without_anchor.status_code, 200)
        zone_goal_without_anchor = next(item for item in goals_without_anchor.json() if item["title"] == "Ride 4 hours of zone 2 per week")
        self.assertEqual(zone_goal_without_anchor["derived_foundation"]["status"], "unavailable")
        self.assertEqual(zone_goal_without_anchor["current_value"], 0.0)

        settings_update = self.client.put(
            "/settings/performance",
            json={
                "anchors": {
                    "ride_threshold_power": {"value": 240, "unit": "W"},
                },
                "zones": {
                    "ride": {"zone2_lower_pct": 0.56, "zone2_upper_pct": 0.75},
                },
            },
        )
        self.assertEqual(settings_update.status_code, 200)
        self.assertTrue(settings_update.json()["anchors"]["ride_threshold_power"]["is_set"])

        performance_summary_ready = self.client.get("/metrics/performance-summary")
        self.assertEqual(performance_summary_ready.status_code, 200)
        ready_body = performance_summary_ready.json()
        self.assertTrue(ready_body["derived"]["zone2_foundation"]["available"])
        self.assertEqual(ready_body["derived"]["zone2_foundation"]["longest_recent_block_min"], 90.0)

        goals_with_anchor = self.client.get("/goals")
        self.assertEqual(goals_with_anchor.status_code, 200)
        zone_goal_with_anchor = next(item for item in goals_with_anchor.json() if item["title"] == "Ride 4 hours of zone 2 per week")
        self.assertEqual(zone_goal_with_anchor["derived_foundation"]["status"], "available")
        self.assertEqual(zone_goal_with_anchor["current_value"], 1.5)


if __name__ == "__main__":
    unittest.main()
