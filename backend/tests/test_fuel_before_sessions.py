import json
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.services import food_log, fuelling, meal_ideas
from backend.app.services.session_brief import build_session_brief

DAY = "2026-10-12"  # Monday


class FuelBeforeSessionsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL, unit TEXT, notes TEXT);
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, duration_min REAL,
                avg_watts REAL, calories INTEGER, workout_intent TEXT);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, detail_json TEXT, streams_json TEXT);
            CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, rpe INTEGER, energy INTEGER,
                muscle_soreness INTEGER, pain_level INTEGER DEFAULT 0);
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
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
            CREATE TABLE daily_checkins (date TEXT PRIMARY KEY, energy INTEGER, muscle_soreness INTEGER, stress INTEGER,
                sleep_quality INTEGER, notes TEXT);
            CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT, end_date TEXT);
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

    def _plan(self, *days):
        self.conn.execute("INSERT OR REPLACE INTO weekly_plans VALUES (?, ?)", (DAY, json.dumps(list(days))))

    def _log(self, day, kcal, meal="lunch"):
        food_log._write_entry(self.conn, None, {
            "date": day, "meal": meal, "source": "manual", "items": [{"name": "obiad", "kcal": kcal, "protein_g": 30}],
        })

    def _target(self, day):
        return food_log.build_food_day(self.conn, day, today=date(2026, 11, 1))["target"]["kcal"]

    # What to eat next ---------------------------------------------------

    def test_leg_day_tomorrow_names_the_session_and_leans_on_carbs(self):
        self._plan({"date": "2026-10-13", "session_type": "WeightTraining", "workout_intent": "strength_lower", "title": "Legs A"})
        self._log(DAY, 600, "breakfast")
        ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=10)
        self.assertEqual(ideas["pre_session"]["kind"], "leg_day")
        self.assertEqual(ideas["pre_session"]["title"], "Legs A")
        self.assertEqual(ideas["pre_session"]["headline"], "Leg day tomorrow, aim for the full target today")
        self.assertAlmostEqual(ideas["pre_session"]["carbs_g"], ideas["left"]["kcal"] * meal_ideas.PRE_SESSION_CARB_SHARE / 4, delta=1)
        self.assertTrue(all("carbs_g" in meal for meal in ideas["meals"]))

    def test_hard_ride_tomorrow_counts_but_an_easy_ride_or_upper_lift_does_not(self):
        self._plan({"date": "2026-10-13", "session_type": "VirtualRide", "workout_intent": "interval", "title": "VO2 5x4"})
        self.assertEqual(meal_ideas.build_meal_ideas(self.conn, DAY, hour=10)["pre_session"]["kind"], "hard_ride")
        self._plan({"date": "2026-10-13", "session_type": "Ride", "workout_intent": "easy"},
                   {"date": "2026-10-13", "session_type": "WeightTraining", "workout_intent": "strength_upper"})
        ideas = meal_ideas.build_meal_ideas(self.conn, DAY, hour=10)
        self.assertIsNone(ideas["pre_session"])
        self.assertTrue(all("carbs_g" not in meal for meal in ideas["meals"]))

    def test_carb_split_moves_ideas_towards_carbs(self):
        self._log(DAY, 400, "breakfast")
        plain = meal_ideas.build_meal_ideas(self.conn, DAY, hour=10)
        self._plan({"date": "2026-10-13", "session_type": "WeightTraining", "workout_intent": "strength_lower"})
        pre = meal_ideas.build_meal_ideas(self.conn, DAY, hour=10)

        def carb_share(result):
            ideas = [idea for meal in result["meals"] for idea in meal["ideas"][:2]]
            return sum(idea["totals"]["carbs_g"] * 4 for idea in ideas) / sum(idea["totals"]["kcal"] for idea in ideas)

        self.assertGreater(carb_share(pre), carb_share(plain))

    # Pre-session brief --------------------------------------------------

    def test_brief_flags_a_logged_under_fuelled_previous_day(self):
        self._log("2026-10-12", 900)
        brief = build_session_brief(
            self.conn, {"date": "2026-10-13", "session_type": "strength", "workout_intent": "strength_lower"}, date(2026, 10, 13)
        )
        self.assertEqual(brief["under_fuelled_yesterday"]["eaten_kcal"], 900)
        self.assertTrue(any(note.startswith("Yesterday was logged under-fuelled (900 of") for note in brief["notes"]))

    def test_brief_stays_quiet_when_yesterday_was_unlogged_or_fuelled(self):
        day = {"date": "2026-10-13", "session_type": "strength", "workout_intent": "strength_lower"}
        brief = build_session_brief(self.conn, day, date(2026, 10, 13))
        self.assertNotIn("under_fuelled_yesterday", brief)
        self._log("2026-10-12", self._target("2026-10-12"))
        brief = build_session_brief(self.conn, day, date(2026, 10, 13))
        self.assertNotIn("under_fuelled_yesterday", brief)
        self.assertFalse(any("under-fuelled" in note for note in brief["notes"]))

    # Weekly Review comparison ------------------------------------------

    def _session_after(self, previous, kcal, energy, rpe=6):
        session_day = (date.fromisoformat(previous) + timedelta(days=1)).isoformat()
        if kcal is not None:
            self._log(previous, kcal)
        activity_id = f"a-{session_day}"
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, 'Ride', 'Ride', 60)",
                          (activity_id, session_day))
        self.conn.execute("INSERT INTO activity_feedback (activity_id, rpe, energy, muscle_soreness) VALUES (?, ?, ?, 2)",
                          (activity_id, rpe, energy))

    def test_comparison_needs_four_logged_days_on_each_side(self):
        start = date(2026, 9, 1)
        for index in range(4):
            self._session_after((start + timedelta(days=index * 2)).isoformat(), 4000, energy=4)
        for index in range(3):
            self._session_after((start + timedelta(days=20 + index * 2)).isoformat(), 800, energy=2)
        # Sessions after unlogged days are unknown: they never fill the under-fuelled side.
        for index in range(5):
            self._session_after((start + timedelta(days=30 + index * 2)).isoformat(), None, energy=1)
        through = date(2026, 10, 18)
        result = fuelling.fuel_session_comparison(self.conn, through, today=through)
        self.assertFalse(result["ready"])
        self.assertEqual((result["fuelled"]["days"], result["under"]["days"]), (4, 3))
        self.assertIsNone(result["summary"])

        self._session_after("2026-09-28", 800, energy=2)
        result = fuelling.fuel_session_comparison(self.conn, through, today=through)
        self.assertTrue(result["ready"])
        self.assertEqual(result["fuelled"]["energy"], 4)
        self.assertEqual(result["under"]["energy"], 2)
        self.assertIn("2.0 energy points better", result["summary"])

    def test_fuel_status_leaves_unlogged_and_unfinished_days_unknown(self):
        self._log("2026-10-10", 700)
        self._log("2026-10-12", 700)
        status = food_log.fuel_status_by_day(self.conn, "2026-10-09", "2026-10-12", today=date(2026, 10, 12))
        self.assertEqual(list(status), ["2026-10-10"])
        self.assertTrue(status["2026-10-10"]["under"])


if __name__ == "__main__":
    unittest.main()
