import json
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.services.protein import build_protein_status, protein_target_g

TODAY = date(2026, 10, 2)  # a Friday
MONDAY = TODAY - timedelta(days=TODAY.weekday())


class ProteinTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL, unit TEXT, notes TEXT);
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, workout_intent TEXT);
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
            CREATE TABLE daily_nutrition (date TEXT PRIMARY KEY, protein_hit INTEGER NOT NULL, updated_at TEXT);
            """
        )
        self.sick = patch("backend.app.services.protein.sick_dates", return_value=set())
        self.sick_dates = self.sick.start()
        self.health = patch("backend.app.services.protein.get_health_metric_history", return_value=[])
        self.health.start()

    def tearDown(self):
        self.sick.stop()
        self.health.stop()
        self.conn.close()

    def _lift(self, day, intent=None):
        self.conn.execute("INSERT INTO activities VALUES (?, ?, 'WeightTraining', ?)", (f"lift-{day}", day.isoformat(), intent))

    def _tick(self, day, hit):
        self.conn.execute("INSERT INTO daily_nutrition (date, protein_hit) VALUES (?, ?)", (day.isoformat(), int(hit)))

    def _status(self):
        return build_protein_status(self.conn, TODAY)

    def test_target_is_1_6_g_per_kg_rounded_to_5(self):
        self.assertEqual(protein_target_g(79.5), 125)
        self.assertEqual(protein_target_g(70), 110)

    def test_target_uses_latest_weigh_in(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-08-01', 'weight', 76), ('2026-09-03', 'weight', 79.5)")
        self.assertEqual(self._status()["target_g"], 125)

    def test_no_weight_means_no_target(self):
        self.assertIsNone(self._status()["target_g"])

    def test_logged_lift_and_planned_lift_count(self):
        self._lift(MONDAY)
        self.conn.execute(
            "INSERT INTO weekly_plans VALUES (?, ?)",
            (MONDAY.isoformat(), json.dumps([{"date": TODAY.isoformat(), "session_type": "strength", "workout_intent": "strength_lower"}])),
        )
        self._tick(MONDAY, True)
        status = self._status()
        self.assertTrue(status["today"]["is_lift_day"])
        self.assertEqual(status["week"], {"lift_days": 2, "hits": 1, "answered": 1})

    def test_mobility_and_sick_days_are_not_lift_days(self):
        self._lift(MONDAY, "mobility")
        self._lift(MONDAY + timedelta(days=1))
        self.sick_dates.return_value = {(MONDAY + timedelta(days=1)).isoformat()}
        self.assertEqual(self._status()["week"]["lift_days"], 0)

    def test_yesterday_stays_answerable(self):
        yesterday = TODAY - timedelta(days=1)
        self._lift(yesterday)
        status = self._status()
        self.assertTrue(status["yesterday"]["is_lift_day"])
        self.assertIsNone(status["yesterday"]["hit"])
        self.assertFalse(status["today"]["is_lift_day"])

    def test_monday_still_sees_sundays_lift(self):
        monday = MONDAY + timedelta(days=7)
        self._lift(monday - timedelta(days=1))
        status = build_protein_status(self.conn, monday)
        self.assertTrue(status["yesterday"]["is_lift_day"])
        self.assertEqual(status["week"]["lift_days"], 0)


if __name__ == "__main__":
    unittest.main()
