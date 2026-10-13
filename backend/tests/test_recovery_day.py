import json
import sqlite3
import unittest
from datetime import datetime, timedelta

from backend.app.services.dashboard import compute_activity_streak
from backend.app.services.downshift import build_downshift, downshift_coaching_context
from backend.app.services.plans import build_plan_day_comparison
from backend.app.services.readiness import build_readiness_summary
from backend.app.services.recovery_day import check_recovery_day, recovery_cap
from backend.tests.test_downshift import EXTRA_SCHEMA
from backend.tests.test_sick_mode import SCHEMA

TODAY = datetime.now().date()
HR_LIMIT = 140  # default riding zone 2 start


def activity(activity_type, minutes, avg_hr=None, intent=None):
    return {"type": activity_type, "duration_min": minutes, "avg_hr": avg_hr, "workout_intent": intent}


class RecoveryCapTests(unittest.TestCase):
    def test_light_activities_fit_the_cap(self):
        for items in (
            [activity("Walk", 50)],
            [activity("Yoga", 25)],
            [activity("WeightTraining", 10, intent="mobility")],
            [activity("VirtualRide", 40, avg_hr=120)],
            [activity("Ride", 30, intent="recovery")],
            [activity("Walk", 30), activity("WeightTraining", 15, intent="mobility")],
        ):
            self.assertTrue(check_recovery_day(items, HR_LIMIT)["within_cap"], items)

    def test_each_limit_is_named_when_crossed(self):
        cases = {
            "walk 75 min > 60": [activity("Walk", 75)],
            "mobility 40 min > 30": [activity("Yoga", 40)],
            "ride 50 min > 45": [activity("Ride", 50, avg_hr=120)],
            "ride avg HR 145 ≥ 140 bpm": [activity("Ride", 40, avg_hr=145)],
            "ride without heart rate": [activity("Ride", 40)],
            "WeightTraining is not a recovery activity": [activity("WeightTraining", 20)],
            "Ride tagged interval": [activity("Ride", 30, avg_hr=120, intent="interval")],
            "70 min in total > 60": [activity("Walk", 45), activity("Yoga", 25)],
        }
        for reason, items in cases.items():
            check = check_recovery_day(items, HR_LIMIT)
            self.assertFalse(check["within_cap"])
            self.assertIn(reason, check["over"])

    def test_no_activities_is_not_a_recovery_day(self):
        self.assertIsNone(check_recovery_day([], HR_LIMIT))

    def test_cap_uses_saved_ride_zones(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO app_settings VALUES ('performance_settings', ?)", (json.dumps({"heart_rate_zones": {"ride": [130, 150, 160, 170]}}),))
        cap = recovery_cap(conn)
        self.assertEqual(cap["spin_hr_below"], 130)
        self.assertIn("under 130 bpm", cap["summary"])


class RecoveryDayEffectsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA + EXTRA_SCHEMA + """
            CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, rpe INTEGER, energy INTEGER, muscle_soreness INTEGER,
                pain_level INTEGER, note TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, title TEXT, days_json TEXT NOT NULL);
        """)

    def tearDown(self):
        self.conn.close()

    def add(self, offset, activity_type, minutes, avg_hr=None, intent=None):
        day = (TODAY - timedelta(days=offset)).isoformat()
        self.conn.execute(
            "INSERT INTO activities (id, date, type, workout_intent, duration_min, avg_hr) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{activity_type}-{offset}-{minutes}", day, activity_type, intent, minutes, avg_hr),
        )

    def test_recovery_days_keep_the_streak_but_are_not_training_days(self):
        for offset in range(7):
            if offset in (1, 4):
                self.add(offset, "Walk", 30, avg_hr=95)
            else:
                self.add(offset, "Ride", 75, avg_hr=135, intent="easy")
        self.assertEqual(compute_activity_streak(self.conn)["value"], 7)
        metrics = build_readiness_summary(self.conn)["metrics"]
        self.assertEqual((metrics["active_days_7d"], metrics["recovery_days_7d"]), (5, 2))
        factor = next(item for item in build_readiness_summary(self.conn)["supporting_factors"] if item["key"] == "active_days_7d")
        self.assertEqual(factor["tone"], "steady")

    def test_going_over_the_cap_counts_as_a_training_day_without_breaking_the_streak(self):
        for offset in range(7):
            self.add(offset, "Walk", 90, avg_hr=95)
        self.assertEqual(compute_activity_streak(self.conn)["value"], 7)
        metrics = build_readiness_summary(self.conn)["metrics"]
        self.assertEqual((metrics["active_days_7d"], metrics["recovery_days_7d"]), (7, 0))

    def plan_today(self, session_type):
        week_start = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
        days = [{"date": TODAY.isoformat(), "session_type": session_type, "title": session_type}]
        self.conn.execute("INSERT OR REPLACE INTO weekly_plans VALUES (?, 'Week', ?)", (week_start, json.dumps(days)))

    def test_downshift_is_offered_on_a_planned_rest_day_until_something_is_recorded(self):
        self.plan_today("Ride")
        self.assertFalse(build_downshift(self.conn, TODAY)["offer"])
        self.plan_today("Rest")
        state = build_downshift(self.conn, TODAY)
        self.assertTrue(state["offer"] and state["rest_day"])
        self.assertEqual(state["reasons"], ["planned rest day"])
        self.assertIn("still counts as rest", downshift_coaching_context(self.conn)["guidance"])
        self.plan_today("Recovery")
        self.assertEqual(build_downshift(self.conn, TODAY)["reasons"], ["planned recovery day"])
        self.add(0, "Walk", 20)
        self.assertFalse(build_downshift(self.conn, TODAY)["offer"])


class RecoveryPlanComparisonTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.past = (TODAY - timedelta(days=3)).isoformat()

    def tearDown(self):
        self.conn.close()

    def row(self, activity_type, minutes, avg_hr=None, intent=None):
        return self.conn.execute(
            """SELECT 'a1' AS id, ? AS date, ? AS type, ? AS workout_intent, 'Activity' AS name, NULL AS distance_km,
                      ? AS duration_min, NULL AS avg_pace, NULL AS avg_watts, ? AS avg_hr, NULL AS linked_planned_session_id""",
            (self.past, activity_type, intent, minutes, avg_hr),
        ).fetchone()

    def compare(self, session_type, rows):
        day = {"date": self.past, "session_type": session_type, "session_id": "s1", "title": session_type}
        return build_plan_day_comparison(self.conn, day, rows, {self.past: rows}, {self.past: day}, [])

    def test_walk_on_a_recovery_day_matches_under_the_cap(self):
        result = self.compare("Recovery", [self.row("Walk", 40, avg_hr=95)])
        self.assertEqual((result["status"], result["label"]), ("matched", "Matched"))
        self.assertTrue(result["recovery_check"]["within_cap"])

    def test_recovery_ride_over_the_cap_still_matches_but_says_so(self):
        result = self.compare("Recovery", [self.row("Ride", 70, avg_hr=125, intent="recovery")])
        self.assertEqual((result["status"], result["label"]), ("matched", "Matched · over cap"))
        self.assertEqual(result["recovery_check"]["over"], ["ride 70 min > 45", "70 min in total > 60"])

    def test_light_walk_on_a_rest_day_is_a_light_day(self):
        result = self.compare("Rest", [self.row("Walk", 30)])
        self.assertEqual((result["status"], result["label"]), ("rest_day_changed", "Light day · under cap"))
        heavy = self.compare("Rest", [self.row("WeightTraining", 50)])
        self.assertEqual(heavy["label"], "Rest day changed · over cap")


if __name__ == "__main__":
    unittest.main()
