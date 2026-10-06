import sqlite3
import unittest
from datetime import date
from unittest import mock

from backend.app.services import session_read, strength_progression
from backend.app.services.return_to_run import save_program, save_symptom_check


def _session(day, activity_id, exercises):
    return {
        "workout_date": day,
        "title": f"Session {day}",
        "matched_activity": {"id": activity_id, "name": "Weight Training"},
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": weight, "is_warmup": False} for reps, weight in sets]}
            for name, sets in exercises.items()
        ],
    }


def _connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, distance_km REAL,
            duration_min REAL, avg_hr INTEGER, workout_intent TEXT);
        CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, pain_level INTEGER);
        CREATE TABLE activity_stream_summaries (activity_id TEXT PRIMARY KEY, hr_trimp REAL);
        CREATE TABLE goals (id INTEGER PRIMARY KEY, title TEXT, period_type TEXT, metric_type TEXT, target_value REAL,
            is_active INTEGER, lifecycle_status TEXT, commitment TEXT);
        """
    )
    return conn


class StrengthReadTests(unittest.TestCase):
    def setUp(self):
        self.conn = _connection()
        self.addCleanup(self.conn.close)

    def read(self, sessions, activity_id, day):
        with mock.patch.object(strength_progression, "_session_index", return_value=sessions), \
                mock.patch.object(session_read, "_session_index", return_value=sessions):
            progression = strength_progression.build_strength_progression(None, activity_id)
            payload = {
                "activity": {"id": activity_id, "date": day, "type": "WeightTraining"},
                "strength_detail": {"status": "enriched", "progression": progression},
            }
            return session_read.build_session_read(self.conn, payload)

    def test_flags_a_stalled_main_lift_but_not_a_fixed_load_accessory(self):
        self.conn.execute("INSERT INTO goals VALUES (1, 'Lift three times per week', 'week', 'strength_sessions', 3, 1, 'active', 'anchor')")
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('s5', '2026-10-06', 'WeightTraining')")
        days = ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"]
        sessions = [
            _session(day, f"s{index + 1}", {"Dumbbell Bench Press": [(10, 24), (10, 24)], "Dumbbell Upright Row": [(10, 20), (10, 20)]})
            for index, day in enumerate(days)
        ]
        read = self.read(sessions, "s5", "2026-10-06")

        self.assertEqual(read["kind"], "strength")
        self.assertEqual(read["verdict"]["tone"], "warn")
        self.assertEqual(read["verdict"]["headline"], "Dumbbell Bench Press hasn't gone up in 4 sessions")
        self.assertEqual(read["next_time"], "Dumbbell Bench Press: Every set at 24 kg × 10 — try 26 kg next time.")
        tiles = {signal["key"]: signal for signal in read["signals"]}
        self.assertEqual(tiles["lift_dumbbellbenchpress"]["tone"], "warn")
        self.assertEqual(len(tiles["lift_dumbbellbenchpress"]["series"]), 5)
        # Accessories at a fixed load are reported but never judged.
        self.assertEqual(tiles["lift_dumbbelluprightrow"]["tone"], "neutral")
        self.assertEqual(tiles["weekly_goal"]["value"], "1 / 3")

    def test_new_best_wins_the_verdict(self):
        sessions = [
            _session("2026-09-29", "a1", {"Back Squat": [(5, 80), (5, 80)]}),
            _session("2026-10-06", "a2", {"Back Squat": [(5, 85), (5, 85)]}),
        ]
        read = self.read(sessions, "a2", "2026-10-06")
        self.assertEqual(read["verdict"], {"tone": "good", "badge": "On intent", "headline": "New best on Back Squat"})
        self.assertEqual(read["signals"][0]["detail"], "new best")


class RideReadTests(unittest.TestCase):
    def setUp(self):
        self.conn = _connection()
        self.addCleanup(self.conn.close)

    def ride(self, activity_id, day, drift, watts, hr):
        return {"activity_id": activity_id, "date": day, "environment": "indoor", "decoupling_pct": drift,
                "avg_watts": watts, "avg_hr": hr, "duration_min": 90}

    def test_steady_ride_gets_drift_rank_same_power_hr_and_a_power_step(self):
        rides = [
            self.ride("r1", "2026-09-01", 6.0, 150, 134),
            self.ride("r2", "2026-09-10", 4.1, 152, 132),
            self.ride("r3", "2026-09-20", 2.8, 151, 129),
        ]
        payload = {
            "activity": {"id": "r3", "date": "2026-09-20", "type": "VirtualRide", "workout_intent": "easy"},
            "cycling": {"power_source": "measured", "environment": "indoor", "power_efforts": []},
        }
        with mock.patch.object(session_read, "build_aerobic_decoupling", return_value={"rides": rides}):
            read = session_read.build_session_read(self.conn, payload)

        tiles = {signal["key"]: signal for signal in read["signals"]}
        self.assertEqual(tiles["decoupling"]["detail"], "best of last 3")
        self.assertEqual(tiles["decoupling"]["series"], [6.0, 4.1, 2.8])
        self.assertEqual(tiles["hr_at_power"]["detail"], "-5 bpm vs 1 Sep")
        self.assertEqual(read["verdict"]["tone"], "good")
        self.assertIn("try 155–160 W", read["next_time"])
        self.assertIsNone(read["watch"])

    def test_heart_rate_falling_late_is_not_ranked_as_the_cleanest_ride(self):
        rides = [
            self.ride("r1", "2026-09-01", 2.0, 150, 134),
            self.ride("r2", "2026-09-10", 3.0, 152, 132),
            self.ride("r3", "2026-09-20", -6.9, 120, 129),
        ]
        payload = {
            "activity": {"id": "r3", "date": "2026-09-20", "type": "VirtualRide", "workout_intent": "easy"},
            "cycling": {"power_source": "measured", "environment": "indoor", "power_efforts": []},
        }
        with mock.patch.object(session_read, "build_aerobic_decoupling", return_value={"rides": rides}):
            read = session_read.build_session_read(self.conn, payload)
        self.assertEqual(read["signals"][0]["detail"], "heart rate fell in the second half")
        self.assertEqual(read["verdict"]["headline"], "Steady ride: heart rate held at 120 W")

    def test_drifting_ride_after_a_bonk_points_at_fuelling(self):
        rides = [self.ride("r1", "2026-09-20", 7.5, 150, 140)]
        payload = {
            "activity": {"id": "r1", "date": "2026-09-20", "type": "VirtualRide", "workout_intent": "long"},
            "cycling": {"power_source": "measured", "environment": "indoor", "power_efforts": []},
            "feedback": {"fuelling": "bonked"},
        }
        with mock.patch.object(session_read, "build_aerobic_decoupling", return_value={"rides": rides}):
            read = session_read.build_session_read(self.conn, payload)
        self.assertEqual(read["verdict"]["tone"], "warn")
        self.assertIn("eat from the first 30 min", read["next_time"])
        self.assertEqual(read["watch"]["text"], "You bonked. Eat earlier and more on the next long session.")


class RunReadTests(unittest.TestCase):
    def setUp(self):
        self.conn = _connection()
        self.addCleanup(self.conn.close)

    def test_return_to_run_flare_is_the_verdict(self):
        save_program(self.conn, {"active": True, "started_on": "2026-09-01", "start_stage": 2, "symptom": "Calf"}, today=date(2026, 9, 1))
        self.conn.execute("INSERT INTO activities VALUES ('run1', '2026-09-05', 'Run', 'Run', 3.0, 25, 150, 'easy')")
        save_symptom_check(self.conn, "run1", {"during": 5, "next_morning": 4})
        payload = {"activity": {"id": "run1", "date": "2026-09-05", "type": "Run", "workout_intent": "easy",
                                "avg_hr": 150, "distance_km": 3.0, "duration_min": 25}}
        read = session_read.build_session_read(self.conn, payload)

        self.assertEqual(read["verdict"]["tone"], "bad")
        self.assertEqual(read["verdict"]["headline"], "Flare at stage 2: 5/10 during")
        tiles = {signal["key"]: signal for signal in read["signals"]}
        self.assertEqual(tiles["return_to_run"]["tone"], "bad")
        self.assertEqual(tiles["hr_cap"]["tone"], "good")
        self.assertIn("Flare after the last run", read["next_time"])

    def test_unsupported_types_have_no_read(self):
        read = session_read.build_session_read(self.conn, {"activity": {"id": "w", "date": "2026-09-05", "type": "Walk"}})
        self.assertFalse(read["available"])


if __name__ == "__main__":
    unittest.main()
