import json
import sqlite3
import unittest
from datetime import date

from backend.app.services.cycling_workouts import get_cycling_workout
from backend.app.services.workout_execution import (
    _timeline,
    build_ftp_workout_check,
    build_workout_execution,
    compare_ride_to_workout,
)

FTP = 242.0


def _ride_streams(workout_id, *, bias=1.0, lead_in_s=0, stop_after_s=None, hr=140):
    """1 Hz streams that follow a planned workout at ``bias`` after ``lead_in_s`` of free riding."""
    blocks = _timeline(get_cycling_workout(workout_id)["steps"])
    watts = [110.0] * lead_in_s
    for block in blocks:
        for second in range(block["end"] - block["start"]):
            share = second / (block["end"] - block["start"])
            watts.append((block["low"] + (block["high"] - block["low"]) * share) * FTP * bias)
    if stop_after_s is not None:
        watts = watts[:stop_after_s]
    return {
        "time": {"data": list(range(len(watts)))},
        "watts": {"data": [round(value) for value in watts]},
        "heartrate": {"data": [hr] * len(watts)},
    }


class CompareRideTests(unittest.TestCase):
    def setUp(self):
        self.workout = get_cycling_workout("sweet-spot-3x10")

    def test_on_target_ride(self):
        result = compare_ride_to_workout(_ride_streams("sweet-spot-3x10"), self.workout, FTP)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["verdict"], "on_target")
        self.assertEqual(result["blocks_ridden"], 3)
        self.assertAlmostEqual(result["ratio"], 1.0, delta=0.02)
        self.assertEqual(result["blocks"][0]["target_watts"], 215)

    def test_lowered_bias_is_visible_even_with_a_late_start(self):
        streams = _ride_streams("sweet-spot-3x10", bias=0.85, lead_in_s=180)
        result = compare_ride_to_workout(streams, self.workout, FTP)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["verdict"], "under")
        self.assertAlmostEqual(result["ratio"], 0.85, delta=0.02)
        self.assertAlmostEqual(result["start_offset_min"], 3.0, delta=0.1)

    def test_timeline_places_every_planned_block_on_the_ride_clock(self):
        streams = _ride_streams("sweet-spot-3x10", lead_in_s=180)
        result = compare_ride_to_workout(streams, self.workout, FTP)
        timeline = result["timeline"]
        self.assertEqual(len(timeline), len(_timeline(self.workout["steps"])))
        self.assertAlmostEqual(timeline[0]["start_s"], 180, delta=10)
        work = [block for block in timeline if block["kind"] == "work"]
        self.assertEqual(len(work), 3)
        self.assertEqual(work[0]["low_watts"], 215)
        self.assertAlmostEqual(work[0]["end_s"] - work[0]["start_s"], 600, delta=1)

    def test_timeline_stops_where_the_ride_stops(self):
        streams = _ride_streams("sweet-spot-3x10", stop_after_s=(12 + 10 + 5 + 2) * 60)
        result = compare_ride_to_workout(streams, self.workout, FTP)
        last = result["timeline"][-1]
        self.assertLessEqual(last["end_s"], (12 + 10 + 5 + 2) * 60)

    def test_stopping_early_marks_blocks_not_ridden(self):
        # Warm-up (12 min) + first block + recovery, then stop.
        streams = _ride_streams("sweet-spot-3x10", stop_after_s=(12 + 10 + 5 + 2) * 60)
        result = compare_ride_to_workout(streams, self.workout, FTP)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["blocks_ridden"], 1)
        self.assertFalse(result["blocks"][2]["ridden"])

    def test_steady_ride_does_not_match_an_interval_plan(self):
        flat = {"time": {"data": list(range(4200))}, "watts": {"data": [150 + (i % 7) for i in range(4200)]}}
        result = compare_ride_to_workout(flat, self.workout, FTP)
        self.assertEqual(result["status"], "not_matched")


class FtpCheckTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript(
            """
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL);
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
            CREATE TABLE activities (id TEXT, date TEXT, type TEXT, name TEXT, linked_planned_session_id TEXT);
            CREATE TABLE activity_details (activity_id TEXT, detail_json TEXT, streams_json TEXT, source_status TEXT);
            """
        )
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-03-12', 'ftp', ?)", (FTP,))

    def _plan(self, week_start, day, workout_id):
        self.conn.execute(
            "INSERT OR REPLACE INTO weekly_plans (week_start, days_json) VALUES (?, ?)",
            (week_start, json.dumps([{"date": day, "session_type": "Ride", "cycling_workout_id": workout_id}])),
        )

    def _ride(self, activity_id, day, streams):
        self.conn.execute("INSERT INTO activities VALUES (?, ?, 'VirtualRide', 'Zwift', NULL)", (activity_id, day))
        self.conn.execute(
            "INSERT INTO activity_details VALUES (?, ?, ?, 'streams_backfill')",
            (activity_id, json.dumps({}), json.dumps(streams)),
        )

    def test_single_ride_payload(self):
        self._plan("2026-10-12", "2026-10-13", "sweet-spot-3x10")
        self._ride("1", "2026-10-13", _ride_streams("sweet-spot-3x10", bias=0.85))
        row = self.conn.execute("SELECT * FROM activities a JOIN activity_details d ON d.activity_id = a.id").fetchone()
        result = build_workout_execution(self.conn, dict(row), row["detail_json"], row["streams_json"], row["source_status"])
        self.assertEqual(result["status"], "available")
        self.assertIn("85%", result["headline"])

    def test_ride_on_a_day_without_a_structured_workout_is_skipped(self):
        self._ride("1", "2026-10-13", _ride_streams("sweet-spot-3x10"))
        row = self.conn.execute("SELECT * FROM activities a JOIN activity_details d ON d.activity_id = a.id").fetchone()
        self.assertIsNone(build_workout_execution(self.conn, dict(row), row["detail_json"], row["streams_json"], row["source_status"]))

    def test_one_low_ride_is_not_enough(self):
        self._plan("2026-10-12", "2026-10-13", "sweet-spot-3x10")
        self._ride("1", "2026-10-13", _ride_streams("sweet-spot-3x10", bias=0.85))
        check = build_ftp_workout_check(self.conn, today=date(2026, 10, 14))
        self.assertEqual(check["status"], "not_enough")
        self.assertIsNone(check["suggestion"])

    def test_two_low_rides_suggest_a_lower_ftp(self):
        self._plan("2026-10-05", "2026-10-07", "sweet-spot-2x20")
        self._ride("1", "2026-10-07", _ride_streams("sweet-spot-2x20", bias=0.86))
        self._plan("2026-10-12", "2026-10-13", "sweet-spot-3x10")
        self._ride("2", "2026-10-13", _ride_streams("sweet-spot-3x10", bias=0.85))
        check = build_ftp_workout_check(self.conn, today=date(2026, 10, 14))
        self.assertEqual(check["status"], "lower")
        self.assertAlmostEqual(check["suggestion"]["watts"], 207, delta=3)

    def test_rides_on_target_hold_ftp(self):
        self._plan("2026-10-05", "2026-10-07", "sweet-spot-2x20")
        self._ride("1", "2026-10-07", _ride_streams("sweet-spot-2x20"))
        self._plan("2026-10-12", "2026-10-13", "sweet-spot-3x10")
        self._ride("2", "2026-10-13", _ride_streams("sweet-spot-3x10"))
        check = build_ftp_workout_check(self.conn, today=date(2026, 10, 14))
        self.assertEqual(check["status"], "holding")


if __name__ == "__main__":
    unittest.main()
