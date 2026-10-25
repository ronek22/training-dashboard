import json
import sqlite3
import unittest
from datetime import date

from backend.app.services.unplanned_ideas import build_unplanned_ideas

SCHEMA = """
CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
"""

# A Sunday, the day after a trip, with no plan for the week.
TODAY = date(2026, 10, 25)
REENTRY = {"headline": "Day 1 of 4 back from the mountains", "rpe_cap": 4}


class UnplannedIdeasTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.addCleanup(self.conn.close)

    def _activity(self, day: str, kind: str):
        self.conn.execute("INSERT INTO activities (id, date, type, name) VALUES (?, ?, ?, ?)",
                          (f"{day}-{kind}", day, kind, kind))

    def _ideas(self, **kwargs):
        return build_unplanned_ideas(self.conn, today=TODAY, **kwargs)

    def test_planned_or_done_days_get_no_ideas(self):
        self.assertIsNone(self._ideas(weekly_plan={"days": [{"date": TODAY.isoformat(), "session_type": "Rest"}]}))
        self._activity(TODAY.isoformat(), "Walk")
        self.assertIsNone(self._ideas())

    def test_lift_ride_and_streak_saver_with_lift_first(self):
        self._activity("2026-10-21", "WeightTraining")
        result = self._ideas(weekly_plan={"days": [{"date": "2026-10-13"}]})
        self.assertEqual([idea["key"] for idea in result["ideas"]], ["lift", "ride", "streak"])
        lift = result["ideas"][0]
        self.assertEqual(lift["title"], "Strength session")
        self.assertIn("Lift 2 of 3 this week; last lift 4 days ago", lift["why"])
        self.assertEqual(result["ideas"][1]["title"], "Endurance ride")
        self.assertEqual(result["ideas"][2]["action"]["to"], "/guided/desk_mobility")

    def test_mountain_reentry_keeps_the_lift_upper_body_and_the_ride_easy(self):
        result = self._ideas(mountain_reentry=REENTRY)
        self.assertTrue(result["message"].startswith("Day 1 of 4 back from the mountains."))
        lift, ride, _ = result["ideas"]
        self.assertEqual(lift["title"], "Upper-body lift")
        self.assertEqual((ride["title"], ride["minutes"]), ("Easy spin", 40))
        self.assertIn("RPE ≤4", ride["summary"])

    def test_moderate_window_caps_the_ride_at_its_rpe(self):
        ride = self._ideas(illness_return={"headline": "Day 4 of 5 back from illness", "rpe_cap": 7})["ideas"][1]
        self.assertEqual(ride["title"], "Steady ride")
        self.assertIn("RPE ≤7", ride["summary"])

    def test_three_lifts_done_drops_the_lift(self):
        for day in ("2026-10-19", "2026-10-21", "2026-10-23"):
            self._activity(day, "WeightTraining")
        self.assertEqual([idea["key"] for idea in self._ideas()["ideas"]], ["ride", "streak"])

    def test_recover_day_leads_with_the_streak_saver(self):
        result = self._ideas(daily_recommendation={"status": "recover"})
        self.assertEqual([idea["key"] for idea in result["ideas"]], ["streak", "ride", "lift"])
        self.assertEqual(result["ideas"][1]["title"], "Easy spin")

    def test_blocked_modality_is_never_suggested(self):
        restrictions = {"modalities": {"ride": {"status": "blocked"}}}
        self.conn.execute("INSERT INTO app_settings (key, value) VALUES ('modality_restrictions', ?)", (json.dumps(restrictions),))
        self.assertEqual([idea["key"] for idea in self._ideas()["ideas"]], ["lift", "streak"])


if __name__ == "__main__":
    unittest.main()
