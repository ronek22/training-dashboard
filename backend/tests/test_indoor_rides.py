import json
import os
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient


def _is_app_module(name):
    return name == "backend.app" or name.startswith("backend.app.")


def import_fresh_app():
    replaced = {name: sys.modules.pop(name) for name in list(sys.modules) if _is_app_module(name)}
    import backend.app.main as main_module

    return main_module.app, replaced


def restore_app_modules(replaced):
    for name in [name for name in sys.modules if _is_app_module(name)]:
        sys.modules.pop(name)
    sys.modules.update(replaced)


class IndoorRidesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "indoor-rides.db")
        os.environ["STRAVA_AUTO_IMPORT"] = "false"
        os.environ["TRAINING_BACKUPS"] = "false"
        app, cls.replaced_modules = import_fresh_app()
        cls.client = TestClient(app, base_url="http://localhost:8000")
        cls.client.__enter__()
        from backend.app.db import get_db

        cls.get_db = staticmethod(get_db)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        os.environ.pop("TRAINING_DB_PATH", None)
        os.environ.pop("STRAVA_AUTO_IMPORT", None)
        os.environ.pop("TRAINING_BACKUPS", None)
        restore_app_modules(cls.replaced_modules)
        cls.temp_dir.cleanup()

    def add(self, activity_id, date, kind, *, started_at=None, streams=None, source="strava", calories=None):
        conn = self.get_db()
        conn.execute(
            "INSERT INTO activities (id, date, type, name, distance_km, duration_min, avg_hr, calories) "
            "VALUES (?, ?, ?, ?, 20.5, 40.0, 140, ?)",
            (activity_id, date, kind, f"Zwift - {activity_id}", calories),
        )
        if started_at:
            conn.execute(
                "INSERT INTO activity_source_refs (source, external_id, activity_id, started_at, status) "
                "VALUES (?, ?, ?, ?, 'linked')",
                (source, activity_id, activity_id, started_at),
            )
        if streams:
            conn.execute(
                "INSERT INTO activity_details (activity_id, fetched_at, source_status, streams_json) "
                "VALUES (?, '2026-10-01', 'streams_backfill', ?)",
                (activity_id, json.dumps({key: {"data": data} for key, data in streams.items()})),
            )
        conn.commit()
        conn.close()

    def test_lists_indoor_rides_with_streams_and_skips_the_rest(self):
        self.add("101", "2026-10-20", "VirtualRide", started_at="2026-10-20T17:00:00+00:00", streams={
            "time": [0, 1, 2, 3],
            "heartrate": [120, 125, 130, 135],
            "watts": [200, 200, 200, None],
            "cadence": [None, None, None, None],
            "distance": [0, 8, 16, 24],
            "altitude": [1, 1, 1, 1],
        })
        self.add("102", "2026-10-21", "Ride", started_at="2026-10-21T07:00:00+00:00")
        self.add("103", "2026-10-22", "VirtualRide", started_at="2026-10-22T07:00:00+00:00", source="healthkit")
        self.add("104", "2026-09-01", "VirtualRide", started_at="2026-09-01T07:00:00+00:00")
        self.add("105", "2026-10-23", "VirtualRide", started_at="2026-10-23T19:00:00+02:00", calories=480)

        response = self.client.get("/integrations/indoor-rides", params={"since": "2026-10-01"})
        self.assertEqual(response.status_code, 200, response.text)
        rides = response.json()["rides"]
        self.assertEqual([ride["id"] for ride in rides], ["101", "105"])

        first = rides[0]
        self.assertEqual(first["start"], "2026-10-20T17:00:00Z")
        self.assertEqual(first["duration_s"], 3)
        self.assertEqual(first["distance_m"], 20500)
        self.assertEqual(set(first["streams"]), {"time", "heartrate", "watts", "distance"})  # empty cadence dropped
        self.assertIsNone(first["energy_kcal"])  # 400 J rounds to 0 kcal

        second = rides[1]
        self.assertEqual(second["start"], "2026-10-23T17:00:00Z")
        self.assertEqual(second["duration_s"], 2400)  # no streams: moving time
        self.assertEqual(second["energy_kcal"], 480)
        self.assertIsNone(second["streams"])

    def test_energy_comes_from_power_when_strava_has_no_calories(self):
        from backend.app.services.indoor_rides import _work_kcal

        self.assertEqual(_work_kcal({"time": list(range(3601)), "watts": [200] * 3601}), 720)
        self.assertIsNone(_work_kcal({"time": [0, 1], "heartrate": [100, 100]}))


if __name__ == "__main__":
    unittest.main()
