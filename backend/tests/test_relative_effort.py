import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.relative_effort import build_relative_effort

SCHEMA = """
CREATE TABLE activities (id INTEGER PRIMARY KEY, date TEXT, type TEXT, duration_min REAL, avg_hr INTEGER);
CREATE TABLE activity_stream_summaries (activity_id INTEGER PRIMARY KEY, hr_trimp REAL);
"""

TODAY = date(2026, 10, 8)  # Thursday
CURRENT_WEEK = TODAY - timedelta(days=TODAY.weekday())
THRESHOLDS = {"resting_hr": 50.0, "run_max_hr": 190.0, "ride_max_hr": 180.0}


class RelativeEffortTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def add(self, day, trimp=None, activity_type="Ride", duration=60, avg_hr=None):
        cursor = self.conn.execute(
            "INSERT INTO activities (date, type, duration_min, avg_hr) VALUES (?, ?, ?, ?)",
            (day.isoformat(), activity_type, duration, avg_hr),
        )
        if trimp is not None:
            self.conn.execute("INSERT INTO activity_stream_summaries VALUES (?, ?)", (cursor.lastrowid, trimp))

    def build(self):
        return build_relative_effort(self.conn, today=TODAY, thresholds=THRESHOLDS)

    def seed_baseline(self, per_week=300):
        for weeks_back in (1, 2, 3):
            self.add(CURRENT_WEEK - timedelta(weeks=weeks_back), trimp=per_week)

    def test_range_comes_from_last_three_full_weeks(self):
        self.seed_baseline(300)
        self.add(CURRENT_WEEK, trimp=100)

        result = self.build()

        self.assertEqual(result["range"], {"low": 201, "high": 399, "baseline": 300})
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["status"], "below")
        self.assertIn("101 more reaches your range", result["detail"])
        self.assertIn("stay under 201", result["detail"])

    def test_in_and_above_range(self):
        self.seed_baseline(300)
        self.add(CURRENT_WEEK, trimp=300)
        self.assertEqual(self.build()["status"], "in")

        self.add(CURRENT_WEEK + timedelta(days=1), trimp=200)
        result = self.build()
        self.assertEqual(result["status"], "above")
        self.assertEqual(result["headline"], "Above weekly range")

    def test_no_range_without_history(self):
        self.add(CURRENT_WEEK, trimp=80)

        result = self.build()

        self.assertIsNone(result["range"])
        self.assertEqual(result["status"], "unknown")

    def test_sessions_without_stream_use_average_hr_then_duration(self):
        self.add(CURRENT_WEEK, activity_type="WeightTraining", duration=40, avg_hr=120)
        self.add(CURRENT_WEEK + timedelta(days=1), activity_type="WeightTraining", duration=40)

        result = self.build()

        self.assertEqual(result["sessions"], 2)
        self.assertEqual(result["estimated_sessions"], 1)
        monday, tuesday = result["days"][0], result["days"][1]
        self.assertGreater(monday["effort"], 0)
        self.assertEqual(tuesday["effort"], 32)  # 40 min × 0.8 duration fallback

    def test_days_cover_the_week_and_mark_future(self):
        self.add(CURRENT_WEEK + timedelta(days=2), trimp=90)

        days = self.build()["days"]

        self.assertEqual([day["label"] for day in days], ["M", "T", "W", "T", "F", "S", "S"])
        self.assertEqual(days[2]["effort"], 90)
        self.assertEqual([day["is_future"] for day in days], [False] * 4 + [True] * 3)

    def test_history_has_eight_weeks_ending_with_current(self):
        weeks = self.build()["weeks"]

        self.assertEqual(len(weeks), 8)
        self.assertEqual(weeks[-1]["week_start"], CURRENT_WEEK.isoformat())
        self.assertTrue(weeks[-1]["is_current"])


if __name__ == "__main__":
    unittest.main()
