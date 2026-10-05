import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.what_worked import (
    build_what_worked,
    build_what_worked_coaching_context,
    get_session_tags,
    save_session_tags,
)

TODAY = date(2026, 10, 5)


class WhatWorkedTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, workout_intent TEXT);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, detail_json TEXT);
            CREATE TABLE activity_feedback (activity_id TEXT PRIMARY KEY, rpe INTEGER);
            CREATE TABLE activity_source_refs (activity_id TEXT, started_at TEXT);
            CREATE TABLE daily_checkins (date TEXT PRIMARY KEY, energy INTEGER, sleep_quality INTEGER);
            CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT, end_date TEXT);
            CREATE TABLE session_tags (activity_id TEXT PRIMARY KEY, verdict TEXT, pre_fuel TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """
        )
        self.addCleanup(self.conn.close)
        self.counter = 0

    def add(self, day, hour_utc, verdict=None, rpe=None, intent="tempo", activity_type="VirtualRide"):
        self.counter += 1
        activity_id = f"a{self.counter}"
        self.conn.execute("INSERT INTO activities VALUES (?, ?, ?, ?, ?)", (activity_id, day.isoformat(), activity_type, activity_id, intent))
        self.conn.execute("INSERT INTO activity_source_refs VALUES (?, ?)", (activity_id, f"{day.isoformat()}T{hour_utc:02d}:00:00+00:00"))
        if rpe is not None:
            self.conn.execute("INSERT INTO activity_feedback VALUES (?, ?)", (activity_id, rpe))
        if verdict:
            self.conn.execute("INSERT INTO session_tags (activity_id, verdict) VALUES (?, ?)", (activity_id, verdict))
        return activity_id

    def test_save_tags_updates_only_given_fields(self):
        activity_id = self.add(TODAY, 6)
        save_session_tags(self.conn, activity_id, {"verdict": "loved", "pre_fuel": "snack"})
        save_session_tags(self.conn, activity_id, {"pre_fuel": None})
        tags = get_session_tags(self.conn, activity_id)
        self.assertEqual((tags["verdict"], tags["pre_fuel"]), ("loved", None))
        with self.assertRaises(LookupError):
            save_session_tags(self.conn, "missing", {"verdict": "fine"})

    def test_confirmed_time_of_day_pattern_needs_six_each_side(self):
        start = TODAY - timedelta(days=60)
        # Morning (07:00 Warsaw) hard rides loved; evening (19:00) ones hated.
        for index in range(6):
            self.add(start + timedelta(days=index * 2), 5, verdict="loved")
            self.add(start + timedelta(days=index * 2 + 1), 17, verdict="hated")
        data = build_what_worked(self.conn, TODAY)
        statements = [p["statement"] for p in data["confirmed"]]
        self.assertIn("Hard rides were rated better in the morning than at other times.", statements)
        morning = next(p for p in data["confirmed"] if p["on"] == "in the morning" and p["family"] == "ride_quality")
        self.assertEqual((morning["n_on"], morning["n_off"]), (6, 6))
        context = build_what_worked_coaching_context(self.conn, TODAY)
        self.assertTrue(context["confirmed"])

    def test_small_samples_are_emerging_and_small_gaps_are_ignored(self):
        start = TODAY - timedelta(days=30)
        for index in range(3):
            self.add(start + timedelta(days=index * 2), 5, verdict="loved")
            self.add(start + timedelta(days=index * 2 + 1), 17, verdict="hated")
        data = build_what_worked(self.conn, TODAY)
        self.assertFalse(data["confirmed"])
        self.assertTrue(any(p["on"] == "in the morning" for p in data["emerging"]))

        self.conn.execute("DELETE FROM session_tags")
        for activity_id in [r[0] for r in self.conn.execute("SELECT id FROM activities")]:
            self.conn.execute("INSERT INTO session_tags (activity_id, verdict) VALUES (?, 'fine')", (activity_id,))
        self.assertFalse(build_what_worked(self.conn, TODAY)["emerging"])

    def test_effort_cost_uses_rpe_against_target_without_tags(self):
        start = TODAY - timedelta(days=40)
        for index in range(6):
            self.add(start + timedelta(days=index * 2), 5, rpe=4, intent="easy", activity_type="Ride")
            self.add(start + timedelta(days=index * 2 + 1), 5, rpe=6, intent="easy", activity_type="VirtualRide")
        data = build_what_worked(self.conn, TODAY)
        venue = next(p for p in data["confirmed"] if p["condition"] == "venue")
        self.assertEqual(venue["statement"], "Easy rides felt easier for the same job outdoors than indoors.")
        self.assertEqual(data["tagged_sessions"], 0)

    def test_sick_days_are_excluded(self):
        sick_day = TODAY - timedelta(days=2)
        self.add(sick_day, 6, verdict="hated")
        self.add(TODAY - timedelta(days=5), 6)
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES (?, NULL)", (sick_day.isoformat(),))
        data = build_what_worked(self.conn, TODAY)
        self.assertEqual(data["sessions_considered"], 0)
        self.assertEqual([item["date"] for item in data["untagged_recent"]], [(TODAY - timedelta(days=5)).isoformat()])


if __name__ == "__main__":
    unittest.main()
