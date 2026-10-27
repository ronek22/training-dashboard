import sqlite3
import unittest
from unittest.mock import patch

from backend.app.services import food_log, meal_protein

DAY = "2026-10-12"


class MealProteinTests(unittest.TestCase):
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
            CREATE TABLE food_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, meal TEXT NOT NULL,
                source TEXT NOT NULL, raw_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE food_items (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER NOT NULL, name TEXT NOT NULL,
                grams REAL, kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
                fat_g REAL NOT NULL DEFAULT 0, confidence TEXT, portions REAL);
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

    def _log(self, meal, protein, kcal=400, day=DAY):
        food_log._write_entry(self.conn, None, {
            "date": day, "meal": meal, "source": "manual",
            "items": [{"name": f"{meal} food", "kcal": kcal, "protein_g": protein}],
        })

    def _day(self):
        return food_log.build_food_day(self.conn, DAY)["meal_protein"]

    def test_empty_day_has_no_warnings(self):
        result = self._day()
        self.assertEqual((result["meals"], result["light_count"]), ([], 0))
        self.assertEqual(result["threshold_g"], meal_protein.MEAL_PROTEIN_MIN_G)

    def test_each_logged_meal_shows_protein_and_light_main_meals_are_marked(self):
        self._log("breakfast", 12)
        self._log("lunch", 40)
        self._log("snack", 5)
        meals = {item["meal"]: item for item in self._day()["meals"]}
        self.assertEqual(list(meals), ["breakfast", "lunch", "snack"])
        self.assertEqual((meals["breakfast"]["protein_g"], meals["breakfast"]["light"], meals["breakfast"]["short_g"]), (12, True, 13))
        self.assertFalse(meals["lunch"]["light"])
        # Snacks are shown but never judged.
        self.assertEqual((meals["snack"]["judged"], meals["snack"]["light"]), (False, False))

    def test_light_meal_gets_a_top_up_from_own_foods_first(self):
        self.conn.execute("INSERT INTO saved_foods (name, grams, kcal, protein_g, carbs_g, fat_g) VALUES ('Skyr', 150, 100, 17, 6, 0)")
        self.conn.execute("INSERT INTO saved_foods (name, grams, kcal, protein_g, carbs_g, fat_g) VALUES ('Bułka', 60, 160, 5, 30, 1)")
        self._log("breakfast", 10)
        breakfast = self._day()["meals"][0]
        titles = [idea["title"] for idea in breakfast["top_ups"]]
        self.assertEqual(titles, ["Skyr"])  # the roll is not protein-forward, staples only fill in when nothing fits
        self.assertEqual(breakfast["top_ups"][0]["meal"], "breakfast")
        self.assertGreaterEqual(breakfast["top_ups"][0]["totals"]["protein_g"], 15)

    def test_staples_fill_in_without_own_foods(self):
        self._log("dinner", 8)
        supper = self._day()["meals"][0]
        self.assertTrue(supper["top_ups"])
        self.assertTrue(all(idea["source"] == "staple" for idea in supper["top_ups"]))

    def test_threshold_is_one_setting(self):
        self._log("breakfast", 22)
        entries = food_log.build_food_day(self.conn, DAY)["entries"]
        self.assertTrue(meal_protein.build_meal_protein(self.conn, entries)["meals"][0]["light"])
        self.assertFalse(meal_protein.build_meal_protein(self.conn, entries, threshold=20)["meals"][0]["light"])

    def test_spread_counts_logged_days_only(self):
        self._log("breakfast", 10, day="2026-10-10")
        self._log("lunch", 45, day="2026-10-10")
        self._log("breakfast", 30, day="2026-10-11")
        spread = meal_protein.meal_spread(self.conn, ["2026-10-09", "2026-10-10", "2026-10-11"])
        self.assertEqual((spread["logged_days"], spread["even_days"], spread["share"]), (2, 1, 0.5))
        self.assertEqual(spread["most_often_light"], {"meal": "breakfast", "label": "Breakfast", "days": 1})
        self.assertIsNone(meal_protein.meal_spread(self.conn, []))


if __name__ == "__main__":
    unittest.main()
