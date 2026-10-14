import sqlite3
import unittest
from unittest.mock import patch

from backend.app.services import food_log, meal_ideas

DAY = "2026-10-12"


class MealIdeasTests(unittest.TestCase):
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
            CREATE TABLE dinner_plans (date TEXT PRIMARY KEY, dish TEXT, notes TEXT, kcal REAL, protein_g REAL,
                recipe_id INTEGER, servings REAL, updated_at TEXT);
            INSERT INTO metrics (date, metric, value) VALUES ('2026-09-03', 'weight', 80);
            """
        )
        self.patches = [
            patch("backend.app.services.protein.get_health_metric_history", return_value=[]),
            patch("backend.app.services.protein.sick_dates", return_value=set()),
        ]
        for item in self.patches:
            item.start()
        food_log.save_nutrition_profile(self.conn, {"sex": "male", "birth_year": 1996, "height_cm": 180, "daily_life": "desk"})

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.conn.close()

    def _log(self, meal, kcal, protein):
        food_log._write_entry(self.conn, None, {
            "date": DAY, "meal": meal, "source": "manual",
            "items": [{"name": meal, "kcal": kcal, "protein_g": protein}],
        })

    def test_needs_a_profile(self):
        self.conn.execute("DELETE FROM app_settings")
        self.assertEqual(meal_ideas.build_meal_ideas(self.conn, DAY)["ready"], False)

    def test_gap_is_split_across_meals_still_ahead(self):
        self._log("breakfast", 400, 20)
        self._log("lunch", 500, 30)
        ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=14)
        self.assertEqual([meal["meal"] for meal in ideas["meals"]], ["dinner", "snack"])
        self.assertAlmostEqual(sum(meal["kcal"] for meal in ideas["meals"]), ideas["left"]["kcal"], delta=2)
        dinner = ideas["meals"][0]
        self.assertGreater(dinner["kcal"], ideas["meals"][1]["kcal"])
        for idea in dinner["ideas"]:
            self.assertLessEqual(idea["totals"]["kcal"], dinner["kcal"] * meal_ideas.OVERSHOOT)

    def test_late_evening_leaves_only_a_snack(self):
        self._log("breakfast", 400, 20)
        ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=22)
        self.assertEqual([meal["meal"] for meal in ideas["meals"]], ["snack"])
        self.assertEqual(ideas["meals"][0]["kcal"], ideas["left"]["kcal"])

    def test_planned_dinner_counts_before_it_is_logged(self):
        self._log("breakfast", 900, 40)
        before = meal_ideas.build_meal_ideas(self.conn, DAY, hour=14)["left"]["kcal"]
        self.conn.execute("INSERT INTO dinner_plans (date, dish, kcal, protein_g) VALUES (?, 'gulasz', 700, 45)", (DAY,))
        ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=14)
        self.assertEqual(ideas["planned_dinner"]["dish"], "gulasz")
        self.assertEqual(ideas["left"]["kcal"], before - 700)
        self.assertNotIn("lunch", [meal["meal"] for meal in ideas["meals"]])
        self._log("lunch", 700, 45)
        self.assertIsNone(meal_ideas.build_meal_ideas(self.conn, DAY, hour=14)["planned_dinner"])

    def test_close_enough_day_has_no_ideas(self):
        target = food_log.build_food_day(self.conn, DAY)["target"]["kcal"]
        self._log("lunch", target - 50, 150)
        self.assertEqual(meal_ideas.build_meal_ideas(self.conn, DAY, hour=14)["meals"], [])

    def test_saved_foods_rank_ahead_of_staples_and_scale_their_portion(self):
        food_log.save_food(self.conn, {"name": "skyr pitny", "grams": 330, "kcal": 210, "protein_g": 26})
        self._log("breakfast", 450, 30)
        self._log("lunch", 650, 50)
        self._log("dinner", 650, 50)
        snack = meal_ideas.build_meal_ideas(self.conn, DAY, hour=20)["meals"][0]
        self.assertEqual(snack["meal"], "snack")
        own = next(idea for idea in snack["ideas"] if idea["source"] == "saved")
        self.assertEqual(own["title"], "skyr pitny")
        self.assertIn(own["portions"], (1, 2))
        self.assertEqual(own["totals"]["kcal"], 210 * own["portions"])

    def test_food_already_eaten_today_sinks(self):
        food_log.save_food(self.conn, {"name": "skyr pitny", "grams": 330, "kcal": 210, "protein_g": 26})
        self._log("breakfast", 450, 30)
        self._log("lunch", 650, 50)
        self._log("dinner", 650, 50)
        def rank():
            ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=20)["meals"][0]["ideas"]
            titles = [idea["title"] for idea in ideas]
            return titles.index("skyr pitny") if "skyr pitny" in titles else len(titles)

        before = rank()
        food_log._write_entry(self.conn, None, {"date": DAY, "meal": "snack", "source": "manual",
                                                "items": [{"name": "Skyr naturalny", "kcal": 1, "protein_g": 0}]})
        self.assertGreater(rank(), before)
