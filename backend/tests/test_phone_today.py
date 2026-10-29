import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.services.phone_today import build_phone_today, sport_of

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


class PhoneTodayTests(unittest.TestCase):
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
        days = [
            {"date": day, "label": label, "session_type": kind, "workout_intent": intent, "title": title, "target_duration_min": minutes}
            for day, label, kind, intent, title, minutes in DAYS
        ]
        self.conn.execute("INSERT INTO weekly_plans (week_start, title, days_json) VALUES (?, ?, ?)", (WEEK, "Test week", json.dumps(days)))
        self.conn.executemany(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, ?, ?, ?)",
            [
                ("a1", "2030-01-08", "WeightTraining", "Workout A", 47),
                ("a2", "2030-01-08", "VirtualRide", "Spin", 30),
                ("a3", "2030-01-03", "WeightTraining", "Workout B", 40),
            ],
        )
        template_id = self.conn.execute("INSERT INTO strength_workout_templates (name) VALUES ('Workout B')").lastrowid
        self.conn.executemany(
            "INSERT INTO strength_template_exercises (template_id, exercise_order, exercise_name, set_count, target_reps, target_weight_kg, rest_seconds) VALUES (?, ?, ?, ?, ?, ?, 90)",
            [(template_id, 1, "Pull-up", 3, 6, None), (template_id, 2, "Dumbbell Row", 3, 10, 34.0)],
        )
        self.conn.commit()

    def test_strength_day_lists_the_template_exercises_and_last_done(self):
        today = build_phone_today(self.conn, TODAY)["today"]
        self.assertEqual(today["sport"], "strength")
        strength = today["strength"]
        self.assertEqual([item["name"] for item in strength["exercises"]], ["Pull-up", "Dumbbell Row"])
        self.assertEqual(strength["exercises"][1]["sets"], 3)
        self.assertEqual(strength["last_done"], "2030-01-03")

    def test_week_shows_done_sports_and_minutes(self):
        brief = build_phone_today(self.conn, TODAY)
        tuesday = brief["week"][1]
        self.assertEqual(tuesday["status"], "done")
        self.assertEqual(tuesday["done_sports"], ["strength", "ride"])
        self.assertEqual(brief["week"][3]["status"], "today")
        self.assertEqual(brief["week_minutes"]["done"], 77)
        self.assertEqual(brief["week_minutes"]["planned"], 285)
        self.assertEqual(brief["week_minutes"]["by_sport"][0], {"sport": "strength", "minutes": 47})

    def test_without_a_plan_the_week_still_has_seven_days(self):
        brief = build_phone_today(self.conn, date(2030, 3, 6))
        self.assertIsNone(brief["today"])
        self.assertEqual(len(brief["week"]), 7)
        self.assertEqual(brief["week"][2]["status"], "today")

    def test_readiness_carries_points_and_factors_and_vitals_carry_ranges(self):
        brief = build_phone_today(self.conn, TODAY)
        self.assertIsInstance(brief["readiness"]["points"], int)
        for factor in brief["readiness"]["factors"]:
            self.assertEqual(set(factor), {"key", "label", "tone", "points"})
        self.assertEqual(brief["vitals"]["ranges"], [])

    def test_sport_of_maps_types_to_app_colours(self):
        self.assertEqual(sport_of("VirtualRide"), "ride")
        self.assertEqual(sport_of("recovery"), "mobility")
        self.assertEqual(sport_of("Workout", "mobility"), "mobility")
        self.assertEqual(sport_of("Hike"), "hike")


if __name__ == "__main__":
    unittest.main()
