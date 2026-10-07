import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from backend.app import db
from backend.app.services import week_report

WEEK = date(2030, 1, 28)  # A Monday, with four earlier weeks to form the norm.


class WeekReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2029-01-01', '2031-01-01', 1, 'active', 'anchor')"
        )
        self.count = 0

    def add(self, day, kind="Ride", minutes=60):
        self.count += 1
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, ?, ?, ?)",
            (f"a{self.count}", day.isoformat(), kind, kind, minutes),
        )
        self.conn.commit()

    def usual_weeks(self, weeks=4):
        """Each earlier week: two 60-minute rides and three lifts of 40 minutes."""
        for index in range(1, weeks + 1):
            monday = WEEK - timedelta(weeks=index)
            for offset in (0, 3):
                self.add(monday + timedelta(days=offset))
            for offset in (1, 2, 4):
                self.add(monday + timedelta(days=offset), "WeightTraining", 40)

    def report(self, today, week=WEEK):
        return week_report.build_week_report(self.conn, week, today=today)

    def test_a_finished_week_is_measured_against_the_four_weeks_before_it(self):
        self.usual_weeks()
        self.add(WEEK, minutes=60)
        self.add(WEEK + timedelta(days=1), "WeightTraining", 40)
        self.add(WEEK + timedelta(days=5), "Walk", 90)

        result = self.report(date(2030, 2, 5))

        self.assertTrue(result["finished"])
        self.assertEqual(result["norm"]["minutes"], 240)
        self.assertEqual(result["norm"]["sessions"], 5)
        # Walks count as movement but not training.
        self.assertEqual(result["totals"]["minutes"], 100)
        self.assertEqual(result["totals"]["movement_minutes"], 190)
        self.assertEqual(result["totals"]["sessions"], 2)
        self.assertEqual(result["goals"][0]["done"], 1)
        self.assertFalse(result["goals"][0]["met"])
        volume = next(item for item in result["insights"] if item["key"] == "volume")
        self.assertEqual(volume["tone"], "warn")
        self.assertIn("58% under your usual 4h 00m for a full week", volume["text"])
        self.assertEqual([week["current"] for week in result["history"]][-1], True)
        self.assertEqual(len(result["history"]), 8)
        self.assertEqual(result["next_week"], "2030-02-04")

    def test_a_running_week_compares_with_the_usual_week_up_to_the_same_day(self):
        self.usual_weeks()
        self.add(WEEK, minutes=60)
        self.add(WEEK + timedelta(days=1), "WeightTraining", 40)

        result = self.report(WEEK + timedelta(days=1))

        self.assertFalse(result["finished"])
        self.assertEqual(result["day_of_week"], 2)
        # Usual Monday and Tuesday: one ride and one lift.
        self.assertEqual(result["norm"]["minutes_to_date"], 100)
        volume = next(item for item in result["insights"] if item["key"] == "volume")
        self.assertEqual(volume["tone"], "good")
        self.assertTrue(result["days"][2]["future"])
        self.assertIsNone(result["next_week"])

    def test_todays_open_session_is_not_missed_yet(self):
        days = [
            {"date": (WEEK + timedelta(days=offset)).isoformat(), "session_type": "ride" if offset < 3 else "rest",
             "title": f"Ride {offset}", "target_duration_min": 60}
            for offset in range(7)
        ]
        self.conn.execute(
            "INSERT INTO weekly_plans (week_start, title, focus, overview, days_json) VALUES (?, 'Plan', '', '', ?)",
            (WEEK.isoformat(), json.dumps(days)),
        )
        self.add(WEEK, minutes=60)

        result = self.report(WEEK + timedelta(days=2))

        states = [item["state"] for day in result["days"] for item in day["planned"]]
        self.assertEqual(states[:3], ["done", "missed", "upcoming"])
        self.assertEqual((result["plan"]["done"], result["plan"]["planned"]), (1, 2))
        self.assertEqual(result["plan"]["missed"], ["Ride 1"])

    def test_three_falling_weeks_are_called_out(self):
        for index, minutes in enumerate((600, 400, 250, 120)):
            self.add(WEEK - timedelta(weeks=4 - index), minutes=minutes)
        self.add(WEEK, minutes=60)

        result = self.report(date(2030, 2, 4))

        trend = next(item for item in result["insights"] if item["key"] == "trend")
        self.assertIn("dropped 4 weeks in a row, from 10h 00m to 1h 00m", trend["text"])

    def test_a_week_that_has_not_started_is_refused(self):
        with self.assertRaises(ValueError):
            self.report(WEEK - timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
