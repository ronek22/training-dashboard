import json
import sqlite3
import unittest
from datetime import date

from backend.app.services.session_brief import (
    _plan_guardrails,
    build_briefs_for_date,
    build_session_brief,
    usual_hr_at_power,
)

TODAY = date(2026, 10, 4)


def ride_streams(watts, hr, seconds=3600):
    return {
        "time": {"data": list(range(seconds))},
        "watts": {"data": [watts] * seconds},
        "heartrate": {"data": [hr] * seconds},
    }


class SessionBriefTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, streams_json TEXT);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric TEXT, value REAL, date TEXT);
            CREATE TABLE daily_checkins (date TEXT PRIMARY KEY, energy INTEGER, muscle_soreness INTEGER, stress INTEGER,
                sleep_quality INTEGER, pain_level INTEGER, note TEXT, updated_at TEXT);
            CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT, end_date TEXT);
            INSERT INTO metrics (metric, value, date) VALUES ('ftp', 250, '2026-09-20');
            """
        )
        self.addCleanup(self.conn.close)

    def add_ride(self, activity_id, day, watts, hr):
        self.conn.execute("INSERT INTO activities VALUES (?, ?, 'VirtualRide', ?)", (activity_id, day, activity_id))
        self.conn.execute("INSERT INTO activity_details VALUES (?, ?)", (activity_id, json.dumps(ride_streams(watts, hr))))

    def test_usual_hr_needs_three_rides_and_ignores_other_power(self):
        self.add_ride("a", "2026-09-20", 170, 150)
        self.add_ride("b", "2026-09-22", 170, 154)
        self.assertIsNone(usual_hr_at_power(self.conn, 170, TODAY))
        self.add_ride("c", "2026-09-24", 172, 158)
        self.add_ride("d", "2026-09-25", 250, 175)  # outside the ±8% band
        baseline = usual_hr_at_power(self.conn, 170, TODAY)
        self.assertEqual((baseline["bpm"], baseline["rides"]), (154, 3))

    def test_endurance_ride_anchors_drift_rule_to_usual_hr(self):
        for index, hr in enumerate((150, 154, 158)):
            self.add_ride(f"r{index}", f"2026-09-2{index}", 170, hr)
        brief = build_session_brief(
            self.conn,
            {"date": "2026-10-04", "session_type": "ride", "workout_intent": "easy", "cycling_workout_id": "endurance-60"},
            TODAY,
        )
        self.assertEqual(brief["feel"]["rpe"], "3–4")
        self.assertIn({"label": "Power", "value": "~170 W"}, brief["targets"])
        self.assertIn("around 154 bpm", brief["bail"][0])
        self.assertIn("past 164 bpm", brief["bail"][0])
        self.assertTrue(any("above zone 2" in note for note in brief["notes"]))

    def test_structured_workout_targets_use_stored_ftp(self):
        brief = build_session_brief(
            self.conn,
            {"date": "2026-10-04", "session_type": "ride", "workout_intent": "tempo", "cycling_workout_id": "sweet-spot-3x10"},
            TODAY,
        )
        self.assertEqual(brief["kind"], "Sweet spot")
        self.assertEqual(brief["feel"]["rpe"], "6–7")
        self.assertTrue(brief["targets"][0]["value"].endswith(" W"))

    def test_recovery_session_type_uses_title_to_pick_bike_or_mobility(self):
        ride = build_session_brief(self.conn, {"session_type": "recovery", "title": "Easy indoor cycling + mobility"}, TODAY)
        mobility = build_session_brief(self.conn, {"session_type": "recovery", "title": "Stretch and foam roll"}, TODAY)
        self.assertEqual((ride["sport"], ride["kind"]), ("ride", "Recovery"))
        self.assertEqual(mobility["sport"], "mobility")
        self.assertIsNone(build_session_brief(self.conn, {"session_type": "rest"}, TODAY))

    def test_plan_guardrails_come_first_but_prescriptions_are_ignored(self):
        details = (
            "Squat 3×6, RDL 3×8 and calf raises only if the heel is symptom-free. "
            "Stop the session if knee pain rises above 3/10."
        )
        self.assertEqual(_plan_guardrails(details), ["Stop the session if knee pain rises above 3/10."])
        brief = build_session_brief(self.conn, {"session_type": "strength", "workout_intent": "strength_lower", "details": details}, TODAY)
        self.assertEqual(brief["bail"][0], "Stop the session if knee pain rises above 3/10.")
        self.assertLessEqual(len(brief["bail"]), 3)

    def test_low_checkin_adds_note(self):
        self.conn.execute("INSERT INTO daily_checkins VALUES ('2026-10-04', 2, 2, 3, 2, 0, NULL, NULL)")
        brief = build_session_brief(self.conn, {"date": "2026-10-04", "session_type": "run", "workout_intent": "easy"}, TODAY)
        self.assertIn("low energy and sleep", brief["notes"][0])
        self.assertIn("Any sharp pain", brief["bail"][-1])

    def test_no_briefs_on_sick_days(self):
        plan = {"days": [{"date": "2026-10-04", "session_type": "run", "workout_intent": "easy"}]}
        self.assertEqual(len(build_briefs_for_date(self.conn, plan, TODAY)), 1)
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES ('2026-10-01', NULL)")
        self.assertEqual(build_briefs_for_date(self.conn, plan, TODAY), [])


if __name__ == "__main__":
    unittest.main()
