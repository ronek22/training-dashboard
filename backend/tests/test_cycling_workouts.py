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
    render_cycling_workout,
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


if __name__ == "__main__":
    unittest.main()
