import json
import sqlite3
import unittest

from backend.app.services.power_trends import (
    POWER_EFFORT_DURATIONS,
    get_cycling_power_trends_data,
)


class CyclingPowerTrendTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT
            );
            CREATE TABLE activity_details (
                activity_id TEXT PRIMARY KEY,
                detail_json TEXT,
                streams_json TEXT,
                source_status TEXT
            );
            """
        )
        self.addCleanup(self.conn.close)

    def insert_activity(
        self,
        activity_id,
        date,
        activity_type="VirtualRide",
        *,
        name=None,
        device_watts=None,
        times=None,
        watts=None,
        heartrate=None,
    ):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name) VALUES (?, ?, ?, ?)",
            (activity_id, date, activity_type, name or activity_id),
        )
        detail = None if device_watts is None else {"device_watts": device_watts}
        streams = None
        if times is not None or watts is not None or heartrate is not None:
            streams = {}
            if times is not None:
                streams["time"] = {"data": times}
            if watts is not None:
                streams["watts"] = {"data": watts}
            if heartrate is not None:
                streams["heartrate"] = {"data": heartrate}
        self.conn.execute(
            "INSERT INTO activity_details (activity_id, detail_json, streams_json) VALUES (?, ?, ?)",
            (activity_id, json.dumps(detail) if detail is not None else None, json.dumps(streams) if streams is not None else None),
        )

    def test_contract_and_strict_meter_coverage(self):
        self.insert_activity(
            "measured",
            "2026-01-03",
            times=list(range(31)),
            watts=[200] * 31,
            heartrate=[150] * 31,
            device_watts=True,
        )
        self.insert_activity("measured-no-stream", "2026-01-04", device_watts=True)
        self.insert_activity(
            "flagged-off",
            "2026-01-05",
            name="KICKR indoor ride",
            times=list(range(31)),
            watts=[250] * 31,
            device_watts=False,
        )
        self.insert_activity(
            "name-only",
            "2026-01-06",
            name="Indoor Trainer Ride",
            times=list(range(31)),
            watts=[300] * 31,
            device_watts=None,
        )
        self.insert_activity(
            "run-is-ignored",
            "2026-01-07",
            activity_type="Run",
            times=list(range(31)),
            watts=[400] * 31,
            device_watts=True,
        )

        result = get_cycling_power_trends_data(self.conn)

        self.assertEqual([item["seconds"] for item in result["durations"]], list(POWER_EFFORT_DURATIONS))
        self.assertEqual(
            result["coverage"],
            {
                "cycling_activities": 4,
                "measured_power_activities": 2,
                "analyzed_activities": 1,
                "missing_streams": 1,
                "unverified_activities": 2,
            },
        )
        self.assertEqual({effort["activity_id"] for effort in result["efforts"]}, {"measured"})
        self.assertEqual([item["month"] for item in result["monthly"]], ["2026-01"])

    def test_elapsed_time_weighting_finds_shifted_window_and_keeps_zero(self):
        self.insert_activity(
            "irregular",
            "2026-02-01",
            times=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18],
            watts=[50, 100, 100, 100, 100, 100, 100, 100, 0, 0],
            device_watts=True,
        )
        self.insert_activity(
            "coasting",
            "2026-02-02",
            times=list(range(16)),
            watts=[0] * 16,
            device_watts=True,
        )

        result = get_cycling_power_trends_data(self.conn)
        irregular = next(item for item in result["efforts"] if item["activity_id"] == "irregular" and item["duration_seconds"] == 15)
        coasting = next(item for item in result["efforts"] if item["activity_id"] == "coasting" and item["duration_seconds"] == 15)

        self.assertEqual(irregular["watts"], 96.7)
        self.assertEqual((irregular["start_seconds"], irregular["end_seconds"]), (1, 16))
        self.assertEqual(coasting["watts"], 0.0)
        self.assertEqual(result["coverage"]["analyzed_activities"], 2)

    def test_gap_and_invalid_power_cannot_be_stitched(self):
        self.insert_activity(
            "gap",
            "2026-03-01",
            # The complete activity spans more than five seconds, but neither
            # side of the three-second gap can support a five-second window.
            times=[0, 2, 4, 7, 9],
            watts=[100, 100, 100, 100, 100],
            device_watts=True,
        )
        self.insert_activity(
            "invalid-power",
            "2026-03-02",
            times=list(range(7)),
            watts=[100, 100, None, 100, 100, 100, 100],
            device_watts=True,
        )

        result = get_cycling_power_trends_data(self.conn)

        self.assertEqual(result["coverage"]["measured_power_activities"], 2)
        self.assertEqual(result["coverage"]["analyzed_activities"], 0)
        self.assertEqual(result["coverage"]["missing_streams"], 2)
        self.assertEqual(result["efforts"], [])

    def test_hr_is_attached_only_when_the_winning_power_window_is_complete(self):
        self.insert_activity(
            "hr-incomplete",
            "2026-04-01",
            times=list(range(22)),
            watts=[100] * 11 + [200] * 11,
            heartrate=[140] * 11 + [None] * 11,
            device_watts=True,
        )
        self.insert_activity(
            "hr-complete",
            "2026-04-02",
            times=list(range(16)),
            watts=[100] * 16,
            heartrate=[150] * 16,
            device_watts=True,
        )

        result = get_cycling_power_trends_data(self.conn)
        incomplete = next(item for item in result["efforts"] if item["activity_id"] == "hr-incomplete" and item["duration_seconds"] == 15)
        complete = next(item for item in result["efforts"] if item["activity_id"] == "hr-complete" and item["duration_seconds"] == 15)

        self.assertIsNone(incomplete["avg_hr"])
        self.assertEqual(complete["avg_hr"], 150.0)

    def test_global_and_monthly_best_efforts_are_stable_and_months_sorted(self):
        for activity_id, date, power in (
            ("march-low", "2026-03-20", 180),
            ("jan", "2026-01-20", 200),
            ("march-high", "2026-03-01", 220),
        ):
            self.insert_activity(
                activity_id,
                date,
                times=list(range(31)),
                watts=[power] * 31,
                device_watts=True,
            )

        result = get_cycling_power_trends_data(self.conn)
        record = next(item for item in result["records"] if item["duration_seconds"] == 30)
        monthly = {
            row["month"]: next(item for item in row["efforts"] if item["duration_seconds"] == 30)
            for row in result["monthly"]
        }

        self.assertEqual(record["activity_id"], "march-high")
        self.assertEqual(monthly["2026-01"]["watts"], 200.0)
        self.assertEqual(monthly["2026-03"]["watts"], 220.0)
        self.assertEqual([row["month"] for row in result["monthly"]], ["2026-01", "2026-03"])

    def test_empty_history_preserves_response_contract(self):
        result = get_cycling_power_trends_data(self.conn)

        self.assertEqual(result["records"], [])
        self.assertEqual(result["monthly"], [])
        self.assertEqual(result["efforts"], [])
        self.assertEqual(result["coverage"], {
            "cycling_activities": 0,
            "measured_power_activities": 0,
            "analyzed_activities": 0,
            "missing_streams": 0,
            "unverified_activities": 0,
        })

    def test_backfilled_virtualride_watts_are_eligible_without_detail_json(self):
        self.insert_activity(
            "zwift-backfill",
            "2026-01-08",
            times=list(range(31)),
            watts=[210] * 31,
            heartrate=[145] * 31,
        )
        self.conn.execute(
            "UPDATE activity_details SET detail_json = NULL, source_status = 'streams_backfill' WHERE activity_id = 'zwift-backfill'"
        )
        result = get_cycling_power_trends_data(self.conn)
        self.assertEqual(result["coverage"]["measured_power_activities"], 1)
        self.assertEqual(result["coverage"]["analyzed_activities"], 1)
        self.assertEqual(result["efforts"][0]["activity_id"], "zwift-backfill")


if __name__ == "__main__":
    unittest.main()
