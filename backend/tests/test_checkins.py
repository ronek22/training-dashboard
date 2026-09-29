import sqlite3
import unittest
from datetime import datetime

from backend.app.services.checkins import get_daily_checkin, latest_daily_checkin, upsert_daily_checkin

SCHEMA = """
CREATE TABLE daily_checkins (
    date TEXT PRIMARY KEY, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL,
    stress INTEGER NOT NULL, sleep_quality INTEGER NOT NULL, pain_level INTEGER NOT NULL DEFAULT 0,
    note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


class DailyCheckinTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_saves_and_edits_one_checkin_per_day(self):
        base = {"energy": 3, "muscle_soreness": 2, "stress": 4, "sleep_quality": 3}
        saved = upsert_daily_checkin(self.conn, base)
        self.assertEqual(saved["date"], datetime.now().date().isoformat())
        self.assertEqual(saved["pain_level"], 0)
        edited = upsert_daily_checkin(self.conn, {**base, "stress": 2, "pain_level": 3, "note": "niggle"})
        self.assertEqual(edited["stress"], 2)
        self.assertEqual(edited["note"], "niggle")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM daily_checkins").fetchone()[0], 1)

    def test_get_returns_none_when_missing_and_latest_finds_newest(self):
        self.assertIsNone(get_daily_checkin(self.conn))
        base = {"energy": 3, "muscle_soreness": 2, "stress": 4, "sleep_quality": 3}
        upsert_daily_checkin(self.conn, {**base, "date": "2026-09-01"})
        upsert_daily_checkin(self.conn, {**base, "date": "2026-09-05"})
        self.assertEqual(latest_daily_checkin(self.conn)["date"], "2026-09-05")

    def test_latest_tolerates_missing_table(self):
        self.conn.execute("DROP TABLE daily_checkins")
        self.assertIsNone(latest_daily_checkin(self.conn))


if __name__ == "__main__":
    unittest.main()
