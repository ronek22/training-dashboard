import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.illness_return import (
    build_illness_return,
    illness_return_coaching_context,
    illness_return_dates,
    illness_return_readiness_factor,
    mentions_symptoms,
)

SCHEMA = """
CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, name TEXT);
CREATE TABLE activity_feedback (
    activity_id TEXT PRIMARY KEY, rpe INTEGER NOT NULL, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL,
    pain_level INTEGER NOT NULL DEFAULT 0, note TEXT
);
CREATE TABLE daily_checkins (
    date TEXT PRIMARY KEY, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL, stress INTEGER NOT NULL,
    sleep_quality INTEGER NOT NULL, pain_level INTEGER NOT NULL DEFAULT 0, note TEXT
);
CREATE TABLE sick_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT NOT NULL, end_date TEXT,
    severity TEXT NOT NULL DEFAULT 'above_neck', note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

ENDED = date(2026, 10, 6)


def day(offset: int) -> str:
    return (ENDED + timedelta(days=offset)).isoformat()


class IllnessReturnTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def _sick(self, start_offset: int, end_offset=0):
        self.conn.execute(
            "INSERT INTO sick_periods (start_date, end_date) VALUES (?, ?)",
            (day(start_offset), None if end_offset is None else day(end_offset)),
        )

    def _session(self, offset: int, rpe: int, note=None, name="Lift"):
        activity_id = f"a{offset}-{rpe}"
        self.conn.execute("INSERT INTO activities VALUES (?, ?, 'WeightTraining', ?)", (activity_id, day(offset), name))
        self.conn.execute("INSERT INTO activity_feedback (activity_id, rpe, energy, muscle_soreness, note) VALUES (?, ?, 3, 1, ?)", (activity_id, rpe, note))

    def test_off_without_sick_history_or_while_still_sick(self):
        self.assertIsNone(build_illness_return(self.conn, ENDED))
        self._sick(-5, None)
        self.assertIsNone(build_illness_return(self.conn, ENDED + timedelta(days=1)))
        self.conn.execute("DROP TABLE sick_periods")
        self.assertIsNone(build_illness_return(self.conn, ENDED))
        self.assertEqual(illness_return_dates(self.conn, ENDED), set())

    def test_window_matches_sickness_length_within_bounds(self):
        self._sick(-5)  # 6 days sick -> 6 days back
        state = build_illness_return(self.conn, ENDED + timedelta(days=1))
        self.assertEqual((state["day_number"], state["length_days"], state["ends_on"]), (1, 6, day(6)))
        self.assertEqual(state["phase"], "easy")
        self.assertEqual(build_illness_return(self.conn, ENDED + timedelta(days=4))["phase"], "build")
        self.assertIsNone(build_illness_return(self.conn, ENDED + timedelta(days=7)))
        self.assertIsNone(build_illness_return(self.conn, ENDED), "the day sick mode ends is still sick mode")

    def test_short_sickness_still_gets_three_days_and_long_caps_at_seven(self):
        self._sick(0)
        self.assertEqual(build_illness_return(self.conn, ENDED + timedelta(days=1))["length_days"], 3)
        self.conn.execute("DELETE FROM sick_periods")
        self._sick(-13)
        self.assertEqual(build_illness_return(self.conn, ENDED + timedelta(days=1))["length_days"], 7)

    def test_symptom_notes_stretch_the_window_and_keep_it_easy(self):
        self._sick(-2)  # 3 days sick -> 3 days back
        self._session(4, 5, "Still feel post sickness symptoms, sinuses")
        state = build_illness_return(self.conn, ENDED + timedelta(days=5))
        self.assertEqual(state["length_days"], 7)
        self.assertTrue(state["lingering_symptoms"])
        self.assertEqual(state["phase"], "easy")
        self.assertEqual(state["last_symptom_date"], day(4))
        factor = illness_return_readiness_factor(state)
        self.assertEqual((factor["tone"], factor["points"]), ("risk", 2))

    def test_morning_check_in_notes_count_too(self):
        self._sick(-2)
        self.conn.execute("INSERT INTO daily_checkins (date, energy, muscle_soreness, stress, sleep_quality, note) VALUES (?, 2, 1, 3, 3, 'katar i ból głowy')", (day(3),))
        self.assertTrue(build_illness_return(self.conn, ENDED + timedelta(days=4))["lingering_symptoms"])

    def test_hard_sessions_in_the_window_are_named(self):
        self._sick(-5)
        self._session(-1, 9, name="Before")  # inside sick mode: not part of the return
        self._session(2, 9, "very hard effort", name="Workout B")
        state = build_illness_return(self.conn, ENDED + timedelta(days=3))
        self.assertEqual([item["name"] for item in state["hard_sessions"]], ["Workout B"])
        self.assertIn("RPE 9, too hard this soon", state["message"])
        context = illness_return_coaching_context(self.conn, ENDED + timedelta(days=3))
        self.assertEqual(context["hard_sessions_in_window"], [f"{day(2)} Workout B RPE 9"])
        self.assertEqual(context["window_ends_on"], day(6))

    def test_dates_run_from_today_to_the_window_end(self):
        self._sick(-5)
        self.assertEqual(illness_return_dates(self.conn, ENDED + timedelta(days=4)), {day(4), day(5), day(6)})

    def test_symptom_words_ignore_negations_and_cold_weather(self):
        self.assertTrue(mentions_symptoms("Still feel a little sick"))
        self.assertTrue(mentions_symptoms("Jeszcze trochę chory, katar"))
        self.assertTrue(mentions_symptoms("caught a cold"))
        self.assertFalse(mentions_symptoms("Not sick anymore, felt great"))
        self.assertFalse(mentions_symptoms("Cold morning, legs heavy"))
        self.assertFalse(mentions_symptoms("Still pushing hard"))
        self.assertFalse(mentions_symptoms(None))


if __name__ == "__main__":
    unittest.main()
