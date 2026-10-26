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


class HeartRateLoadScaleTests(unittest.TestCase):
    """Heart-rate TRIMP must land on the TSS scale, or HR-only rides count double."""

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
        self.thresholds = dashboard.estimate_thresholds(self.conn)

    def add(self, activity_id, kind, minutes, avg_hr, days_ago=1, hr_trimp=None, power_tss=None):
        day = (self.today - timedelta(days=days_ago)).isoformat()
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, avg_hr) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, kind, minutes, 10.0, avg_hr),
        )
        if hr_trimp is not None:
            self.conn.execute(
                "INSERT INTO activity_stream_summaries (activity_id, fetched_at, source, hr_trimp, power_tss) VALUES (?, ?, ?, ?, ?)",
                (activity_id, day, "power_tss" if power_tss else "hr_trimp", hr_trimp, power_tss),
            )
        self.conn.commit()

    def test_an_hour_at_threshold_heart_rate_scores_100(self):
        scales = dashboard.hr_load_scales(self.conn, self.thresholds, self.today)
        for sport, lthr, max_hr in (("run", "run_lthr", "run_max_hr"), ("ride", "ride_lthr", "ride_max_hr")):
            trimp = dashboard.trimp_score(60, self.thresholds[lthr], self.thresholds["resting_hr"], self.thresholds[max_hr])
            self.assertAlmostEqual(trimp * scales[sport], 100.0, places=6)

    def test_rides_calibrate_from_rides_with_both_scores(self):
        for index in range(5):
            self.add(f"paired-{index}", "VirtualRide", 60, 150, days_ago=index + 2, hr_trimp=120.0, power_tss=60.0)
        self.add("hr-only", "Ride", 90, 150, hr_trimp=200.0)

        summary = dashboard.build_training_load_summary(self.conn, days=14)

        self.assertEqual(summary["model"]["hr_load_scale"]["ride"], 0.5)
        day = (self.today - timedelta(days=1)).isoformat()
        self.assertEqual(next(item for item in summary["chart"] if item["date"] == day)["load"], 100.0)

    def test_an_easy_hike_is_scored_by_heart_rate_not_duration(self):
        self.add("hike", "Hike", 480, 100)

        summary = dashboard.build_training_load_summary(self.conn, days=14)

        day = (self.today - timedelta(days=1)).isoformat()
        hike = next(item for item in summary["chart"] if item["date"] == day)
        self.assertEqual(hike["load_source"], "hr_trimp")
        self.assertLess(hike["load"], 480 * 0.6 / 2)


if __name__ == "__main__":
    unittest.main()
