import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from backend.app.services import food_log
from backend.app.services.protein import build_protein_status

TODAY = date(2026, 10, 9)
YESTERDAY = TODAY - timedelta(days=1)


class FoodLogTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL, unit TEXT, notes TEXT);
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, duration_min REAL,
                avg_watts REAL, calories INTEGER, workout_intent TEXT);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, detail_json TEXT);
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
            CREATE TABLE daily_nutrition (date TEXT PRIMARY KEY, protein_hit INTEGER NOT NULL, updated_at TEXT);
            CREATE TABLE food_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, meal TEXT NOT NULL,
                source TEXT NOT NULL, raw_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE food_items (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER NOT NULL, name TEXT NOT NULL,
                grams REAL, kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
                fat_g REAL NOT NULL DEFAULT 0, confidence TEXT);
            CREATE TABLE saved_foods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, grams REAL,
                kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
                fat_g REAL NOT NULL DEFAULT 0, use_count INTEGER NOT NULL DEFAULT 0, created_at TEXT);
            INSERT INTO metrics (date, metric, value) VALUES ('2026-09-03', 'weight', 80);
            """
        )
        self.patches = [
            patch("backend.app.services.protein.get_health_metric_history", return_value=[]),
            patch("backend.app.services.protein.sick_dates", return_value=set()),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.conn.close()

    def _profile(self, **overrides):
        food_log.save_nutrition_profile(
            self.conn, {"sex": "male", "birth_year": 1996, "height_cm": 180, "daily_life": "desk", **overrides}
        )

    def _log(self, day, kcal, protein=20, meal="lunch"):
        food_log._write_entry(self.conn, None, {
            "date": day.isoformat(), "meal": meal, "source": "text", "raw_text": "obiad",
            "items": [{"name": "kurczak z ryżem", "grams": 400, "kcal": kcal, "protein_g": protein, "carbs_g": 60, "fat_g": 10}],
        })

    def test_resting_needs_full_profile(self):
        self.assertIsNone(food_log.resting_kcal({"sex": "male"}, 80, TODAY))
        # 10*80 + 6.25*180 - 5*30 + 5
        self.assertEqual(food_log.resting_kcal({"sex": "male", "birth_year": 1996, "height_cm": 180}, 80, TODAY), 1780)

    def test_without_profile_there_is_no_target(self):
        self._log(TODAY, 600)
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        self.assertFalse(day["profile_ready"])
        self.assertIsNone(day["target"])
        self.assertEqual(day["totals"]["kcal"], 600)

    def test_target_adds_net_training_burn(self):
        self._profile()
        # Power: 200 W for 60 min = 720 kJ ≈ 720 kcal gross, minus ~74 kcal resting share.
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min, avg_watts) VALUES ('r', ?, 'VirtualRide', 60, 200)", (TODAY.isoformat(),))
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        self.assertEqual(day["target"]["resting"], 1780)
        self.assertEqual(day["target"]["training"], 646)
        self.assertEqual(day["target"]["kcal"], round(1780 * 1.25 + 646))
        self.assertEqual(day["exercise"]["activities"][0]["basis"], "power")

    def test_recorded_calories_beat_estimates(self):
        self._profile()
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('l', ?, 'WeightTraining', 60)", (TODAY.isoformat(),))
        self.conn.execute("INSERT INTO activity_details VALUES ('l', '{\"calories\": 374}')")
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        self.assertEqual(day["exercise"]["activities"][0], {"id": "l", "type": "WeightTraining", "name": None, "kcal": 300, "basis": "recorded"})

    def test_gain_goal_adds_surplus(self):
        self._profile(goal="gain")
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        self.assertEqual(day["target"]["surplus"], food_log.GAIN_SURPLUS_KCAL)

    def test_only_finished_logged_days_are_judged_under(self):
        self._profile()
        self._log(YESTERDAY, 1200)
        self._log(TODAY, 300)
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        by_date = {item["date"]: item for item in day["week"]}
        self.assertTrue(by_date[YESTERDAY.isoformat()]["under"])
        self.assertFalse(by_date[TODAY.isoformat()]["under"])
        self.assertFalse(by_date[(TODAY - timedelta(days=3)).isoformat()]["logged"])
        self.assertEqual(day["week_summary"]["logged_days"], 1)
        self.assertEqual(day["week_summary"]["under_days"], 1)

    def test_update_replaces_items_and_delete_removes_entry(self):
        self._log(TODAY, 500)
        entry_id = self.conn.execute("SELECT id FROM food_entries").fetchone()["id"]
        food_log._write_entry(self.conn, entry_id, {
            "date": TODAY.isoformat(), "meal": "dinner", "source": "photo",
            "items": [{"name": "pizza", "kcal": 900}, {"name": "cola", "kcal": 140}],
        })
        day = food_log.build_food_day(self.conn, TODAY.isoformat(), TODAY)
        self.assertEqual(day["entries"][0]["meal"], "dinner")
        self.assertEqual(day["totals"]["kcal"], 1040)
        food_log.delete_food_entry(self.conn, entry_id)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM food_items").fetchone()[0], 0)

    def test_entry_needs_a_named_item(self):
        with self.assertRaises(HTTPException):
            food_log._write_entry(self.conn, None, {"date": TODAY.isoformat(), "items": [{"name": " "}]})

    def test_saved_food_upserts_by_name(self):
        food_log.save_food(self.conn, {"name": "Skyr Pilos", "grams": 150, "kcal": 95, "protein_g": 17})
        saved = food_log.save_food(self.conn, {"name": "Skyr Pilos", "grams": 150, "kcal": 99, "protein_g": 17})
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["kcal"], 99)

    def test_logged_protein_fills_the_protein_tick(self):
        self._log(TODAY, 2000, protein=130)
        status = build_protein_status(self.conn, TODAY)
        self.assertTrue(status["today"]["hit"])
        self.assertTrue(status["today"]["from_food_log"])
        self.conn.execute("INSERT INTO daily_nutrition (date, protein_hit) VALUES (?, 0)", (TODAY.isoformat(),))
        self.assertFalse(build_protein_status(self.conn, TODAY)["today"]["hit"])

    def test_coaching_context_is_none_without_logs(self):
        self.assertIsNone(food_log.nutrition_coaching_context(self.conn))


if __name__ == "__main__":
    unittest.main()
