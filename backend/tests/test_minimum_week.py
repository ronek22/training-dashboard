import json
import sqlite3
import unittest
from datetime import date, timedelta

from fastapi import HTTPException

from backend.app.services.life_load import set_life_load_day
from backend.app.services.minimum_week import build_minimum_week, minimum_week_state

SCHEMA = """
CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, workout_intent TEXT);
CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, title TEXT, days_json TEXT NOT NULL);
CREATE TABLE goals (
    id INTEGER PRIMARY KEY, title TEXT, period_type TEXT, metric_type TEXT, target_value REAL, start_date TEXT,
    end_date TEXT, activity_type TEXT, is_active INTEGER DEFAULT 1, lifecycle_status TEXT DEFAULT 'active',
    commitment TEXT DEFAULT 'flexible', season_end TEXT
);
CREATE TABLE plan_revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, week_start TEXT, adaptation_reason TEXT, previous_plan_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT, severity TEXT, note TEXT);
CREATE TABLE life_load_days (
    date TEXT PRIMARY KEY, tags_json TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

MONDAY = date(2026, 10, 5)
WEEK = MONDAY.isoformat()


def day(offset: int) -> str:
    return (MONDAY + timedelta(days=offset)).isoformat()


FULL_WEEK = [
    {"date": day(0), "label": "Mon", "session_type": "strength", "title": "Workout B"},
    {"date": day(1), "label": "Tue", "session_type": "ride", "workout_intent": "interval", "title": "VO2"},
    {"date": day(2), "label": "Wed", "session_type": "strength", "title": "Workout D"},
    {"date": day(3), "label": "Thu", "session_type": "ride", "workout_intent": "tempo", "title": "Sweet spot"},
    {"date": day(4), "label": "Fri", "session_type": "run", "workout_intent": "easy", "title": "Run"},
    {"date": day(5), "label": "Sat", "session_type": "strength", "title": "Workout A"},
    {"date": day(6), "label": "Sun", "session_type": "ride", "workout_intent": "long", "title": "Long ride"},
]


class MinimumWeekTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT INTO weekly_plans VALUES (?, 'Full week', ?)", (WEEK, json.dumps(FULL_WEEK)))
        # A weekly anchor whose end date has passed still counts: anchors outlast their dates.
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2026-01-01', '2026-07-05', 'anchor')"
        )

    def tearDown(self):
        self.conn.close()

    def kinds(self, proposal):
        return {item["date"]: item["session_type"] for item in proposal["days"]}

    def test_whole_week_keeps_anchor_lifts_on_their_days_and_two_easy_rides(self):
        proposal = build_minimum_week(self.conn, WEEK, today=MONDAY)
        self.assertEqual(proposal["targets"], {"lifts": 3, "rides": 2})
        self.assertEqual(proposal["anchors"], ["Lift three times per week"])
        kinds = self.kinds(proposal)
        self.assertEqual([key for key, kind in kinds.items() if kind == "WeightTraining"], [day(0), day(2), day(5)])
        self.assertEqual([key for key, kind in kinds.items() if kind == "Ride"], [day(1), day(3)])
        self.assertEqual(kinds[day(4)], "Rest")
        self.assertEqual(kinds[day(6)], "Rest")
        ride = next(item for item in proposal["days"] if item["session_type"] == "Ride")
        self.assertEqual((ride["workout_intent"], ride["target_duration_min"]), ("easy", 40))
        self.assertEqual(proposal["summary"], "3 short lifts and 2 easy rides; everything else rests.")

    def test_mid_week_counts_what_is_done_and_keeps_lifts_apart(self):
        self.conn.execute("INSERT INTO activities VALUES ('a', ?, 'WeightTraining', 'strength_upper'), ('b', ?, 'Ride', 'easy')", (day(0), day(1)))
        proposal = build_minimum_week(self.conn, WEEK, today=MONDAY + timedelta(days=2))
        self.assertEqual(proposal["effective_from"], day(2))
        self.assertEqual(proposal["done"], {"lifts": 1, "rides": 1})
        kinds = self.kinds(proposal)
        lifts = [key for key, kind in kinds.items() if kind == "WeightTraining"]
        self.assertEqual(len(lifts), 2)
        self.assertFalse(any(abs(date.fromisoformat(a).toordinal() - date.fromisoformat(b).toordinal()) == 1 for a in lifts for b in lifts if a != b))
        self.assertEqual(sum(1 for kind in kinds.values() if kind == "Ride"), 1)
        self.assertIn("(1 done)", proposal["summary"])

    def test_travel_days_get_nothing_and_other_tags_are_avoided(self):
        set_life_load_day(self.conn, day(0), ["travel"])
        set_life_load_day(self.conn, day(1), ["deadline"])
        kinds = self.kinds(build_minimum_week(self.conn, WEEK, today=MONDAY))
        self.assertEqual(kinds[day(0)], "Rest")
        self.assertEqual(kinds[day(1)], "Rest")
        self.assertEqual(sum(1 for kind in kinds.values() if kind == "WeightTraining"), 3)

    def test_sick_days_rest(self):
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date, severity) VALUES (?, ?, 'above_neck')", (day(0), day(1)))
        kinds = self.kinds(build_minimum_week(self.conn, WEEK, today=MONDAY))
        self.assertEqual((kinds[day(0)], kinds[day(1)]), ("Rest", "Rest"))
        self.assertEqual(sum(1 for kind in kinds.values() if kind == "WeightTraining"), 3)

    def test_late_in_week_reports_lifts_that_no_longer_fit(self):
        proposal = build_minimum_week(self.conn, WEEK, today=MONDAY + timedelta(days=5))
        self.assertEqual(self.kinds(proposal), {day(5): "WeightTraining", day(6): "WeightTraining"})
        self.assertEqual(proposal["shortfall"], {"lifts": 1, "rides": 2})
        self.assertIn("Only room for 2 more lifts", proposal["summary"])

    def test_without_an_anchor_two_lifts_are_kept(self):
        self.conn.execute("DELETE FROM goals")
        self.assertEqual(build_minimum_week(self.conn, WEEK, today=MONDAY)["targets"], {"lifts": 2, "rides": 2})

    def test_errors_without_plan_or_open_days(self):
        with self.assertRaises(HTTPException):
            build_minimum_week(self.conn, day(7), today=MONDAY)
        with self.assertRaises(HTTPException):
            build_minimum_week(self.conn, WEEK, today=MONDAY + timedelta(days=7))

    def test_state_follows_the_latest_revision(self):
        self.assertIsNone(minimum_week_state(self.conn, WEEK))
        self.conn.execute("INSERT INTO plan_revisions (week_start, adaptation_reason) VALUES (?, 'Minimum viable week: 3 short lifts')", (WEEK,))
        self.conn.execute("INSERT INTO plan_revisions (week_start, adaptation_reason) VALUES (?, 'Moved Strength from Tue to Wed')", (WEEK,))
        state = minimum_week_state(self.conn, WEEK)
        self.assertEqual((state["active"], state["revision_id"], state["summary"]), (True, 1, "3 short lifts"))
        self.conn.execute("INSERT INTO plan_revisions (week_start, adaptation_reason) VALUES (?, 'Restored full week')", (WEEK,))
        self.assertIsNone(minimum_week_state(self.conn, WEEK))


if __name__ == "__main__":
    unittest.main()
