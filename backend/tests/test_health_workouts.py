import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

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


def workout(uuid, start, *, kind="Ride", minutes=60, distance_m=30000.0, name="Outdoor Cycling", avg_hr=140):
    seconds = minutes * 60
    return {
        "uuid": uuid,
        "type": kind,
        "name": name,
        "start": start.isoformat(timespec="seconds"),
        "end": (start + timedelta(seconds=seconds)).isoformat(timespec="seconds"),
        "duration_s": seconds,
        "distance_m": distance_m,
        "energy_kcal": 700,
        "avg_hr": avg_hr,
        "max_hr": 170,
        "source_bundle": "com.apple.health.ABC",
        "device": "Watch7,2",
        "streams": {
            "time": [0, 1, 2, 3],
            "heartrate": [130, 135, 140, 145],
            "velocity_smooth": [8.0, 8.2, 8.4, 8.3],
            "altitude": [100, 100.5, 101, 101.2],
            "latlng": [[50.0, 19.9], [50.0001, 19.9], [50.0002, 19.9], [50.0003, 19.9]],
            "watts": [None, None, None, None],
        },
    }


class HealthWorkoutPushTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "health-workouts.db")
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

    def push(self, *workouts):
        response = self.client.post("/integrations/health-workouts/push", json={"workouts": list(workouts)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def query(self, sql, *args):
        conn = self.get_db()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def test_new_workout_is_created_with_streams_and_repush_is_a_no_op(self):
        start = datetime(2026, 9, 1, 7, 0).astimezone()
        result = self.push(workout("AAAA-1", start))
        item = result["items"][0]
        self.assertEqual(item["action"], "created")
        self.assertEqual(item["activity_id"], "healthkit:aaaa-1")

        row = self.query("SELECT * FROM activities WHERE id = ?", "healthkit:aaaa-1")[0]
        self.assertEqual((row["date"], row["type"], row["distance_km"], row["duration_min"]), ("2026-09-01", "Ride", 30.0, 60.0))
        detail = self.query("SELECT source_status, streams_json FROM activity_details WHERE activity_id = ?", "healthkit:aaaa-1")[0]
        streams = json.loads(detail["streams_json"])
        self.assertEqual(detail["source_status"], "healthkit_fit")
        self.assertEqual(streams["heartrate"]["data"], [130, 135, 140, 145])
        self.assertNotIn("watts", streams)  # all-empty streams are dropped
        self.assertTrue(self.query("SELECT 1 FROM activity_stream_summaries WHERE activity_id = ?", "healthkit:aaaa-1"))

        again = self.push(workout("AAAA-1", start))
        self.assertEqual(again["items"][0]["action"], "already_processed")
        self.assertEqual(len(self.query("SELECT id FROM activities WHERE date = '2026-09-01'")), 1)

    def test_workout_links_to_strava_activity_and_only_fills_empty_fields(self):
        start = datetime(2026, 9, 2, 18, 0).astimezone()
        conn = self.get_db()
        conn.execute(
            "INSERT INTO activities (id, date, type, name, distance_km, duration_min, avg_hr, calories) "
            "VALUES ('9001', '2026-09-02', 'Ride', 'Evening loop', 30.1, 59.0, NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO activity_source_refs (source, external_id, activity_id, started_at, status) "
            "VALUES ('strava', '9001', '9001', ?, 'linked')",
            (start.isoformat(),),
        )
        conn.commit()
        conn.close()

        item = self.push(workout("BBBB-2", start + timedelta(seconds=30)))["items"][0]
        self.assertEqual((item["action"], item["activity_id"]), ("linked", "9001"))
        row = self.query("SELECT name, distance_km, avg_hr, calories FROM activities WHERE id = '9001'")[0]
        self.assertEqual((row["name"], row["distance_km"], row["avg_hr"], row["calories"]), ("Evening loop", 30.1, 140, 700))
        self.assertFalse(self.query("SELECT 1 FROM activities WHERE id = 'healthkit:bbbb-2'"))

    def test_later_strava_import_enriches_the_watch_activity(self):
        from backend.app.services import strava
        from backend.app.services.activities import upsert_activity
        from backend.app.services.dashboard import estimate_thresholds, intensity_bucket_from_hr
        from backend.app.repositories.activities import get_latest_activity_date

        start = datetime(2026, 9, 3, 7, 0).astimezone()
        self.push(workout("CCCC-3", start))
        strava_item = {
            "id": 7777, "type": "Ride", "sport_type": "Ride", "name": "Morning coffee ride",
            "start_date": start.astimezone().isoformat(), "start_date_local": "2026-09-03T07:00:20Z",
            "distance": 30050.0, "moving_time": 3550, "average_heartrate": 141, "max_heartrate": 171,
            "average_watts": 182.4, "total_elevation_gain": 210, "calories": 690,
        }
        conn = self.get_db()
        try:
            with patch.object(strava, "get_strava_access_token", return_value="token"), \
                    patch.object(strava, "fetch_strava_activities", return_value=[strava_item]), \
                    patch.object(strava, "_store_mountain_tracks"):
                strava.import_strava_activities_data(
                    conn, SimpleNamespace(start_date="2026-09-03", end_date="2026-09-03", fetch_streams=False),
                    get_latest_activity_date_fn=get_latest_activity_date,
                    get_setting_fn=lambda key: None, set_setting_fn=lambda key, value: None,
                    upsert_activity_fn=upsert_activity, estimate_thresholds_fn=estimate_thresholds,
                    intensity_bucket_from_hr_fn=intensity_bucket_from_hr,
                )
        finally:
            conn.close()

        row = self.query("SELECT name, avg_watts FROM activities WHERE id = 'healthkit:cccc-3'")[0]
        self.assertEqual((row["name"], row["avg_watts"]), ("Morning coffee ride", 182.4))
        self.assertFalse(self.query("SELECT 1 FROM activities WHERE id = '7777'"))

        from backend.app.services.activities import get_activity_detail_data

        fetched = []

        def fetch_detail(client, activity_id):
            fetched.append(activity_id)
            return {"id": 7777, "device_watts": False, "average_watts": 182.4}, None

        def fetch_streams(client, activity_id, keys):
            raise AssertionError("watch streams are kept")

        conn = self.get_db()
        try:
            for _ in range(2):
                get_activity_detail_data(
                    conn, "healthkit:cccc-3",
                    get_setting_fn=lambda key: None, set_setting_fn=lambda key, value: None,
                    get_strava_access_token_fn=lambda get, set_: "token",
                    fetch_strava_activity_detail_fn=fetch_detail,
                    fetch_strava_activity_streams_fn=fetch_streams,
                )
        finally:
            conn.close()
        self.assertEqual(fetched, ["7777"])  # fetched once, by its Strava ID
        detail = self.query("SELECT source_status, detail_json, streams_json FROM activity_details WHERE activity_id = 'healthkit:cccc-3'")[0]
        self.assertEqual(detail["source_status"], "healthkit_fit+strava")
        self.assertEqual(json.loads(detail["detail_json"])["average_watts"], 182.4)
        self.assertEqual(json.loads(detail["streams_json"])["heartrate"]["data"], [130, 135, 140, 145])

    def _import_strava(self, item, day):
        from backend.app.services import strava
        from backend.app.services.activities import upsert_activity
        from backend.app.services.dashboard import estimate_thresholds, intensity_bucket_from_hr
        from backend.app.repositories.activities import get_latest_activity_date

        conn = self.get_db()
        try:
            with patch.object(strava, "get_strava_access_token", return_value="token"), \
                    patch.object(strava, "fetch_strava_activities", return_value=[item]), \
                    patch.object(strava, "_store_mountain_tracks"):
                strava.import_strava_activities_data(
                    conn, SimpleNamespace(start_date=day, end_date=day, fetch_streams=False),
                    get_latest_activity_date_fn=get_latest_activity_date,
                    get_setting_fn=lambda key: None, set_setting_fn=lambda key, value: None,
                    upsert_activity_fn=upsert_activity, estimate_thresholds_fn=estimate_thresholds,
                    intensity_bucket_from_hr_fn=intensity_bucket_from_hr,
                )
        finally:
            conn.close()

    def test_strava_weight_training_links_to_a_watch_core_training_workout(self):
        # The phone sends Core Training as Workout; Strava files the same workout as WeightTraining.
        start = datetime(2026, 9, 14, 23, 0).astimezone()
        self.push(workout("CORE-6", start, kind="Workout", minutes=28, distance_m=None,
                          name="Core Training", avg_hr=119))
        self._import_strava({
            "id": 8888, "type": "WeightTraining", "sport_type": "WeightTraining", "name": "Night Workout",
            "start_date": start.astimezone().isoformat(), "start_date_local": "2026-09-14T23:00:00Z",
            "distance": 0.0, "moving_time": 1680, "average_heartrate": 119, "max_heartrate": 147,
        }, "2026-09-14")

        self.assertFalse(self.query("SELECT 1 FROM activities WHERE id = '8888'"))
        ref = self.query("SELECT activity_id FROM activity_source_refs WHERE source = 'strava' AND external_id = '8888'")[0]
        self.assertEqual(ref["activity_id"], "healthkit:core-6")

    def test_same_day_weight_training_at_another_time_stays_separate(self):
        start = datetime(2026, 9, 15, 7, 0).astimezone()
        self.push(workout("CORE-7", start, kind="Workout", minutes=28, distance_m=None, name="Core Training"))
        later = start + timedelta(hours=10)
        self._import_strava({
            "id": 9999, "type": "WeightTraining", "sport_type": "WeightTraining", "name": "Evening Weight Training",
            "start_date": later.astimezone().isoformat(), "start_date_local": "2026-09-15T17:00:00Z",
            "distance": 0.0, "moving_time": 1680, "average_heartrate": 140, "max_heartrate": 160,
        }, "2026-09-15")

        self.assertTrue(self.query("SELECT 1 FROM activities WHERE id = '9999'"))

    def _one_time_session(self):
        payload = {
            "name": "Watch link test",
            "exercises": [{"exercise_name": "Goblet Squat", "set_count": 1, "target_reps": 8,
                           "target_weight_kg": None, "rest_seconds": 60}],
        }
        response = self.client.post("/strength/workouts/sessions/one-time", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_strength_workout_pushed_after_the_session_links_to_it(self):
        session = self._one_time_session()
        self.client.post(f"/strength/workouts/sessions/{session['id']}/finish", json={})
        start = datetime.fromisoformat(session["started_at"]) + timedelta(seconds=40)
        item = self.push(workout("DDDD-4", start, kind="WeightTraining", minutes=45, distance_m=None,
                                 name="Traditional Strength Training"))["items"][0]
        self.assertEqual(item["strength_session_id"], session["id"])
        linked = self.client.get(f"/strength/workouts/sessions/{session['id']}").json()
        self.assertEqual(linked["linked_activity"]["id"], "healthkit:dddd-4")

    def test_strength_workout_pushed_before_finish_links_when_the_session_ends(self):
        session = self._one_time_session()
        start = datetime.fromisoformat(session["started_at"]) - timedelta(minutes=2)
        # Arrives while the session is still running; it matches but there's no completion yet,
        # so either path must end with exactly one link.
        self.push(workout("EEEE-5", start, kind="WeightTraining", minutes=40, distance_m=None,
                          name="Traditional Strength Training"))
        finished = self.client.post(f"/strength/workouts/sessions/{session['id']}/finish", json={}).json()
        self.assertEqual(finished["linked_activity"]["id"], "healthkit:eeee-5")


if __name__ == "__main__":
    unittest.main()
