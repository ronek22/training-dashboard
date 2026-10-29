import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from fastapi import HTTPException

from backend.app import db
from backend.app.models.strength_workouts import StrengthTemplateExerciseInput, StrengthTemplateInput
from backend.app.services import strength_phases, strength_progression, strength_workouts

TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _session(day, exercises):
    return {
        "workout_date": day,
        "workout_timestamp": f"{day}T18:00:00+00:00",
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": weight, "is_warmup": False} for reps, weight in sets]}
            for name, sets in exercises.items()
        ],
    }


# Every target rep hit last time: both lifts would go up a step.
LAST = (TODAY - timedelta(days=3)).isoformat()
HISTORY = [_session(LAST, {"Back Squat": [(8, 60)] * 4, "Bench Press": [(8, 50)] * 3})]


class StrengthPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        path = os.path.join(self.temp_dir.name, "phases.db")
        for target in (mock.patch.object(db, "DB_PATH", path),
                       mock.patch.object(strength_progression, "_session_index", return_value=HISTORY),
                       mock.patch.object(strength_workouts, "_max_dumbbell_kg", return_value=None)):
            target.start()
            self.addCleanup(target.stop)
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        exercises = [
            StrengthTemplateExerciseInput(exercise_name=name, set_count=sets, target_reps=8, target_weight_kg=load, rest_seconds=90)
            for name, sets, load in (("Back Squat", 4, 60), ("Bench Press", 3, 50))
        ]
        self.template = strength_workouts.save_template(self.conn, StrengthTemplateInput(name="Workout A", exercises=exercises))

    def _start(self):
        session = strength_workouts.start_session(self.conn, self.template["id"])
        self.addCleanup(lambda: strength_workouts.delete_session(self.conn, session["id"]))
        return [(item["exercise_name"], len([s for s in item["sets"] if s["set_type"] == "working"]),
                 item["sets"][0]["target_weight_kg"]) for item in session["exercises"]]

    def _phase(self, kind, start=MONDAY, days=6):
        return strength_phases.save_phase(self.conn, kind, start, start + timedelta(days=days))

    def test_no_phase_changes_nothing(self):
        self.assertIsNone(strength_phases.current_phase(self.conn))
        self.assertEqual(self._start(), [("Back Squat", 4, 62.5), ("Bench Press", 3, 52.5)])

    def test_deload_trims_sets_on_the_same_lifts_and_holds_load(self):
        self._phase("deload")
        self.assertEqual(self._start(), [("Back Squat", 2, 60), ("Bench Press", 2, 50)])
        squat = strength_workouts.get_template(self.conn, self.template["id"])["exercises"][0]
        self.assertEqual((squat["set_count"], squat["next"]["held"]), (4, "phase"), "the saved workout keeps its sets")
        self.assertIn("Deload week", squat["next"]["hint"])

    def test_template_next_step_carries_last_top_set(self):
        squat = strength_workouts.get_template(self.conn, self.template["id"])["exercises"][0]
        self.assertEqual(squat["next"]["last"], {"date": LAST, "weight_kg": 60.0, "reps": 8, "set_count": 4})

    def test_hold_pauses_load_jumps_but_keeps_sets(self):
        self._phase("hold", days=20)
        self.assertEqual(self._start(), [("Back Squat", 4, 60), ("Bench Press", 3, 50)])

    def test_volume_is_a_label_only(self):
        self._phase("volume", days=20)
        self.assertEqual(self._start(), [("Back Squat", 4, 62.5), ("Bench Press", 3, 52.5)])
        self.assertIn("Volume", strength_phases.current_phase(self.conn)["headline"])

    def test_past_or_future_phase_is_off_today(self):
        self._phase("deload", start=MONDAY + timedelta(weeks=1))
        self.assertEqual(self._start(), [("Back Squat", 4, 62.5), ("Bench Press", 3, 52.5)])

    def test_deload_sets_never_drop_a_lift(self):
        self.assertEqual([strength_phases.deload_sets(n) for n in (1, 2, 3, 4, 5)], [1, 1, 2, 2, 3])

    def test_suggestions_follow_arc_lighter_weeks_until_confirmed(self):
        start = MONDAY - timedelta(weeks=1)
        self.conn.execute(
            "INSERT INTO winter_arc_blocks (start_date, end_date, focus, label, weekly_hours, ride_mix_json, lighter_every) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (start.isoformat(), (start + timedelta(weeks=8, days=-1)).isoformat(), "base", "Base 1", 6, json.dumps({"z2": 3}), 3),
        )
        self.conn.commit()
        found = strength_phases.suggestions(self.conn)
        self.assertEqual([item["start_date"] for item in found],
                         [(start + timedelta(weeks=2)).isoformat(), (start + timedelta(weeks=5)).isoformat()])
        self.assertEqual(found[0]["kind"], "deload")
        self.assertEqual(strength_phases.list_phases(self.conn), [], "suggesting saves nothing")

        first = found[0]
        strength_phases.save_phase(self.conn, "deload", date.fromisoformat(first["start_date"]),
                                   date.fromisoformat(first["end_date"]), source=first["source"])
        self.assertEqual(len(strength_phases.suggestions(self.conn)), 1)

    def test_overlaps_and_long_deloads_are_refused(self):
        phase = self._phase("hold", days=13)
        with self.assertRaises(HTTPException) as overlap:
            self._phase("deload", start=MONDAY + timedelta(weeks=1))
        self.assertEqual(overlap.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            self._phase("deload", start=MONDAY + timedelta(weeks=3), days=20)
        strength_phases.delete_phase(self.conn, phase["id"])
        self.assertEqual(strength_phases.list_phases(self.conn), [])


if __name__ == "__main__":
    unittest.main()
