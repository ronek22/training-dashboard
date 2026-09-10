import json
import sqlite3
import unittest

from backend.app.services.power_zones import build_activity_power_zone_summary


class PowerZoneTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL)")
        self.conn.execute("INSERT INTO metrics VALUES (1, '2026-01-01', 'ftp', 200)")
        self.conn.execute("INSERT INTO metrics VALUES (2, '2026-03-01', 'ftp', 300)")
        self.addCleanup(self.conn.close)

    def summary(self, watts, times=None, sport="Ride", date="2026-02-01"):
        return build_activity_power_zone_summary(
            self.conn, {"type": sport, "date": date},
            {"streams_json": json.dumps({"time": {"data": times if times is not None else list(range(len(watts)))}, "watts": {"data": watts}})},
        )

    def test_boundaries_coasting_and_historical_ftp(self):
        result = self.summary([0, 0, 110, 150, 180, 210, 240, 300, 301])
        self.assertTrue(result["available"])
        self.assertEqual(result["ftp_watts"], 200)
        self.assertEqual([z["seconds"] for z in result["zones"]], [2, 1, 1, 1, 1, 1, 1])
        self.assertEqual(result["dominant_zone_key"], "zone1")

    def test_duration_weighting_and_virtual_ride(self):
        result = self.summary([0, 120, 220], [0, 60, 240], sport="VirtualRide")
        self.assertEqual(result["zone2_pct"], 25)
        self.assertEqual(result["total_minutes"], 4)
        self.assertEqual(result["zones"][4]["minutes"], 3)

    def test_invalid_samples_and_time_intervals_are_skipped(self):
        result = self.summary([0, None, -1, float("nan"), float("inf"), 120, 120, 120], [0, 1, 2, 3, 4, 4, 3, 63])
        self.assertEqual(result["zone2_minutes"], 1)
        self.assertEqual(result["zone2_pct"], 100)

    def test_unavailable_cases(self):
        self.assertEqual(self.summary([0, 120], sport="Run")["reason"], "unsupported_activity_type")
        self.assertEqual(self.summary([0, 120], date="2025-01-01")["reason"], "missing_ftp")
        self.assertEqual(self.summary([])["reason"], "missing_time_stream")
        self.assertEqual(self.summary([], [0, 1])["reason"], "missing_power_stream")
        self.assertEqual(self.summary([0, None])["reason"], "empty_zone_samples")
        self.assertFalse(build_activity_power_zone_summary(self.conn, {"type": "Ride"}, None)["available"])

    def test_mismatched_stream_lengths(self):
        result = self.summary([0, 120], [0, 60, 120])
        self.assertEqual(result["total_minutes"], 1)
