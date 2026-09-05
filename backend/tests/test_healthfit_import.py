import sqlite3
import json
import tempfile
import unittest
import importlib
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

def parsed(file_hash: str, date: str, *, duration: float = 60.0, distance: float | None = 10.0):
    return {
        "file_hash": file_hash,
        "file_name": f"{date}-120000-Outdoor Running-Watch.fit",
        "started_at": f"{date}T10:00:00+00:00",
        "activity": {
            "id": f"healthfit:{file_hash[:24]}", "date": date, "type": "Run", "name": "Outdoor Running",
            "distance_km": distance, "duration_min": duration, "avg_hr": 145, "max_hr": 170,
            "avg_pace": "6:00", "avg_watts": None, "elevation_m": 50, "calories": 500,
            "zone2": False, "notes": None,
        },
        "streams": {"time": {"data": [0, 60]}, "heartrate": {"data": [140, 150]}},
    }


class HealthFitImportTests(unittest.TestCase):
    def setUp(self):
        self.healthfit = importlib.import_module("backend.app.services.healthfit")
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (
                id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, workout_intent TEXT, name TEXT,
                distance_km REAL, duration_min REAL, avg_hr INTEGER, max_hr INTEGER, avg_pace TEXT,
                avg_watts REAL, elevation_m INTEGER, calories INTEGER, zone2 INTEGER, notes TEXT,
                linked_planned_session_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE activity_source_refs (
                source TEXT, external_id TEXT, activity_id TEXT, started_at TEXT, file_name TEXT, file_hash TEXT,
                status TEXT, match_reason TEXT, metadata_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(source, external_id)
            );
            CREATE TABLE activity_details (
                activity_id TEXT PRIMARY KEY, fetched_at TEXT, source_status TEXT, streams_json TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def _file(self, name: str):
        (self.directory / name).touch()

    def test_historical_unmatched_file_is_baselined_without_activity(self):
        self.conn.execute(
            "INSERT INTO activities (id, date, type) VALUES ('strava-old', '2026-07-10', 'Ride')"
        )
        item = parsed("a" * 64, "2026-07-09")
        self._file(item["file_name"])
        with patch.object(self.healthfit, "healthfit_directory", return_value=self.directory), patch.object(
            self.healthfit, "parse_healthfit_file", return_value=item
        ):
            preview = self.healthfit.preview_healthfit_import(self.conn)
            result = self.healthfit.apply_healthfit_import(self.conn)
        self.assertEqual(preview["counts"]["baseline"], 1)
        self.assertEqual(result["applied"]["baselined"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 1)

    def test_compatible_existing_activity_is_linked_not_duplicated(self):
        self.conn.execute(
            """INSERT INTO activities
               (id, date, type, name, distance_km, duration_min, avg_hr)
               VALUES ('strava-1', '2026-07-11', 'Run', 'Morning Run', 10.01, 60.2, 146)"""
        )
        item = parsed("b" * 64, "2026-07-11")
        self._file(item["file_name"])
        with patch.object(self.healthfit, "healthfit_directory", return_value=self.directory), patch.object(
            self.healthfit, "parse_healthfit_file", return_value=item
        ):
            result = self.healthfit.apply_healthfit_import(self.conn)
        self.assertEqual(result["applied"]["linked"], 1)
        self.assertEqual(result["applied"]["streams_imported"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 1)
        ref = self.conn.execute("SELECT activity_id FROM activity_source_refs").fetchone()
        self.assertEqual(ref["activity_id"], "strava-1")
        detail = self.conn.execute(
            "SELECT streams_json FROM activity_details WHERE activity_id = 'strava-1'"
        ).fetchone()
        self.assertEqual(json.loads(detail["streams_json"])["heartrate"]["data"], [140, 150])

    def test_new_file_is_created_once_and_second_import_is_idempotent(self):
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('old', '2026-07-10', 'Ride')")
        item = parsed("c" * 64, "2026-07-12")
        self._file(item["file_name"])
        with patch.object(self.healthfit, "healthfit_directory", return_value=self.directory), patch.object(
            self.healthfit, "parse_healthfit_file", return_value=item
        ):
            first = self.healthfit.apply_healthfit_import(self.conn)
            second = self.healthfit.apply_healthfit_import(self.conn)
        self.assertEqual(first["applied"]["created"], 1)
        self.assertEqual(second["applied"]["created"], 0)
        self.assertEqual(second["applied"]["skipped"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)

    def test_repeated_import_backfills_missing_streams_for_existing_link(self):
        self.conn.execute(
            """INSERT INTO activities
               (id, date, type, name, distance_km, duration_min, avg_hr)
               VALUES ('watch-1', '2026-07-11', 'Run', 'Morning Run', 10.01, 60.2, 146)"""
        )
        item = parsed("f" * 64, "2026-07-11")
        self._file(item["file_name"])
        with patch.object(self.healthfit, "healthfit_directory", return_value=self.directory), patch.object(
            self.healthfit, "parse_healthfit_file", return_value=item
        ):
            first = self.healthfit.apply_healthfit_import(self.conn)
            self.conn.execute("DELETE FROM activity_details WHERE activity_id = 'watch-1'")
            second = self.healthfit.apply_healthfit_import(self.conn)

        self.assertEqual(first["applied"]["linked"], 1)
        self.assertEqual(second["applied"]["skipped"], 1)
        self.assertEqual(second["applied"]["streams_imported"], 1)
        detail = self.conn.execute(
            "SELECT streams_json FROM activity_details WHERE activity_id = 'watch-1'"
        ).fetchone()
        self.assertEqual(json.loads(detail["streams_json"])["heartrate"]["data"], [140, 150])

    def test_later_strava_import_reuses_healthfit_activity_id(self):
        healthfit_id = "healthfit:" + "d" * 24
        self.conn.execute(
            """INSERT INTO activities
               (id, date, type, name, distance_km, duration_min, avg_hr)
               VALUES (?, '2026-07-12', 'Run', 'Outdoor Running', 10.0, 60.0, 145)""",
            (healthfit_id,),
        )
        raw_strava = {
            "id": 987654321,
            "start_date": "2026-07-12T10:00:00Z",
            "start_date_local": "2026-07-12T12:00:00Z",
            "type": "Run", "sport_type": "Run", "name": "Morning Run",
            "distance": 10010.0, "moving_time": 3605, "average_speed": 2.777,
            "average_heartrate": 146, "max_heartrate": 170,
        }
        strava = importlib.import_module("backend.app.services.strava")
        activities = importlib.import_module("backend.app.services.activities")
        with patch.object(strava, "get_strava_access_token", return_value="token"), patch.object(
            strava, "fetch_strava_activities", return_value=[raw_strava]
        ):
            strava.import_strava_activities_data(
                self.conn,
                SimpleNamespace(start_date="2026-07-12", end_date="2026-07-12", fetch_streams=False),
                get_latest_activity_date_fn=lambda conn: "2026-07-12",
                get_setting_fn=lambda key: None,
                set_setting_fn=lambda key, value: None,
                upsert_activity_fn=activities.upsert_activity,
                estimate_thresholds_fn=lambda conn: {},
                intensity_bucket_from_hr_fn=lambda hr, low, high: "low_aerobic",
            )
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 1)
        ref = self.conn.execute(
            "SELECT activity_id FROM activity_source_refs WHERE source = 'strava' AND external_id = '987654321'"
        ).fetchone()
        self.assertEqual(ref["activity_id"], healthfit_id)

    def test_later_strava_virtual_ride_reuses_healthfit_indoor_ride(self):
        healthfit_id = "healthfit:" + "v" * 24
        self.conn.execute(
            """INSERT INTO activities
               (id, date, type, name, distance_km, duration_min, avg_hr)
               VALUES (?, '2026-08-18', 'Ride', 'Indoor Cycling', 25.15, 49.0, 158)""",
            (healthfit_id,),
        )
        raw_strava = {
            "id": 19797867373,
            "start_date": "2026-08-18T17:17:21Z",
            "start_date_local": "2026-08-18T19:17:21Z",
            "type": "VirtualRide", "sport_type": "VirtualRide", "name": "Zwift - Coast to Coast",
            "distance": 25150.0, "moving_time": 2868, "average_speed": 8.77,
            "average_heartrate": 158, "max_heartrate": 177, "average_watts": 146,
        }
        strava = importlib.import_module("backend.app.services.strava")
        activities = importlib.import_module("backend.app.services.activities")
        with patch.object(strava, "get_strava_access_token", return_value="token"), patch.object(
            strava, "fetch_strava_activities", return_value=[raw_strava]
        ):
            strava.import_strava_activities_data(
                self.conn,
                SimpleNamespace(start_date="2026-08-18", end_date="2026-08-18", fetch_streams=False),
                get_latest_activity_date_fn=lambda conn: "2026-08-18",
                get_setting_fn=lambda key: None,
                set_setting_fn=lambda key, value: None,
                upsert_activity_fn=activities.upsert_activity,
                estimate_thresholds_fn=lambda conn: {},
                intensity_bucket_from_hr_fn=lambda hr, low, high: "low_aerobic",
            )

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 1)
        activity = self.conn.execute("SELECT id, type FROM activities").fetchone()
        self.assertEqual(activity["id"], healthfit_id)
        self.assertEqual(activity["type"], "VirtualRide")
        ref = self.conn.execute(
            "SELECT activity_id FROM activity_source_refs WHERE source = 'strava' AND external_id = '19797867373'"
        ).fetchone()
        self.assertEqual(ref["activity_id"], healthfit_id)

    def test_start_time_reconciles_elapsed_and_moving_time_difference(self):
        healthfit_id = "healthfit:" + "w" * 24
        self.conn.execute(
            """INSERT INTO activities
               (id, date, type, name, distance_km, duration_min, avg_hr)
               VALUES (?, '2026-08-15', 'Walk', 'Outdoor Walking', 5.09, 101.1, 83)""",
            (healthfit_id,),
        )
        self.conn.execute(
            """INSERT INTO activity_source_refs
               (source, external_id, activity_id, started_at, status)
               VALUES ('healthfit', 'hash', ?, '2026-08-15T11:16:48+00:00', 'create')""",
            (healthfit_id,),
        )
        candidate = {
            "date": "2026-08-15", "type": "Walk", "distance_km": 5.09,
            "duration_min": 82.7, "avg_hr": 84, "started_at": "2026-08-15T11:16:47+00:00",
        }

        match = importlib.import_module("backend.app.services.activity_sources").find_activity_match(
            self.conn, candidate
        )

        self.assertEqual(match["status"], "matched")
        self.assertEqual(match["activity"]["id"], healthfit_id)
        self.assertIn("start time", match["reason"])

    def test_unseen_older_file_after_initialization_is_created(self):
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('newer', '2026-07-17', 'Ride')")
        self.conn.execute(
            """INSERT INTO activity_source_refs
               (source, external_id, status, file_name, match_reason)
               VALUES ('healthfit', 'filename:old.fit', 'baseline', 'old.fit', 'Initial baseline')"""
        )
        item = parsed("e" * 64, "2026-07-15")
        self._file(item["file_name"])
        with patch.object(self.healthfit, "healthfit_directory", return_value=self.directory), patch.object(
            self.healthfit, "parse_healthfit_file", return_value=item
        ):
            preview = self.healthfit.preview_healthfit_import(self.conn)
            result = self.healthfit.apply_healthfit_import(self.conn)
        self.assertTrue(preview["initialized"])
        self.assertEqual(preview["counts"]["create"], 1)
        self.assertIn("late-arriving", preview["items"][0]["reason"])
        self.assertEqual(result["applied"]["created"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
