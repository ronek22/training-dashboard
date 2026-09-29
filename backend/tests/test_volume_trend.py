import json
import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.volume_trend import build_volume_trend, save_volume_trend_label

SCHEMA = """
CREATE TABLE activities (id INTEGER PRIMARY KEY, date TEXT, type TEXT, duration_min REAL);
CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, title TEXT, days_json TEXT);
CREATE TABLE volume_trend_labels (
    week_start TEXT PRIMARY KEY, label TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

TODAY = date(2026, 9, 30)  # Wednesday; last completed week starts 2026-09-21
CURRENT_WEEK = TODAY - timedelta(days=TODAY.weekday())


def week(offset):
    return CURRENT_WEEK - timedelta(weeks=offset)


class VolumeTrendTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def add_week(self, offset, minutes, sessions=2, activity_type="Ride"):
        for index in range(sessions):
            self.conn.execute(
                "INSERT INTO activities (date, type, duration_min) VALUES (?, ?, ?)",
                ((week(offset) + timedelta(days=index)).isoformat(), activity_type, minutes / sessions),
            )

    def add_plan(self, offset, minutes, title="Normal week"):
        days = [{"date": week(offset).isoformat(), "session_type": "ride", "target_duration_min": minutes},
                {"date": (week(offset) + timedelta(days=1)).isoformat(), "session_type": "walk", "target_duration_min": 60}]
        self.conn.execute("INSERT INTO weekly_plans VALUES (?, ?, ?)", (week(offset).isoformat(), title, json.dumps(days)))

    def seed_slide(self, recent=(700, 460, 340)):
        for offset in (7, 6, 5, 4):
            self.add_week(offset, 650)
        for offset, minutes in zip((3, 2, 1), recent):
            self.add_week(offset, minutes)

    def test_alerts_on_two_consecutive_unplanned_drops(self):
        self.seed_slide()
        self.add_week(0, 900)  # the week in progress never counts
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertEqual(trend["status"], "sliding")
        self.assertTrue(trend["alert"])
        self.assertEqual([item["total_min"] for item in trend["weeks"]], [700, 460, 340])
        self.assertEqual(trend["week_start"], week(1).isoformat())
        self.assertEqual(trend["drop_pct"], 51)
        self.assertIn("700 → 460 → 340", trend["message"])

    def test_walks_are_not_training_volume(self):
        self.seed_slide(recent=(700, 460, 340))
        self.add_week(1, 600, activity_type="Walk")
        self.assertTrue(build_volume_trend(self.conn, today=TODAY)["alert"])

    def test_no_alert_when_not_consecutive_or_drop_is_small(self):
        self.seed_slide(recent=(700, 720, 340))
        self.assertEqual(build_volume_trend(self.conn, today=TODAY)["status"], "steady")
        self.conn.execute("DELETE FROM activities")
        self.seed_slide(recent=(660, 640, 620))
        self.assertEqual(build_volume_trend(self.conn, today=TODAY)["status"], "steady")

    def test_planned_lighter_weeks_do_not_alert(self):
        self.seed_slide()
        for offset in (5, 4, 3):
            self.add_plan(offset, 400)
        self.add_plan(2, 330)  # well under the previous plans
        self.add_plan(1, 400, title="Deload week")
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertEqual(trend["status"], "planned_lighter")
        self.assertFalse(trend["alert"])

    def test_steady_low_plan_is_not_a_planned_drop(self):
        # Beating a consistently modest plan by less each week is still a slide.
        self.seed_slide()
        for offset in (5, 4, 3, 2, 1):
            self.add_plan(offset, 340)
        self.assertTrue(build_volume_trend(self.conn, today=TODAY)["alert"])

    def test_insufficient_data_never_alerts(self):
        for offset, minutes in zip((3, 2, 1), (700, 460, 340)):
            self.add_week(offset, minutes)
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertEqual(trend["status"], "insufficient_data")
        self.assertFalse(trend["alert"])

    def test_label_hides_alert_and_is_reported(self):
        self.seed_slide()
        save_volume_trend_label(self.conn, week(1).isoformat(), "life", "Busy at work")
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertEqual(trend["status"], "sliding")
        self.assertFalse(trend["alert"])
        self.assertEqual(trend["label"]["label"], "life")
        self.assertEqual(trend["label"]["label_text"], "Life got in the way")
        self.assertEqual(trend["label"]["note"], "Busy at work")


if __name__ == "__main__":
    unittest.main()
