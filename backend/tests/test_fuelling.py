import unittest

from backend.app.services.fuelling import build_fuel_plan


def ride(minutes=None, intent=None, workout=None, session_type="Ride"):
    return {"session_type": session_type, "target_duration_min": minutes, "workout_intent": intent, "cycling_workout_id": workout}


class FuelPlanTests(unittest.TestCase):
    def test_short_easy_ride_needs_no_plan(self):
        self.assertIsNone(build_fuel_plan(ride(75, "easy")))

    def test_recovery_ride_needs_no_plan(self):
        self.assertIsNone(build_fuel_plan(ride(150, "recovery")))

    def test_runs_and_strength_are_ignored(self):
        self.assertIsNone(build_fuel_plan(ride(150, "long", session_type="Run")))
        self.assertIsNone(build_fuel_plan(ride(60, None, session_type="WeightTraining")))

    def test_endurance_ride_uses_30_to_60_band(self):
        plan = build_fuel_plan(ride(120, "long"))
        self.assertEqual(plan["carbs_g_per_h"], {"low": 30, "high": 60, "target": 50})
        self.assertEqual(plan["total_carbs_g"], 100)
        self.assertEqual(plan["bottles"], 2)
        self.assertEqual(plan["hot_bottles"], 3)

    def test_long_endurance_ride_moves_to_top_of_band(self):
        self.assertEqual(build_fuel_plan(ride(240, "long"))["carbs_g_per_h"]["target"], 60)

    def test_hard_hour_gets_60_to_90_band(self):
        plan = build_fuel_plan(ride(60, "interval"))
        self.assertEqual(plan["carbs_g_per_h"], {"low": 60, "high": 90, "target": 60})
        self.assertEqual(plan["total_carbs_g"], 60)
        self.assertEqual(plan["bottles"], 1)

    def test_longer_hard_ride_targets_75(self):
        self.assertEqual(build_fuel_plan(ride(90, "tempo"))["carbs_g_per_h"]["target"], 75)

    def test_short_hard_ride_needs_no_plan(self):
        self.assertIsNone(build_fuel_plan(ride(45, "interval")))

    def test_library_workout_supplies_intent_and_duration(self):
        plan = build_fuel_plan(ride(workout="endurance-long-120"))
        self.assertEqual(plan["intent"], "long")
        self.assertGreaterEqual(plan["duration_min"], 110)

    def test_summary_mentions_hot_bottles_only_when_different(self):
        self.assertIn("if hot", build_fuel_plan(ride(120, "long"))["summary"])


if __name__ == "__main__":
    unittest.main()
