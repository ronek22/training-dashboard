import sqlite3
import unittest
from unittest import mock

from backend.app.services import exercise_history as history


def _session(day, exercises):
    return {
        "workout_date": day,
        "workout_timestamp": f"{day}T18:00:00+00:00",
        "exercises": [{"exercise_name": name, "sets": sets} for name, sets in exercises.items()],
    }


def _set(set_id, reps, weight=None, warmup=False):
    return {"id": set_id, "reps": reps, "weight_kg": weight, "is_warmup": warmup}


class ExerciseHistoryTests(unittest.TestCase):
    def run_history(self, sessions, name, limit=4, conn=None):
        with mock.patch.object(history, "_session_index", return_value=sessions):
            return history.exercise_history(conn, name, limit)

    def test_latest_sessions_first_without_warmups_and_best_ever(self):
        sessions = [
            _session("2026-09-02", {"Back Squat": [_set(1, 6, 80), _set(2, 6, 80)]}),
            _session("2026-09-10", {"Back Squat": [_set(3, 6, 60)], "Bench Press": [_set(4, 5, 60)]}),
            _session("2026-09-22", {"Back Squat": [_set(5, 10, 20, warmup=True), _set(6, 6, 75)]}),
            _session("2026-10-15", {"back squat": [_set(7, 6, 77.5), _set(8, 5, 77.5)]}),
        ]
        result = self.run_history(sessions, "Back Squat", limit=3)
        self.assertEqual(result["session_count"], 4)
        self.assertEqual([item["date"] for item in result["sessions"]], ["2026-10-15", "2026-09-22", "2026-09-10"])
        latest = result["sessions"][0]
        self.assertEqual(latest["top_load_kg"], 77.5)
        self.assertEqual(latest["best_reps"], 6)
        # Warm-ups never show.
        self.assertEqual(len(result["sessions"][1]["sets"]), 1)
        # The best set counts every session, not only the ones returned.
        self.assertEqual(result["best"], {"date": "2026-09-02", "weight_kg": 80, "reps": 6, "seconds": None})

    def test_bodyweight_best_is_most_reps_and_unknown_lift_is_empty(self):
        sessions = [
            _session("2026-10-01", {"Pull Up": [_set(1, 6), _set(2, 8)]}),
            _session("2026-10-08", {"Pull Up": [_set(3, 7)]}),
        ]
        result = self.run_history(sessions, "Pull Up")
        self.assertEqual(result["best"]["reps"], 8)
        self.assertIsNone(result["sessions"][0]["top_load_kg"])
        empty = self.run_history(sessions, "Front Lever")
        self.assertEqual(empty["sessions"], [])
        self.assertIsNone(empty["best"])

    def test_trainlog_sets_carry_effort_and_hold_seconds(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE strength_session_sets (id INTEGER PRIMARY KEY, effort TEXT, actual_seconds INTEGER)")
        conn.executemany("INSERT INTO strength_session_sets VALUES (?, ?, ?)", [(11, "solid", None), (12, None, 50)])
        sessions = [
            _session("2026-10-15", {"Back Squat": [_set(-11, 6, 77.5)], "Plank": [_set(-12, None)]}),
        ]
        squat = self.run_history(sessions, "Back Squat", conn=conn)
        self.assertEqual(squat["sessions"][0]["sets"][0]["effort"], "solid")
        plank = self.run_history(sessions, "Plank", conn=conn)
        self.assertEqual(plank["sessions"][0]["best_seconds"], 50)
        self.assertEqual(plank["best"]["seconds"], 50)


if __name__ == "__main__":
    unittest.main()
