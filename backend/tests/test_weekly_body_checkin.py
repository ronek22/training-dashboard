import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException

from backend.app.services.weekly_body_checkin import build_weekly_body_checkin, save_weekly_body_checkin

MONDAY = date(2026, 10, 12)
LAST_MONDAY = "2026-10-05"


class WeeklyBodyCheckinTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL, unit TEXT, notes TEXT);
            CREATE TABLE weekly_body_checkins (
                week_start TEXT PRIMARY KEY, protein_most_days INTEGER, weight_kg REAL,
                skipped INTEGER NOT NULL DEFAULT 0, updated_at TEXT
            );
            """
        )
        self.health = patch("backend.app.services.protein.get_health_metric_history", return_value=[])
        self.health.start()

    def tearDown(self):
        self.health.stop()
        self.conn.close()

    def _weights(self):
        return [tuple(row) for row in self.conn.execute("SELECT date, value FROM metrics WHERE metric = 'weight'")]

    def test_due_monday_to_wednesday_for_last_week(self):
        state = build_weekly_body_checkin(self.conn, MONDAY)
        self.assertEqual((state["week_start"], state["week_end"], state["due"]), (LAST_MONDAY, "2026-10-11", True))
        self.assertTrue(build_weekly_body_checkin(self.conn, date(2026, 10, 14))["due"])
        self.assertFalse(build_weekly_body_checkin(self.conn, date(2026, 10, 15))["due"])

    def test_answer_closes_prompt_and_logs_weight_once(self):
        state = save_weekly_body_checkin(self.conn, True, 79.4, False, MONDAY)
        self.assertFalse(state["due"])
        self.assertTrue(state["protein_most_days"])
        self.assertEqual(state["last_weight"]["kg"], 79.4)
        save_weekly_body_checkin(self.conn, True, 79.1, False, MONDAY)
        self.assertEqual(self._weights(), [("2026-10-12", 79.1)])

    def test_skip_closes_prompt_without_data(self):
        state = save_weekly_body_checkin(self.conn, True, 80, True, MONDAY)
        self.assertTrue(state["skipped"])
        self.assertIsNone(state["protein_most_days"])
        self.assertFalse(state["due"])
        self.assertEqual(self._weights(), [])

    def test_rejects_empty_and_implausible_answers(self):
        with self.assertRaises(HTTPException):
            save_weekly_body_checkin(self.conn, None, None, False, MONDAY)
        with self.assertRaises(HTTPException):
            save_weekly_body_checkin(self.conn, None, 7.9, False, MONDAY)


if __name__ == "__main__":
    unittest.main()
