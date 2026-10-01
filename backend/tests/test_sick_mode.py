import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.services.dashboard import compute_activity_streak
from backend.app.services.sick_mode import (
    SESSIONS,
    public_session,
    save_sick_session_completion,
    sick_dates,
    build_sick_mode,
    end_sick_mode,
    log_sick_session,
    sick_days_between,
    start_sick_mode,
)

SCHEMA = """
CREATE TABLE activities (
    id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, workout_intent TEXT, name TEXT,
    distance_km REAL, duration_min REAL, avg_hr INTEGER, max_hr INTEGER, avg_pace TEXT, avg_watts REAL,
    elevation_m INTEGER, calories INTEGER, zone2 INTEGER DEFAULT 0, notes TEXT,
    linked_planned_session_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE activity_source_refs (source TEXT, external_id TEXT, activity_id TEXT, started_at TEXT, file_name TEXT);
CREATE TABLE sick_session_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, session_key TEXT NOT NULL, started_at TEXT NOT NULL,
    elapsed_seconds INTEGER NOT NULL, completed_steps INTEGER NOT NULL DEFAULT 0, extras_json TEXT, activity_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(session_key, started_at)
);
CREATE TABLE sick_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT NOT NULL, end_date TEXT,
    severity TEXT NOT NULL DEFAULT 'above_neck', note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

TODAY = date.today()


class SickModeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_inactive_by_default_and_tolerates_missing_table(self):
        self.assertEqual(build_sick_mode(self.conn), {"active": False})
        self.conn.execute("DROP TABLE sick_periods")
        self.assertEqual(build_sick_mode(self.conn), {"active": False})
        self.assertEqual(sick_days_between(self.conn, TODAY, TODAY), 0)

    def test_start_updates_severity_without_opening_a_second_period(self):
        state = start_sick_mode(self.conn, "above_neck", today=TODAY - timedelta(days=1))
        self.assertTrue(state["active"])
        self.assertIn("easy_walk", [s["key"] for s in state["sessions"]])
        state = start_sick_mode(self.conn, "below_neck", today=TODAY)
        self.assertEqual(state["day_number"], 2)
        self.assertEqual(state["severity_label"], "Fever or chest")
        self.assertNotIn("easy_walk", [s["key"] for s in state["sessions"]])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sick_periods").fetchone()[0], 1)

    def test_logged_session_counts_toward_the_streak(self):
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('y', ?, 'Ride')", ((TODAY - timedelta(days=1)).isoformat(),))
        start_sick_mode(self.conn, "above_neck", today=TODAY)
        with patch("backend.app.services.activities.reconcile_workout_template_rotation_state"):
            state = log_sick_session(self.conn, "mobility_flow", today=TODAY)
            log_sick_session(self.conn, "mobility_flow", today=TODAY)  # idempotent per day
        self.assertEqual([item["name"] for item in state["moved_today"]], ["Mobility flow"])
        row = self.conn.execute("SELECT type, workout_intent, duration_min FROM activities WHERE date = ?", (TODAY.isoformat(),)).fetchone()
        self.assertEqual(tuple(row), ("Yoga", "mobility", 10))
        self.assertEqual(compute_activity_streak(self.conn)["value"], 2)
        self.assertFalse(state["synced_today"])

    def test_watch_workout_synced_today_replaces_manual_logging(self):
        start_sick_mode(self.conn, "below_neck", today=TODAY)
        self.conn.execute("INSERT INTO activities (id, date, type, name) VALUES ('strava-1', ?, 'Yoga', 'Flexibility')", (TODAY.isoformat(),))
        state = build_sick_mode(self.conn, today=TODAY)
        self.assertTrue(state["synced_today"])
        self.assertTrue(all(session["watch_workout"] for session in state["sessions"]))
        self.assertNotIn("WeightTraining", [session["type"] for session in state["sessions"]])

    def test_sessions_expose_structured_exercises_and_readable_steps(self):
        session = public_session("gentle_stretch")
        self.assertEqual(session["steps"][0], "Knee-to-chest 1 min/side")
        self.assertEqual(public_session("light_circuit")["steps"][:2], ["3 easy rounds", "Air squats ×10"])
        self.assertIsNone(public_session("sprints"))
        for key in SESSIONS:
            self.assertTrue(all(("reps" in item) != ("seconds" in item) for item in SESSIONS[key]["exercises"]), key)

    def test_duration_comes_from_the_exercises(self):
        self.assertEqual(public_session("light_circuit")["duration_min"], 12)  # 3 rounds, ≥10 min
        self.assertEqual(public_session("easy_walk")["duration_min"], 20)

    def add_synced(self, activity_id, started_at, name="Evening Workout"):
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, 'WeightTraining', ?, 10.1)", (activity_id, TODAY.isoformat(), name))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', ?, ?, ?)", (activity_id, activity_id, started_at))

    def test_guided_completion_links_the_watch_workout_closest_in_time(self):
        start_sick_mode(self.conn, "above_neck", today=TODAY)
        self.add_synced("morning", f"{TODAY.isoformat()}T07:00:00+00:00", "Morning Walk")
        payload = {"session_key": "light_circuit", "started_at": f"{TODAY.isoformat()}T18:06:00.000Z", "elapsed_seconds": 380, "extras": ["Pull-ups ×5"]}
        state = save_sick_session_completion(self.conn, payload, today=TODAY)
        self.assertIsNone(state["completed_today"][0]["activity_id"])  # watch workout not synced yet
        self.add_synced("evening", f"{TODAY.isoformat()}T18:07:34+00:00")
        state = save_sick_session_completion(self.conn, {**payload, "elapsed_seconds": 610}, today=TODAY)  # extra round, same row
        [completion] = state["completed_today"]
        self.assertEqual((completion["activity_id"], completion["elapsed_min"], completion["extras"]), ("evening", 10.2, ["Pull-ups ×5"]))
        self.assertTrue(next(s for s in state["sessions"] if s["key"] == "light_circuit")["completed_today"])
        row = self.conn.execute("SELECT workout_intent, notes FROM activities WHERE id = 'evening'").fetchone()
        self.assertEqual(row["workout_intent"], "mobility")
        self.assertIn("Light bodyweight circuit + Pull-ups ×5", row["notes"])
        self.assertIsNone(self.conn.execute("SELECT workout_intent FROM activities WHERE id = 'morning'").fetchone()[0])

    def test_sick_dates_cover_open_periods(self):
        start_sick_mode(self.conn, "above_neck", today=TODAY - timedelta(days=1))
        self.assertEqual(sick_dates(self.conn), {(TODAY - timedelta(days=1)).isoformat(), TODAY.isoformat()})

    def test_unknown_session_is_rejected(self):
        with self.assertRaises(ValueError):
            log_sick_session(self.conn, "sprints")

    def test_end_closes_period_and_counts_sick_days(self):
        start_sick_mode(self.conn, "above_neck", today=TODAY - timedelta(days=3))
        self.assertEqual(end_sick_mode(self.conn, today=TODAY), {"active": False})
        self.assertEqual(sick_days_between(self.conn, TODAY - timedelta(days=6), TODAY), 4)
        self.assertEqual(sick_days_between(self.conn, TODAY + timedelta(days=1), TODAY + timedelta(days=7)), 0)


if __name__ == "__main__":
    unittest.main()
