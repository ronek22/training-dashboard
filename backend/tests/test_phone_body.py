import os
import sqlite3
import tempfile
import unittest
from unittest import mock
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
        resting = body["vitals"]["resting_hr"]
        self.assertEqual((resting["date"], resting["value"], resting["baseline"]), (NIGHT, 52, 60))
        self.assertIsNone(resting["typical_low"])
        self.assertEqual([item["value"] for item in resting["days"]], [60, 60, 60, 60, 60, 52])
        self.assertIsNone(body["vitals"]["hrv"])
        self.assertIsNone(body["sleep"])

    def test_typical_range_is_the_middle_of_the_month_before(self):
        values = [50 + offset for offset in range(30)]
        for offset, value in enumerate([45] + values):
            self.sample("resting_hr", (TODAY - timedelta(days=offset)).isoformat(), value)
        self.conn.commit()

        resting = build_phone_body(self.conn, TODAY)["vitals"]["resting_hr"]
        self.assertEqual((resting["typical_low"], resting["typical_high"]), (53, 76))
        self.assertEqual(len(resting["days"]), 7)
        self.assertEqual(resting["days"][-1]["value"], 45)

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

    def test_training_lists_every_sport_of_the_last_week_with_lift_sets(self):
        day = (TODAY - timedelta(days=2)).isoformat()
        for row in (
            ("ride1", day, "VirtualRide", "recovery", "Zwift", 44),
            ("lift1", day, "WeightTraining", None, "Evening Weight Training", 55),
            ("old", (TODAY - timedelta(days=7)).isoformat(), "Ride", None, "Old ride", 90),
        ):
            self.conn.execute(
                "INSERT INTO activities (id, date, type, workout_intent, name, duration_min) VALUES (?, ?, ?, ?, ?, ?)", row)
        self.conn.commit()
        session = {
            "workout_date": day, "title": "Workout B", "matched_activity": {"id": "lift1"}, "total_duration_seconds": 3300,
            "exercises": [
                {"exercise_name": "Chin Up", "sets": [{"reps": 8}, {"reps": 7}, {"reps": 10, "is_warmup": True}]},
                {"exercise_name": "Stretch", "sets": []},
            ],
        }
        with mock.patch("backend.app.services.phone_body._session_index", return_value=[session]):
            training = build_phone_body(self.conn, TODAY)["training"]

        self.assertEqual(sorted(item["sport"] for item in training), ["ride", "strength"])
        lift = next(item for item in training if item["sport"] == "strength")
        self.assertEqual(lift["title"], "Workout B")
        self.assertEqual(lift["minutes"], 55)
        self.assertEqual(lift["exercises"], [{"name": "Chin Up", "sets": 2}])

    def test_empty_history_has_no_debt_training_or_issues(self):
        body = build_phone_body(self.conn, TODAY)
        self.assertIsNone(body["sleep_debt"])
        self.assertEqual(body["training"], [])
        self.assertEqual(body["issues"], [])

    def test_issues_pin_the_protected_area_of_active_injuries(self):
        self.conn.execute(
            "INSERT INTO recovery_issues (title, body_area, side, started_on) VALUES ('Outside of left knee', 'knee', 'left', '2026-10-24')")
        self.conn.execute(
            "INSERT INTO recovery_issues (title, body_area, side, started_on, status) VALUES ('Old shoulder', 'shoulder', 'right', '2026-01-01', 'healed')")
        self.conn.commit()

        issues = build_phone_body(self.conn, TODAY)["issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["areas"], ["knee"])
        self.assertEqual(issues[0]["side"], "left")
        self.assertEqual(issues[0]["since"], "2026-10-24")


if __name__ == "__main__":
    unittest.main()
