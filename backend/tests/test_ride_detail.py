import json
import sqlite3
import unittest

from backend.app.services.ride_detail import build_ride_detail


def steady_streams(minutes=60, watts=150, hr=140, latlng=False):
    times = list(range(minutes * 60 + 1))
    streams = {
        "time": {"data": times},
        "watts": {"data": [watts * 2 if 600 <= second < 900 else watts for second in times]},
        "heartrate": {"data": [hr for _ in times]},
    }
    if latlng:
        streams["latlng"] = {"data": [[50.0 + second / 1e5, 19.0] for second in times]}
    return streams


class RideDetailTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL)")
        self.conn.execute("INSERT INTO metrics VALUES (1, '2026-01-01', 'ftp', 200)")
        self.conn.execute(
            "CREATE TABLE activity_details (activity_id TEXT, source_status TEXT, detail_json TEXT, streams_json TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE activity_stream_summaries (activity_id TEXT, hr_trimp REAL, power_tss REAL, normalized_power REAL)"
        )
        self.addCleanup(self.conn.close)

    def build(self, activity, detail=None, streams=None, summary=(80.0, 70.0, 180.0), records=None, source="cached"):
        self.conn.execute("DELETE FROM activity_details")
        self.conn.execute("DELETE FROM activity_stream_summaries")
        self.conn.execute(
            "INSERT INTO activity_details VALUES (?, ?, ?, ?)",
            (activity["id"], source, json.dumps(detail) if detail else None, json.dumps(streams) if streams else None),
        )
        self.conn.execute("INSERT INTO activity_stream_summaries VALUES (?, ?, ?, ?)", (activity["id"], *summary))
        row = self.conn.execute("SELECT * FROM activity_details").fetchone()
        stream_summary = self.conn.execute("SELECT * FROM activity_stream_summaries").fetchone()
        return build_ride_detail(self.conn, activity, row, stream_summary, power_records=records or {})

    def test_non_cycling_activity_has_no_ride_block(self):
        self.assertIsNone(self.build({"id": "1", "type": "Run", "date": "2026-02-01"}))

    def test_outdoor_ride_without_meter_reports_estimated_power_only(self):
        result = self.build(
            {"id": "2", "type": "Ride", "date": "2026-02-01", "avg_watts": 109},
            detail={"device_watts": False, "trainer": False},
            streams=steady_streams(),
        )
        self.assertEqual(result["power_source"], "estimated")
        self.assertEqual(result["environment"], "outdoor")
        self.assertEqual(result["estimated_avg_watts"], 109)
        self.assertIsNone(result["power"])
        self.assertEqual(result["power_efforts"], [])
        self.assertEqual(result["hr_load"], 80.0)

    def test_ride_without_any_power_reports_none(self):
        result = self.build({"id": "3", "type": "Ride", "date": "2026-02-01", "avg_watts": None}, detail={})
        self.assertEqual(result["power_source"], "none")

    def test_measured_ride_reports_intensity_bests_and_decoupling(self):
        records = {300: {"watts": 250, "activity_id": "9", "date": "2026-01-10"}, 1200: {"watts": 170, "activity_id": "4", "date": "2026-02-01"}}
        result = self.build(
            {"id": "4", "type": "Ride", "date": "2026-02-01", "avg_watts": 158},
            detail={"device_watts": True, "kilojoules": 570},
            streams=steady_streams(latlng=True),
            records=records,
        )
        self.assertEqual(result["power_source"], "measured")
        self.assertEqual(result["power"]["intensity_factor"], 0.9)
        self.assertEqual(result["power"]["tss"], 70)
        self.assertEqual(result["power"]["work_kj"], 570)
        efforts = {effort["duration_s"]: effort for effort in result["power_efforts"]}
        self.assertEqual(efforts[300]["watts"], 300)
        self.assertEqual(efforts[300]["start_time_s"], 600)
        self.assertEqual(efforts[300]["pct_of_ftp"], 150)
        self.assertEqual(efforts[300]["pct_of_best"], 120)
        self.assertFalse(efforts[300]["is_record"])
        self.assertTrue(efforts[1200]["is_record"])
        self.assertEqual(len(efforts[300]["route_segment"]), 301)
        self.assertIn(3600, efforts)
        self.assertIsNone(efforts[15]["best_watts"])
        # The 5-minute surge makes the ride too variable for a decoupling read.
        self.assertFalse(result["decoupling"]["available"])
        self.assertEqual(result["decoupling"]["reason"], "not_steady")

    def test_virtual_ride_backfill_counts_as_measured_and_indoor(self):
        streams = steady_streams()
        streams["watts"]["data"] = [150 for _ in streams["time"]["data"]]
        result = self.build(
            {"id": "5", "type": "VirtualRide", "date": "2026-02-01", "avg_watts": 150},
            streams=streams,
            source="streams_backfill",
        )
        self.assertEqual(result["power_source"], "measured")
        self.assertEqual(result["environment"], "indoor")
        self.assertTrue(result["decoupling"]["available"])
        self.assertEqual(result["decoupling"]["decoupling_pct"], 0)
        self.assertTrue(result["decoupling"]["coupled"])


if __name__ == "__main__":
    unittest.main()
