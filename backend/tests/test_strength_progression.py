import unittest
from unittest import mock

from backend.app.services import strength_progression


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
