import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.tests.test_health_workouts import import_fresh_app, restore_app_modules, workout


class FakeStrava:
    """Answers POST /uploads, then each poll from `polls` in turn."""

    def __init__(self, first, polls=()):
        self.first, self.polls, self.posts = first, list(polls), []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, data=None, files=None):
        self.posts.append({"url": url, "data": data, "file": json.loads(files["file"][1])})
        return _Response(201, self.first)

    def get(self, url, headers=None):
        return _Response(200, self.polls.pop(0))


class _Response:
    def __init__(self, status_code, body):
        self.status_code, self.body, self.text = status_code, body, json.dumps(body)

    def json(self):
        return self.body


class StravaUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "strava-upload.db")
        os.environ["STRAVA_AUTO_IMPORT"] = "false"
        os.environ["TRAINING_BACKUPS"] = "false"
        app, cls.replaced_modules = import_fresh_app()
        cls.client = TestClient(app, base_url="http://localhost:8000")
        cls.client.__enter__()
        from backend.app.db import get_db
        from backend.app.services import strava_upload

        cls.get_db = staticmethod(get_db)
        cls.upload = strava_upload

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        for key in ("TRAINING_DB_PATH", "STRAVA_AUTO_IMPORT", "TRAINING_BACKUPS"):
            os.environ.pop(key, None)
        restore_app_modules(cls.replaced_modules)
        cls.temp_dir.cleanup()

    def setUp(self):
        self.settings = {"strava_scope": "activity:read_all,activity:write,read"}
        self.start = datetime.now().astimezone().replace(microsecond=0) - timedelta(hours=2)

    def push_watch_workout(self, uuid, *, kind="WeightTraining", bundle="com.ronek22.trainlog", minutes=40):
        # Hours apart, so no push is taken for an earlier test's workout.
        self.start = self.start - timedelta(hours=3 * int(uuid[1:]))
        item = workout(uuid, self.start, kind=kind, minutes=minutes, distance_m=None, name="Workout", avg_hr=110)
        item["source_bundle"] = bundle
        item["streams"] = {"time": [1, 2, 3], "heartrate": [100, None, 112]}
        self.client.post("/integrations/health-workouts/push", json={"workouts": [item]})
        return f"healthkit:{uuid}"

    def link_strength(self, activity_id):
        conn = self.get_db()
        session_id = conn.execute(
            "INSERT INTO strength_workout_sessions (template_name, status, started_at, linked_activity_id) VALUES (?, 'completed', ?, ?)",
            ("Workout B", self.start.isoformat(), activity_id),
        ).lastrowid
        squat = conn.execute(
            "INSERT INTO strength_session_exercises (session_id, exercise_order, exercise_name) VALUES (?, 1, 'Back Squat')",
            (session_id,),
        ).lastrowid
        plank = conn.execute(
            "INSERT INTO strength_session_exercises (session_id, exercise_order, exercise_name) VALUES (?, 2, 'Plank')",
            (session_id,),
        ).lastrowid
        rows = [
            (squat, 1, 5, 80.0, 5, 82.5, "completed", None, None),
            (squat, 2, 5, 80.0, None, None, "pending", None, None),
            (plank, 1, 1, None, None, None, "completed", 45, 50),
        ]
        for exercise, order, target_reps, target_kg, reps, kg, status, target_s, actual_s in rows:
            conn.execute(
                """INSERT INTO strength_session_sets (session_exercise_id, set_order, target_reps, target_weight_kg,
                   actual_reps, actual_weight_kg, status, completed_at, target_seconds, actual_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (exercise, order, target_reps, target_kg, reps, kg, status,
                 self.start.isoformat() if status == "completed" else None, target_s, actual_s),
            )
        conn.commit()
        conn.close()

    def run_uploads(self, fake):
        conn = self.get_db()
        try:
            with patch.object(self.upload, "get_strava_access_token", return_value="token"):
                return self.upload.upload_watch_workouts(
                    conn, self.settings.get, self.settings.__setitem__, client=fake, sleep=lambda _: None
                )
        finally:
            conn.close()

    def test_maps_trainlog_exercise_names(self):
        names = {
            "Romanian Deadlift": "ROMANIAN_DEADLIFTS",
            "Hammer Curls": "DUMBBELL_HAMMER_CURL",
            "Push-ups": "PUSH_UP_GENERIC",
            "Pike push-ups": "PIKE_PUSH_UP",
            "Dumbbell Upright Row": "BARBELL_UPRIGHT_ROW",
            "Dumbbell Row": "DUMBBELL_ROW",
            "Barbell Incline Bench Press": "INCLINE_BARBELL_BENCH_PRESS",
            "Chair or sofa triceps dips": "CHAIR_DIPS",
            "Side plank (knees bent if needed)": "SIDE_PLANK",
            "Side-lying hip abduction": "SIDE_LYING_LEG_RAISE",
            "Hamstring and glute stretch (gentle)": "STANDING_HAMSTRING_STRETCH",
            "Sit-to-stand to a high chair": "AIR_SQUAT",
            "Something new": "TOTAL_BODY_GENERIC",
        }
        self.assertEqual({name: self.upload.exercise_type(name) for name in names}, names)

    def test_uploads_a_linked_strength_workout_with_sets_and_heart_rate(self):
        activity_id = self.push_watch_workout("a1")
        self.link_strength(activity_id)
        fake = FakeStrava({"id": 77, "activity_id": None, "error": None}, [{"id": 77, "activity_id": 9001, "error": None}])

        results = self.run_uploads(fake)

        self.assertEqual([result["status"] for result in results], ["uploaded"])
        sent = fake.posts[0]
        self.assertEqual(sent["data"]["sport_type"], "WeightTraining")
        self.assertEqual(sent["data"]["name"], "Workout B")
        self.assertEqual(sent["data"]["data_type"], "json")
        self.assertEqual(sent["file"]["sets"], [
            {"exercise_type": "BARBELL_BACK_SQUAT", "repetitions": 5, "weight": 82.5},
            {"exercise_type": "PLANK_GENERIC", "duration": 50},
        ])
        # Points without a reading are dropped (Strava wants every array as long as time), and the
        # first reading stands in for second 0.
        self.assertEqual(sent["file"]["streams"], {"time": [0, 1, 3], "heartrate": [100, 100, 112]})
        self.assertTrue(sent["file"]["start_time"].endswith("Z"))
        self.assertEqual(sent["file"]["utc_offset"], int(self.start.utcoffset().total_seconds()))
        self.assertEqual(sent["file"]["elapsed_time"], 40 * 60)
        conn = self.get_db()
        ref = conn.execute("SELECT activity_id FROM activity_source_refs WHERE source = 'strava' AND external_id = '9001'").fetchone()
        conn.close()
        self.assertEqual(ref["activity_id"], activity_id)
        # Sent once: the next run finds it on Strava.
        self.assertEqual(self.run_uploads(FakeStrava({})), [])

    def test_waits_for_the_upload_permission(self):
        activity_id = self.push_watch_workout("a2")
        self.link_strength(activity_id)
        self.settings["strava_scope"] = "activity:read_all,read"
        fake = FakeStrava({})
        self.assertEqual(self.run_uploads(fake), [])
        self.assertEqual(fake.posts, [])

    def test_skips_apple_workout_app_and_unlinked_workouts(self):
        self.link_strength(self.push_watch_workout("a3", bundle="com.apple.health.7F3A"))
        self.push_watch_workout("a4")  # TrainLog, but no session or rehab behind it yet
        fake = FakeStrava({})
        self.run_uploads(fake)
        self.assertEqual(fake.posts, [])

    def test_rehab_goes_up_as_a_workout_with_each_set(self):
        activity_id = self.push_watch_workout("a5", kind="Workout", minutes=27)
        routine = {
            "issues": ["Left outside of left knee, probably ITBS"],
            "exercises": [
                {"name": "Glute bridge", "sets": 2, "reps": 12},
                {"name": "Shallow wall sit isometric", "sets": 1, "seconds": 30},
            ],
        }
        conn = self.get_db()
        conn.execute("UPDATE sick_session_completions SET activity_id = NULL WHERE activity_id = ?", (activity_id,))
        conn.execute(
            """INSERT INTO sick_session_completions (date, session_key, started_at, elapsed_seconds, completed_steps,
               extras_json, session_json, activity_id) VALUES (?, 'rehab', ?, 1620, 3, '[]', ?, ?)""",
            (self.start.date().isoformat(), self.start.isoformat(), json.dumps(routine), activity_id),
        )
        conn.commit()
        conn.close()
        fake = FakeStrava({"id": 5, "activity_id": 9005, "error": None})

        self.run_uploads(fake)

        sent = fake.posts[0]
        self.assertEqual(sent["data"]["sport_type"], "Workout")
        self.assertIn("ITBS", sent["data"]["description"])
        self.assertEqual(sent["file"]["sets"], [
            {"exercise_type": "GLUTE_BRIDGE", "repetitions": 12},
            {"exercise_type": "GLUTE_BRIDGE", "repetitions": 12},
            {"exercise_type": "WALL_SIT", "duration": 30},
        ])

    def test_a_duplicate_links_the_activity_strava_already_has(self):
        activity_id = self.push_watch_workout("a6")
        self.link_strength(activity_id)
        error = "a1.json duplicate of <a href='/activities/9006' target='_blank'>Workout B</a>"
        fake = FakeStrava({"id": 6, "activity_id": None, "error": None}, [{"id": 6, "activity_id": None, "error": error}])

        results = self.run_uploads(fake)

        self.assertEqual(results[0]["status"], "duplicate")
        self.assertEqual(results[0]["strava_activity_id"], "9006")


if __name__ == "__main__":
    unittest.main()
