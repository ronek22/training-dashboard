import os
import tempfile
import unittest
from datetime import date
from unittest import mock

from fastapi import HTTPException

from backend.app import db
from backend.app.models.strength_workouts import StrengthTemplateExerciseInput, StrengthTemplateInput
from backend.app.services import session_brief, stall_blocks, strength_plateaus, strength_progression, strength_workouts

TODAY = date(2026, 10, 12)


def _session(day, exercises):
    return {
        "workout_date": day,
        "workout_timestamp": f"{day}T18:00:00+00:00",
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": weight, "is_warmup": False} for reps, weight in sets]}
            for name, sets in exercises.items()
        ],
    }


# Upright row flat at 20 kg × 10 for a month: an isolation lift under 12 reps, so 3 × 12–15 a step lighter.
# Skullcrusher flat for 7 weeks: long enough for a variation.
HISTORY = [_session("2026-08-20", {"Dumbbell Skullcrusher": [(15, 14)] * 3})] + [
    _session(day, {"Dumbbell Upright Row": [(10, 20)] * 3, "Dumbbell Skullcrusher": [(15, 14)] * 3})
    for day in ("2026-09-10", "2026-09-24", "2026-10-06")
]


class StallBlockTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        path = os.path.join(self.temp_dir.name, "blocks.db")
        for target in (mock.patch.object(db, "DB_PATH", path),
                       mock.patch.object(strength_plateaus, "_session_index", return_value=HISTORY),
                       mock.patch.object(strength_progression, "_session_index", return_value=HISTORY),
                       mock.patch.object(strength_plateaus, "_max_dumbbell_kg", return_value=None),
                       mock.patch.object(strength_progression, "_max_dumbbell_kg", return_value=None),
                       mock.patch.object(strength_workouts, "_max_dumbbell_kg", return_value=None)):
            target.start()
            self.addCleanup(target.stop)
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        exercises = [
            StrengthTemplateExerciseInput(exercise_name=name, set_count=3, target_reps=reps, target_weight_kg=load, rest_seconds=90)
            for name, reps, load in (("Dumbbell Upright Row", 10, 20), ("Dumbbell Skullcrusher", 15, 14))
        ]
        self.template = strength_workouts.save_template(self.conn, StrengthTemplateInput(name="Workout C", exercises=exercises))

    def _template_lift(self, order):
        return strength_workouts.get_template(self.conn, self.template["id"])["exercises"][order]

    def test_block_rewrites_saved_workout_and_live_session_then_reverts(self):
        session = strength_workouts.start_session(self.conn, self.template["id"])
        self.assertEqual(session["exercises"][0]["sets"][0]["target_weight_kg"], 22, "normal progression before the block")

        block = stall_blocks.start_block(self.conn, "Dumbbell Upright Row", session["id"], today=TODAY)
        self.assertEqual((block["kind"], block["scope"], block["ends_on"], block["week"]), ("rep_scheme", "block", "2026-11-02", 1))
        self.assertEqual(block["stall"]["weeks"], 4)

        lift = self._template_lift(0)
        self.assertEqual((lift["set_count"], lift["target_reps"], lift["target_weight_kg"]), (3, 12, 18))
        self.assertIsNone(lift["next"], "stalled sessions before the block must not override its targets")
        self.assertIn("12–15 reps", lift["notes"])

        live = strength_workouts.get_session(self.conn, session["id"])["exercises"][0]["sets"]
        self.assertEqual([(item["target_reps"], item["target_weight_kg"]) for item in live], [(12, 18)] * 3)

        # One lift at a time.
        with self.assertRaises(HTTPException) as busy:
            stall_blocks.start_block(self.conn, "Dumbbell Skullcrusher", session["id"], today=TODAY)
        self.assertEqual(busy.exception.status_code, 409)
        plateaus = stall_blocks.annotate_plateaus(self.conn, strength_plateaus.find_plateaus(self.conn, TODAY), TODAY)
        self.assertEqual([(item["exercise_name"], item["queued_behind"]) for item in plateaus],
                         [("Dumbbell Skullcrusher", "Dumbbell Upright Row")])

        done = stall_blocks.finish_block(self.conn, block["id"], today=date(2026, 11, 2))
        self.assertEqual(done["status"], "reverted")
        self.assertEqual(done["outcome"]["e1rm_before"], block["stall"]["e1rm"])
        lift = self._template_lift(0)
        self.assertEqual((lift["target_reps"], lift["target_weight_kg"], lift["notes"]), (10, 20, None))

    def test_undo_restores_session_and_template(self):
        session = strength_workouts.start_session(self.conn, self.template["id"])
        block = stall_blocks.start_block(self.conn, "Dumbbell Upright Row", session["id"], today=TODAY)
        undone = stall_blocks.undo_block(self.conn, block["id"], today=TODAY)
        self.assertEqual(undone["status"], "undone")
        live = strength_workouts.get_session(self.conn, session["id"])["exercises"][0]
        self.assertEqual(live["exercise_name"], "Dumbbell Upright Row")
        self.assertEqual([(item["target_reps"], item["target_weight_kg"]) for item in live["sets"]], [(10, 22)] * 3)
        self.assertEqual(self._template_lift(0)["target_weight_kg"], 20)

    def test_variation_swaps_the_lift_and_keep_leaves_it(self):
        block = stall_blocks.start_block(self.conn, "Dumbbell Skullcrusher", today=TODAY)
        self.assertEqual(block["applied_name"], "Overhead Dumbbell Triceps Extension")
        self.assertEqual(self._template_lift(1)["exercise_name"], "Overhead Dumbbell Triceps Extension")
        kept = stall_blocks.finish_block(self.conn, block["id"], keep=True, today=date(2026, 11, 2))
        self.assertEqual(kept["status"], "kept")
        self.assertEqual(self._template_lift(1)["exercise_name"], "Overhead Dumbbell Triceps Extension")

    def test_today_only_changes_just_the_session_and_ends_with_it(self):
        session = strength_workouts.start_session(self.conn, self.template["id"])
        block = stall_blocks.start_block(self.conn, "Dumbbell Upright Row", session["id"], scope="today", today=TODAY)
        self.assertEqual(self._template_lift(0)["target_weight_kg"], 20)
        self.assertEqual(strength_workouts.get_session(self.conn, session["id"])["exercises"][0]["sets"][0]["target_weight_kg"], 18)
        self.assertEqual(stall_blocks.active_blocks(self.conn, TODAY), [], "a one-session change doesn't hold the slot")
        strength_workouts.finish_session(self.conn, session["id"])
        self.assertEqual(stall_blocks.list_blocks(self.conn, TODAY)[0]["status"], "done")
        self.assertEqual(stall_blocks.list_blocks(self.conn, TODAY)[0]["id"], block["id"])

    def test_running_block_has_a_week_headline(self):
        self.assertIsNone(stall_blocks.current_block(self.conn, TODAY))
        stall_blocks.start_block(self.conn, "Dumbbell Upright Row", today=TODAY)
        block = stall_blocks.current_block(self.conn, date(2026, 10, 20))
        self.assertEqual(block["headline"], "Dumbbell Upright Row stall block, week 2 of 3")
        self.assertIn("finish it", stall_blocks.current_block(self.conn, date(2026, 11, 2))["headline"])
        # The pre-session brief for a workout with that lift says so too.
        notes = session_brief._session_block_notes({"title": "Workout C"}, self.conn, date(2026, 10, 20))
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("Dumbbell Upright Row stall block, week 2 of 3. Rep scheme: Switch to 3 × 12–15"))

    def _stall_again(self, after_block):
        """Finish a 3-week rep-scheme block on the upright row, then stall again in December at ``after_block``."""
        block = stall_blocks.start_block(self.conn, "Dumbbell Upright Row", today=TODAY)
        stall_blocks.finish_block(self.conn, block["id"], today=date(2026, 11, 2))
        later = HISTORY + [_session(day, {"Dumbbell Upright Row": [after_block] * 3})
                           for day in ("2026-11-05", "2026-11-19", "2026-12-03")]
        with mock.patch.object(strength_plateaus, "_session_index", return_value=later):
            return strength_plateaus.find_plateaus(self.conn, date(2026, 12, 10), ["Dumbbell Upright Row"])[0]["suggestion"]

    def test_a_block_that_worked_is_suggested_again_with_its_result(self):
        suggestion = self._stall_again((10, 22))  # e1RM 29.3 vs 26.7 at the stall
        self.assertEqual(suggestion["kind"], "rep_scheme")
        self.assertFalse(suggestion["history"]["reranked"])
        self.assertEqual(suggestion["history"]["text"], "Last rep scheme block (12 Oct) added 2.6 kg to the estimated 1RM.")

    def test_a_block_that_did_not_work_gives_way_to_the_other_kind(self):
        suggestion = self._stall_again((10, 20.5))  # e1RM 27.3: under 1 kg past the stall
        self.assertEqual((suggestion["kind"], suggestion["label"]), ("variation", "Tempo"))
        self.assertTrue(suggestion["history"]["reranked"])
        self.assertEqual(suggestion["history"]["text"],
                         "Last rep scheme block (12 Oct) added only 0.6 kg to the estimated 1RM. Trying tempo instead.")

    def test_no_block_history_leaves_suggestions_unchanged(self):
        plateaus = strength_plateaus.find_plateaus(self.conn, TODAY)
        self.assertTrue(plateaus)
        self.assertTrue(all("history" not in item["suggestion"] for item in plateaus))
        self.assertEqual(stall_blocks.block_results(self.conn, TODAY), {})


if __name__ == "__main__":
    unittest.main()
