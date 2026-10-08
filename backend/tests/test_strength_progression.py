import unittest
from unittest import mock

from backend.app.services import strength_progression
from backend.app.services.strength_progression import max_load_for, next_step, plan_next_step


def _session(day, activity_id, exercises):
    return {
        "workout_date": day,
        "workout_timestamp": f"{day}T18:00:00+00:00",
        "title": f"Session {day}",
        "matched_activity": {"id": activity_id, "name": "Weight Training"} if activity_id else None,
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": weight, "is_warmup": warmup} for reps, weight, warmup in sets]}
            for name, sets in exercises.items()
        ],
    }


def _work(*pairs):
    return [(reps, weight, False) for reps, weight in pairs]


class StrengthProgressionTests(unittest.TestCase):
    def build(self, sessions, activity_id, targets=None):
        with mock.patch.object(strength_progression, "_session_index", return_value=sessions):
            return strength_progression.build_strength_progression(None, activity_id, targets)

    def test_compares_with_most_recent_prior_session_and_flags_pr(self):
        sessions = [
            _session("2026-09-01", "a1", {"Back Squat": _work((5, 80), (5, 80))}),
            _session("2026-09-08", "a2", {"Back Squat": _work((5, 70), (5, 70))}),
            _session("2026-09-15", "a3", {"Back Squat": [(10, 40, True), *_work((5, 85), (5, 85))]}),
        ]
        result = self.build(sessions, "a3")
        squat = result["exercises"]["backsquat"]
        self.assertEqual(squat["metric"], "e1rm")
        self.assertEqual(squat["previous"]["date"], "2026-09-08")
        self.assertEqual(squat["previous"]["activity_id"], "a2")
        self.assertEqual(squat["direction"], "up")
        self.assertTrue(squat["is_pr"])
        self.assertEqual(squat["best_before"], round(80 * (1 + 5 / 30), 1))
        self.assertEqual(result["pr_count"], 1)
        # Warm-ups never count toward the comparison.
        self.assertEqual(len(squat["current"]["sets"]), 2)

    def test_matched_session_suggests_load_increase_and_respects_targets(self):
        sessions = [
            _session("2026-09-01", "a1", {"Dumbbell Press": _work((8, 18), (8, 18))}),
            _session("2026-09-08", "a2", {"Dumbbell Press": _work((8, 18), (8, 18)), "Barbell Row": _work((8, 60), (6, 60))}),
        ]
        result = self.build(sessions, "a2", {"barbellrow": [8, 8]})
        press = result["exercises"]["dumbbellpress"]
        self.assertEqual(press["direction"], "same")
        self.assertFalse(press["is_pr"])
        self.assertIn("try 20 kg", press["next_hint"])
        row = result["exercises"]["barbellrow"]
        self.assertEqual(row["direction"], "first")
        self.assertIsNone(row["previous"])
        self.assertIn("until every set reaches 8 reps", row["next_hint"])

    def test_bodyweight_compares_reps_and_counts_extra_volume(self):
        sessions = [
            _session("2026-09-01", "a1", {"Hanging Leg Raise": _work((12, None), (12, None))}),
            _session("2026-09-08", "a2", {"Hanging Leg Raise": _work((12, None), (12, None), (12, None))}),
        ]
        raise_ = self.build(sessions, "a2")["exercises"]["hanginglegraise"]
        self.assertEqual(raise_["metric"], "reps")
        self.assertEqual(raise_["delta"], 0)
        self.assertEqual(raise_["direction"], "up")
        self.assertIn("aim for 13", raise_["next_hint"])

    def test_drop_recommends_repeating_load(self):
        sessions = [
            _session("2026-09-01", "a1", {"Bench Press": _work((5, 80), (5, 80))}),
            _session("2026-09-08", "a2", {"Bench Press": _work((5, 75), (4, 75))}),
        ]
        bench = self.build(sessions, "a2")["exercises"]["benchpress"]
        self.assertEqual(bench["direction"], "down")
        self.assertIn("repeat 75 kg", bench["next_hint"])

    def test_unlinked_activity_returns_none(self):
        self.assertIsNone(self.build([_session("2026-09-01", "a1", {"Squat": _work((5, 80))})], "missing"))


if __name__ == "__main__":
    unittest.main()


class NextStepTests(unittest.TestCase):
    def test_capped_dumbbell_progresses_reps_then_tempo(self):
        sets = [{"reps": 10, "weight_kg": 24.0}] * 3
        uncapped = next_step("Dumbbell Row", sets, None)
        self.assertEqual((uncapped["weight_kg"], uncapped["reps"]), (26.0, 10))
        capped = next_step("Dumbbell Row", sets, None, max_load_for("Dumbbell Row", 24))
        self.assertEqual((capped["weight_kg"], capped["reps"]), (24.0, 11))
        self.assertIn("heaviest dumbbell", capped["hint"])
        maxed = next_step("Dumbbell Row", [{"reps": 15, "weight_kg": 24.0}] * 3, None, 24.0)
        self.assertEqual((maxed["weight_kg"], maxed["reps"]), (24.0, 15))
        self.assertIn("3 seconds", maxed["hint"])

    def test_dumbbell_names_and_ramp_up_sets(self):
        self.assertEqual(max_load_for("Hammer Curls", 24), 24.0)
        self.assertIsNone(max_load_for("Bent Over Barbell Row", 24))
        self.assertEqual(next_step("Hammer Curls", [{"reps": 10, "weight_kg": 14.0}] * 3, None)["weight_kg"], 16.0)
        # An unflagged light warm-up must not block the load increase.
        sets = [{"reps": 40, "weight_kg": 40.0}] + [{"reps": 8, "weight_kg": 80.0}] * 3
        self.assertEqual(next_step("Bent Over Barbell Row", sets, None)["weight_kg"], 82.5)

    def test_plan_step_respects_saved_rep_target(self):
        lift = {"sets": [{"reps": 8, "weight_kg": 80.0}] * 3, "previous": None, "date": "2026-09-17"}
        step = plan_next_step(lift, "Bent Over Barbell Row", 10, None)
        self.assertEqual((step["target_weight_kg"], step["target_reps"]), (80.0, 10))
        self.assertIsNone(plan_next_step(None, "Bent Over Barbell Row", 10, None))
