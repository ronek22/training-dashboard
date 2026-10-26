import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.life_load import set_life_load_day
from backend.app.services.sleep_payback import _stress_days, build_sleep_payback_plan
from backend.tests.test_downshift import EXTRA_SCHEMA
from backend.tests.test_sick_mode import SCHEMA
from backend.tests.test_sleep_debt import TODAY, nights

RISK_WEEK = nights(7.5, [6.5] * 7)  # 7 h debt
CAUTION_WEEK = nights(7.5, [7.0] * 7)  # 3.5 h debt
STRESSED = [(TODAY - timedelta(days=1)).isoformat(), TODAY.isoformat()]
WAKE = [7 * 60] * 10
PLAN = [
    {"date": (TODAY + timedelta(days=1)).isoformat(), "session_type": "strength", "title": "Workout A", "target_duration_min": 75},
    {"date": (TODAY + timedelta(days=2)).isoformat(), "session_type": "rest", "title": "Rest"},
    {"date": (TODAY + timedelta(days=3)).isoformat(), "session_type": "ride", "title": "Sweet spot", "target_duration_min": 50},
]


class SleepPaybackTriggerTests(unittest.TestCase):
    def test_needs_risk_debt_and_two_stressed_days(self):
        self.assertTrue(build_sleep_payback_plan(RISK_WEEK, STRESSED, PLAN, WAKE, TODAY)["active"])
        self.assertFalse(build_sleep_payback_plan(CAUTION_WEEK, STRESSED, PLAN, WAKE, TODAY)["active"])
        self.assertFalse(build_sleep_payback_plan(RISK_WEEK, STRESSED[:1], PLAN, WAKE, TODAY)["active"])
        self.assertFalse(build_sleep_payback_plan(RISK_WEEK, [], PLAN, WAKE, TODAY)["active"])

    def test_stress_days_outside_the_window_do_not_count(self):
        old = [(TODAY - timedelta(days=5)).isoformat(), (TODAY - timedelta(days=6)).isoformat()]
        self.assertFalse(build_sleep_payback_plan(RISK_WEEK, old, PLAN, WAKE, TODAY)["active"])

    def test_no_baseline_means_no_plan(self):
        self.assertFalse(build_sleep_payback_plan(nights(7.5, [6.5] * 7, baseline_nights=5), STRESSED, PLAN, WAKE, TODAY)["active"])


class SleepPaybackPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_sleep_payback_plan(RISK_WEEK, STRESSED, PLAN, WAKE, TODAY)

    def test_bedtime_comes_from_median_sleep_and_wake_time(self):
        # 7.5 h median + 1 h payback + 15 min to fall asleep before a 07:00 wake.
        self.assertEqual(self.plan["bedtime"], "22:15")
        self.assertEqual(self.plan["finish_by"], "19:15")
        self.assertEqual([item["night_of"] for item in self.plan["bedtimes"]], [TODAY.isoformat(), (TODAY + timedelta(days=1)).isoformat(), (TODAY + timedelta(days=2)).isoformat()])

    def test_lifts_are_shortened_never_removed(self):
        sessions = {item["title"]: item for item in self.plan["sessions"]}
        self.assertEqual(set(sessions), {"Workout A", "Sweet spot"})
        self.assertEqual(sessions["Workout A"]["shorten_to_min"], 60)
        self.assertIn("main lifts first", sessions["Workout A"]["action"])
        self.assertIsNone(sessions["Sweet spot"]["shorten_to_min"])

    def test_progress_shows_debt_falling_each_night(self):
        projected = [item["debt_hours"] for item in self.plan["progress"] if item["projected"]]
        self.assertGreater(len(projected), 1)
        self.assertTrue(all(later < earlier for earlier, later in zip(projected, projected[1:])))
        self.assertLess(projected[-1], 3.0)
        self.assertEqual(self.plan["clears_on"], self.plan["progress"][-1]["date"])
        self.assertEqual(self.plan["progress"][0]["projected"], False)

    def test_unknown_wake_time_still_gives_a_sleep_target(self):
        plan = build_sleep_payback_plan(RISK_WEEK, STRESSED, PLAN, [], TODAY)
        self.assertIsNone(plan["bedtime"])
        self.assertEqual(plan["target_sleep_hours"], 8.5)
        self.assertIn("done 3 h before bed", plan["sessions"][0]["slot"])


class StressDaysTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA + EXTRA_SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_high_stress_check_ins_and_deadline_tags_count(self):
        today = date.today()
        yesterday, older = today - timedelta(days=1), today - timedelta(days=4)
        for day, stress in ((today, 4), (yesterday, 3), (older, 5)):
            self.conn.execute("INSERT INTO daily_checkins (date, energy, muscle_soreness, stress, sleep_quality) VALUES (?, 3, 2, ?, 3)", (day.isoformat(), stress))
        self.assertEqual(_stress_days(self.conn, today), [today.isoformat()])
        set_life_load_day(self.conn, yesterday.isoformat(), ["deadline"])
        self.assertEqual(_stress_days(self.conn, today), [yesterday.isoformat(), today.isoformat()])


if __name__ == "__main__":
    unittest.main()
