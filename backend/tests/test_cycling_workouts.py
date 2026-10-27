import json
import sqlite3
import unittest
import xml.etree.ElementTree as ET
from datetime import date

from pydantic import ValidationError

from backend.app.models.plans import WeeklyPlanDay
from backend.app.services.cycling_workouts import (
    CYCLING_WORKOUTS,
    build_cycling_workout_library,
    build_zwo,
    get_cycling_workout,
    last_ridden_dates,
    render_cycling_workout,
    rotated_workout_id,
)
from backend.app.services.plans import build_day_change_details, serialize_plan_day


class CyclingWorkoutTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL)")
        self.addCleanup(self.conn.close)

    def test_library_has_unique_ids_and_valid_intents(self):
        ids = [workout["id"] for workout in CYCLING_WORKOUTS]
        self.assertEqual(len(ids), len(set(ids)))
        for workout in CYCLING_WORKOUTS:
            self.assertIn(workout["workout_intent"], {"recovery", "easy", "long", "tempo", "interval"})
            self.assertTrue(workout["steps"])

    def test_render_duration_watts_and_tss(self):
        rendered = render_cycling_workout(get_cycling_workout("threshold-4x8"), 200)
        self.assertEqual(rendered["duration_min"], 76)
        intervals = next(step for step in rendered["steps"] if step["kind"] == "intervals")
        self.assertEqual((intervals["on_watts"], intervals["off_watts"]), (200, 110))
        self.assertEqual(intervals["duration_s"], 4 * (480 + 240))
        self.assertGreater(rendered["intensity_factor"], 0.75)
        self.assertLess(rendered["intensity_factor"], 1.0)
        recovery = render_cycling_workout(get_cycling_workout("recovery-spin-40"))
        self.assertLess(recovery["estimated_tss"], rendered["estimated_tss"])
        self.assertIsNone(recovery["steps"][1]["watts"])

    def test_library_reports_ftp_source_and_staleness(self):
        missing = build_cycling_workout_library(self.conn, today=date(2026, 9, 28))
        self.assertFalse(missing["ftp"]["available"])
        self.assertIsNone(missing["workouts"][0]["steps"][0]["watts_low"])

        self.conn.execute("INSERT INTO metrics VALUES (1, '2026-03-12', 'ftp', 242)")
        stale = build_cycling_workout_library(self.conn, today=date(2026, 9, 28))
        self.assertEqual(stale["ftp"]["watts"], 242)
        self.assertEqual(stale["ftp"]["age_days"], 200)
        self.assertTrue(stale["ftp"]["stale"])

        self.conn.execute("INSERT INTO metrics VALUES (2, '2026-09-01', 'ftp', 230)")
        fresh = build_cycling_workout_library(self.conn, today=date(2026, 9, 28))
        self.assertEqual(fresh["ftp"]["watts"], 230)
        self.assertFalse(fresh["ftp"]["stale"])

    def test_zwo_is_well_formed_and_ftp_relative(self):
        for workout in CYCLING_WORKOUTS:
            root = ET.fromstring(build_zwo(workout))
            self.assertEqual(root.tag, "workout_file")
            self.assertEqual(root.findtext("sportType"), "bike")
            self.assertEqual(root.findtext("name"), workout["name"])
            steps = list(root.find("workout"))
            self.assertEqual(len(steps), len(workout["steps"]))
            total = 0
            for element in steps:
                for key in ("Power", "PowerLow", "PowerHigh", "OnPower", "OffPower"):
                    if key in element.attrib:
                        self.assertLess(float(element.attrib[key]), 2.0)
                if element.tag == "IntervalsT":
                    total += int(element.attrib["Repeat"]) * (
                        int(element.attrib["OnDuration"]) + int(element.attrib["OffDuration"])
                    )
                else:
                    total += int(element.attrib["Duration"])
            self.assertEqual(round(total / 60), render_cycling_workout(workout)["duration_min"])

    def test_cooldown_ramps_down(self):
        root = ET.fromstring(build_zwo(get_cycling_workout("endurance-60")))
        cooldown = root.find("workout/Cooldown")
        self.assertGreater(float(cooldown.attrib["PowerLow"]), float(cooldown.attrib["PowerHigh"]))

    def test_plan_day_accepts_known_ride_workout_only(self):
        base = {"date": "2026-09-29", "label": "Tue", "title": "Sweet spot"}
        day = WeeklyPlanDay(**base, session_type="ride", cycling_workout_id="sweet-spot-3x10")
        self.assertEqual(day.cycling_workout_id, "sweet-spot-3x10")
        self.assertIsNone(WeeklyPlanDay(**base, session_type="Ride", cycling_workout_id="").cycling_workout_id)
        with self.assertRaises(ValidationError):
            WeeklyPlanDay(**base, session_type="Ride", cycling_workout_id="made-up")
        with self.assertRaises(ValidationError):
            WeeklyPlanDay(**base, session_type="Run", cycling_workout_id="sweet-spot-3x10")

    def test_serialized_day_names_workout_and_diff_shows_change(self):
        before = serialize_plan_day({"date": "2026-09-29", "label": "Tue", "title": "Ride", "session_type": "Ride",
                                     "cycling_workout_id": "endurance-60"})
        after = serialize_plan_day({**before, "cycling_workout_id": "vo2-5x3"})
        self.assertEqual(before["cycling_workout_name"], "Endurance 60")
        changes = build_day_change_details(before, after)
        self.assertEqual([item["label"] for item in changes], ["Structured workout"])


class WorkoutRotationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL)")
        self.conn.execute("CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT)")
        self.conn.execute("CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT)")
        self.addCleanup(self.conn.close)

    def plan(self, week_start, *days):
        self.conn.execute("INSERT INTO weekly_plans VALUES (?, ?)", (week_start, json.dumps([
            {"date": day, "session_type": "Ride", "cycling_workout_id": workout_id} for day, workout_id in days
        ])))

    def ride(self, day, kind="VirtualRide"):
        self.conn.execute("INSERT INTO activities VALUES (?, ?, ?)", (f"{day}-{kind}", f"{day}T18:00:00", kind))

    def test_last_ridden_needs_a_planned_workout_and_a_ride_that_day(self):
        self.plan("2026-10-05", ("2026-10-06", "sweet-spot-3x10"), ("2026-10-08", "vo2-5x3"))
        self.plan("2026-10-12", ("2026-10-13", "sweet-spot-3x10"), ("2026-10-15", "endurance-60"))
        self.ride("2026-10-06")
        self.ride("2026-10-13", "Ride")
        self.ride("2026-10-15", "Run")  # not a ride
        self.assertEqual(last_ridden_dates(self.conn), {"sweet-spot-3x10": "2026-10-13"})
        library = {item["id"]: item for item in build_cycling_workout_library(self.conn, date(2026, 10, 27))["workouts"]}
        self.assertEqual(library["sweet-spot-3x10"]["last_ridden"], "2026-10-13")
        self.assertIsNone(library["vo2-5x3"]["last_ridden"])

    def test_rotation_prefers_an_unridden_equivalent_and_keeps_fresh_choices(self):
        on = date(2026, 10, 26)
        # Ridden 13 days ago: same intent (tempo), similar load, never ridden beats the rest; closest load breaks ties.
        self.assertEqual(rotated_workout_id("sweet-spot-3x10", {"sweet-spot-3x10": "2026-10-13"}, on), "tempo-3x12")
        self.assertEqual(rotated_workout_id(
            "sweet-spot-3x10", {"sweet-spot-3x10": "2026-10-13", "tempo-3x12": "2026-10-20"}, on), "sweet-spot-2x20")
        # Exactly three weeks ago no longer counts as recent.
        self.assertEqual(rotated_workout_id("sweet-spot-3x10", {"sweet-spot-3x10": "2026-10-05"}, on), "sweet-spot-3x10")
        # VO2 5x3 swaps to 30/30, never to threshold (same intent, but load is outside the margin).
        self.assertEqual(rotated_workout_id("vo2-5x3", {"vo2-5x3": "2026-10-20"}, on), "vo2-30-30")

    def test_rotation_falls_back_to_the_original_without_an_equivalent(self):
        on = date(2026, 10, 26)
        recent = {"sweet-spot-3x10": "2026-10-13", "tempo-3x12": "2026-10-16", "sweet-spot-2x20": "2026-10-20"}
        self.assertEqual(rotated_workout_id("sweet-spot-3x10", recent, on), "sweet-spot-3x10")
        # The long ride has no other "long" workout in the library.
        self.assertEqual(rotated_workout_id("endurance-long-120", {"endurance-long-120": "2026-10-25"}, on), "endurance-long-120")


if __name__ == "__main__":
    unittest.main()


class PlanDayBriefTests(unittest.TestCase):
    def test_structured_brief_fields_are_trimmed_and_kept(self):
        day = WeeklyPlanDay(date="2026-10-28", label="Wed", title="Easy spin", session_type="ride",
                            check="  Go only if pain is 0-2/10 ", steps=["10 min easy", " ", "25 min Zone 2"],
                            cues=["Stop at the first ping"], fallback="")
        payload = serialize_plan_day(day)
        self.assertEqual(payload["check"], "Go only if pain is 0-2/10")
        self.assertEqual(payload["steps"], ["10 min easy", "25 min Zone 2"])
        self.assertIsNone(payload["fallback"])
        with self.assertRaises(ValidationError):
            WeeklyPlanDay(date="2026-10-28", label="Wed", title="Too long", steps=["step"] * 13)
