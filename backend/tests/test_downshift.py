import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.dashboard import compute_activity_streak
from backend.app.services.downshift import build_downshift, downshift_coaching_context
from backend.app.services.guided_sessions import public_session, save_guided_completion
from backend.app.services.life_load import set_life_load_day
from backend.app.services.sick_mode import build_sick_mode, log_sick_session, start_sick_mode
from backend.tests.test_sick_mode import SCHEMA

EXTRA_SCHEMA = """
CREATE TABLE daily_checkins (
    date TEXT PRIMARY KEY, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL, stress INTEGER NOT NULL,
    sleep_quality INTEGER NOT NULL, pain_level INTEGER NOT NULL DEFAULT 0, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE life_load_days (
    date TEXT PRIMARY KEY, tags_json TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

TODAY = date.today()


class DownshiftTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA + EXTRA_SCHEMA)

    def tearDown(self):
        self.conn.close()

    def checkin(self, stress, day=TODAY):
        self.conn.execute("INSERT OR REPLACE INTO daily_checkins (date, energy, muscle_soreness, stress, sleep_quality) VALUES (?, 3, 2, ?, 3)", (day.isoformat(), stress))

    def finish(self, key="two_minute_downshift", minute=0):
        return save_guided_completion(self.conn, {"session_key": key, "started_at": f"{TODAY.isoformat()}T12:{minute:02d}:00Z", "elapsed_seconds": 130}, today=TODAY)

    def test_offered_on_high_stress_check_in_only(self):
        self.assertEqual(build_downshift(self.conn, TODAY), {"offer": False})
        self.checkin(3)
        self.assertFalse(build_downshift(self.conn, TODAY)["offer"])
        self.checkin(3, TODAY - timedelta(days=1))
        self.checkin(4)
        state = build_downshift(self.conn, TODAY)
        self.assertEqual(state["reasons"], ["stress 4/5 in today's check-in"])
        self.assertEqual([item["key"] for item in state["sessions"]], ["two_minute_downshift", "desk_mobility"])
        self.assertEqual(downshift_coaching_context(self.conn)["reasons"], ["stress 4/5 in today's check-in"])

    def test_offered_on_deadline_and_late_night_days(self):
        set_life_load_day(self.conn, TODAY.isoformat(), ["family"])
        self.assertFalse(build_downshift(self.conn, TODAY)["offer"])
        set_life_load_day(self.conn, TODAY.isoformat(), ["deadline", "late_night"])
        self.assertEqual(build_downshift(self.conn, TODAY)["reasons"], ["deadline day", "late night day"])

    def test_never_offered_in_sick_mode(self):
        self.checkin(5)
        start_sick_mode(self.conn, "above_neck", today=TODAY)
        self.assertEqual(build_downshift(self.conn, TODAY), {"offer": False})

    def test_sessions_are_short_and_have_no_watch_workout(self):
        two_minute = public_session("two_minute_downshift")
        self.assertEqual((two_minute["duration_min"], two_minute["watch_workout"], two_minute["context_label"]), (2, None, "Downshift"))
        self.assertLessEqual(public_session("desk_mobility")["duration_min"], 10)

    def test_finished_downshift_keeps_the_streak_without_an_activity(self):
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('y', ?, 'Ride')", ((TODAY - timedelta(days=1)).isoformat(),))
        self.checkin(4)
        self.finish()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 1)
        self.assertEqual(compute_activity_streak(self.conn)["value"], 2)
        state = build_downshift(self.conn, TODAY)
        self.assertTrue(next(item for item in state["sessions"] if item["key"] == "two_minute_downshift")["completed_today"])
        self.assertEqual([item["title"] for item in state["completed_today"]], ["Two-minute downshift"])

    def test_done_downshift_stays_visible_after_the_trigger_clears(self):
        self.finish()
        self.assertTrue(build_downshift(self.conn, TODAY)["offer"])

    def test_downshift_never_relabels_a_real_session(self):
        self.conn.execute("INSERT INTO activities (id, date, type, name) VALUES ('ride', ?, 'Ride', 'Lunch ride')", (TODAY.isoformat(),))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'ride', 'ride', ?)", (f"{TODAY.isoformat()}T12:05:00+00:00",))
        state = self.finish()
        self.assertIsNone(state["completed_today"][0]["activity_id"])
        self.assertIsNone(self.conn.execute("SELECT workout_intent FROM activities WHERE id = 'ride'").fetchone()[0])

    def test_sick_mode_lists_and_logs_only_sick_sessions(self):
        state = start_sick_mode(self.conn, "below_neck", today=TODAY)
        self.assertNotIn("two_minute_downshift", [item["key"] for item in state["sessions"]])
        self.finish()
        self.assertEqual(build_sick_mode(self.conn, today=TODAY)["completed_today"], [])
        with self.assertRaises(ValueError):
            log_sick_session(self.conn, "two_minute_downshift", today=TODAY)


if __name__ == "__main__":
    unittest.main()
