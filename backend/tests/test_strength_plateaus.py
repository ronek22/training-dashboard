import sqlite3
import unittest
from datetime import date
from unittest import mock

from backend.app.services import session_brief, strength_plateaus
from backend.app.services.strength_plateaus import find_plateaus

TODAY = date(2026, 10, 8)


def _session(day, exercises):
    return {
        "workout_date": day,
        "workout_timestamp": f"{day}T18:00:00+00:00",
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": weight, "is_warmup": False} for reps, weight in sets]}
            for name, sets in exercises.items()
        ],
    }


class StrengthPlateauTests(unittest.TestCase):
    def find(self, sessions, max_dumbbell_kg=None, names=None):
        with mock.patch.object(strength_plateaus, "_session_index", return_value=sessions), \
                mock.patch.object(strength_plateaus, "_max_dumbbell_kg", return_value=max_dumbbell_kg):
            return find_plateaus(None, TODAY, names)

    def test_flat_compound_gets_heavier_rep_scheme(self):
        sessions = [_session(day, {"Back Squat": [(8, 80), (8, 80)]}) for day in ("2026-09-10", "2026-09-20", "2026-10-01")]
        [plateau] = self.find(sessions)
        self.assertEqual((plateau["since"], plateau["weeks"], plateau["sessions"]), ("2026-09-10", 4, 3))
        self.assertEqual(plateau["suggestion"]["kind"], "rep_scheme")
        self.assertIn("4 × 5–6 at 85 kg", plateau["suggestion"]["text"])

    def test_progress_or_short_history_is_not_a_plateau(self):
        rising = [_session(day, {"Back Squat": [(8, load)]}) for day, load in (("2026-09-10", 80), ("2026-09-20", 80), ("2026-10-01", 82.5))]
        self.assertEqual(self.find(rising), [])
        recent = [_session(day, {"Back Squat": [(8, 80)]}) for day in ("2026-09-25", "2026-10-01", "2026-10-06")]
        self.assertEqual(self.find(recent), [], "best set under 3 weeks ago")
        # A break is not a plateau: the lift must still be trained.
        old = [_session(day, {"Back Squat": [(8, 80)]}) for day in ("2026-08-01", "2026-08-08", "2026-08-15")]
        self.assertEqual(self.find(old), [])

    def test_sliding_back_suggests_micro_deload_for_that_lift(self):
        sessions = [
            _session("2026-09-10", {"Bent Over Barbell Row": [(10, 80)]}),
            _session("2026-09-20", {"Bent Over Barbell Row": [(8, 80)]}),
            _session("2026-10-01", {"Bent Over Barbell Row": [(7, 80)]}),
        ]
        [plateau] = self.find(sessions)
        self.assertEqual(plateau["suggestion"]["kind"], "micro_deload")
        self.assertIn("72.5 kg × 7", plateau["suggestion"]["text"])

    def test_heaviest_dumbbell_gets_tempo_and_isolation_gets_higher_reps(self):
        sessions = [
            _session(day, {"Dumbbell Bench Press": [(10, 24)], "Dumbbell Lateral Raise": [(10, 10)]})
            for day in ("2026-09-10", "2026-09-20", "2026-10-01")
        ]
        plateaus = {item["exercise_name"]: item["suggestion"] for item in self.find(sessions, max_dumbbell_kg=24)}
        self.assertIn("lower every rep over 3 s", plateaus["Dumbbell Bench Press"]["text"])
        self.assertIn("3 × 12–15 at 8 kg", plateaus["Dumbbell Lateral Raise"]["text"])

    def test_long_stall_suggests_variation_and_extra_reps_count_as_movement(self):
        sessions = [_session(day, {"Back Squat": [(8, 80)]}) for day in ("2026-08-20", "2026-09-10", "2026-10-01")]
        [plateau] = self.find(sessions)
        self.assertEqual(plateau["suggestion"]["kind"], "variation")
        self.assertIn("paused back squats", plateau["suggestion"]["text"])
        # 15 reps at the same load is progress even past the usual e1RM rep cap.
        reps = [_session(day, {"Dumbbell Curl": [(r, 12)]}) for day, r in (("2026-09-10", 13), ("2026-09-20", 13), ("2026-10-01", 15))]
        self.assertEqual(self.find(reps), [])

    def test_limits_to_named_lifts_and_skips_bodyweight(self):
        sessions = [_session(day, {"Back Squat": [(8, 80)], "Pull Up": [(5, 10)]}) for day in ("2026-09-10", "2026-09-20", "2026-10-01")]
        self.assertEqual([item["exercise_name"] for item in self.find(sessions)], ["Back Squat"])
        self.assertEqual(self.find(sessions, names=["Romanian Deadlift"]), [])

    def test_strength_brief_shows_plateaus_for_todays_workout(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        conn.executescript(
            """
            CREATE TABLE strength_workout_templates (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE strength_template_exercises (id INTEGER PRIMARY KEY, template_id INTEGER, exercise_order INTEGER,
                exercise_name TEXT, set_count INTEGER, target_reps INTEGER, target_weight_kg REAL, rest_seconds INTEGER);
            INSERT INTO strength_workout_templates VALUES (1, 'Workout D');
            INSERT INTO strength_template_exercises VALUES (1, 1, 1, 'Back Squat', 3, 8, 80, 120);
            """
        )
        sessions = [_session(day, {"Back Squat": [(8, 80)]}) for day in ("2026-09-10", "2026-09-20", "2026-10-01")]
        with mock.patch.object(strength_plateaus, "_session_index", return_value=sessions), \
                mock.patch.object(strength_plateaus, "_max_dumbbell_kg", return_value=None):
            brief = session_brief.build_session_brief(
                conn, {"date": "2026-10-08", "session_type": "strength", "title": "Workout D"}, TODAY
            )
        self.assertEqual([item["exercise_name"] for item in brief["plateaus"]], ["Back Squat"])


if __name__ == "__main__":
    unittest.main()
