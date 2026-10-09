import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from backend.app.services import strength_volume
from backend.app.services.strength_volume import apply_lift_volume, build_lift_volume

WEEK_START = "2026-10-05"
TODAY = date(2026, 10, 8)

TEMPLATES = {
    "Workout A": [("Barbell Incline Bench Press", 4, 8, 70.0), ("Dumbbell Bench Press", 3, 10, 24.0), ("Pull Up", 3, 10, None), ("Dumbbell Lateral Raise", 4, 15, 12.0), ("Dumbbell Bicep Curl", 3, 10, 14.0)],
    "Workout B": [("Chin Up", 4, 10, None), ("Bent Over Barbell Row", 4, 8, 80.0), ("Dumbbell Row", 3, 10, 24.0), ("Hammer Curls", 3, 10, 16.0), ("Dumbbell Rear Delt Raise", 4, 12, 12.0)],
    "Workout C": [("Standing Dumbbell Shoulder Press", 3, 8, 18.0), ("Dumbbell Lateral Raise", 5, 20, 12.0), ("Dumbbell Skullcrusher", 3, 10, 14.0)],
    "Workout D": [("Back Squat", 3, 6, 75.0), ("Romanian Deadlift", 3, 8, 75.0), ("Dumbbell Bulgarian Split Squat", 3, 8, 14.0), ("Standing Dumbbell Calf Raise", 3, 15, 24.0)],
}


def _day(day, template, title=None):
    return {"date": day, "session_type": "strength", "title": title or template, "template_label": template}


class LiftVolumeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE strength_workout_templates (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE strength_template_exercises (
                id INTEGER PRIMARY KEY, template_id INTEGER, exercise_order INTEGER, exercise_name TEXT,
                set_count INTEGER, target_reps INTEGER, target_weight_kg REAL, rest_seconds INTEGER DEFAULT 90
            );
            """
        )
        for template_id, (name, exercises) in enumerate(TEMPLATES.items(), start=1):
            self.conn.execute("INSERT INTO strength_workout_templates VALUES (?, ?)", (template_id, name))
            for order, (exercise, sets, reps, kg) in enumerate(exercises, start=1):
                self.conn.execute(
                    "INSERT INTO strength_template_exercises (template_id, exercise_order, exercise_name, set_count, target_reps, target_weight_kg) VALUES (?, ?, ?, ?, ?, ?)",
                    (template_id, order, exercise, sets, reps, kg),
                )
        self.sessions = []
        self.sick = set()
        self.returning = set()
        self.mountains = set()
        self.patches = [
            patch.object(strength_volume, "_session_index", lambda conn: self.sessions),
            patch.object(strength_volume, "latest_next_steps", lambda conn: {}),
            patch.object(strength_volume, "_max_dumbbell_kg", lambda conn: None),
            patch.object(strength_volume, "sick_dates", lambda conn: self.sick),
            patch.object(strength_volume, "illness_return_dates", lambda conn, today=None: self.returning),
            patch.object(strength_volume, "mountain_dates", lambda conn, start, end: self.mountains),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.conn.close()

    def _build(self, days, **kwargs):
        return build_lift_volume(self.conn, days, WEEK_START, today=TODAY, **kwargs)

    def _group(self, volume, key):
        return next(group for group in volume["groups"] if group["key"] == key)

    def _additions(self, volume, day):
        return next(row for row in volume["days"] if row["date"] == day)["additions"]

    def test_brings_every_main_group_to_target_without_cutting_days(self):
        days = [_day("2026-10-08", "Workout A"), _day("2026-10-09", "Workout B"), _day("2026-10-10", "Workout C")]
        volume = self._build(days)

        for key in ("legs", "back", "chest", "shoulders", "arms"):
            self.assertGreaterEqual(self._group(volume, key)["total_sets"], 8, key)
        self.assertEqual(self._group(volume, "legs")["added_sets"], 8)
        self.assertEqual(len(volume["days"]), 3)
        # Legs spread over the three days, never more than the per-day cap.
        for row in volume["days"]:
            self.assertLessEqual(sum(item["sets"] for item in row["additions"]), strength_volume.MAX_ADDED_SETS_PER_DAY)
        legs_per_day = [sum(item["sets"] for item in row["additions"] if item["group"] == "legs") for row in volume["days"]]
        self.assertEqual(sorted(legs_per_day), [2, 3, 3])

    def test_protected_knee_keeps_split_squats_out_of_the_top_up(self):
        days = [_day("2026-10-08", "Workout A"), _day("2026-10-09", "Workout B"), _day("2026-10-10", "Workout C")]
        restrictions = {"body_areas": [{"area": "knee", "side": "left", "summary_label": "left knee"}]}
        with patch.object(strength_volume, "get_modality_restrictions_for_conn", lambda conn: restrictions):
            volume = self._build(days)

        added = [item["exercise_name"] for row in volume["days"] for item in row["additions"]]
        self.assertNotIn("Dumbbell Bulgarian Split Squat", added)
        self.assertIn("Romanian Deadlift", added)
        self.assertIn("Dumbbell Bulgarian Split Squat", volume["skipped_for_protection"])
        self.assertEqual(volume["protected_areas"], ["left knee"])
        self.assertIn("left out lifts that load your left knee", volume["summary"].lower())

    def test_small_gap_extends_the_lightest_matching_lift_on_a_day_that_trains_it(self):
        days = [_day("2026-10-08", "Workout B"), _day("2026-10-10", "Workout A"), _day("2026-10-11", "Workout D")]
        volume = self._build(days)

        self.assertEqual(self._group(volume, "chest")["planned_sets"], 7)
        self.assertEqual(
            [item for item in self._additions(volume, "2026-10-10") if item["group"] == "chest"],
            [{"exercise_name": "Dumbbell Bench Press", "group": "chest", "sets": 1, "mode": "extend", "reason": "Brings chest toward 8 hard sets this week"}],
        )

    def test_new_accessory_carries_targets_from_saved_workouts(self):
        volume = self._build([_day("2026-10-08", "Workout A"), _day("2026-10-10", "Workout B")])
        split_squat = next(item for row in volume["days"] for item in row["additions"] if item["exercise_name"] == "Dumbbell Bulgarian Split Squat")
        self.assertEqual((split_squat["mode"], split_squat["target_reps"], split_squat["target_weight_kg"]), ("add", 8, 14.0))

    def test_logged_sets_count_and_done_or_missed_days_get_nothing(self):
        self.sessions.append(
            {
                "workout_date": "2026-10-06",
                "exercises": [{"exercise_name": "Back Squat", "sets": [{"reps": 6, "weight_kg": 75, "is_warmup": False}] * 5 + [{"reps": 5, "weight_kg": 40, "is_warmup": True}]}],
            }
        )
        days = [_day("2026-10-05", "Workout C"), _day("2026-10-06", "Workout D"), _day("2026-10-08", "Workout A"), _day("2026-10-10", "Workout B")]
        volume = self._build(days)

        legs = self._group(volume, "legs")
        self.assertEqual((legs["done_sets"], legs["added_sets"]), (5, 3))
        states = {row["date"]: row["state"] for row in volume["days"]}
        self.assertEqual(states, {"2026-10-05": "missed", "2026-10-06": "done", "2026-10-08": "planned", "2026-10-10": "planned"})
        self.assertEqual(self._additions(volume, "2026-10-05") + self._additions(volume, "2026-10-06"), [])

    def test_light_days_and_minimum_weeks_get_no_extra_sets(self):
        days = [_day("2026-10-08", "Workout A", title="Light Workout A"), _day("2026-10-10", "Workout B")]
        volume = self._build(days)
        self.assertEqual(self._additions(volume, "2026-10-08"), [])
        self.assertTrue(self._additions(volume, "2026-10-10"))

        minimum = self._build(days, minimum_week_active=True)
        self.assertEqual(minimum["added_sets"], 0)
        self.assertEqual(minimum["summary"], "Minimum week: no extra sets added.")

    def test_return_from_illness_days_get_no_extra_sets(self):
        self.returning = {"2026-10-08", "2026-10-09", "2026-10-10"}
        days = [_day("2026-10-08", "Workout A"), _day("2026-10-09", "Workout B"), _day("2026-10-10", "Workout C")]
        volume = self._build(days)

        self.assertEqual(volume["added_sets"], 0)
        self.assertEqual({row["state"] for row in volume["days"]}, {"light"})

    def test_mountain_trip_lifts_stay_bare_and_hiking_covers_legs(self):
        self.mountains = {"2026-10-08", "2026-10-09"}
        days = [
            _day("2026-10-08", None, "Travel kit · Upper body"),
            _day("2026-10-09", None, "Travel kit · Upper body"),
            _day("2026-10-10", "Workout C"),
        ]
        volume = self._build(days)

        legs = self._group(volume, "legs")
        self.assertEqual((legs["status"], legs["shortfall"], legs["added_sets"]), ("hiking", 0, 0))
        self.assertTrue(volume["hiking_covers_legs"])
        self.assertIn("Hiking covers legs", volume["summary"])
        self.assertEqual(self._additions(volume, "2026-10-08"), [])
        self.assertEqual(self._additions(volume, "2026-10-09"), [])

    def test_reports_shortfall_when_no_lift_days_remain(self):
        volume = build_lift_volume(self.conn, [_day("2026-10-06", "Workout A")], WEEK_START, today=TODAY)
        self.assertEqual(self._group(volume, "legs")["shortfall"], 8)
        self.assertIn("Still short", volume["summary"])

    def test_past_weeks_and_weeks_without_lifts_are_skipped(self):
        self.assertIsNone(build_lift_volume(self.conn, [_day("2026-09-30", "Workout A")], "2026-09-28", today=TODAY))
        self.assertIsNone(self._build([{"date": "2026-10-08", "session_type": "run"}]))

    def test_apply_attaches_additions_to_lift_days_only(self):
        days = [_day("2026-10-08", "Workout A"), {"date": "2026-10-09", "session_type": "run"}]
        applied = apply_lift_volume(days, self._build(days))
        self.assertTrue(applied[0]["lift_volume_additions"])
        self.assertNotIn("lift_volume_additions", applied[1])


if __name__ == "__main__":
    unittest.main()
