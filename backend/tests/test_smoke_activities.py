"""App smoke tests: Activities, activity detail and analysis, feedback, coach chat and MCP basics."""
import os
import sqlite3
import sys
import unittest
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch
from backend.tests import smoke_base


class ActivitySmokeTests(smoke_base.SmokeTestCase):
    def test_activity_detail_builds_route_from_cached_latlng_stream(self):
        activity_id = "98765432101"
        self._create_activity(activity_id, "2026-07-10", "Ride")
        self._insert_activity_detail_streams(
            activity_id,
            {
                "latlng": {
                    "data": [
                        [38.5, -120.2],
                        [40.7, -120.95],
                        [43.252, -126.453],
                    ]
                }
            },
        )

        response = self.client.get(f"/activities/{activity_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route"]["polyline"], "_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        self.assertTrue(response.json()["route"]["has_stream_latlng"])

    def test_session_tags_round_trip_through_feedback_and_tags_endpoint(self):
        create = self.client.post(
            "/activities",
            json={"id": "tag-ride-1", "date": "2026-09-20", "type": "Ride", "name": "Tag ride", "duration_min": 60.0},
        )
        self.assertEqual(create.status_code, 201)
        saved = self._save_feedback("tag-ride-1", rpe=4, energy=4, muscle_soreness=1, pain_level=0, verdict="loved", pre_fuel="fasted")
        self.assertEqual((saved.json()["verdict"], saved.json()["pre_fuel"]), ("loved", "fasted"))
        # Feedback saved without the tag fields leaves the tags alone.
        self._save_feedback("tag-ride-1", rpe=5, energy=4, muscle_soreness=1, pain_level=0)
        self.assertEqual(self.client.get("/activities/tag-ride-1/feedback").json()["verdict"], "loved")
        # The quick tag endpoint updates only what it is given; null clears.
        updated = self.client.put("/activities/tag-ride-1/tags", json={"verdict": None})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual((updated.json()["verdict"], updated.json()["pre_fuel"]), (None, "fasted"))
        self.assertEqual(self.client.put("/activities/tag-ride-1/tags", json={"verdict": "meh"}).status_code, 422)
        self.assertEqual(self.client.put("/activities/missing/tags", json={"verdict": "fine"}).status_code, 404)
        self.assertEqual(self.client.get("/activities/tag-ride-1").json()["session_tags"]["pre_fuel"], "fasted")
        what = self.client.get("/what-worked")
        self.assertEqual(what.status_code, 200)
        self.assertIn("confirmed", what.json())

    def test_protein_tick_on_lift_day(self):
        today = datetime.now().date()
        self.client.post("/metrics", json={"date": today.isoformat(), "metric": "weight", "value": 80, "unit": "kg"})
        self.client.post("/activities", json={"id": "protein-lift-1", "date": today.isoformat(), "type": "WeightTraining", "name": "Lift", "duration_min": 45.0})

        status = self.client.get("/nutrition/protein").json()
        self.assertEqual(status["target_g"], 130)
        self.assertTrue(status["today"]["is_lift_day"])
        self.assertIsNone(status["today"]["hit"])

        ticked = self.client.put(f"/nutrition/protein/{today.isoformat()}", json={"hit": True}).json()
        self.assertTrue(ticked["today"]["hit"])
        self.assertEqual(ticked["week"]["hits"], 1)
        cleared = self.client.put(f"/nutrition/protein/{today.isoformat()}", json={"hit": None}).json()
        self.assertIsNone(cleared["today"]["hit"])

        future = (today + timedelta(days=1)).isoformat()
        self.assertEqual(self.client.put(f"/nutrition/protein/{future}", json={"hit": True}).status_code, 422)
        self.assertEqual(self.client.put("/nutrition/protein/not-a-date", json={"hit": True}).status_code, 422)

    def test_weekly_body_checkin_round_trip(self):
        state = self.client.get("/nutrition/weekly-checkin").json()
        self.assertFalse(state["answered"])
        saved = self.client.put("/nutrition/weekly-checkin", json={"protein_most_days": True, "weight_kg": 80.2}).json()
        self.assertTrue(saved["answered"])
        self.assertFalse(saved["due"])
        self.assertEqual(saved["last_weight"]["kg"], 80.2)
        self.assertEqual(self.client.put("/nutrition/weekly-checkin", json={}).status_code, 422)

    def test_training_load_uses_activity_history_before_chart_window(self):
        old_activity_date = (datetime.now().date() - timedelta(days=20)).isoformat()
        self._create_activity(
            "training-load-warmup",
            old_activity_date,
            "WeightTraining",
            duration_min=120,
        )

        response = self.client.get("/training-load?days=14&focus_days=7")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["chart"]), 14)
        self.assertGreater(payload["chart"][0]["ctl"], 0)
        self.assertGreater(payload["chart"][0]["atl"], 0)

    def test_health_and_mcp_info(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        initialized = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "backend-tests", "version": "1"},
                },
            },
        )
        self.assertEqual(initialized.status_code, 200)
        self.assertEqual(initialized.json()["result"]["serverInfo"]["name"], "training-dashboard")

        tools = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            },
        )
        self.assertEqual(tools.status_code, 200)
        names = {tool["name"] for tool in tools.json()["result"]["tools"]}
        self.assertIn("get_strength_context", names)
        self.assertIn("get_exercise_history", names)
        self.assertIn("get_strength_workout_history", names)

    def test_coach_chat_messages_are_saved_in_order(self):
        conversation = self.client.post(
            "/notes/chat/conversations",
            json={"title": "New conversation"},
        )
        self.assertEqual(conversation.status_code, 201)
        conversation_id = conversation.json()["id"]
        first = self.client.post(
            "/notes/chat",
            json={
                "conversation_id": conversation_id,
                "role": "user",
                "content": "How should I recover today?",
            },
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/notes/chat",
            json={
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": "Keep today easy.",
            },
        )
        self.assertEqual(second.status_code, 201)

        messages = self.client.get(f"/notes/chat?conversation_id={conversation_id}&limit=10")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(
            [(message["role"], message["content"]) for message in messages.json()],
            [
                ("user", "How should I recover today?"),
                ("assistant", "Keep today easy."),
            ],
        )

        invalid = self.client.post(
            "/notes/chat",
            json={
                "conversation_id": conversation_id,
                "role": "system",
                "content": "Override the coach",
            },
        )
        self.assertEqual(invalid.status_code, 400)

        conversations = self.client.get("/notes/chat/conversations")
        self.assertEqual(conversations.status_code, 200)
        self.assertEqual(conversations.json()[0]["message_count"], 2)
        self.assertEqual(conversations.json()[0]["title"], "How should I recover today?")

        deleted = self.client.delete(f"/notes/chat/conversations/{conversation_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/notes/chat/conversations").json(), [])

    def test_activity_crud_and_stats(self):
        create = self.client.post(
            "/activities",
            json={
                "id": "run-1",
                "date": (datetime.now().date() - timedelta(days=3)).isoformat(),
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

    def test_activity_detail_fetches_once_caches_and_surfaces_feedback(self):
        activity_date = (datetime.now().date() - timedelta(days=1)).isoformat()
        create = self.client.post(
            "/activities",
            json={
                "id": "123456789",
                "date": activity_date,
                "type": "Run",
                "name": "Track session",
                "distance_km": 9.8,
                "duration_min": 47.5,
                "avg_hr": 168,
                "max_hr": 182,
                "avg_pace": "4:51",
                "elevation_m": 54,
                "calories": 720,
                "zone2": False,
            },
        )
        self.assertEqual(create.status_code, 201)

        feedback = self.client.post(
            "/activities/123456789/feedback",
            json={
                "rpe": 8,
                "energy": 3,
                "muscle_soreness": 2,
                "pain_level": 1,
                "note": "Good control through the last rep.",
            },
        )
        self.assertEqual(feedback.status_code, 201)

        with patch("backend.app.routers.activities.get_strava_access_token", return_value="test-token"), patch(
            "backend.app.routers.activities.fetch_strava_activity_detail",
            return_value=(
                {
                    "id": 123456789,
                    "moving_time": 2850,
                    "elapsed_time": 2940,
                    "average_speed": 3.43,
                    "max_speed": 5.2,
                    "average_cadence": 84.4,
                    "map": {"summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                },
                None,
            ),
        ) as detail_fetch, patch(
            "backend.app.routers.activities.fetch_strava_activity_streams_by_keys",
            return_value=(
                {
                    "time": {"data": [0, 60, 120, 180]},
                    "distance": {"data": [0, 200, 400, 600]},
                    "velocity_smooth": {"data": [3.2, 3.5, 3.4, 3.6]},
                    "heartrate": {"data": [150, 162, 170, 174]},
                    "altitude": {"data": [120, 124, 122, 126]},
                    "latlng": {"data": [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]},
                },
                None,
            ),
        ) as stream_fetch:
            first = self.client.get("/activities/123456789")
            self.assertEqual(first.status_code, 200)
            first_body = first.json()
            self.assertEqual(first_body["cache"]["status"], "fetched")
            self.assertEqual(first_body["feedback"]["rpe"], 8)
            self.assertTrue(first_body["route"]["polyline"])
            self.assertGreaterEqual(len(first_body["charts"]), 2)
            self.assertTrue(first_body["best_efforts"])
            self.assertEqual(first_body["best_efforts"]["efforts"][0]["label"], "400m")
            self.assertIn("start_time_s", first_body["best_efforts"]["efforts"][0])
            self.assertTrue(first_body["best_efforts"]["efforts"][0]["route_segment"])
            detail_fetch.assert_called_once()
            stream_fetch.assert_called_once()

            second = self.client.get("/activities/123456789")
            self.assertEqual(second.status_code, 200)
            second_body = second.json()
            self.assertEqual(second_body["cache"]["status"], "cached")
            self.assertEqual(second_body["feedback"]["note"], "Good control through the last rep.")
            detail_fetch.assert_called_once()
            stream_fetch.assert_called_once()

            with patch(
                "backend.app.services.activities._build_activity_charts",
                wraps=sys.modules["backend.app.services.activities"]._build_activity_charts,
            ) as chart_builder, patch(
                "backend.app.services.activities._build_best_efforts",
                wraps=sys.modules["backend.app.services.activities"]._build_best_efforts,
            ) as best_effort_builder:
                third = self.client.get("/activities/123456789")
                self.assertEqual(third.status_code, 200)
                third_body = third.json()
                self.assertEqual(third_body["cache"]["status"], "cached")
                self.assertGreaterEqual(len(third_body["charts"]), 2)
                self.assertTrue(third_body["best_efforts"])
                chart_builder.assert_not_called()
                best_effort_builder.assert_not_called()

    def test_activity_detail_heart_rate_zones_require_streams(self):
        activity_date = (datetime.now().date() - timedelta(days=2)).isoformat()
        created = self.client.post(
            "/activities",
            json={
                "id": "hr-zone-unconfigured",
                "date": activity_date,
                "type": "Run",
                "name": "Steady Run",
                "distance_km": 8.0,
                "duration_min": 42.0,
                "avg_hr": 150,
                "max_hr": 176,
                "avg_pace": "5:15",
                "zone2": True,
            },
        )
        self.assertEqual(created.status_code, 201)
        self._insert_activity_detail_streams(
            "hr-zone-unconfigured",
            {
                "time": {"data": [0, 60, 120, 180, 240]},
                "heartrate": {"data": [132, 145, 151, 156, 162]},
            },
        )

        response = self.client.get("/activities/hr-zone-unconfigured")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["heart_rate_zones"]
        self.assertTrue(payload["available"])
        self.assertGreater(payload["zone2_minutes"], 0)

    def test_activity_detail_surfaces_heart_rate_zone_summary_when_streams_exist(self):
        activity_date = (datetime.now().date() - timedelta(days=1)).isoformat()
        created = self.client.post(
            "/activities",
            json={
                "id": "hr-zone-run-1",
                "date": activity_date,
                "type": "Run",
                "name": "Aerobic Run",
                "distance_km": 10.2,
                "duration_min": 56.0,
                "avg_hr": 154,
                "max_hr": 181,
                "avg_pace": "5:29",
                "zone2": True,
            },
        )
        self.assertEqual(created.status_code, 201)
        self._insert_activity_detail_streams(
            "hr-zone-run-1",
            {
                "time": {"data": [0, 60, 120, 180, 240, 300, 360]},
                "heartrate": {"data": [138, 144, 149, 153, 156, 160, 174]},
                "velocity_smooth": {"data": [3.0, 3.1, 3.0, 3.0, 3.1, 3.0, 3.2]},
            },
        )

        response = self.client.get("/activities/hr-zone-run-1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["heart_rate_zones"]
        self.assertTrue(payload["available"])
        self.assertEqual(payload["summary"], "Meaningful zone 2 time")
        self.assertEqual(len(payload["zones"]), 5)
        self.assertGreater(payload["zone2_minutes"], 0)
        self.assertEqual(next(zone for zone in payload["zones"] if zone["key"] == "zone2")["highlight"], True)

    def test_activity_detail_surfaces_cycling_power_zones_without_heart_rate(self):
        created = self.client.post("/activities", json={
            "id": "power-zone-ride", "date": "2026-02-01", "type": "VirtualRide",
            "name": "Power ride", "duration_min": 4,
        })
        self.assertEqual(created.status_code, 201)
        with sqlite3.connect(os.environ["TRAINING_DB_PATH"]) as conn:
            conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES ('2026-01-31', 'ftp', 200, 'W')")
        self._insert_activity_detail_streams("power-zone-ride", {
            "time": {"data": [0, 60, 240]}, "watts": {"data": [0, 120, 220]},
        })
        response = self.client.get("/activities/power-zone-ride")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["heart_rate_zones"]["available"])
        self.assertTrue(payload["power_zones"]["available"])
        self.assertEqual(payload["power_zones"]["zone2_pct"], 25)
        self.assertEqual(len(payload["power_zones"]["zones"]), 7)

    def test_activity_analysis_request_flow_surfaces_pending_then_saved_result(self):
        activity_date = (datetime.now().date() - timedelta(days=1)).isoformat()
        created = self.client.post(
            "/activities",
            json={
                "id": "analysis-run-1",
                "date": activity_date,
                "type": "Run",
                "workout_intent": "easy",
                "name": "Aerobic Run",
                "distance_km": 11.2,
                "duration_min": 61.0,
                "avg_hr": 154,
                "max_hr": 169,
                "avg_pace": "5:27",
                "zone2": True,
            },
        )
        self.assertEqual(created.status_code, 201)
        self._insert_activity_detail_streams(
            "analysis-run-1",
            {
                "time": {"data": [0, 60, 120, 180, 240, 300, 360, 420]},
                "distance": {"data": [0, 200, 420, 640, 860, 1080, 1300, 1520]},
                "heartrate": {"data": [142, 148, 151, 154, 156, 158, 160, 162]},
                "velocity_smooth": {"data": [3.1, 3.1, 3.0, 3.0, 3.0, 3.1, 3.0, 3.1]},
            },
        )
        feedback = self.client.post(
            "/activities/analysis-run-1/feedback",
            json={"rpe": 6, "energy": 4, "muscle_soreness": 2, "pain_level": 0, "note": "Felt controlled."},
        )
        self.assertEqual(feedback.status_code, 201)

        detail_before = self.client.get("/activities/analysis-run-1")
        self.assertEqual(detail_before.status_code, 200)
        self.assertEqual(detail_before.json()["analysis"]["status"], "not_requested")
        detail_stats = {item["key"]: item for item in detail_before.json()["stats"]}
        self.assertEqual(detail_stats["avg_speed_kmh"]["value"], 11.0)

        first = self.client.post("/activities/analysis-run-1/analysis", json={})
        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertEqual(first_body["status"], "requested")
        self.assertTrue(first_body["available"])
        self.assertTrue(first_body["requested_at"])
        self.assertIsNone(first_body["generated_at"])

        second = self.client.post("/activities/analysis-run-1/analysis", json={})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "requested")

        context = self.client.get("/activities/analysis-run-1/analysis/context")
        self.assertEqual(context.status_code, 200)
        context_body = context.json()
        self.assertEqual(context_body["status"], "requested")
        self.assertTrue(context_body["context"]["summary_stats"]["distance_km"])
        self.assertEqual(context_body["context"]["activity"]["id"], "analysis-run-1")
        self.assertEqual(context_body["context"]["feedback"]["note"], "Felt controlled.")
        self.assertIn("recent training trajectory", context_body["instructions"]["task"])
        self.assertTrue(any("never restate" in rule.lower() for rule in context_body["instructions"]["rules"]))
        self.assertIsNone(context_body["question"])
        self.assertEqual(context_body["context"]["session_read"]["verdict"]["headline"], "Easy run stayed easy")
        self.assertTrue(any("feedback note" in rule.lower() for rule in context_body["instructions"]["rules"]))

        saved = self.client.post(
            "/activities/analysis-run-1/analysis/save",
            json={
                "headline": "Aerobic control stayed intact",
                "summary": "The run stayed mostly in controlled aerobic territory and matched the easy-session brief.",
                "key_observations": [
                    "Heart-rate distribution stayed mostly aerobic.",
                    "Subjective feedback described the run as controlled.",
                ],
                "limitations": [
                    "No explicit planned-session link was attached.",
                ],
                "confidence_note": "Confidence is moderate because heart-rate and subjective feedback were both available.",
                "generator": "chatgpt",
                "model_name": "gpt-5",
            },
        )
        self.assertEqual(saved.status_code, 200)
        saved_body = saved.json()
        self.assertEqual(saved_body["status"], "ready")
        self.assertEqual(saved_body["generator"], "chatgpt")
        self.assertEqual(saved_body["model_name"], "gpt-5")
        self.assertEqual(saved_body["headline"], "Aerobic control stayed intact")
        generated_at = saved_body["generated_at"]

        detail_after = self.client.get("/activities/analysis-run-1")
        self.assertEqual(detail_after.status_code, 200)
        self.assertEqual(detail_after.json()["analysis"]["status"], "ready")
        self.assertEqual(detail_after.json()["analysis"]["generated_at"], generated_at)
        self.assertEqual(detail_after.json()["analysis"]["headline"], "Aerobic control stayed intact")

    def test_activity_analysis_question_survives_the_coach_request_and_is_saved(self):
        activity_date = (datetime.now().date() - timedelta(days=1)).isoformat()
        created = self.client.post(
            "/activities",
            json={"id": "analysis-question-run", "date": activity_date, "type": "Run", "workout_intent": "easy",
                  "name": "Question Run", "distance_km": 8.0, "duration_min": 45.0, "avg_hr": 150},
        )
        self.assertEqual(created.status_code, 201)
        self._insert_activity_detail_streams(
            "analysis-question-run",
            {"time": {"data": [0, 60, 120]}, "distance": {"data": [0, 180, 360]}, "heartrate": {"data": [140, 148, 150]}},
        )

        detail = self.client.get("/activities/analysis-question-run").json()
        self.assertTrue(detail["analysis"]["session_read"]["available"])
        self.assertEqual(detail["analysis"]["session_read"]["kind"], "run")

        asked = self.client.post("/activities/analysis-question-run/analysis", json={"force_refresh": True, "question": "  Was this   too fast? "})
        self.assertEqual(asked.json()["status"], "requested")
        self.assertEqual(asked.json()["pending_question"], "Was this too fast?")

        # The coach CLI re-requests through MCP without a question; the pending one must survive.
        mcp_request = self.client.post("/activities/analysis-question-run/analysis", json={"force_refresh": True})
        self.assertEqual(mcp_request.json()["pending_question"], "Was this too fast?")

        context = self.client.get("/activities/analysis-question-run/analysis/context").json()
        self.assertEqual(context["question"], "Was this too fast?")
        self.assertIn("Was this too fast?", context["instructions"]["task"])

        saved = self.client.post(
            "/activities/analysis-question-run/analysis/save",
            json={"headline": "No, it was easy enough", "summary": "Heart rate stayed under the easy cap.",
                  "confidence_note": "Based on average heart rate only."},
        ).json()
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["question"], "Was this too fast?")
        self.assertIsNone(saved["pending_question"])

        # An empty question asks for a general read and clears the old one.
        general = self.client.post("/activities/analysis-question-run/analysis", json={"force_refresh": True, "question": ""}).json()
        self.assertIsNone(general["pending_question"])
        context = self.client.get("/activities/analysis-question-run/analysis/context").json()
        self.assertIsNone(context["question"])
        self.assertIn("session_read", context["instructions"]["task"])

    def test_activity_analysis_is_unavailable_without_detail_context(self):
        activity_date = (datetime.now().date() - timedelta(days=1)).isoformat()
        created = self.client.post(
            "/activities",
            json={
                "id": "analysis-no-detail",
                "date": activity_date,
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Uncached Run",
                "distance_km": 8.0,
                "duration_min": 40.0,
                "avg_hr": 165,
            },
        )
        self.assertEqual(created.status_code, 201)

        analysis = self.client.post("/activities/analysis-no-detail/analysis", json={})
        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(analysis.json()["status"], "unavailable")
        self.assertIn("cached", analysis.json()["reason"].lower())

    def test_mcp_activity_analysis_context_and_save_round_trip(self):
        activity_date = (datetime.now().date() - timedelta(days=2)).isoformat()
        created = self.client.post(
            "/activities",
            json={
                "id": "analysis-mcp-run",
                "date": activity_date,
                "type": "Run",
                "workout_intent": "tempo",
                "name": "Tempo Run",
                "distance_km": 9.4,
                "duration_min": 46.0,
                "avg_hr": 168,
                "max_hr": 181,
                "avg_pace": "4:54",
            },
        )
        self.assertEqual(created.status_code, 201)
        self._insert_activity_detail_streams(
            "analysis-mcp-run",
            {
                "time": {"data": [0, 60, 120, 180, 240, 300]},
                "distance": {"data": [0, 250, 510, 760, 1020, 1270]},
                "heartrate": {"data": [150, 160, 167, 171, 173, 176]},
                "velocity_smooth": {"data": [3.4, 3.5, 3.5, 3.4, 3.4, 3.5]},
            },
        )

        request_mcp = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 41,
                "method": "tools/call",
                "params": {
                    "name": "analyze_activity",
                    "arguments": {"activity_id": "analysis-mcp-run"},
                },
            },
        )
        self.assertEqual(request_mcp.status_code, 200)
        requested = request_mcp.json()["result"]["structuredContent"]
        self.assertEqual(requested["status"], "requested")

        context_mcp = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {
                    "name": "get_activity_analysis_context",
                    "arguments": {"activity_id": "analysis-mcp-run"},
                },
            },
        )
        self.assertEqual(context_mcp.status_code, 200)
        context_structured = context_mcp.json()["result"]["structuredContent"]
        self.assertEqual(context_structured["activity_id"], "analysis-mcp-run")
        self.assertEqual(context_structured["status"], "requested")
        self.assertTrue(context_structured["context"]["summary_stats"]["avg_hr"])

        save_mcp = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 43,
                "method": "tools/call",
                "params": {
                    "name": "save_activity_analysis",
                    "arguments": {
                        "activity_id": "analysis-mcp-run",
                        "headline": "The workout carried real intensity",
                        "summary": "Heart-rate, pace, and the workout brief all point to a purposeful harder run rather than steady aerobic volume.",
                        "key_observations": [
                            "Average heart rate sat high for this duration.",
                            "The workout intent was tempo.",
                        ],
                        "limitations": [
                            "No explicit post-workout feedback was logged.",
                        ],
                        "confidence_note": "Confidence is moderate because multiple endurance signals were available.",
                        "generator": "chatgpt",
                        "model_name": "gpt-5",
                    },
                },
            },
        )
        self.assertEqual(save_mcp.status_code, 200)
        saved = save_mcp.json()["result"]["structuredContent"]
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["generator"], "chatgpt")
        self.assertEqual(saved["model_name"], "gpt-5")
        self.assertEqual(saved["headline"], "The workout carried real intensity")

    def test_dashboard_heart_rate_zone_summary_reports_partial_coverage(self):
        dates = [
            (datetime.now().date() - timedelta(days=1)).isoformat(),
            (datetime.now().date() - timedelta(days=3)).isoformat(),
        ]
        for activity_id, activity_date, name in [
            ("dashboard-hr-run-1", dates[0], "Run With Streams"),
            ("dashboard-hr-run-2", dates[1], "Run Missing Streams"),
        ]:
            created = self.client.post(
                "/activities",
                json={
                    "id": activity_id,
                    "date": activity_date,
                    "type": "Run",
                    "name": name,
                    "distance_km": 9.0,
                    "duration_min": 48.0,
                    "avg_hr": 152,
                    "max_hr": 179,
                    "avg_pace": "5:20",
                    "zone2": True,
                },
            )
            self.assertEqual(created.status_code, 201)

        self._insert_activity_detail_streams(
            "dashboard-hr-run-1",
            {
                "time": {"data": [0, 60, 120, 180, 240, 300]},
                "heartrate": {"data": [140, 146, 151, 155, 158, 161]},
            },
        )

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["heart_rate_zone_summary"]
        self.assertTrue(payload["available"])
        self.assertEqual(payload["state"], "partial")
        self.assertEqual(payload["eligible_activities"], 2)
        self.assertEqual(payload["usable_activities"], 1)
        self.assertEqual(payload["unavailable_activities"], 1)
        self.assertGreater(payload["zone2_minutes"], 0)


if __name__ == "__main__":
    unittest.main()
