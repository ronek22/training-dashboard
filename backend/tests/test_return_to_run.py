import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.execution_quality import evaluate_execution_quality
from backend.app.services.return_to_run import (
    RUN_HR_CAP,
    build_return_to_run,
    build_return_to_run_context,
    check_run_progression,
    save_program,
    save_symptom_check,
    suggest_start_stage,
)
from backend.app.services.session_brief import build_session_brief

TODAY = date(2026, 10, 5)


class ReturnToRunTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, distance_km REAL,
                duration_min REAL, avg_hr INTEGER, workout_intent TEXT);
            CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, pain_level INTEGER);
            """
        )
        self.addCleanup(self.conn.close)
        self.counter = 0

    def run_on(self, day, minutes=25, during=None, morning=None, hr=150, activity_type="Run", intent=None, feedback_pain=None):
        self.counter += 1
        activity_id = f"r{self.counter}"
        self.conn.execute(
            "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day.isoformat(), activity_type, activity_id, 4.0, minutes, hr, intent),
        )
        if feedback_pain is not None:
            self.conn.execute("INSERT INTO activity_feedback VALUES (?, ?)", (activity_id, feedback_pain))
        if activity_type == "Run" and (during is not None or morning is not None):
            payload = {key: value for key, value in (("during", during), ("next_morning", morning)) if value is not None}
            save_symptom_check(self.conn, activity_id, payload)
        return activity_id

    def start(self, stage=1, started=TODAY - timedelta(days=30)):
        save_program(self.conn, {"active": True, "start_stage": stage, "started_on": started.isoformat()}, TODAY)

    def test_inactive_program_suggests_start_stage(self):
        data = build_return_to_run(self.conn, TODAY)
        self.assertFalse(data["active"])
        self.assertEqual(data["suggested_start"]["stage"], 1)
        self.run_on(TODAY - timedelta(days=26), minutes=28, during=0)
        suggestion = suggest_start_stage(self.conn, TODAY)
        self.assertEqual(suggestion["stage"], 3)  # 28 min -> stage 4, minus one after 26 days off
        self.assertIn("26 days", suggestion["reason"])
        self.run_on(TODAY - timedelta(days=2), minutes=28, during=3)
        self.assertEqual(suggest_start_stage(self.conn, TODAY)["stage"], 1)

    def test_two_clean_runs_advance_only_with_morning_score(self):
        self.start(stage=1)
        self.run_on(TODAY - timedelta(days=6), during=1, morning=0)
        self.run_on(TODAY - timedelta(days=3), during=0)
        data = build_return_to_run(self.conn, TODAY)
        self.assertEqual(data["stage"]["stage"], 1)
        self.assertEqual(data["next"]["status"], "needs_morning")
        latest = data["history"][0]["activity_id"]
        save_symptom_check(self.conn, latest, {"next_morning": 1})
        data = build_return_to_run(self.conn, TODAY)
        self.assertEqual(data["stage"]["stage"], 2)
        self.assertEqual(data["history"][0]["stage_change"], "up")

    def test_flare_drops_a_stage_and_feedback_pain_stands_in(self):
        self.start(stage=3)
        self.run_on(TODAY - timedelta(days=4), feedback_pain=5)
        data = build_return_to_run(self.conn, TODAY)
        self.assertEqual(data["stage"]["stage"], 2)
        self.assertEqual(data["history"][0]["during_source"], "feedback")
        self.assertEqual(data["next"]["status"], "flare")

    def test_long_break_drops_a_stage(self):
        self.start(stage=4, started=TODAY - timedelta(days=60))
        self.run_on(TODAY - timedelta(days=50), during=0, morning=0)
        self.run_on(TODAY - timedelta(days=20), during=0, morning=0)
        data = build_return_to_run(self.conn, TODAY)
        self.assertTrue(data["history"][0]["after_break"])
        self.assertEqual(data["stage"]["stage"], 3)

    def test_rest_day_and_graduation(self):
        self.start(stage=6)
        for offset in (9, 6, 3):
            self.run_on(TODAY - timedelta(days=offset), minutes=50, during=0, morning=0)
        self.assertEqual(build_return_to_run(self.conn, TODAY)["next"]["status"], "graduated")
        self.conn.execute("DELETE FROM activities")
        self.start(stage=2, started=TODAY)
        self.run_on(TODAY, during=0, morning=None)
        self.assertEqual(build_return_to_run(self.conn, TODAY)["next"]["status"], "rest")

    def test_symptoms_only_for_runs(self):
        ride = self.run_on(TODAY, activity_type="Ride")
        with self.assertRaises(ValueError):
            save_symptom_check(self.conn, ride, {"during": 1})
        with self.assertRaises(LookupError):
            save_symptom_check(self.conn, "missing", {"during": 1})

    def test_plan_flags_distance_and_pace_rising_together(self):
        week_start = TODAY - timedelta(days=TODAY.weekday())
        self.run_on(week_start - timedelta(days=4), minutes=25)
        easy_more = [
            {"date": week_start.isoformat(), "session_type": "run", "workout_intent": "easy", "target_duration_min": 30},
            {"date": (week_start + timedelta(days=3)).isoformat(), "session_type": "run", "workout_intent": "easy", "target_duration_min": 30},
        ]
        self.assertIsNone(check_run_progression(self.conn, easy_more, week_start.isoformat()))
        both = [*easy_more[:1], {**easy_more[1], "workout_intent": "tempo"}]
        flag = check_run_progression(self.conn, both, week_start.isoformat())
        self.assertEqual(flag["type"], "run_distance_and_pace")
        same_volume_faster = [{**easy_more[0], "workout_intent": "tempo", "target_duration_min": 25}]
        self.assertIsNone(check_run_progression(self.conn, same_volume_faster, week_start.isoformat()))

    def test_easy_run_above_hr_cap_is_marked_in_execution_quality(self):
        result = evaluate_execution_quality(
            {"workout_intent": "easy"},
            {"type": "Run", "avg_hr": RUN_HR_CAP + 8, "duration_min": 30},
            heart_rate_zones={"available": True, "zone2_pct": 70, "zones": [{"key": "zone3", "pct": 10}]},
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["evidence"]["hr_cap_bpm"], RUN_HR_CAP)
        ride = evaluate_execution_quality(
            {"workout_intent": "easy"},
            {"type": "Ride", "avg_hr": RUN_HR_CAP + 8, "duration_min": 30},
            heart_rate_zones={"available": True, "zone2_pct": 70, "zones": [{"key": "zone3", "pct": 10}]},
        )
        self.assertEqual(ride["status"], "matched")

    def test_brief_and_context_use_the_current_stage(self):
        self.assertEqual(build_return_to_run_context(self.conn, TODAY), {"active": False})
        self.start(stage=2)
        brief = build_session_brief(self.conn, {"date": TODAY.isoformat(), "session_type": "run", "workout_intent": "easy"}, TODAY)
        self.assertIn("stage 2 of 6", brief["purpose"])
        self.assertIn("heel pain reaches 3/10", brief["bail"][0])
        context = build_return_to_run_context(self.conn, TODAY)
        self.assertEqual(context["stage"]["name"], "Run/walk 2:1")


if __name__ == "__main__":
    unittest.main()
