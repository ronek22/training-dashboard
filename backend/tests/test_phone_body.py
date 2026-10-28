import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from backend.app import db
from backend.app.services.phone_body import build_phone_body

# The health queries window on SQLite's date('now'), so the fixtures sit around the real today.
TODAY = date.today()
NIGHT = TODAY.isoformat()


class PhoneBodyTests(unittest.TestCase):
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
        self.import_id = self.conn.execute(
            "INSERT INTO health_data_imports (file_name, file_hash, file_size, file_modified_ns) VALUES ('t', 'h', 0, 0)"
        ).lastrowid
        self.rows = 0

    def sample(self, metric, day, value, start=None, end=None, stage=None, seconds=None, source="watch"):
        self.rows += 1
        self.conn.execute(
            """
            INSERT INTO health_metric_samples
                (sample_key, metric, timestamp, end_timestamp, date, value, category_label, duration_seconds, source_name, source_bundle, import_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"k{self.rows}", metric, start or f"{day}T08:00:00Z", end, day, value, stage, seconds, source, source, self.import_id),
        )

    def test_last_night_keeps_the_staged_source_in_order(self):
        segments = [
            ("core", "00:00", "01:00", 3600),
            ("deep", "01:00", "01:30", 1800),
            ("awake", "01:30", "01:40", 600),
            ("rem", "01:40", "02:40", 3600),
        ]
        for stage, start, end, seconds in segments:
            self.sample("sleep", NIGHT, 0, f"{NIGHT}T{start}:00Z", f"{NIGHT}T{end}:00Z", stage, seconds)
        # The phone's own unstaged estimate of the same night loses to the watch.
        self.sample("sleep", NIGHT, 1, f"{NIGHT}T00:00:00Z", f"{NIGHT}T03:00:00Z", "asleep_unspecified", 10800, source="phone")
        self.conn.commit()

        sleep = build_phone_body(self.conn, TODAY)["sleep"]
        self.assertEqual([item["stage"] for item in sleep["segments"]], ["core", "deep", "awake", "rem"])
        self.assertEqual(sleep["start"], f"{NIGHT}T00:00:00Z")
        self.assertEqual(sleep["end"], f"{NIGHT}T02:40:00Z")
        self.assertEqual(sleep["asleep_h"], 2.5)
        self.assertEqual(sleep["stages"]["deep"], 0.5)
        self.assertIsNone(sleep["baseline_h"])

    def test_vitals_compare_the_latest_reading_with_the_month_before(self):
        for offset, value in enumerate([52, 60, 60, 60, 60, 60]):
            self.sample("resting_hr", (TODAY - timedelta(days=offset)).isoformat(), value)
        self.conn.commit()

        body = build_phone_body(self.conn, TODAY)
        self.assertEqual(body["vitals"]["resting_hr"], {"date": NIGHT, "value": 52, "baseline": 60})
        self.assertIsNone(body["vitals"]["hrv"])
        self.assertIsNone(body["sleep"])

    def test_load_returns_the_fitness_fatigue_and_form_chart(self):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES ('a1', ?, 'Ride', 'Ride', 60)",
            ((TODAY - timedelta(days=1)).isoformat(),),
        )
        self.conn.commit()

        load = build_phone_body(self.conn, TODAY)["load"]
        self.assertEqual(len(load["chart"]), 42)
        self.assertEqual(load["chart"][-1]["date"], NIGHT)
        self.assertGreater(load["chart"][-2]["load"], 0)
        self.assertGreater(load["fatigue"], load["fitness"])
        self.assertEqual(set(load["chart"][-1]), {"date", "load", "fitness", "fatigue", "form"})


if __name__ == "__main__":
    unittest.main()
