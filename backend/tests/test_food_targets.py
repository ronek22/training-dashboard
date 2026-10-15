import json
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.services import food_log, food_targets

MONDAY = date(2026, 10, 5)


def day(offset, session_type, minutes=None, intent=None, title="Session"):
    return {
        "date": (MONDAY + timedelta(days=offset)).isoformat(), "label": "", "title": title, "session_type": session_type,
        "target_duration_min": minutes, "workout_intent": intent,
    }


WEEK = [
    day(0, "Rest"),
    day(1, "VirtualRide", 75, "interval", "Sweet spot"),
    day(2, "WeightTraining", 50, "strength_lower", "Legs"),
    day(3, "Ride", 60, "easy", "Z2"),
    day(5, "Ride", 180, "long", "Long ride"),
]


class FoodTargetTests(unittest.TestCase):
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
            CREATE TABLE food_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, meal TEXT NOT NULL,
                source TEXT NOT NULL, raw_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE food_items (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER NOT NULL, name TEXT NOT NULL,
                grams REAL, kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
                fat_g REAL NOT NULL DEFAULT 0, confidence TEXT, portions REAL);
            INSERT INTO metrics (date, metric, value) VALUES ('2026-09-03', 'weight', 80);
            """
        )
        food_log.save_nutrition_profile(self.conn, {"sex": "male", "birth_year": 1996, "height_cm": 180, "daily_life": "desk"})
        self.health = patch("backend.app.services.protein.get_health_metric_history", return_value=[])
        self.health.start()

    def tearDown(self):
        self.health.stop()
        self.conn.close()

    def _plan(self, days):
        self.conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES (?, ?)", (MONDAY.isoformat(), json.dumps(days)))

    def _recent_rides(self, hours_per_week):
        for week in range(1, 5):
            self.conn.execute(
                "INSERT INTO activities (id, date, type, duration_min) VALUES (?, ?, 'Ride', ?)",
                (f"r{week}", (MONDAY - timedelta(weeks=week)).isoformat(), hours_per_week * 60),
            )

    def _food(self, today=MONDAY):
        return food_log.build_food_day(self.conn, today.isoformat(), today)

    def test_day_kinds_get_different_targets(self):
        self._plan(WEEK)
        days = {item["date"][-2:]: item for item in self._food()["planned_week"]["days"]}
        self.assertEqual([days[d]["kind"] for d in ("05", "06", "07", "08", "10")], ["rest", "key_ride", "lift", "easy_ride", "long_ride"])
        # Carbs by g/kg at 80 kg: rest 3, lift 4, easy 5, key 6, long 7.
        self.assertEqual([days[d]["carbs_g"] for d in ("05", "07", "08", "06", "10")], [240, 320, 400, 480, 560])
        kcal = {kind: days[d]["target_kcal"] for kind, d in (("rest", "05"), ("key", "06"), ("lift", "07"), ("long", "10"))}
        self.assertEqual(len(set(kcal.values())), 4)
        self.assertLess(kcal["rest"], kcal["lift"])
        self.assertLess(kcal["lift"], kcal["key"])
        self.assertLess(kcal["key"], kcal["long"])

    def test_today_target_counts_the_planned_session(self):
        self._plan(WEEK)
        food = self._food(MONDAY + timedelta(days=1))
        self.assertTrue(food["target"]["training_planned"])
        self.assertEqual(food["target"]["day_kind"], "key_ride")
        self.assertEqual(food["target"]["training"], round(9.5 * 80 * 75 / 60))

    def test_finished_days_are_judged_on_what_was_done(self):
        self._plan(WEEK)
        food = self._food(MONDAY + timedelta(days=2))
        tuesday = next(item for item in food["planned_week"]["days"] if item["date"] == "2026-10-06")
        self.assertEqual(tuesday["training_kcal"], 0)

    def test_logged_training_beats_a_smaller_plan(self):
        self._plan(WEEK)
        tuesday = MONDAY + timedelta(days=1)
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min, avg_watts) VALUES ('x', ?, 'VirtualRide', 120, 220)", (tuesday.isoformat(),))
        target = self._food(tuesday)["target"]
        self.assertFalse(target["training_planned"])
        self.assertGreater(target["training"], round(9.5 * 80 * 75 / 60))

    def test_bigger_week_shows_eat_more_hint_and_more_ride_carbs(self):
        self._plan(WEEK)  # 75 + 60 + 180 min ≈ 5.3 h of riding
        self._recent_rides(3)
        week = self._food()["planned_week"]
        self.assertTrue(week["big_week"])
        self.assertIn("needs more food", week["hint"])
        days = {item["kind"]: item["carbs_g"] for item in week["days"]}
        self.assertEqual(days["long_ride"], 640)
        self.assertEqual(days["key_ride"], 560)
        self.assertEqual(days["lift"], 320)
        self.assertEqual(days["rest"], 240)

    def test_steady_week_has_no_hint(self):
        self._plan(WEEK)
        self._recent_rides(5)
        self.assertFalse(self._food()["planned_week"]["big_week"])
        self.assertFalse(food_targets.is_big_week(4.0, None))
        self.assertFalse(food_targets.is_big_week(9.0, 8.5))
        self.assertTrue(food_targets.is_big_week(10.0, 8.0))

    def test_lighter_week_never_drops_below_baseline(self):
        self._recent_rides(6)
        baseline = self._food()["target"]["kcal"]
        with patch.object(food_targets, "_arc_ride_hours", return_value=(4.0, True)):
            food = self._food()
        week = food["planned_week"]
        self.assertTrue(week["lighter"])
        self.assertFalse(week["big_week"])
        self.assertEqual(food["target"]["kcal"], baseline)
        for item in week["days"]:
            self.assertGreaterEqual(item["target_kcal"], baseline)
            self.assertEqual(item["carbs_g"], 240)


if __name__ == "__main__":
    unittest.main()
