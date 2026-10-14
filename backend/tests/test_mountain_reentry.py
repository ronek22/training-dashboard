import json
import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.mountain_reentry import (
    build_mountain_reentry,
    mountain_reentry_coaching_context,
    mountain_reentry_dates,
    mountain_reentry_readiness_factor,
    window_length,
)
from backend.app.services.session_brief import build_session_brief

SCHEMA = """
CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT);
CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, streams_json TEXT);
CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, rpe INTEGER, energy INTEGER, muscle_soreness INTEGER,
    pain_level INTEGER DEFAULT 0, note TEXT);
CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric TEXT, value REAL, date TEXT);
CREATE TABLE daily_checkins (date TEXT PRIMARY KEY, energy INTEGER, muscle_soreness INTEGER, stress INTEGER,
    sleep_quality INTEGER, pain_level INTEGER, note TEXT, updated_at TEXT);
CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT, end_date TEXT, severity TEXT DEFAULT 'above_neck');
CREATE TABLE life_load_days (date TEXT PRIMARY KEY, tags_json TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT INTO metrics (metric, value, date) VALUES ('ftp', 250, '2026-09-20');
"""

# A Sunday: trips usually end on a weekend, so the window runs into the next plan week.
LAST_DAY = date(2026, 10, 11)


def day(offset: int) -> date:
    return LAST_DAY + timedelta(days=offset)


class MountainReentryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.addCleanup(self.conn.close)

    def _trip(self, days: int, last: date = LAST_DAY, tags=("mountains",)):
        for offset in range(days):
            self.conn.execute(
                "INSERT INTO life_load_days (date, tags_json) VALUES (?, ?)",
                ((last - timedelta(days=offset)).isoformat(), json.dumps(list(tags))),
            )

    def test_window_length_scales_with_the_trip_and_caps_at_four_days(self):
        self.assertEqual([window_length(days) for days in (1, 2, 3, 4, 5, 6, 7, 10)], [0, 0, 2, 2, 3, 3, 4, 4])

    def test_short_runs_and_other_tags_open_no_window(self):
        self._trip(2)
        self.assertIsNone(build_mountain_reentry(self.conn, day(1)))
        self._trip(3, day(-10), tags=("travel",))
        self.assertIsNone(build_mountain_reentry(self.conn, day(-9)))

    def test_trip_ending_on_sunday_opens_the_window_on_monday(self):
        self._trip(5)
        self.assertEqual(LAST_DAY.weekday(), 6)
        self.assertIsNone(build_mountain_reentry(self.conn, LAST_DAY), "still on the trip")

        monday = build_mountain_reentry(self.conn, day(1))
        self.assertEqual((monday["day_number"], monday["length_days"], monday["ends_on"]), (1, 3, day(3).isoformat()))
        self.assertEqual((monday["phase"], monday["rpe_cap"]), ("easy", 4))
        self.assertEqual(monday["trip"], {"start_date": day(-4).isoformat(), "end_date": LAST_DAY.isoformat(), "days": 5})
        self.assertEqual(build_mountain_reentry(self.conn, day(2))["phase"], "easy")
        self.assertEqual(build_mountain_reentry(self.conn, day(3))["phase"], "build")
        self.assertIsNone(build_mountain_reentry(self.conn, day(4)))
        self.assertEqual(mountain_reentry_dates(self.conn, day(2)), {day(2).isoformat(), day(3).isoformat()})

    def test_three_day_trip_is_one_easy_day_then_one_moderate(self):
        self._trip(3)
        self.assertEqual(build_mountain_reentry(self.conn, day(1))["phase"], "easy")
        self.assertEqual(build_mountain_reentry(self.conn, day(2))["phase"], "build")
        self.assertIsNone(build_mountain_reentry(self.conn, day(3)))

    def test_long_trip_window_is_capped_at_four_days(self):
        self._trip(9)
        self.assertEqual(build_mountain_reentry(self.conn, day(4))["length_days"], 4)
        self.assertIsNone(build_mountain_reentry(self.conn, day(5)))

    def test_readiness_factor_and_coaching_context(self):
        self._trip(4)
        state = build_mountain_reentry(self.conn, day(1))
        self.assertEqual(mountain_reentry_readiness_factor(state)["label"], "Back from the mountains")
        context = mountain_reentry_coaching_context(self.conn, day(1))
        self.assertEqual((context["window_ends_on"], context["rpe_cap"], context["trip_days"]), (day(2).isoformat(), 4, 4))
        self.assertIn("no extra leg sets", context["guidance"])
        self.assertIsNone(mountain_reentry_coaching_context(self.conn, day(5)))

    def test_ride_brief_is_capped_and_quality_rides_ridden_as_endurance(self):
        self._trip(5)
        brief = build_session_brief(self.conn, {"session_type": "ride", "workout_intent": "interval"}, day(1))
        self.assertEqual(brief["feel"]["rpe"], "≤4")
        self.assertTrue(brief["notes"][0].startswith("Day 1 of 3 back from the mountains"))
        self.assertTrue(brief["bail"][0].startswith("Ride it as endurance"))

    def test_lower_body_lift_holds_loads_and_upper_body_is_untouched(self):
        self._trip(5)
        lower = build_session_brief(self.conn, {"session_type": "strength", "workout_intent": "strength_lower"}, day(1))
        self.assertIn({"label": "Reps in reserve", "value": "2+"}, lower["targets"])
        self.assertIn("pre-trip loads", lower["notes"][0])
        self.assertEqual(lower["sport"], "strength", "the lift stays on the plan")

        upper = build_session_brief(self.conn, {"session_type": "strength", "workout_intent": "strength_upper"}, day(1))
        self.assertNotIn("mountain_reentry", upper)
        self.assertIn({"label": "Reps in reserve", "value": "1–2"}, upper["targets"])

    def test_overlap_with_illness_return_takes_the_stricter_cap(self):
        self._trip(5)
        # Sick for 6 days ending the day before: day 4 of 6 back from illness is "moderate" (RPE ≤7).
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES (?, ?)", (day(-8).isoformat(), day(-3).isoformat()))
        brief = build_session_brief(self.conn, {"session_type": "ride", "workout_intent": "easy"}, day(1))
        self.assertEqual(brief["illness_return"]["rpe_cap"], 7)
        self.assertEqual(brief["feel"]["rpe"], "≤4", "mountain re-entry is stricter here")

        # Day 1 back from illness (RPE ≤5) during the moderate mountain phase (RPE ≤6): illness wins.
        self.conn.execute("UPDATE sick_periods SET end_date = ?", (day(2).isoformat(),))
        brief = build_session_brief(self.conn, {"session_type": "ride", "workout_intent": "easy"}, day(3))
        self.assertEqual((brief["illness_return"]["rpe_cap"], brief["mountain_reentry"]["rpe_cap"]), (5, 6))
        self.assertEqual(brief["feel"]["rpe"], "≤5")


if __name__ == "__main__":
    unittest.main()
