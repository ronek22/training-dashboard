import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from backend.app import db
from backend.app.services import dashboard


class LongHistoryTests(unittest.TestCase):
    """Years of imported history must not slow the load model or shift today's thresholds."""

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
        self.today = date.today()

    def add(self, activity_id, day, kind="Run", minutes=50, avg_hr=150, max_hr=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, avg_hr, max_hr) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day.isoformat(), kind, kind, minutes, 10.0, avg_hr, max_hr),
        )
        self.conn.commit()

    def test_a_year_of_warm_up_gives_the_same_chart_as_all_history(self):
        for offset in range(0, 8 * 365, 2):
            self.add(f"day-{offset}", self.today - timedelta(days=offset), minutes=40 + offset % 60, avg_hr=140 + offset % 25)

        capped = dashboard.build_training_load_summary(self.conn, days=120)
        with mock.patch.object(dashboard, "TRAINING_LOAD_WARMUP_DAYS", 100_000):
            everything = dashboard.build_training_load_summary(self.conn, days=120)

        # Older training weighs under 0.02%, so at most a rounding step of 0.1 differs.
        self.assertEqual([item["date"] for item in capped["chart"]], [item["date"] for item in everything["chart"]])
        for short, full in zip(capped["chart"], everything["chart"]):
            for key in ("load", "ctl", "atl", "tsb"):
                self.assertLessEqual(abs(short[key] - full[key]), 0.1 + 1e-9, (short["date"], key))

    def test_max_heart_rate_only_counts_the_last_two_years(self):
        self.add("now", self.today - timedelta(days=10), max_hr=178)
        self.add("long-ago", self.today - timedelta(days=dashboard.MAX_HR_LOOKBACK_DAYS + 30), max_hr=204)

        thresholds = dashboard.estimate_thresholds(self.conn)

        self.assertEqual(thresholds["run_max_hr"], 183.0)  # The 183 floor, not the old 204.
        old_day = (self.today - timedelta(days=dashboard.MAX_HR_LOOKBACK_DAYS)).isoformat()
        self.assertEqual(dashboard.estimate_thresholds(self.conn, as_of_date=old_day)["run_max_hr"], 204.0)


if __name__ == "__main__":
    unittest.main()
