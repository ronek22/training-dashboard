import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest import mock

from backend.app import db
from backend.app.services import month_report, monthly_letters

TODAY = date(2030, 10, 3)  # September 2030 is finished; October is running.


def lift(day, name, weight, reps, sets=1):
    return {"workout_date": day, "exercises": [{"exercise_name": name, "sets": [{"weight_kg": weight, "reps": reps}] * sets}]}


class MonthReportTests(unittest.TestCase):
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
        for target, value in ((monthly_letters, "get_sleep_history"), (month_report, "build_running_fitness")):
            patch = mock.patch.object(target, value, return_value=[] if value == "get_sleep_history" else {})
            patch.start()
            self.addCleanup(patch.stop)
        self.sessions = mock.patch.object(month_report, "_session_index", return_value=[])
        self.session_index = self.sessions.start()
        self.addCleanup(self.sessions.stop)
        self.count = 0

    def add(self, day, kind="WeightTraining", minutes=45):
        self.count += 1
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, ?, ?, ?)",
            (f"a{self.count}", day, kind, kind, minutes),
        )
        self.conn.commit()

    def weigh(self, day, kg):
        self.conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES (?, 'weight', ?, 'kg')", (day, kg))
        self.conn.commit()

    def report(self, month="2030-09", today=TODAY):
        return month_report.build_month_report(self.conn, month, today=today)

    def test_a_finished_month_has_totals_a_calendar_and_the_letters_wins_without_saving_a_letter(self):
        for day in ("2030-08-04", "2030-08-11"):
            self.add(day, "Ride", 60)
        self.add("2030-09-01", "Ride", 60)
        self.add("2030-09-01", "Walk", 120)  # the ride is the day's training, even though the walk is longer
        self.add("2030-09-02", "Hike", 300)
        self.add("2030-09-03", "Walk", 40)
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES ('2030-09-10', '2030-09-11')")
        self.conn.commit()

        result = self.report()

        self.assertTrue(result["finished"])
        self.assertEqual(result["previous_month"], "2030-08")
        self.assertEqual(result["next_month"], "2030-10")
        self.assertEqual(result["totals"]["minutes"], 360)  # walks are movement, not training
        self.assertEqual(result["totals"]["movement_minutes"], 520)
        self.assertEqual(result["totals"]["days"], 30)
        self.assertEqual(result["prior_average"]["minutes"], 120)
        days = {day["date"]: day for day in result["days"]}
        self.assertEqual(len(days), 30)
        self.assertEqual(days["2030-09-01"]["sport"], "cycling")
        self.assertEqual(days["2030-09-01"]["minutes"], 180)
        self.assertEqual(days["2030-09-02"]["sport"], "hiking")
        self.assertEqual(days["2030-09-03"]["sport"], "walking")
        self.assertIsNone(days["2030-09-04"]["sport"])
        self.assertTrue(days["2030-09-10"]["sick"])
        self.assertFalse(any(day["future"] for day in result["days"]))
        self.assertEqual(result["rides"]["previous_minutes"], 120)
        self.assertEqual(result["rides"]["hiking_minutes"], 300)
        self.assertIsNotNone(result["focus"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM monthly_letters").fetchone()[0], 0)

    def test_a_running_month_compares_with_the_usual_to_date_and_has_no_wins_yet(self):
        for day in ("2030-07-05", "2030-08-05", "2030-09-05"):
            self.add(day, "Ride", 300)
        self.add("2030-10-01", "Ride", 90)
        self.add("2030-10-02", "Ride", 60)

        result = self.report("2030-10")

        self.assertFalse(result["finished"])
        self.assertIsNone(result["next_month"])
        self.assertEqual(result["totals"]["days"], 31)
        self.assertEqual(result["totals"]["elapsed_days"], 3)
        self.assertEqual(result["prior_average"]["minutes_to_date"], round(300 * 3 / 31, 1))
        self.assertEqual(result["streak_days"], 2)  # today is still open, so the streak runs to yesterday
        self.assertTrue(result["days"][5]["future"])
        self.assertEqual(result["wins"], [])
        self.assertIsNone(result["focus"])

    def test_weight_trend_needs_three_weigh_ins_a_week_apart(self):
        self.weigh("2030-09-02", 80.0)
        self.weigh("2030-09-20", 80.5)
        self.assertFalse(self.report()["weight"]["available"])

        self.weigh("2030-09-29", 81.0)
        weight = self.report()["weight"]

        self.assertTrue(weight["available"])
        self.assertEqual([point["avg_kg"] for point in weight["weigh_ins"]], [80.0, 80.5, 81.0])
        self.assertEqual(weight["change_kg"], 1.0)
        self.assertEqual(weight["kg_per_week"], round(1.0 / 27 * 7, 2))
        self.assertEqual(weight["status"], "gentle_gain")  # 0.32% a week
        self.assertEqual(weight["lane_kg_per_week"], [0.08, 0.28])

    def test_lifts_are_tallied_against_last_months_best_e1rm(self):
        self.session_index.return_value = [
            lift("2030-08-05", "Squat", 100, 5), lift("2030-08-06", "Curl", 20, 8), lift("2030-08-07", "Row", 60, 8),
            lift("2030-09-05", "Squat", 100, 3, sets=3), lift("2030-09-06", "Curl", 22, 8), lift("2030-09-07", "Row", 60, 8, sets=2),
            lift("2030-09-08", "Press", 40, 5),  # new this month: nothing to compare with
        ]
        for day in ("2030-09-02", "2030-09-04", "2030-09-06", "2030-09-09"):
            self.add(day)

        strength = self.report()["strength"]

        self.assertEqual((strength["up"], strength["held"], strength["down"]), (1, 1, 1))
        self.assertEqual([item["name"] for item in strength["top"]], ["Squat", "Row", "Curl"])
        self.assertEqual(strength["dropped"][0]["name"], "Squat")
        self.assertLess(strength["dropped"][0]["change_kg"], 0)
        self.assertEqual(strength["lift_days"], 4)
        weeks = {week["week_start"]: week["days"] for week in strength["weeks"]}
        self.assertEqual(weeks["2030-09-02"], 3)
        self.assertEqual(weeks["2030-09-09"], 1)
        self.assertEqual(strength["weeks"][0]["week_start"], "2030-08-26")

    def test_a_month_that_has_not_started_is_refused(self):
        with self.assertRaises(ValueError):
            self.report("2030-11")


if __name__ == "__main__":
    unittest.main()
