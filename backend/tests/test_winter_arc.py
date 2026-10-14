import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from fastapi import HTTPException

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WinterArc
from backend.app.services.life_load import set_life_load_day
from backend.app.services.plans import list_weekly_plans_data, upsert_weekly_plan_data
from backend.app.services.winter_arc import (
    build_winter_arc,
    clear_winter_arc,
    planned_mix,
    save_winter_arc,
    winter_arc_coaching_context,
)

TODAY = date(2029, 12, 1)  # Before the arc starts; plan weeks are in the future, so none is locked.
DATES = ["2030-01-07", "2030-01-08", "2030-01-09", "2030-01-10", "2030-01-11", "2030-01-12", "2030-01-13"]
LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REST = ("Rest", None, "Rest", None)
LIFT = ("WeightTraining", "strength_upper", "Upper", 50)
Z2 = ("Ride", "easy", "Z2 ride", 75)
LONG = ("Ride", "long", "Long ride", 150)

ARC = {
    "blocks": [
        {"start_date": "2029-12-03", "end_date": "2029-12-30", "focus": "base", "weekly_hours": 6,
         "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 4},
        # 2030-01-07 is week 2 of this block, 2030-01-13's week (01-14) is week 3 = lighter.
        {"start_date": "2029-12-31", "end_date": "2030-02-10", "focus": "sweet_spot", "weekly_hours": 6,
         "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 0}, "lighter_every": 3},
    ]
}


def week(*sessions, dates=DATES):
    return [
        {"date": dates[i], "label": LABELS[i], "session_type": kind, "workout_intent": intent, "title": title, "target_duration_min": minutes}
        for i, (kind, intent, title, minutes) in enumerate(sessions)
    ]


class WinterArcTests(unittest.TestCase):
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

    def save_arc(self, arc=ARC):
        return save_winter_arc(self.conn, WinterArc(**arc), TODAY)

    def save_week(self, days, week_start=DATES[0]):
        result = upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=week_start, title="Test", days=[WeeklyPlanDay(**day) for day in days]))
        stored = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()[0])
        return result, stored

    def test_create_edit_and_clear(self):
        arc = self.save_arc()
        self.assertEqual([block["focus"] for block in arc["blocks"]], ["base", "sweet_spot"])
        self.assertEqual(arc["blocks"][1]["weeks"], 6)
        self.assertEqual(arc["blocks"][1]["lighter_weeks"], ["2030-01-14", "2030-02-04"])
        self.assertEqual(arc["blocks"][1]["key_types"], ["sweet_spot"])
        self.assertEqual(arc["status"], "upcoming")

        edited = {"blocks": [dict(ARC["blocks"][0], label="Winter base", weekly_hours=5)]}
        arc = self.save_arc(edited)
        self.assertEqual(len(arc["blocks"]), 1)
        self.assertEqual((arc["blocks"][0]["label"], arc["blocks"][0]["weekly_hours"]), ("Winter base", 5.0))

        self.assertEqual(clear_winter_arc(self.conn, TODAY)["blocks"], [])

    def test_invalid_blocks_are_rejected(self):
        bad_day = {"blocks": [dict(ARC["blocks"][0], start_date="2029-12-04")]}
        overlap = {"blocks": [ARC["blocks"][0], dict(ARC["blocks"][1], start_date="2029-12-24")]}
        for arc in (bad_day, overlap):
            with self.assertRaises(HTTPException):
                self.save_arc(arc)

    def test_strip_shows_current_block_and_weeks_left(self):
        self.save_arc()
        arc = build_winter_arc(self.conn, date(2030, 1, 9))
        self.assertEqual(arc["status"], "active")
        current = arc["current"]
        self.assertEqual((current["label"], current["week_number"], current["weeks_in_block"], current["weeks_left"]), ("Sweet-spot build", 2, 6, 4))

    def test_coaching_context_has_this_and_next_week(self):
        self.save_arc()
        context = winter_arc_coaching_context(self.conn, date(2030, 1, 9))
        self.assertEqual(context["this_week"]["key_types"], ["sweet_spot"])
        self.assertFalse(context["this_week"]["lighter"])
        self.assertTrue(context["next_week"]["lighter"])
        self.assertEqual(context["next_week"]["ride_hours"], 3.6)
        self.assertIsNone(winter_arc_coaching_context(self.conn, date(2030, 3, 1)))

    def test_generated_week_gets_the_blocks_key_rides(self):
        self.save_arc()
        result, days = self.save_week(week(LIFT, Z2, REST, LIFT, Z2, LONG, LIFT))
        self.assertEqual(planned_mix(days)["sweet_spot"], 2)
        self.assertEqual([change["kind"] for change in result["arc_changes"]], ["key_ride", "key_ride"])
        # The long weekend ride and all three lifts are left alone.
        self.assertEqual(days[5]["title"], "Long ride")
        self.assertEqual(sum(1 for day in days if day["session_type"] == "WeightTraining"), 3)
        status = list_weekly_plans_data(self.conn)[0]["winter_arc"]
        self.assertEqual(status["missing"], [])

    def test_tagged_days_never_get_a_quality_ride(self):
        self.save_arc()
        set_life_load_day(self.conn, DATES[1], ["deadline"])
        _, days = self.save_week(week(LIFT, Z2, REST, LIFT, REST, LONG, LIFT))
        self.assertEqual(days[1]["workout_intent"], "easy")
        status = list_weekly_plans_data(self.conn)[0]["winter_arc"]
        self.assertEqual(status["missing"], [{"type": "sweet_spot", "label": "Sweet spot", "count": 2}])

    def test_lighter_week_trims_rides_but_keeps_lifts(self):
        self.save_arc()
        dates = ["2030-01-14", "2030-01-15", "2030-01-16", "2030-01-17", "2030-01-18", "2030-01-19", "2030-01-20"]
        z2_long = ("Ride", "easy", "Z2 ride", 120)
        result, days = self.save_week(week(LIFT, z2_long, LIFT, z2_long, REST, z2_long, LIFT, dates=dates), week_start=dates[0])
        rides = [day for day in days if day["session_type"] == "Ride"]
        self.assertEqual(sum(1 for day in rides if day.get("cycling_workout_id")), 1)  # one key ride in a lighter week
        self.assertLessEqual(sum(day["target_duration_min"] for day in rides), 3.6 * 60 + 15)
        self.assertEqual([day["title"] for day in days if day["session_type"] == "WeightTraining"], ["Upper"] * 3)
        self.assertIn("lighter", [change["kind"] for change in result["arc_changes"]])

    def test_weeks_outside_the_arc_are_untouched(self):
        result, days = self.save_week(week(LIFT, Z2, REST, LIFT, Z2, LONG, LIFT))
        self.assertEqual(result["arc_changes"], [])
        self.assertEqual(planned_mix(days)["sweet_spot"], 0)
        self.assertIsNone(list_weekly_plans_data(self.conn)[0]["winter_arc"])


if __name__ == "__main__":
    unittest.main()
