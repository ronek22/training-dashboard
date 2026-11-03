import json
import sqlite3
import unittest
from unittest.mock import patch

from backend.app.services import food_log, phone_food

DAY = "2026-10-12"
YESTERDAY = "2026-10-11"


class PhoneFoodTests(unittest.TestCase):
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
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
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

    def _log(self, day, meal, items):
        food_log._write_entry(self.conn, None, {"date": day, "meal": meal, "source": "text", "items": items})

    def _food(self, name, kcal, protein, carbs=0, fat=0, grams=None):
        return {"name": name, "grams": grams, "kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}

    def _quick(self, hour, day=DAY):
        return phone_food.build_food_quick(self.conn, day, hour)

    def test_slot_follows_the_clock(self):
        self.assertEqual([phone_food.slot_for_hour(h) for h in (7, 12, 19, 23)], ["breakfast", "lunch", "dinner", "snack"])

    def test_again_starts_with_yesterdays_meal_for_this_time(self):
        self._log(YESTERDAY, "breakfast", [self._food("owsianka", 400, 15)])
        self._log(YESTERDAY, "lunch", [self._food("pierogi", 700, 25)])
        again = self._quick(8)["again"]
        self.assertEqual(again[0]["kind"], "yesterday")
        self.assertEqual(again[0]["title"], "Owsianka")
        self.assertEqual(self._quick(13)["again"][0]["title"], "Pierogi")

    def test_favourites_group_spelling_variants_and_need_two(self):
        self._log("2026-10-01", "lunch", [self._food("frankfurterki z jagnięciny", 237, 21)])
        self._log("2026-10-05", "lunch", [self._food("Frankfurterki z jagnięciną", 284, 25)])
        self._log("2026-10-06", "lunch", [self._food("gulasz", 600, 40)])
        again = self._quick(8)["again"]
        self.assertEqual([(card["kind"], card["count"]) for card in again], [("favourite", 2)])
        # The newest version wins, with its own macros.
        self.assertEqual(again[0]["totals"]["kcal"], 284)

    def test_eaten_today_hides_its_card_and_saved_foods_follow(self):
        self._log("2026-10-01", "lunch", [self._food("skyr", 100, 17)])
        self._log("2026-10-02", "lunch", [self._food("skyr", 100, 17)])
        food_log.save_food(self.conn, self._food("shake", 270, 34))
        food_log.save_food(self.conn, self._food("Skyr", 100, 17))
        self.assertEqual([card["kind"] for card in self._quick(8)["again"]], ["favourite", "saved"])
        self._log(DAY, "breakfast", [self._food("skyr", 100, 17)])
        self.assertEqual([card["title"] for card in self._quick(9)["again"]], ["shake"])

    def test_no_gap_before_evening_or_before_anything_is_logged(self):
        self._log("2026-10-01", "lunch", [self._food("kurczak z ryżem", 700, 50, 80)])
        self.assertIsNone(self._quick(19)["gap"])
        self._log(DAY, "breakfast", [self._food("kanapka", 400, 15)])
        self.assertIsNone(self._quick(15)["gap"])
        self.assertIsNotNone(self._quick(19)["gap"])

    def test_picks_come_from_the_log_and_stay_within_a_dinner(self):
        self._log("2026-10-01", "dinner", [self._food("kurczak z ryżem", 700, 50, 80, 10)])
        self._log("2026-10-02", "dinner", [self._food("antrykot", 1300, 90, 0, 100)])
        self._log("2026-10-03", "snack", [self._food("baton", 250, 3, 30, 12)])
        self._log(DAY, "breakfast", [self._food("kanapka", 400, 15, 50, 12)])
        gap = self._quick(19)["gap"]
        self.assertEqual(gap["focus"], "both")
        self.assertEqual(gap["meal"], "dinner")
        self.assertGreater(gap["left"]["kcal"], 1000)
        self.assertLessEqual(len(gap["picks"]), 2)
        for pick in gap["picks"]:
            self.assertLessEqual(pick["totals"]["kcal"], phone_food.PICK_MAX_KCAL * 1.15)
            self.assertEqual(pick["source"], "log")
        self.assertIn("Kurczak z ryżem", [pick["title"] for pick in gap["picks"]])
        leads = [pick["title"].split()[0].lower() for pick in gap["picks"]]
        self.assertEqual(len(leads), len(set(leads)))

    def test_protein_only_when_kcal_is_nearly_there(self):
        self._log("2026-10-01", "snack", [self._food("szynka", 50, 8, 0.5, 2, grams=40)])
        self._log("2026-10-02", "snack", [self._food("tiramisu", 380, 6, 36, 22)])
        target = food_log.build_food_day(self.conn, DAY)["target"]["kcal"]
        self._log(DAY, "lunch", [self._food("obiad", target - 150, 80, 300, 80)])
        gap = self._quick(20)["gap"]
        self.assertEqual(gap["focus"], "protein")
        self.assertEqual(gap["picks"][0]["title"], "Szynka")
        self.assertGreater(gap["picks"][0]["portions"], 1)
        self.assertNotIn("Tiramisu", [pick["title"] for pick in gap["picks"]])

    def test_close_enough_shows_no_gap(self):
        target = food_log.build_food_day(self.conn, DAY)
        self._log(DAY, "lunch", [self._food("obiad", target["target"]["kcal"] - 100, target["protein_target_g"], 300, 80)])
        self.assertIsNone(self._quick(20)["gap"])

    def test_after_a_long_ride_the_picks_refuel(self):
        self._log("2026-10-01", "dinner", [self._food("makaron z tuńczykiem", 650, 40, 90, 8)])
        self._log(DAY, "breakfast", [self._food("kanapka", 400, 15, 50, 12)])
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('r', ?, 'Ride', 120)", (DAY + "T09:00:00",))
        self.assertEqual(self._quick(19)["gap"]["focus"], "refuel")

    def _plan(self, day):
        self.conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES ('2026-10-12', ?)", (json.dumps([day]),))

    def test_fuel_plan_for_a_ride_that_needs_it(self):
        self._plan({"date": DAY, "session_type": "Ride", "title": "Sweet spot", "workout_intent": "tempo",
                    "target_duration_min": 70, "cycling_workout_id": "sweet-spot-3x10"})
        fuel = self._quick(8)["fuel"]
        self.assertEqual((fuel["total_carbs_g"], fuel["bottles"]), (70, 1))
        self.assertEqual([stop["min"] for stop in fuel["stops"]], [15, 35, 55])
        self.assertEqual(len(fuel["blocks"]), 3)
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('r', ?, 'VirtualRide', 70)", (DAY + "T10:00:00",))
        self.assertIsNone(self._quick(12)["fuel"])

    def test_no_fuel_for_a_short_easy_spin(self):
        self._plan({"date": DAY, "session_type": "Ride", "title": "Easy spin", "workout_intent": "easy", "target_duration_min": 40})
        self.assertIsNone(self._quick(8)["fuel"])


if __name__ == "__main__":
    unittest.main()
