import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WeeklyPlanSwap
from backend.app.services.lift_ride_clash import (
    best_swap,
    find_clashes,
    is_hard_ride,
    is_lower_lift,
    plan_clashes,
    resolve_clashes,
)
from backend.app.services.plans import swap_weekly_plan_days_data, upsert_weekly_plan_data

WEEK = "2030-01-07"  # A Monday in the future, so no day is locked as past.
DATES = ["2030-01-07", "2030-01-08", "2030-01-09", "2030-01-10", "2030-01-11", "2030-01-12", "2030-01-13"]
LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def week(*sessions):
    """Seven plan days from (session_type, intent, title) tuples, Monday first."""
    return [
        {"date": DATES[index], "label": LABELS[index], "session_type": kind, "workout_intent": intent, "title": title}
        for index, (kind, intent, title) in enumerate(sessions)
    ]


REST = ("Rest", None, "Rest")
LEGS = ("WeightTraining", "strength_lower", "Legs")
UPPER = ("WeightTraining", "strength_upper", "Upper")
SWEET = ("Ride", "tempo", "Sweet spot 2 × 20")
VO2 = ("Ride", "interval", "VO2 5 × 3")
Z2 = ("Ride", "easy", "Z2 ride")


class ClashDetectionTests(unittest.TestCase):
    def test_hard_rides_and_leg_lifts_are_recognised(self):
        self.assertTrue(is_hard_ride({"session_type": "Ride", "workout_intent": "tempo"}))
        self.assertTrue(is_hard_ride({"session_type": "VirtualRide", "workout_intent": "interval"}))
        self.assertTrue(is_hard_ride({"session_type": "Ride", "cycling_workout_id": "threshold-4x8"}))
        self.assertFalse(is_hard_ride({"session_type": "Ride", "workout_intent": "easy"}))
        self.assertFalse(is_hard_ride({"session_type": "Ride", "cycling_workout_id": "endurance-60", "workout_intent": "tempo"}))
        self.assertFalse(is_hard_ride({"session_type": "Run", "workout_intent": "interval"}))
        self.assertTrue(is_lower_lift({"session_type": "WeightTraining", "workout_intent": "strength_lower"}))
        self.assertFalse(is_lower_lift({"session_type": "WeightTraining", "workout_intent": "strength_upper"}, lambda day: True))
        self.assertTrue(is_lower_lift({"session_type": "WeightTraining", "workout_intent": "strength_general"}, lambda day: True))

    def test_lift_before_and_after_a_hard_ride_both_clash(self):
        clashes = find_clashes(week(LEGS, SWEET, LEGS, REST, REST, REST, REST))
        self.assertEqual(
            [(item["lift_date"], item["ride_date"], item["order"]) for item in clashes],
            [("2030-01-07", "2030-01-08", "lift_first"), ("2030-01-09", "2030-01-08", "ride_first")],
        )
        self.assertEqual(clashes[0]["lift_title"], "Legs")
        self.assertEqual(clashes[0]["ride_title"], "Sweet spot 2 × 20")

    def test_upper_lifts_and_easy_rides_never_clash(self):
        self.assertEqual(find_clashes(week(UPPER, VO2, UPPER, REST, REST, REST, REST)), [])
        self.assertEqual(find_clashes(week(LEGS, Z2, LEGS, ("Ride", "recovery", "Spin"), LEGS, REST, REST)), [])
        self.assertEqual(find_clashes(week(LEGS, REST, VO2, REST, LEGS, REST, REST)), [])


class ClashSwapTests(unittest.TestCase):
    def test_best_swap_moves_the_lift_to_a_clean_day(self):
        days = week(REST, LEGS, VO2, REST, REST, REST, REST)
        swap = best_swap(days, find_clashes(days)[0])
        self.assertEqual(swap, {"from_date": "2030-01-08", "to_date": "2030-01-07"})

    def test_best_swap_skips_locked_days_and_moves_the_ride_if_needed(self):
        days = week(REST, LEGS, VO2, REST, REST, REST, REST)
        swap = best_swap(days, find_clashes(days)[0], locked=["2030-01-07", "2030-01-08"])
        self.assertEqual(swap["from_date"], "2030-01-09")
        self.assertNotIn(swap["to_date"], ("2030-01-07", "2030-01-08"))
        locked_but_pair = [value for value in DATES if value not in ("2030-01-08", "2030-01-09")]
        self.assertIsNone(best_swap(days, find_clashes(days)[0], locked=locked_but_pair))

    def test_best_swap_leaves_the_pinned_session_in_place(self):
        days = week(REST, LEGS, VO2, REST, REST, REST, REST)
        swap = best_swap(days, find_clashes(days)[0], pinned=["2030-01-08"])
        self.assertEqual(swap["from_date"], "2030-01-09")

    def test_resolve_clears_every_clash_when_possible(self):
        days = week(LEGS, SWEET, REST, LEGS, VO2, REST, Z2)
        resolved, swaps = resolve_clashes(days)
        self.assertTrue(swaps)
        self.assertEqual(find_clashes(resolved), [])
        self.assertEqual(sorted(day["title"] for day in resolved), sorted(day["title"] for day in days))
        moved = [day for day in resolved if day["title"] == "Legs" and day.get("planning_rule_reason")]
        self.assertTrue(moved)

    def test_resolve_reduces_but_cannot_clear_a_packed_week(self):
        days = week(VO2, LEGS, VO2, LEGS, VO2, LEGS, VO2)
        resolved, swaps = resolve_clashes(days)
        self.assertTrue(swaps)
        self.assertLess(len(find_clashes(resolved)), len(find_clashes(days)))
        self.assertTrue(find_clashes(resolved))


class ClashPlanFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def stored_days(self):
        return json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])

    def save(self, days):
        return upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=WEEK, title="Test", days=[WeeklyPlanDay(**day) for day in days]))

    def test_generated_plan_is_saved_without_a_clash(self):
        result = self.save(week(REST, LEGS, SWEET, REST, Z2, UPPER, REST))
        self.assertTrue(result["clash_swaps"])
        self.assertEqual(find_clashes(self.stored_days()), [])

    def test_moving_a_lift_into_a_clash_is_allowed_and_warned_with_a_swap(self):
        self.save(week(LEGS, REST, REST, SWEET, REST, Z2, REST))
        result = swap_weekly_plan_days_data(self.conn, WeeklyPlanSwap(from_date="2030-01-07", to_date="2030-01-09"))
        self.assertEqual(self.stored_days()[2]["title"], "Legs")
        self.assertEqual(len(result["clashes"]), 1)
        clash = result["clashes"][0]
        self.assertEqual((clash["lift_title"], clash["ride_title"]), ("Legs", "Sweet spot 2 × 20"))
        swap = clash["suggested_swap"]
        self.assertEqual(swap["from_date"], "2030-01-10")  # the ride moves, the lift stays where it was put
        swap_weekly_plan_days_data(self.conn, WeeklyPlanSwap(**swap))
        self.assertEqual(find_clashes(self.stored_days()), [])
        self.assertEqual(result["plan"]["lift_ride_clashes"][0]["lift_date"], "2030-01-09")

    def test_upper_lift_move_next_to_a_hard_ride_is_not_warned(self):
        self.save(week(UPPER, REST, REST, VO2, REST, REST, REST))
        result = swap_weekly_plan_days_data(self.conn, WeeklyPlanSwap(from_date="2030-01-07", to_date="2030-01-09"))
        self.assertEqual(result["clashes"], [])


if __name__ == "__main__":
    unittest.main()
