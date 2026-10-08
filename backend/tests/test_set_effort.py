import sqlite3
import unittest

from backend.app.services.set_effort import effort_carryover


def _db(sessions):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE strength_workout_sessions (id INTEGER PRIMARY KEY, started_at TEXT, status TEXT);
        CREATE TABLE strength_session_exercises (id INTEGER PRIMARY KEY, session_id INTEGER, exercise_name TEXT);
        CREATE TABLE strength_session_sets (
            id INTEGER PRIMARY KEY, session_exercise_id INTEGER, set_order INTEGER, actual_reps INTEGER,
            actual_weight_kg REAL, status TEXT, set_type TEXT, effort TEXT
        );
    """)
    for session_id, (started_at, status, exercises) in enumerate(sessions, start=1):
        conn.execute("INSERT INTO strength_workout_sessions VALUES (?, ?, ?)", (session_id, started_at, status))
        for name, sets in exercises.items():
            exercise_id = conn.execute(
                "INSERT INTO strength_session_exercises (session_id, exercise_name) VALUES (?, ?)", (session_id, name)
            ).lastrowid
            for order, (reps, weight, effort) in enumerate(sets, start=1):
                conn.execute(
                    "INSERT INTO strength_session_sets (session_exercise_id, set_order, actual_reps, actual_weight_kg, status, set_type, effort)"
                    " VALUES (?, ?, ?, ?, 'completed', 'working', ?)",
                    (exercise_id, order, reps, weight, effort),
                )
    return conn


class SetEffortCarryoverTests(unittest.TestCase):
    def test_grinding_last_time_says_repeat_the_load(self):
        conn = _db([("2026-10-08T18:00:00", "completed", {
            "Bent Over Barbell Row": [(8, 82.5, "grinding"), (6, 82.5, None), (6, 82.5, "grinding"), (5, 82.5, "solid")],
            "Hammer Curls": [(10, 16, "solid")],
        })])
        [note] = effort_carryover(conn, ["Bent Over Barbell Row", "Hammer Curls"])
        self.assertEqual((note["exercise_name"], note["effort"]), ("Bent Over Barbell Row", "grinding"))
        self.assertIn("2 of 3 rated sets at 82.5 kg", note["text"])

    def test_only_the_latest_completed_session_counts(self):
        conn = _db([
            ("2026-09-20T18:00:00", "completed", {"Dumbbell Row": [(11, 24, "form")]}),
            ("2026-10-01T18:00:00", "completed", {"dumbbell row": [(11, 24, "easy"), (11, 24, "easy")]}),
            ("2026-10-08T18:00:00", "active", {"Dumbbell Row": [(11, 26, "grinding")]}),
        ])
        [note] = effort_carryover(conn, ["Dumbbell Row"])
        self.assertEqual(note["effort"], "easy")
        self.assertIn("24 kg", note["text"])

    def test_form_breaks_rank_first_and_unrated_lifts_are_skipped(self):
        conn = _db([("2026-10-08T18:00:00", "completed", {
            "Chin Up": [(11, None, "grinding")],
            "Squat": [(8, 100, "form"), (8, 100, "solid")],
            "Curl": [(12, 14, None)],
        })])
        notes = effort_carryover(conn, ["Chin Up", "Squat", "Curl"])
        self.assertEqual([item["exercise_name"] for item in notes], ["Squat", "Chin Up"])
        self.assertIn("bodyweight", notes[1]["text"])


if __name__ == "__main__":
    unittest.main()
