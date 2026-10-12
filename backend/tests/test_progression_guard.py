import unittest
from collections import defaultdict
from datetime import date
from unittest import mock

from backend.app.services import progression_guard

TODAY = date(2026, 10, 14)


def _lift(day, load, reps=10, count=3):
    return {"date": day, "sets": [{"reps": reps, "weight_kg": load}] * count}


def _step(load, reps=10):
    return {"target_weight_kg": load, "target_reps": reps, "hint": "Add load."}


def _rating(day, finish=None, **counts):
    return {"date": day, "counts": defaultdict(int, counts), "total": sum(counts.values()), "finish_load": finish}


class ProgressionGuardTests(unittest.TestCase):
    def guard(self, names, lifts, steps, ratings=None, tagged=None):
        with mock.patch.object(progression_guard, "latest_ratings", return_value=ratings or {}), \
                mock.patch.object(progression_guard, "get_life_load_days", return_value=tagged or {}):
            return progression_guard.guard_steps(None, names, lifts, steps, TODAY)

    def test_grinding_or_broken_form_holds_or_goes_back_to_the_finishing_load(self):
        lifts = [_lift("2026-10-12", 16, 20, 5), _lift("2026-10-12", 22, 5)]
        ratings = {"dumbbelllateralraise": _rating("2026-10-12", finish=14, grinding=4, form=1),
                   "shoulderpress": _rating("2026-10-12", finish=22, grinding=2, solid=2)}
        lateral, press = self.guard(["Dumbbell Lateral Raise", "Shoulder Press"], lifts, [_step(16, 20), _step(24, 5)], ratings)
        self.assertEqual((lateral["target_weight_kg"], lateral["held"]), (14, "effort"))
        self.assertIn("Form broke", lateral["hint"])
        self.assertEqual((press["target_weight_kg"], press["held"]), (22, "effort"))

    def test_big_jump_waits_for_easy_sets_but_small_jumps_go(self):
        lifts = [_lift("2026-10-12", 14, 20), _lift("2026-10-12", 60, 8)]
        solid = {"lateral": _rating("2026-10-12", solid=4), "bench": _rating("2026-10-12", solid=4)}
        lateral, bench = self.guard(["Lateral", "Bench"], lifts, [_step(16, 20), _step(62.5, 8)], solid)
        self.assertEqual((lateral["target_weight_kg"], lateral["held"]), (14, "big_jump"))
        self.assertEqual(bench["target_weight_kg"], 62.5)
        [easy] = self.guard(["Lateral"], lifts[:1], [_step(16, 20)], {"lateral": _rating("2026-10-12", easy=3, solid=1)})
        self.assertEqual(easy["target_weight_kg"], 16)
        # Ratings from an older session than the latest history say nothing about it.
        [stale] = self.guard(["Lateral"], lifts[:1], [_step(16, 20)], {"lateral": _rating("2026-10-01", form=3)})
        self.assertEqual(stale["target_weight_kg"], 16)

    def test_at_most_two_lifts_go_up_and_easy_ones_first(self):
        names = ["A", "B", "C"]
        lifts = [_lift("2026-10-12", 60, 8)] * 3
        steps = [_step(62.5, 8)] * 3
        result = self.guard(names, lifts, steps, {"c": _rating("2026-10-12", easy=3)})
        self.assertEqual([item["target_weight_kg"] for item in result], [62.5, 60, 62.5])
        self.assertEqual(result[1]["held"], "one_change")

    def test_busy_day_holds_every_load(self):
        tagged = {TODAY.isoformat(): {"tags": ["deadline"], "labels": ["Deadline"]}}
        result = self.guard(["A"], [_lift("2026-10-12", 60, 8)], [_step(62.5, 8)], tagged=tagged)
        self.assertEqual((result[0]["target_weight_kg"], result[0]["held"]), (60, "life_load"))
        self.assertIn("Deadline today", result[0]["hint"])


if __name__ == "__main__":
    unittest.main()
