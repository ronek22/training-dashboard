import unittest

from backend.app.models.plans import WeeklyPlanDay
from backend.app.services.bodyweight_lifts import lift_exercises, parse_step

COACH_STEPS = [
    "Warm up 5 min: arm circles, shoulder rolls, cat-cow and 10 slow scapular push-ups.",
    "Push-ups, 4 sets x 8-15 reps at 2 reps in reserve (hands on a table or sofa edge if too hard, feet on the floor).",
    "Pike push-ups, 3 sets x 6-10 reps for shoulders, hips high, head toward the floor between hands.",
    "Plank, 3 sets x 30-45 sec.",
    "Side plank, 3 sets x 20-30 sec per side (knees bent if needed).",
    "Dead bug, 3 sets x 10 per side, slow.",
    "Finish with a protein-rich meal.",
]


class BodyweightLiftTests(unittest.TestCase):
    def test_coach_steps_become_exercises_in_order(self):
        exercises = lift_exercises({"title": "Bodyweight upper + core", "steps": COACH_STEPS})
        self.assertEqual([item["name"] for item in exercises], ["Push-ups", "Pike push-ups", "Plank", "Side plank", "Dead bug"])
        push, pike, plank, side, bug = exercises
        self.assertEqual((push["sets"], push["reps"], push["seconds"]), (4, 12, None))
        self.assertTrue(push["notes"].startswith("At 2 reps in reserve"))
        self.assertEqual(pike["reps"], 8)
        self.assertEqual((plank["sets"], plank["reps"], plank["seconds"], plank["notes"]), (3, None, 40, None))
        self.assertEqual((side["seconds"], side["notes"]), (25, "Per side (knees bent if needed)"))
        self.assertEqual((bug["reps"], bug["notes"]), (10, "Per side, slow"))

    def test_structured_exercises_win_over_steps(self):
        day = {"title": "Bodyweight", "steps": COACH_STEPS, "exercises": [{"name": "Burpee", "sets": 5, "reps": 10, "rest_seconds": 30}]}
        self.assertEqual(lift_exercises(day), [
            {"name": "Burpee", "sets": 5, "reps": 10, "seconds": None, "weight_kg": None, "rest_seconds": 30, "notes": None},
        ])

    def test_unwritten_day_falls_back_to_stock_moves(self):
        names = [item["name"] for item in lift_exercises({"title": "Travel kit · Core"})]
        self.assertEqual(names[:2], ["Push Up", "Pike Push Up"])
        self.assertIn("Plank", names)

    def test_minutes_and_plain_counts(self):
        self.assertEqual(parse_step("Wall sit, 2 x 1 min")["seconds"], 60)
        self.assertEqual(parse_step("Squats, 3 x 15")["reps"], 15)
        self.assertIsNone(parse_step("Easy walk 20 min"))

    def test_plan_exercise_needs_reps_or_seconds(self):
        base = {"date": "2030-01-01", "label": "Tue", "title": "Bodyweight"}
        WeeklyPlanDay(**base, exercises=[{"name": "Plank", "sets": 3, "seconds": 40}])
        with self.assertRaises(ValueError):
            WeeklyPlanDay(**base, exercises=[{"name": "Plank", "sets": 3}])


if __name__ == "__main__":
    unittest.main()
