import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WinterArc
from backend.app.repositories.plans import upsert_weekly_plan_row
from backend.app.services.life_load import set_life_load_day
from backend.app.services.winter_arc import (
    CARRY_REASON,
    block_progress,
    fit_week_to_arc,
    save_winter_arc,
    winter_arc_coaching_context,
)

# Past weeks, so last week's planned days are compared against (no) activities and count as skipped.
WEEK1, WEEK2, WEEK3 = "2026-01-12", "2026-01-19", "2026-01-26"
LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REST = ("Rest", None, "Rest", None)
Z2 = ("Ride", "easy", "Z2 ride", 75)
LONG = ("Ride", "long", "Long ride", 150)
SS = ("Ride", "tempo", "Sweet spot", 60)

# One sweet-spot ride a week; the third week of the block (WEEK3) is lighter.
ARC = {"blocks": [{"start_date": "2026-01-12", "end_date": "2026-02-08", "focus": "sweet_spot", "weekly_hours": 6,
                   "ride_mix": {"z2": 2, "sweet_spot": 1, "vo2": 0}, "lighter_every": 3}]}


def week(week_start, *sessions, reasons=None):
    start = date.fromisoformat(week_start)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "label": LABELS[i], "session_type": kind, "workout_intent": intent,
         "title": title, "target_duration_min": minutes,
         "cycling_workout_id": "sweet-spot-3x10" if intent == "tempo" else None,
         "planning_rule_reason": (reasons or {}).get(i)}
        for i, (kind, intent, title, minutes) in enumerate(sessions)
    ]


def day_before(week_start):
    return date.fromisoformat(week_start) - timedelta(days=1)


class WinterArcProgressTests(unittest.TestCase):
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
        save_winter_arc(self.conn, WinterArc(**arc), date(2026, 1, 1))

    def store(self, week_start, days):
        upsert_weekly_plan_row(self.conn, WeeklyPlan(week_start=week_start, title="Test", days=[WeeklyPlanDay(**day) for day in days]))
        self.conn.commit()

    def fit(self, week_start, days):
        return fit_week_to_arc(self.conn, days, week_start, today=day_before(week_start))

    def test_missed_key_ride_carries_into_next_week(self):
        self.save_arc()
        self.store(WEEK1, week(WEEK1, REST, SS, Z2, REST, Z2, LONG, REST))  # Nothing was ridden.

        days, changes = self.fit(WEEK2, week(WEEK2, REST, Z2, REST, Z2, REST, LONG, Z2))

        carried = [change for change in changes if change["kind"] == "carry_over"]
        self.assertEqual(len(carried), 1)
        self.assertEqual((carried[0]["type"], carried[0]["from"]), ("sweet_spot", "2026-01-13"))
        moved = next(day for day in days if day["date"] == carried[0]["date"])
        self.assertTrue(moved["planning_rule_reason"].startswith(CARRY_REASON))
        self.assertEqual(sum(day.get("cycling_workout_id") == "sweet-spot-3x10" for day in days), 2)  # Block ride + carried one.
        self.assertNotEqual(date.fromisoformat(moved["date"]).weekday(), 5)  # The long ride stays.

        note = block_progress(self.conn, WEEK2, days)["note"]
        self.assertEqual(note, "Week 2 of 4 in Sweet-spot build, last week's SS ride moved here, last week 0 of 6 h riding, lighter week next")

        # Saving the same week again does not add a second carried ride.
        _, again = self.fit(WEEK2, days)
        self.assertEqual(again, [])

    def test_carried_ride_does_not_carry_twice(self):
        self.save_arc(dict(ARC, blocks=[dict(ARC["blocks"][0], lighter_every=0)]))
        # Week 2 holds only the carried sweet-spot ride, and it was missed too.
        self.store(WEEK2, week(WEEK2, REST, SS, Z2, REST, Z2, LONG, REST, reasons={1: f"{CARRY_REASON} last week's missed sweet spot ride"}))

        days, changes = self.fit(WEEK3, week(WEEK3, REST, Z2, REST, Z2, REST, LONG, Z2))

        self.assertEqual([change["kind"] for change in changes], ["key_ride"])  # Only the block's own ride.
        self.assertIn("not carried (already moved once)", block_progress(self.conn, WEEK3, days)["note"])

    def test_no_carry_into_lighter_week(self):
        self.save_arc()
        self.store(WEEK2, week(WEEK2, REST, SS, Z2, REST, Z2, LONG, REST))

        days, changes = self.fit(WEEK3, week(WEEK3, REST, Z2, REST, Z2, REST, LONG, Z2))

        self.assertNotIn("carry_over", [change["kind"] for change in changes])
        progress = block_progress(self.conn, WEEK3, days)
        self.assertIsNone(progress["carry_over"])
        self.assertTrue(progress["note"].startswith("Week 3 of 4 in Sweet-spot build (lighter), last week's SS ride missed, not carried (lighter week)"))

    def test_no_carry_onto_guarded_day(self):
        self.save_arc()
        self.store(WEEK1, week(WEEK1, REST, SS, Z2, REST, Z2, LONG, REST))
        new_week = week(WEEK2, REST, Z2, REST, REST, REST, LONG, Z2)
        set_life_load_day(self.conn, "2026-01-25", ["deadline"])  # Sunday: the only other easy ride.

        days, changes = self.fit(WEEK2, new_week)

        # Tuesday becomes the block's own sweet-spot ride; Sunday is tagged, so nothing carries.
        self.assertEqual([change["kind"] for change in changes], ["key_ride"])
        self.assertIn("no safe day to move it", block_progress(self.conn, WEEK2, days)["note"])

    def test_planner_context_carries_last_week(self):
        self.save_arc()
        self.store(WEEK1, week(WEEK1, REST, SS, Z2, REST, Z2, LONG, REST))

        context = winter_arc_coaching_context(self.conn, date(2026, 1, 18))

        next_week = context["next_week"]
        self.assertEqual(next_week["carry_over"], "sweet_spot")
        self.assertEqual(next_week["last_week"]["key_rides"], {"planned": 1, "hit": 0, "missed": ["sweet_spot"]})
        self.assertEqual(next_week["last_week"]["follow_through"], {"planned": 4, "done": 0, "changed": 0, "missed": 4})
        self.assertEqual(next_week["last_week"]["ride_hours"], [0.0, 6.0])
        self.assertTrue(next_week["next_week_lighter"])
        self.assertIn("may move here once", next_week["note"])

    def test_week_without_arc(self):
        self.store(WEEK1, week(WEEK1, REST, SS, Z2, REST, Z2, LONG, REST))
        days = week(WEEK2, REST, Z2, REST, Z2, REST, LONG, Z2)

        self.assertIsNone(block_progress(self.conn, WEEK2, days))
        self.assertEqual(self.fit(WEEK2, days), (days, []))
        self.assertIsNone(winter_arc_coaching_context(self.conn, date(2026, 1, 18)))


if __name__ == "__main__":
    unittest.main()
