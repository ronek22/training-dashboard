import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.services.widget_brief import WIDGET_FILE_NAME, build_widget_brief, write_widget_brief

WEEK = "2030-01-07"
DAYS = [
    ("2030-01-07", "Mon", "Rest", None, "Rest", None),
    ("2030-01-08", "Tue", "WeightTraining", None, "Workout A", 45),
    ("2030-01-09", "Wed", "Ride", "easy", "Easy aerobic ride", 45),
    ("2030-01-10", "Thu", "WeightTraining", None, "Workout B", 45),
    ("2030-01-11", "Fri", "Ride", "interval", "VO2 intervals", 60),
    ("2030-01-12", "Sat", "Rest", None, "Rest", None),
    ("2030-01-13", "Sun", "Ride", "easy", "Easy ride", 90),
]
TODAY = date(2030, 1, 10)


class WidgetBriefTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp_dir = temp.name
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        days = [
            {"date": day, "label": label, "session_type": kind, "workout_intent": intent, "title": title, "target_duration_min": minutes}
            for day, label, kind, intent, title, minutes in DAYS
        ]
        self.conn.execute("INSERT INTO weekly_plans (week_start, title, days_json) VALUES (?, ?, ?)", (WEEK, "Test week", json.dumps(days)))
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("a1", "2030-01-08", "WeightTraining", "Workout A", 47),
        )
        self.conn.commit()

    def test_today_and_tomorrow_come_from_the_current_week(self):
        brief = build_widget_brief(self.conn, TODAY)
        self.assertEqual(brief["date"], "2030-01-10")
        self.assertEqual(brief["today"]["title"], "Workout B")
        self.assertEqual(brief["today"]["duration_min"], 45)
        self.assertEqual(brief["tomorrow"]["title"], "VO2 intervals")
        self.assertFalse(brief["checkin_done"])
        self.assertIsNone(brief["sick"])
        self.assertIn(brief["readiness"]["level"], {"green", "amber", "red", "unknown"})

    def test_week_strip_marks_done_missed_rest_today_and_upcoming(self):
        statuses = {day["label"]: day["status"] for day in build_widget_brief(self.conn, TODAY)["week"]}
        self.assertEqual(
            statuses,
            {"Mon": "rest", "Tue": "done", "Wed": "missed", "Thu": "today", "Fri": "upcoming", "Sat": "upcoming", "Sun": "upcoming"},
        )

    def test_no_plan_for_the_week_leaves_sessions_empty(self):
        brief = build_widget_brief(self.conn, date(2030, 3, 6))
        self.assertIsNone(brief["today"])
        self.assertEqual(brief["week"], [])

    def test_write_replaces_the_file_without_leaving_temp_files(self):
        out = os.path.join(self.temp_dir, "icloud")
        write_widget_brief(self.conn, out, TODAY)
        path = write_widget_brief(self.conn, out, TODAY)
        self.assertEqual(os.listdir(out), [WIDGET_FILE_NAME])
        with open(path, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream)["today"]["title"], "Workout B")


if __name__ == "__main__":
    unittest.main()
