import os
import sqlite3
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient


def import_fresh_app():
    for name in list(sys.modules):
        if name == "backend.app" or name.startswith("backend.app."):
            sys.modules.pop(name)
    import backend.app.main as main_module

    return main_module.app


class StrengthWorkoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "strength-workouts.db")
        cls.client = TestClient(import_fresh_app(), base_url="http://localhost:8000")
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        os.environ.pop("TRAINING_DB_PATH", None)
        cls.temp_dir.cleanup()

    def test_fitbod_history_drives_exercise_suggestions(self):
        conn = sqlite3.connect(os.environ["TRAINING_DB_PATH"])
        try:
            batch = conn.execute(
                """
                INSERT INTO fitbod_import_batches
                (file_name, file_hash, parser_version, grouping_version, imported_at)
                VALUES ('history.csv', 'suggestion-history', 'v1', 'v1', '2026-09-01T10:00:00')
                """
            )
            session = conn.execute(
                """
                INSERT INTO fitbod_workout_sessions
                (batch_id, session_key, workout_timestamp, workout_date, title)
                VALUES (?, 'lat-pulldown-session', '2026-08-28T18:00:00', '2026-08-28', 'Pull')
                """,
                (batch.lastrowid,),
            )
            exercise = conn.execute(
                """
                INSERT INTO fitbod_workout_exercises
                (session_id, exercise_order, exercise_name, set_count, rep_count, work_set_count)
                VALUES (?, 1, 'Lat Pulldown', 3, 30, 3)
                """,
                (session.lastrowid,),
            )
            for set_order, weight in enumerate((52.5, 55.0, 55.0), start=1):
                conn.execute(
                    """
                    INSERT INTO fitbod_workout_sets
                    (exercise_id, set_order, reps, weight_kg, is_warmup)
                    VALUES (?, ?, 10, ?, 0)
                    """,
                    (exercise.lastrowid, set_order, weight),
                )
            conn.commit()
        finally:
            conn.close()

        response = self.client.get(
            "/strength/workouts/exercise-suggestions?q=lat%20pull"
        )
        self.assertEqual(response.status_code, 200)
        suggestion = response.json()[0]
        self.assertEqual(suggestion["exercise_name"], "Lat Pulldown")
        self.assertEqual(suggestion["suggested_set_count"], 3)
        self.assertEqual(suggestion["suggested_reps"], 10)
        self.assertEqual(suggestion["suggested_weight_kg"], 55.0)
        self.assertEqual(suggestion["sources"], ["Fitbod"])

    def test_template_live_session_and_watch_activity_link(self):
        template_response = self.client.post(
            "/strength/workouts/templates",
            json={
                "name": "Back Quick",
                "notes": "Controlled reps",
                "exercises": [
                    {
                        "exercise_name": "Back Squat",
                        "set_count": 3,
                        "target_reps": 5,
                        "target_weight_kg": 80,
                        "rest_seconds": 120,
                    },
                    {
                        "exercise_name": "Pull Up",
                        "set_count": 2,
                        "target_reps": 8,
                        "target_weight_kg": None,
                        "rest_seconds": 90,
                    },
                ],
            },
        )
        self.assertEqual(template_response.status_code, 201)
        template = template_response.json()
        self.assertEqual(template["set_count"], 5)

        started_response = self.client.post(
            "/strength/workouts/sessions",
            json={"template_id": template["id"]},
        )
        self.assertEqual(started_response.status_code, 201)
        session = started_response.json()
        self.assertEqual(session["progress"], {"completed_sets": 0, "total_sets": 5, "fraction": 0})

        conflict = self.client.post(
            "/strength/workouts/sessions",
            json={"template_id": template["id"]},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["session_id"], session["id"])

        first_set = session["exercises"][0]["sets"][0]
        completed_response = self.client.post(
            f"/strength/workouts/sessions/{session['id']}/sets/{first_set['id']}/complete",
            json={"actual_reps": 5, "actual_weight_kg": 82.5},
        )
        self.assertEqual(completed_response.status_code, 200)
        completed = completed_response.json()
        self.assertEqual(completed["progress"]["completed_sets"], 1)
        self.assertEqual(completed["exercises"][0]["sets"][0]["actual_weight_kg"], 82.5)
        self.assertIsNotNone(completed["exercises"][0]["sets"][0]["rest_ends_at"])

        switched_response = self.client.post(
            f"/strength/workouts/sessions/{session['id']}/position",
            json={"exercise_order": 2},
        )
        self.assertEqual(switched_response.status_code, 200)
        self.assertEqual(switched_response.json()["current_exercise_order"], 2)

        added_response = self.client.post(
            f"/strength/workouts/sessions/{session['id']}/exercises",
            json={
                "exercise_name": "Overhead Press",
                "set_count": 3,
                "target_reps": 8,
                "target_weight_kg": 35,
                "rest_seconds": 90,
                "switch_to": True,
            },
        )
        self.assertEqual(added_response.status_code, 201)
        added = added_response.json()
        self.assertEqual(len(added["exercises"]), 3)
        self.assertEqual(added["exercises"][-1]["exercise_name"], "Overhead Press")
        self.assertEqual(len(added["exercises"][-1]["sets"]), 3)
        self.assertEqual(added["current_exercise_order"], 3)
        self.assertEqual(added["progress"]["total_sets"], 8)

        finished_response = self.client.post(
            f"/strength/workouts/sessions/{session['id']}/finish",
            json={},
        )
        self.assertEqual(finished_response.status_code, 200)
        self.assertEqual(finished_response.json()["status"], "completed")

        add_after_finish = self.client.post(
            f"/strength/workouts/sessions/{session['id']}/exercises",
            json={
                "exercise_name": "Too Late",
                "set_count": 1,
                "target_reps": 1,
                "rest_seconds": 0,
            },
        )
        self.assertEqual(add_after_finish.status_code, 409)

        activity_response = self.client.post(
            "/activities",
            json={
                "id": "apple-watch-strength-1",
                "date": finished_response.json()["started_at"][:10],
                "type": "WeightTraining",
                "name": "Traditional Strength Training",
                "duration_min": 52,
                "avg_hr": 126,
                "max_hr": 158,
                "calories": 390,
            },
        )
        self.assertEqual(activity_response.status_code, 201)

        candidates_response = self.client.get(
            f"/strength/workouts/sessions/{session['id']}/activity-candidates"
        )
        self.assertEqual(candidates_response.status_code, 200)
        self.assertEqual(candidates_response.json()[0]["id"], "apple-watch-strength-1")

        linked_response = self.client.put(
            f"/strength/workouts/sessions/{session['id']}/activity",
            json={"activity_id": "apple-watch-strength-1"},
        )
        self.assertEqual(linked_response.status_code, 200)
        self.assertEqual(linked_response.json()["linked_activity"]["avg_hr"], 126)
        self.assertEqual(linked_response.json()["linked_activity"]["calories"], 390)

        activities_response = self.client.get("/activities?type=WeightTraining")
        self.assertEqual(activities_response.status_code, 200)
        linked_activity = next(
            activity for activity in activities_response.json()
            if activity["id"] == "apple-watch-strength-1"
        )
        self.assertEqual(linked_activity["display_name"], "Back Quick")
        self.assertEqual(linked_activity["source_name"], "Traditional Strength Training")
        self.assertEqual(linked_activity["recorded_strength_session"]["id"], session["id"])

        overview_response = self.client.get("/strength/overview?weeks=4")
        self.assertEqual(overview_response.status_code, 200)
        overview = overview_response.json()
        self.assertEqual(overview["summary"]["session_count"], 1)
        self.assertEqual(overview["summary"]["total_sets"], 1)
        self.assertEqual(overview["summary"]["total_reps"], 5)
        self.assertEqual(overview["summary"]["total_volume_kg"], 412.5)
        self.assertEqual(overview["sessions"][0]["title"], "Back Quick")
        self.assertEqual(overview["sessions"][0]["source"], "trainlog")
        self.assertEqual(
            overview["sessions"][0]["matched_activity"]["id"],
            "apple-watch-strength-1",
        )

        detail_response = self.client.get("/activities/apple-watch-strength-1")
        self.assertEqual(detail_response.status_code, 200)
        strength_detail = detail_response.json()["strength_detail"]
        self.assertEqual(strength_detail["status"], "enriched")
        self.assertEqual(strength_detail["source"], "trainlog")
        self.assertEqual(strength_detail["session"]["exercise_count"], 1)
        self.assertEqual(strength_detail["session"]["set_count"], 1)
        self.assertEqual(strength_detail["session"]["rep_count"], 5)
        self.assertEqual(strength_detail["session"]["total_volume_kg"], 412.5)
        performed_set = strength_detail["session"]["exercises"][0]["sets"][0]
        self.assertEqual(performed_set["reps"], 5)
        self.assertEqual(performed_set["weight_kg"], 82.5)

        analysis_context_response = self.client.get(
            "/activities/apple-watch-strength-1/analysis/context"
        )
        self.assertEqual(analysis_context_response.status_code, 200)
        self.assertTrue(analysis_context_response.json()["available"])

        suggestions_response = self.client.get(
            "/strength/workouts/exercise-suggestions?q=back%20sq"
        )
        self.assertEqual(suggestions_response.status_code, 200)
        suggestions = suggestions_response.json()
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["exercise_name"], "Back Squat")
        self.assertEqual(suggestions[0]["suggested_set_count"], 1)
        self.assertEqual(suggestions[0]["suggested_reps"], 5)
        self.assertEqual(suggestions[0]["suggested_weight_kg"], 82.5)
        self.assertEqual(suggestions[0]["sources"], ["TrainLog"])

        disposable_response = self.client.post(
            "/strength/workouts/sessions",
            json={"template_id": template["id"]},
        )
        self.assertEqual(disposable_response.status_code, 201)
        disposable_id = disposable_response.json()["id"]

        abandoned_response = self.client.post(
            f"/strength/workouts/sessions/{disposable_id}/abandon"
        )
        self.assertEqual(abandoned_response.status_code, 204)
        self.assertEqual(
            self.client.get(f"/strength/workouts/sessions/{disposable_id}").status_code,
            404,
        )
        session_ids = {
            item["id"]
            for item in self.client.get("/strength/workouts/sessions").json()
        }
        self.assertNotIn(disposable_id, session_ids)

        deletable_response = self.client.post(
            "/strength/workouts/sessions",
            json={"template_id": template["id"]},
        )
        self.assertEqual(deletable_response.status_code, 201)
        deletable_id = deletable_response.json()["id"]
        finished_deletable = self.client.post(
            f"/strength/workouts/sessions/{deletable_id}/finish",
            json={},
        )
        self.assertEqual(finished_deletable.status_code, 200)

        deleted_response = self.client.delete(
            f"/strength/workouts/sessions/{deletable_id}"
        )
        self.assertEqual(deleted_response.status_code, 204)
        self.assertEqual(
            self.client.get(f"/strength/workouts/sessions/{deletable_id}").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
