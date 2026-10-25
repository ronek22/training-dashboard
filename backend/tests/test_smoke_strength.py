"""App smoke tests: Fitbod imports, strength history and the lift rotation."""
import os
import sqlite3
import unittest
import json
from datetime import date, datetime, timedelta
from backend.tests import smoke_base


class StrengthSmokeTests(smoke_base.SmokeTestCase):
    def test_fitbod_import_filters_groups_matches_and_enriches_strength_activity(self):
        activity_date = "2026-06-30"
        for payload in [
            {
                "id": "fitbod-strength-a",
                "date": activity_date,
                "type": "WeightTraining",
                "name": "Upper Strength",
                "duration_min": 48,
                "calories": 320,
            },
            {
                "id": "fitbod-strength-b",
                "date": "2026-06-29",
                "type": "WeightTraining",
                "name": "Lower Strength",
                "duration_min": 44,
                "calories": 340,
            },
            {
                "id": "fitbod-strength-c",
                "date": "2026-07-01",
                "type": "WeightTraining",
                "name": "Posterior Chain",
                "duration_min": 50,
                "calories": 360,
            },
            {
                "id": "fitbod-strength-d",
                "date": "2026-07-01",
                "type": "WeightTraining",
                "name": "Strength Session",
                "duration_min": 52,
                "calories": 355,
            },
        ]:
            created = self.client.post("/activities", json=payload)
            self.assertEqual(created.status_code, 201)

        csv_text = """Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
2025-12-15 18:30:00,Front Squat,5,90,60,,,,false,,1
2025-12-15 18:30:00,Romanian Deadlift,8,80,55,,,,false,,1
2026-06-30 18:00:00,Bench Press,8,60,45,,,,false,,1
2026-06-30 18:00:00,Bench Press,8,60,45,,,,false,,1
2026-06-30 18:00:00,Incline Dumbbell Press,10,22.5,50,,,,false,,2
2026-06-30 18:00:00,Cycling,,,1800,12000,,,false,Commute,1
2026-03-28 20:47:00,Cycling - Stationary,,,3725,,,,false,Zwift sync,1
2026-07-01 07:15:00,Deadlift,5,100,60,,,,true,Warm-up,1
2026-07-01 07:15:00,Deadlift,5,140,70,,,,false,,1
2026-07-01 07:15:00,Deadlift,5,140,70,,,,false,,1
2026-07-01 07:15:00,Barbell Row,10,60,55,,,,false,,1
2026-07-01 07:15:00,Barbell Row,10,60,55,,,,false,,1
bad-date,Squat,5,100,60,,,,false,,1
"""

        imported = self.client.post(
            "/fitbod/import",
            json={
                "file_name": "fitbod-june.csv",
                "csv_text": csv_text,
            },
        )
        self.assertEqual(imported.status_code, 200)
        body = imported.json()
        self.assertEqual(body["raw_row_count"], 13)
        self.assertEqual(body["ignored_row_count"], 2)
        self.assertEqual(body["rejected_row_count"], 1)
        self.assertEqual(body["session_count"], 3)
        self.assertEqual(body["matched_count"], 1)
        self.assertEqual(body["ambiguous_count"], 1)
        self.assertEqual(body["outside_activity_range_count"], 1)
        self.assertEqual(body["actionable_count"], 1)

        first_session = next(session for session in body["sessions"] if session["workout_date"] == "2026-06-30")
        self.assertEqual(first_session["set_count"], 3)
        self.assertEqual(first_session["rep_count"], 26)
        self.assertEqual(first_session["matched_activity"]["id"], "fitbod-strength-a")
        self.assertEqual(first_session["match_provenance"], "matched_automatically")
        self.assertEqual(first_session["exercises"][0]["exercise_name"], "Bench Press")
        self.assertEqual(first_session["exercises"][0]["set_count"], 2)
        self.assertEqual(first_session["exercises"][0]["sets"][0]["reps"], 8)

        old_session = next(session for session in body["sessions"] if session["workout_date"] == "2025-12-15")
        self.assertEqual(old_session["review_state"], "outside_activity_range")
        self.assertFalse(old_session["actionable"])
        self.assertTrue(old_session["range_reason"])

        ambiguous_session = next(session for session in body["sessions"] if session["workout_date"] == "2026-07-01")
        self.assertEqual(ambiguous_session["match_status"], "ambiguous")
        self.assertEqual(ambiguous_session["review_state"], "ambiguous")
        self.assertTrue(ambiguous_session["actionable"])
        self.assertTrue(ambiguous_session["candidate_activities"])
        self.assertEqual(ambiguous_session["candidate_activities"][0]["id"], "fitbod-strength-c")

        latest = self.client.get("/fitbod/imports/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["id"], body["id"])

        linked = self.client.post(
            f"/fitbod/sessions/{ambiguous_session['id']}/link",
            json={"activity_id": "fitbod-strength-c"},
        )
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(linked.json()["match_status"], "matched")
        self.assertEqual(linked.json()["match_provenance"], "matched_manually")
        self.assertEqual(linked.json()["matched_activity"]["id"], "fitbod-strength-c")
        self.assertEqual(linked.json()["review_state"], "matched")

        enriched = self.client.get("/activities/fitbod-strength-c")
        self.assertEqual(enriched.status_code, 200)
        strength_detail = enriched.json()["strength_detail"]
        self.assertEqual(strength_detail["status"], "enriched")
        self.assertEqual(strength_detail["session"]["match_provenance"], "matched_manually")
        self.assertEqual(strength_detail["session"]["rep_count"], 35)
        self.assertEqual(len(strength_detail["session"]["exercises"]), 2)

        cached_repeat = self.client.post(
            "/fitbod/import",
            json={
                "file_name": "fitbod-june.csv",
                "csv_text": csv_text,
            },
        )
        self.assertEqual(cached_repeat.status_code, 200)
        self.assertEqual(cached_repeat.json()["id"], body["id"])

    def test_strength_overview_aggregates_matched_fitbod_history(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        day_one = week_start - timedelta(weeks=2) + timedelta(days=1)
        day_two = week_start - timedelta(weeks=1) + timedelta(days=2)
        day_three = week_start + timedelta(days=1)
        generic_day = week_start + timedelta(days=5)
        unmatched_day = week_start + timedelta(days=3)

        for activity_id, activity_date, name in [
            ("strength-overview-a", day_one, "Push A"),
            ("strength-overview-b", day_two, "Lower + Push"),
            ("strength-overview-c", day_three, "Push B"),
        ]:
            created = self.client.post(
                "/activities",
                json={
                    "id": activity_id,
                    "date": activity_date.isoformat(),
                    "type": "WeightTraining",
                    "name": name,
                    "duration_min": 50,
                    "calories": 330,
                },
            )
            self.assertEqual(created.status_code, 201)

        csv_text = f"""Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
{day_one.isoformat()} 07:00:00,Bench Press,5,60,45,,,,false,,1
{day_one.isoformat()} 07:00:00,Bench Press,5,62.5,45,,,,false,,1
{day_one.isoformat()} 07:00:00,Chest Supported Row,10,45,50,,,,false,,1
{day_two.isoformat()} 07:00:00,Back Squat,5,100,60,,,,false,,1
{day_two.isoformat()} 07:00:00,Bench Press,6,65,45,,,,false,,1
{day_three.isoformat()} 07:00:00,Bench Press,5,67.5,45,,,,false,,1
{day_three.isoformat()} 07:00:00,Pull Up,8,,45,,,,false,,1
{unmatched_day.isoformat()} 07:00:00,Deadlift,5,140,60,,,,false,,1
"""

        imported = self.client.post(
            "/fitbod/import",
            json={"file_name": "strength-overview.csv", "csv_text": csv_text},
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["matched_count"], 3)
        self.assertEqual(imported.json()["unmatched_count"], 1)

        overview = self.client.get("/strength/overview?weeks=4")
        self.assertEqual(overview.status_code, 200)
        body = overview.json()

        self.assertEqual(body["summary"]["session_count"], 3)
        self.assertEqual(body["summary"]["total_sets"], 7)
        self.assertEqual(body["summary"]["total_reps"], 44)
        self.assertEqual(body["summary"]["total_volume_kg"], 2290.0)
        self.assertEqual(body["selected_exercise"]["exercise_name"], "Bench Press")
        self.assertEqual(body["selected_exercise"]["appearance_count"], 3)
        self.assertEqual(body["selected_exercise"]["trend"][-1]["top_load_kg"], 67.5)
        self.assertEqual(body["selected_exercise"]["progression"]["headline"], "Load is trending up")
        self.assertEqual(body["important_prs"][0]["label"], "Bench Press")
        self.assertEqual(body["important_prs"][0]["top_load_kg"], 67.5)
        self.assertEqual(body["important_prs"][1]["label"], "Back Squat")
        self.assertEqual(body["important_prs"][1]["top_load_kg"], 100.0)
        self.assertEqual(body["sessions"][0]["matched_activity"]["id"], "strength-overview-c")
        self.assertEqual(body["weekly"][-3]["week_start"], (day_one - timedelta(days=day_one.weekday())).isoformat())
        self.assertEqual(body["weekly"][-3]["session_count"], 1)
        self.assertEqual(body["weekly"][-3]["total_volume_kg"], 1062.5)

        lower = self.client.get("/strength/overview?weeks=4&body_part=lower")
        self.assertEqual(lower.status_code, 200)
        lower_body = lower.json()
        self.assertEqual(lower_body["summary"]["session_count"], 1)
        self.assertEqual(lower_body["summary"]["total_volume_kg"], 500.0)
        self.assertEqual(lower_body["selected_exercise"]["exercise_name"], "Back Squat")

    def test_mcp_strength_context_exposes_enriched_history_and_excludes_unlinked_rows(self):
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        day_one = week_start - timedelta(weeks=2) + timedelta(days=1)
        day_two = week_start - timedelta(weeks=1) + timedelta(days=2)
        day_three = week_start + timedelta(days=1)
        generic_day = week_start + timedelta(days=5)
        unmatched_day = week_start + timedelta(days=3)

        for activity_id, activity_date, name in [
            ("strength-mcp-a", day_one, "Push A"),
            ("strength-mcp-b", day_two, "Lower + Push"),
            ("strength-mcp-c", day_three, "Push B"),
            ("strength-mcp-generic", generic_day, "Generic gym session"),
        ]:
            created = self.client.post(
                "/activities",
                json={
                    "id": activity_id,
                    "date": activity_date.isoformat(),
                    "type": "WeightTraining",
                    "name": name,
                    "duration_min": 50,
                    "calories": 330,
                },
            )
            self.assertEqual(created.status_code, 201)

        csv_text = f"""Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
{day_one.isoformat()} 07:00:00,Bench Press,5,60,45,,,,false,,1
{day_one.isoformat()} 07:00:00,Bench Press,5,62.5,45,,,,false,,1
{day_one.isoformat()} 07:00:00,Chest Supported Row,10,45,50,,,,false,,1
{day_two.isoformat()} 07:00:00,Back Squat,5,100,60,,,,false,,1
{day_two.isoformat()} 07:00:00,Bench Press,6,65,45,,,,false,,1
{day_three.isoformat()} 07:00:00,Bench Press,5,67.5,45,,,,false,,1
{day_three.isoformat()} 07:00:00,Pull Up,8,,45,,,,false,,1
{unmatched_day.isoformat()} 07:00:00,Deadlift,5,140,60,,,,false,,1
"""

        imported = self.client.post(
            "/fitbod/import",
            json={"file_name": "strength-mcp.csv", "csv_text": csv_text},
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["matched_count"], 3)
        self.assertEqual(imported.json()["unmatched_count"], 1)

        mcp = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 26,
                "method": "tools/call",
                "params": {
                    "name": "get_strength_context",
                    "arguments": {"weeks": 4},
                },
            },
        )
        self.assertEqual(mcp.status_code, 200)

        body = mcp.json()
        self.assertEqual(body["id"], 26)
        structured = body["result"]["structuredContent"]

        self.assertEqual(structured["summary"]["session_count"], 3)
        self.assertEqual(structured["summary"]["total_sets"], 7)
        self.assertEqual(structured["summary"]["total_reps"], 44)
        self.assertEqual(structured["summary"]["total_volume_kg"], 2290.0)
        self.assertEqual(structured["selected_exercise"]["exercise_name"], "Bench Press")
        self.assertEqual(structured["selected_exercise"]["trend"][-1]["top_load_kg"], 67.5)
        self.assertEqual(structured["important_prs"][0]["label"], "Bench Press")
        self.assertEqual(structured["important_prs"][1]["label"], "Back Squat")
        self.assertEqual(structured["recent_sessions"][0]["matched_activity"]["id"], "strength-mcp-c")
        self.assertEqual(structured["recent_sessions"][0]["exercises"][0]["exercise_name"], "Bench Press")
        self.assertEqual(structured["recent_sessions"][0]["exercises"][0]["sets"][0]["reps"], 5)
        self.assertEqual(structured["recent_sessions"][0]["exercises"][0]["sets"][0]["weight_kg"], 67.5)
        self.assertFalse(structured["recent_sessions"][0]["exercises"][0]["sets"][0]["is_warmup"])
        self.assertEqual(structured["recent_sessions"][0]["exercises"][1]["exercise_name"], "Pull Up")
        self.assertIsNone(structured["recent_sessions"][0]["exercises"][1]["sets"][0]["weight_kg"])
        self.assertEqual(structured["recurring_lifts"][0]["exercise_name"], "Bench Press")
        self.assertEqual(
            structured["data_source"]["kind"],
            "linked_exercise_level_strength_history",
        )
        self.assertIn("Unlinked sessions", structured["data_source"]["exclusion_note"])

        matched_activity_ids = {
            session["matched_activity"]["id"]
            for session in structured["recent_sessions"]
        }
        self.assertNotIn("strength-mcp-generic", matched_activity_ids)
        self.assertNotIn("Deadlift", {lift["exercise_name"] for lift in structured["recurring_lifts"]})

        alias = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 27,
                "method": "tools/call",
                "params": {
                    "name": "get_exercise_history",
                    "arguments": {"weeks": 4},
                },
            },
        )
        self.assertEqual(alias.status_code, 200)
        alias_structured = alias.json()["result"]["structuredContent"]
        self.assertEqual(alias_structured["recent_sessions"][0]["exercises"][0]["exercise_name"], "Bench Press")
        self.assertEqual(alias_structured["recent_sessions"][0]["exercises"][0]["sets"][0]["weight_kg"], 67.5)

    def test_init_db_cleans_up_existing_fitbod_non_strength_sessions(self):
        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        try:
            conn.execute(
                """
                INSERT INTO fitbod_import_batches
                (
                    id, file_name, file_hash, parser_version, grouping_version, imported_at,
                    raw_row_count, strength_row_count, ignored_row_count, rejected_row_count,
                    session_count, matched_count, ambiguous_count, unmatched_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "legacy-fitbod.csv",
                    "legacy-hash",
                    "fitbod_csv_v1",
                    "timestamp_group_v1",
                    "2026-07-03T09:00:00",
                    1,
                    1,
                    0,
                    0,
                    1,
                    0,
                    0,
                    1,
                ),
            )
            conn.execute(
                """
                INSERT INTO fitbod_import_rows
                (batch_id, row_index, row_kind, workout_timestamp, exercise_name, ignore_reason, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    2,
                    "strength",
                    "2026-03-28T20:47:00",
                    "Cycling - Stationary",
                    None,
                    '{"Exercise":"Cycling - Stationary"}',
                ),
            )
            conn.execute(
                """
                INSERT INTO fitbod_workout_sessions
                (
                    id, batch_id, session_key, workout_timestamp, workout_date, title,
                    exercise_count, set_count, rep_count, total_volume_kg, total_duration_seconds,
                    total_distance_m, calories, match_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    "2026-03-28T20:47:00",
                    "2026-03-28T20:47:00",
                    "2026-03-28",
                    "Cycling - Stationary",
                    1,
                    1,
                    0,
                    0,
                    3725,
                    None,
                    None,
                    "unmatched",
                ),
            )
            conn.execute(
                """
                INSERT INTO fitbod_workout_exercises
                (
                    id, session_id, exercise_order, exercise_name, set_count, rep_count,
                    total_volume_kg, work_set_count, warmup_set_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    1,
                    "Cycling - Stationary",
                    1,
                    0,
                    0,
                    1,
                    0,
                ),
            )
            conn.execute(
                """
                INSERT INTO fitbod_workout_sets
                (
                    id, exercise_id, set_order, reps, weight_kg, duration_seconds,
                    distance_m, incline, resistance, is_warmup, note, multiplier
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    1,
                    0,
                    None,
                    3725,
                    None,
                    None,
                    None,
                    0,
                    "legacy zwift duplicate",
                    1,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        smoke_base.import_fresh_app()

        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            session_count = conn.execute("SELECT COUNT(*) AS count FROM fitbod_workout_sessions").fetchone()["count"]
            exercise_count = conn.execute("SELECT COUNT(*) AS count FROM fitbod_workout_exercises").fetchone()["count"]
            set_count = conn.execute("SELECT COUNT(*) AS count FROM fitbod_workout_sets").fetchone()["count"]
            self.assertEqual(session_count, 0)
            self.assertEqual(exercise_count, 0)
            self.assertEqual(set_count, 0)

            cleaned_row = conn.execute(
                """
                SELECT row_kind, ignore_reason
                FROM fitbod_import_rows
                WHERE batch_id = 1
                """
            ).fetchone()
            self.assertEqual(cleaned_row["row_kind"], "ignored")
            self.assertIn("Retrospective cleanup", cleaned_row["ignore_reason"])

            batch_row = conn.execute(
                """
                SELECT strength_row_count, ignored_row_count, session_count, unmatched_count
                FROM fitbod_import_batches
                WHERE id = 1
                """
            ).fetchone()
            self.assertEqual(batch_row["strength_row_count"], 0)
            self.assertEqual(batch_row["ignored_row_count"], 1)
            self.assertEqual(batch_row["session_count"], 0)
            self.assertEqual(batch_row["unmatched_count"], 0)
        finally:
            conn.close()

    def test_fitbod_session_can_be_rejected_manually(self):
        created = self.client.post(
            "/activities",
            json={
                "id": "fitbod-strength-july",
                "date": "2026-07-01",
                "type": "WeightTraining",
                "name": "Workout A Upper Chest",
                "duration_min": 58,
            },
        )
        self.assertEqual(created.status_code, 201)

        csv_text = """Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
"""
        imported = self.client.post(
            "/fitbod/import",
            json={"file_name": "fitbod-dip.csv", "csv_text": csv_text},
        )
        self.assertEqual(imported.status_code, 200)
        body = imported.json()
        self.assertEqual(body["session_count"], 1)
        session = body["sessions"][0]
        self.assertEqual(session["title"], "Dip")

        rejected = self.client.post(
            f"/fitbod/sessions/{session['id']}/reject",
            json={"reason": "This export row does not represent a workout I want to review."},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], "rejected")

        latest = self.client.get("/fitbod/imports/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["session_count"], 0)
        self.assertEqual(latest.json()["ignored_row_count"], 3)
        self.assertEqual(latest.json()["actionable_count"], 0)

        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            session_count = conn.execute("SELECT COUNT(*) AS count FROM fitbod_workout_sessions").fetchone()["count"]
            self.assertEqual(session_count, 0)
            row = conn.execute(
                """
                SELECT row_kind, ignore_reason
                FROM fitbod_import_rows
                WHERE batch_id = ? AND exercise_name = 'Dip'
                LIMIT 1
                """,
                (body["id"],),
            ).fetchone()
            self.assertEqual(row["row_kind"], "ignored")
            self.assertIn("does not represent a workout", row["ignore_reason"])
        finally:
            conn.close()

    def test_fitbod_reimport_deduplicates_sessions_and_preserves_manual_decisions(self):
        for payload in [
            {
                "id": "fitbod-repeat-a",
                "date": "2026-06-30",
                "type": "WeightTraining",
                "name": "Upper Strength",
                "duration_min": 48,
            },
            {
                "id": "fitbod-repeat-b",
                "date": "2026-07-01",
                "type": "WeightTraining",
                "name": "Posterior Chain",
                "duration_min": 50,
            },
            {
                "id": "fitbod-repeat-c",
                "date": "2026-07-01",
                "type": "WeightTraining",
                "name": "Strength Session",
                "duration_min": 52,
            },
            {
                "id": "fitbod-repeat-d",
                "date": "2026-07-02",
                "type": "WeightTraining",
                "name": "Leg Day",
                "duration_min": 46,
            },
        ]:
            created = self.client.post("/activities", json=payload)
            self.assertEqual(created.status_code, 201)

        first_csv = """Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-06-30 18:00:00,Bench Press,8,60,45,,,,false,,1
2026-06-30 18:00:00,Incline Dumbbell Press,10,22.5,50,,,,false,,2
2026-07-01 07:15:00,Deadlift,5,140,70,,,,false,,1
2026-07-01 07:15:00,Barbell Row,10,60,55,,,,false,,1
"""
        first_import = self.client.post(
            "/fitbod/import",
            json={"file_name": "fitbod-export-1.csv", "csv_text": first_csv},
        )
        self.assertEqual(first_import.status_code, 200)
        first_body = first_import.json()
        self.assertEqual(first_body["session_count"], 3)

        july1_session = next(session for session in first_body["sessions"] if session["workout_date"] == "2026-07-01")
        linked = self.client.post(
            f"/fitbod/sessions/{july1_session['id']}/link",
            json={"activity_id": "fitbod-repeat-b"},
        )
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(linked.json()["match_provenance"], "matched_manually")

        dip_session = next(session for session in first_body["sessions"] if session["title"] == "Dip")
        rejected = self.client.post(
            f"/fitbod/sessions/{dip_session['id']}/reject",
            json={"reason": "Bodyweight accessory set; do not review as a standalone workout."},
        )
        self.assertEqual(rejected.status_code, 200)

        second_csv = """Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-02-25 21:26:00,Dip,20,10,0,,,,false,,1
2026-06-30 18:00:00,Bench Press,8,60,45,,,,false,,1
2026-06-30 18:00:00,Incline Dumbbell Press,10,22.5,50,,,,false,,2
2026-07-01 07:15:00,Deadlift,5,140,70,,,,false,,1
2026-07-01 07:15:00,Barbell Row,10,60,55,,,,false,,1
2026-07-02 18:10:00,Back Squat,5,100,60,,,,false,,1
2026-07-02 18:10:00,Back Squat,5,100,60,,,,false,,1
"""
        second_import = self.client.post(
            "/fitbod/import",
            json={"file_name": "fitbod-export-2.csv", "csv_text": second_csv},
        )
        self.assertEqual(second_import.status_code, 200)
        second_body = second_import.json()
        self.assertEqual(second_body["session_count"], 3)
        self.assertEqual(second_body["new_session_count"], 1)
        self.assertEqual(second_body["updated_session_count"], 2)
        self.assertEqual(second_body["preserved_manual_match_count"], 1)
        self.assertEqual(second_body["preserved_rejected_count"], 1)
        self.assertEqual(second_body["actionable_count"], 0)

        july1_after = next(session for session in second_body["sessions"] if session["workout_date"] == "2026-07-01")
        self.assertEqual(july1_after["match_provenance"], "matched_manually")
        self.assertEqual(july1_after["matched_activity"]["id"], "fitbod-repeat-b")

        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            session_count = conn.execute("SELECT COUNT(*) AS count FROM fitbod_workout_sessions").fetchone()["count"]
            distinct_timestamps = conn.execute(
                "SELECT COUNT(DISTINCT workout_timestamp) AS count FROM fitbod_workout_sessions"
            ).fetchone()["count"]
            self.assertEqual(session_count, 3)
            self.assertEqual(distinct_timestamps, 3)

            decision_rows = conn.execute(
                "SELECT workout_timestamp, decision_type FROM fitbod_session_decisions ORDER BY workout_timestamp ASC"
            ).fetchall()
            self.assertEqual(len(decision_rows), 2)
            self.assertEqual({row["decision_type"] for row in decision_rows}, {"matched_manually", "rejected_manually"})
        finally:
            conn.close()

        enriched = self.client.get("/activities/fitbod-repeat-b")
        self.assertEqual(enriched.status_code, 200)
        self.assertEqual(enriched.json()["strength_detail"]["session"]["match_provenance"], "matched_manually")

    def test_zzz_sick_day_weight_training_does_not_advance_strength_rotation(self):
        before = self.client.get("/settings/workout-templates").json()["programs"]["strength"]["rotation_state"]
        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": "2031-03-03",
                "title": "Sick week",
                "days": [{"date": "2031-03-04", "label": "Tue", "session_type": "WeightTraining", "title": "Strength", "target_duration_min": 55}],
            },
        )
        self.assertEqual(created.status_code, 201)
        with sqlite3.connect(os.environ["TRAINING_DB_PATH"]) as conn:
            conn.execute("INSERT INTO sick_periods (start_date, end_date, severity) VALUES ('2031-03-03', '2031-03-05', 'above_neck')")
        # The watch's Core Training workout syncs from Strava as WeightTraining, unlinked.
        activity = self.client.post(
            "/activities",
            json={"id": "sick-day-core", "date": "2031-03-04", "type": "WeightTraining", "name": "Evening Workout", "duration_min": 10.1},
        )
        self.assertEqual(activity.status_code, 201)
        after = self.client.get("/settings/workout-templates").json()["programs"]["strength"]["rotation_state"]
        self.assertEqual(after.get("next_template_id"), before.get("next_template_id"))
        self.assertNotIn("sick-day-core", after.get("processed_activity_ids") or [])

    def test_zz_strength_rotation_advances_on_completion_and_postpones_missed_sessions(self):
        settings = self.client.get("/settings/workout-templates")
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(settings.json()["programs"]["strength"]["rotation_state"]["next_template_id"], "strength-a")

        first_week = "2031-01-06"
        second_week = "2031-01-13"
        third_week = "2031-01-20"

        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": first_week,
                "title": "Strength progression week 1",
                "days": [
                    {
                        "date": "2031-01-07",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 55,
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        first_plan = self._find_plan(first_week)
        self.assertIsNotNone(first_plan)
        self.assertEqual(first_plan["days"][0]["template_id"], "strength-a")

        activity = self.client.post(
            "/activities",
            json={
                "id": "strength-rotation-a",
                "date": "2031-01-07",
                "type": "WeightTraining",
                "name": "Workout A completed",
                "duration_min": 56.0,
                "linked_planned_session_id": first_plan["days"][0]["session_id"],
            },
        )
        self.assertEqual(activity.status_code, 201)

        reread_settings = self.client.get("/settings/workout-templates")
        self.assertEqual(reread_settings.status_code, 200)
        strength_program = reread_settings.json()["programs"]["strength"]
        self.assertEqual(strength_program["rotation_state"]["last_completed_template_id"], "strength-a")
        self.assertEqual(strength_program["rotation_state"]["next_template_id"], "strength-b")

        second = self.client.post(
            "/plans/weekly",
            json={
                "week_start": second_week,
                "title": "Strength progression week 2",
                "days": [
                    {
                        "date": "2031-01-14",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 55,
                    }
                ],
            },
        )
        self.assertEqual(second.status_code, 201)
        second_plan = self._find_plan(second_week)
        self.assertIsNotNone(second_plan)
        self.assertEqual(second_plan["days"][0]["template_id"], "strength-b")

        third = self.client.post(
            "/plans/weekly",
            json={
                "week_start": third_week,
                "title": "Strength progression week 3",
                "days": [
                    {
                        "date": "2031-01-21",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 55,
                    }
                ],
            },
        )
        self.assertEqual(third.status_code, 201)
        third_plan = self._find_plan(third_week)
        self.assertIsNotNone(third_plan)
        self.assertEqual(third_plan["days"][0]["template_id"], "strength-b")

    def test_zz_explicit_strength_workout_title_can_restart_rotation_from_a(self):
        updated = self.client.put(
            "/settings/workout-templates",
            json={
                "programs": {
                    "strength": {
                        "rotation_state": {
                            "next_template_id": "strength-b",
                            "pending_template_id": "strength-b",
                        }
                    }
                }
            },
        )
        self.assertEqual(updated.status_code, 200)

        week_start = "2031-01-27"
        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start,
                "title": "Restart strength rotation",
                "days": [
                    {
                        "date": "2031-01-27",
                        "label": "Mon",
                        "session_type": "WeightTraining",
                        "title": "Workout A · Upper Chest",
                        "template_id": "strength-b",
                        "target_duration_min": 45,
                    },
                    {
                        "date": "2031-01-30",
                        "label": "Thu",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 50,
                    },
                ],
            },
        )
        self.assertEqual(created.status_code, 201)

        plan = self._find_plan(week_start)
        self.assertEqual(plan["days"][0]["template_id"], "strength-a")
        self.assertEqual(plan["days"][0]["template_label"], "Workout A · Upper Chest")
        self.assertEqual(plan["days"][1]["template_id"], "strength-b")
        self.assertEqual(plan["days"][1]["template_label"], "Workout B · Back + Arms")

    def test_zz_strength_rotation_advances_from_inferred_same_day_completion_without_explicit_link(self):
        first_week = "2031-02-03"

        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": first_week,
                "title": "Strength progression inferred link",
                "days": [
                    {
                        "date": "2031-02-04",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 55,
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        first_plan = self._find_plan(first_week)
        self.assertIsNotNone(first_plan)
        self.assertEqual(first_plan["days"][0]["template_id"], "strength-a")
        self.assertEqual(first_plan["days"][0]["template_label"], "Workout A · Upper Chest")

        activity = self.client.post(
            "/activities",
            json={
                "id": "strength-rotation-inferred-a",
                "date": "2031-02-04",
                "type": "WeightTraining",
                "name": "Workout A Upper Chest",
                "duration_min": 56.0,
            },
        )
        self.assertEqual(activity.status_code, 201)

        reread_settings = self.client.get("/settings/workout-templates")
        self.assertEqual(reread_settings.status_code, 200)
        strength_program = reread_settings.json()["programs"]["strength"]
        self.assertEqual(strength_program["rotation_state"]["last_completed_template_id"], "strength-a")
        self.assertEqual(strength_program["rotation_state"]["last_completed_template_label"], "Workout A · Upper Chest")
        self.assertEqual(strength_program["rotation_state"]["next_template_id"], "strength-b")

    def test_zz_strength_rotation_completion_overrides_stale_postponed_next_template(self):
        updated = self.client.put(
            "/settings/workout-templates",
            json={
                "programs": {
                    "strength": {
                        "rotation_state": {
                            "next_template_id": "strength-d",
                            "pending_template_id": "strength-d",
                        }
                    }
                }
            },
        )
        self.assertEqual(updated.status_code, 200)

        week_start = "2031-02-10"
        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start,
                "title": "Strength progression stale pending",
                "days": [
                    {
                        "date": "2031-02-11",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 55,
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)

        activity = self.client.post(
            "/activities",
            json={
                "id": "strength-rotation-stale-pending-a",
                "date": "2031-02-11",
                "type": "WeightTraining",
                "name": "Workout A Upper Chest",
                "duration_min": 56.0,
            },
        )
        self.assertEqual(activity.status_code, 201)

        reread_settings = self.client.get("/settings/workout-templates")
        self.assertEqual(reread_settings.status_code, 200)
        strength_program = reread_settings.json()["programs"]["strength"]
        self.assertEqual(strength_program["rotation_state"]["last_completed_template_id"], "strength-a")
        self.assertEqual(strength_program["rotation_state"]["next_template_id"], "strength-b")
        self.assertEqual(strength_program["rotation_state"]["pending_template_id"], "strength-b")

    def test_zz_running_restriction_delays_lower_body_template_assignment(self):
        updated = self.client.put(
            "/settings/workout-templates",
            json={
                "programs": {
                    "strength": {
                        "rotation_state": {
                            "next_template_id": "strength-d",
                        }
                    }
                }
            },
        )
        self.assertEqual(updated.status_code, 200)

        restrictions = self.client.put(
            "/settings/modality-restrictions",
            json={
                "modalities": {
                    "run": {"status": "limited", "reason": "No extra lower-body loading"},
                    "ride": {"status": "allowed"},
                    "strength": {"status": "allowed"},
                }
            },
        )
        self.assertEqual(restrictions.status_code, 200)

        week_start = "2031-02-03"
        created = self.client.post(
            "/plans/weekly",
            json={
                "week_start": week_start,
                "title": "Restriction-aware strength week",
                "days": [
                    {
                        "date": "2031-02-04",
                        "label": "Tue",
                        "session_type": "WeightTraining",
                        "title": "Strength",
                        "target_duration_min": 50,
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        plan = self._find_plan(week_start)
        self.assertIsNotNone(plan)
        self.assertNotEqual(plan["days"][0]["template_id"], "strength-d")
        self.assertIn("Lower-body strength was delayed", plan["days"][0]["planning_rule_reason"])


if __name__ == "__main__":
    unittest.main()
