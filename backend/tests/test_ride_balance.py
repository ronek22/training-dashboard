import json
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from backend.app.services import ride_balance
from backend.app.services.ride_balance import build_ride_balance, classify_ride

TODAY = date(2026, 10, 8)
FTP = 200.0


def _streams(blocks, key="watts"):
    """blocks: [(seconds, value), ...] sampled at 1 Hz."""
    values = [value for seconds, value in blocks for _ in range(seconds)]
    return json.dumps({"time": {"data": list(range(len(values)))}, key: {"data": values}})


def _detail(streams, *, power_meter=True):
    return {"detail_json": json.dumps({"device_watts": power_meter}), "streams_json": streams, "source_status": "detail"}


def _ride(minutes=60, intent=None, avg_hr=None, kind="VirtualRide"):
    return {"type": kind, "duration_min": minutes, "workout_intent": intent, "avg_hr": avg_hr}


class ClassifyRideTests(unittest.TestCase):
    def test_vo2_intervals_from_power(self):
        streams = _streams([(900, 130), *[(180, 235), (180, 110)] * 5, (600, 120)])
        self.assertEqual(classify_ride(_ride(), _detail(streams), FTP)["type"], "vo2")

    def test_sweet_spot_blocks_from_power(self):
        streams = _streams([(600, 130), (1200, 180), (300, 110), (1200, 180), (600, 120)])
        result = classify_ride(_ride(70), _detail(streams), FTP)
        self.assertEqual((result["type"], result["basis"]), ("sweet_spot", "power"))

    def test_short_sweet_spot_bursts_stay_z2(self):
        streams = _streams([(600, 140), *[(240, 180), (120, 130)] * 6, (600, 140)])
        self.assertEqual(classify_ride(_ride(), _detail(streams), FTP)["type"], "z2")

    def test_short_easy_ride_is_recovery(self):
        streams = _streams([(2700, 110)])
        self.assertEqual(classify_ride(_ride(45), _detail(streams), FTP)["type"], "recovery")

    def test_hard_stream_beats_easy_label(self):
        streams = _streams([(900, 130), (1500, 185), (900, 130)])
        self.assertEqual(classify_ride(_ride(intent="easy"), _detail(streams), FTP)["type"], "sweet_spot")

    def test_unconfirmed_power_falls_back_to_heart_rate(self):
        streams = json.loads(_streams([(600, 140), (1500, 160), (600, 140)], key="heartrate"))
        streams["watts"] = {"data": [400] * len(streams["time"]["data"])}
        result = classify_ride(_ride(kind="Ride"), _detail(json.dumps(streams), power_meter=False), FTP)
        self.assertEqual((result["type"], result["basis"]), ("sweet_spot", "heart_rate"))

    def test_no_stream_uses_intent(self):
        self.assertEqual(classify_ride(_ride(intent="interval"), None, FTP)["type"], "vo2")
        self.assertEqual(classify_ride(_ride(intent="recovery"), None, None)["type"], "recovery")
        self.assertEqual(classify_ride(_ride(90), None, None)["type"], "z2")


class BuildRideBalanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, duration_min REAL, avg_hr REAL, workout_intent TEXT);
            CREATE TABLE activity_details (activity_id TEXT, detail_json TEXT, streams_json TEXT, source_status TEXT);
            """
        )
        patcher = patch.object(ride_balance, "_reference_ftp", return_value={"watts": FTP, "source": "estimate", "basis": "95% of best 20 min"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _add(self, day, intent=None, minutes=60, kind="Ride"):
        index = self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        self.conn.execute("INSERT INTO activities VALUES (?, ?, ?, ?, ?, NULL, ?)", (str(index), day, kind, f"Ride {index}", minutes, intent))

    def test_flags_type_that_disappeared(self):
        self._add("2026-09-01", "interval")
        self._add("2026-09-10", "tempo")
        self._add("2026-09-30", "tempo")
        self._add("2026-10-06", "easy")
        self._add("2026-10-07", "recovery", minutes=45)
        self._add("2026-10-07", "easy", minutes=10, kind="VirtualRide")  # cool-down fragment, ignored

        result = build_ride_balance(self.conn, TODAY)

        self.assertEqual(result["window_start"], "2026-08-31")
        self.assertEqual(len(result["weeks"]), 6)
        self.assertTrue(result["weeks"][-1]["partial"])
        self.assertEqual(result["ride_count"], 5)
        status = {item["key"]: item["status"] for item in result["types"]}
        self.assertEqual(status, {"z2": "ok", "sweet_spot": "ok", "vo2": "gone", "recovery": "ok"})
        self.assertEqual([flag["type"] for flag in result["flags"]], ["vo2"])
        self.assertIn("37 days ago", result["flags"][0]["message"])
        self.assertEqual(result["weeks"][-1]["counts"], {"z2": 1, "sweet_spot": 0, "vo2": 0, "recovery": 1})

    def test_absent_type_is_not_flagged(self):
        self._add("2026-10-01", "easy")
        self._add("2026-10-06", "tempo")
        result = build_ride_balance(self.conn, TODAY)
        self.assertEqual(result["flags"], [])
        self.assertIn("No VO2 or Recovery in 6 weeks", result["summary"])

    def test_no_recent_rides_gives_one_flag(self):
        self._add("2026-09-01", "easy")
        self._add("2026-09-08", "interval")
        result = build_ride_balance(self.conn, TODAY)
        self.assertEqual(len(result["flags"]), 1)
        self.assertIsNone(result["flags"][0]["type"])


if __name__ == "__main__":
    unittest.main()
