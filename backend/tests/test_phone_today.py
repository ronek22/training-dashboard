import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app import db
from backend.app.services.food_log import save_nutrition_profile
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

    def test_protein_is_missing_without_a_weigh_in(self):
        self.assertIsNone(build_phone_today(self.conn, TODAY)["protein"])

    def test_protein_counts_todays_logged_food_against_the_target(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2030-01-09', 'weight', 81.0)")
        entry = self.conn.execute("INSERT INTO food_entries (date, meal, source) VALUES ('2030-01-10', 'lunch', 'text')").lastrowid
        yesterday = self.conn.execute("INSERT INTO food_entries (date, meal, source) VALUES ('2030-01-09', 'lunch', 'text')").lastrowid
        self.conn.executemany(
            "INSERT INTO food_items (entry_id, name, kcal, protein_g) VALUES (?, ?, 0, ?)",
            [(entry, "Chicken", 62.5), (entry, "Skyr", 35.0), (yesterday, "Eggs", 80.0)],
        )
        self.conn.commit()
        protein = build_phone_today(self.conn, TODAY)["protein"]
        self.assertEqual(protein, {"eaten_g": 97.5, "target_g": 130, "hit": False})

        self.conn.execute("INSERT INTO food_items (entry_id, name, kcal, protein_g) VALUES (?, 'Tuna', 0, 33)", (entry,))
        self.conn.commit()
        self.assertTrue(build_phone_today(self.conn, TODAY)["protein"]["hit"])

    def test_food_is_missing_until_the_profile_gives_a_target(self):
        self.assertIsNone(build_phone_today(self.conn, TODAY)["food"])

    def test_food_counts_todays_kcal_against_the_food_target(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2030-01-09', 'weight', 80.0)")
        save_nutrition_profile(self.conn, {"sex": "male", "birth_year": 1996, "height_cm": 175})
        entry = self.conn.execute("INSERT INTO food_entries (date, meal, source) VALUES ('2030-01-10', 'lunch', 'text')").lastrowid
        self.conn.execute("INSERT INTO food_items (entry_id, name, kcal, protein_g) VALUES (?, 'Pasta', 640.4, 20)", (entry,))
        self.conn.commit()
        food = build_phone_today(self.conn, TODAY)["food"]
        self.assertEqual(food["eaten_kcal"], 640)
        self.assertGreater(food["target_kcal"], 1500)

    def test_sleep_need_is_missing_without_enough_nights(self):
        self.assertIsNone(build_phone_today(self.conn, TODAY)["sleep_need"])

    def test_sleep_need_carries_the_median_night_and_the_debt(self):
        history = [{"date": (TODAY - timedelta(days=offset)).isoformat(), "value": 6.0 if offset < 7 else 7.5} for offset in range(40)]
        with patch("backend.app.services.phone_today.get_sleep_history", return_value=history):
            need = build_phone_today(self.conn, TODAY)["sleep_need"]
        self.assertEqual(need, {"need_h": 7.5, "debt_h": 10.5})

    def test_strength_day_lists_the_template_exercises_and_last_done(self):
        today = build_phone_today(self.conn, TODAY)["today"]
        self.assertEqual(today["sport"], "strength")
        strength = today["strength"]
        self.assertEqual([item["name"] for item in strength["exercises"]], ["Pull-up", "Dumbbell Row"])
        self.assertEqual(strength["exercises"][1]["sets"], 3)
        self.assertEqual(strength["last_done"], "2030-01-03")

    def test_bodyweight_day_lists_bodyweight_moves_without_a_template(self):
        row = self.conn.execute("SELECT days_json FROM weekly_plans").fetchone()
        days = json.loads(row["days_json"])
        days[3]["title"] = "Bodyweight upper + core (parents' home)"
        self.conn.execute("UPDATE weekly_plans SET days_json = ?", (json.dumps(days),))
        self.conn.commit()

        strength = build_phone_today(self.conn, TODAY)["today"]["strength"]
        self.assertIsNone(strength["template_id"])
        self.assertEqual(strength["name"], "Bodyweight upper + core (parents' home)")
        names = [item["name"] for item in strength["exercises"]]
        self.assertEqual(names[:2], ["Push Up", "Pike Push Up"])
        self.assertIn("Dead Bug", names)
        self.assertNotIn("Air Squat", names)
        self.assertTrue(all(item["weight_kg"] is None for item in strength["exercises"]))

    def test_gym_day_the_coach_rewrote_runs_its_exercises_not_the_template(self):
        row = self.conn.execute("SELECT days_json FROM weekly_plans").fetchone()
        days = json.loads(row["days_json"])
        title = days[3]["title"]
        days[3]["title"] = f"{title} (short, dumbbells only)"
        days[3]["exercises"] = [
            {"name": "Dumbbell Bench Press", "sets": 3, "reps": 10, "weight_kg": 24},
            {"name": "Dumbbell Lateral Raise", "sets": 3, "reps": 15, "weight_kg": 12},
        ]
        self.conn.execute("UPDATE weekly_plans SET days_json = ?", (json.dumps(days),))
        self.conn.commit()

        strength = build_phone_today(self.conn, TODAY)["today"]["strength"]
        self.assertIsNone(strength["template_id"])
        self.assertEqual(strength["name"], f"{title} (short, dumbbells only)")
        self.assertEqual([(item["name"], item["weight_kg"]) for item in strength["exercises"]],
                         [("Dumbbell Bench Press", 24), ("Dumbbell Lateral Raise", 12)])

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

    def test_rehab_is_null_without_a_routine(self):
        self.assertIsNone(build_phone_today(self.conn, TODAY)["rehab"])

    def test_sport_of_maps_types_to_app_colours(self):
        self.assertEqual(sport_of("VirtualRide"), "ride")
        self.assertEqual(sport_of("recovery"), "mobility")
        self.assertEqual(sport_of("Workout", "mobility"), "mobility")
        self.assertEqual(sport_of("Hike"), "hike")


if __name__ == "__main__":
    unittest.main()
