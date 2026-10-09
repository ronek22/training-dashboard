import json
import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.life_load import set_life_load_day
from backend.app.services.volume_trend import build_volume_trend, save_volume_trend_label

SCHEMA = """
CREATE TABLE activities (id INTEGER PRIMARY KEY, date TEXT, type TEXT, duration_min REAL);
CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, title TEXT, days_json TEXT);
CREATE TABLE volume_trend_labels (
    week_start TEXT PRIMARY KEY, label TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE daily_checkins (
    date TEXT PRIMARY KEY, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL, stress INTEGER NOT NULL,
    sleep_quality INTEGER NOT NULL, pain_level INTEGER NOT NULL DEFAULT 0, note TEXT
);
CREATE TABLE sick_periods (id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT, severity TEXT, note TEXT);
CREATE TABLE life_load_days (
    date TEXT PRIMARY KEY, tags_json TEXT NOT NULL, note TEXT,
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

    def test_three_life_load_days_in_a_falling_week_read_as_life(self):
        self.seed_slide()
        for index in range(3):
            set_life_load_day(self.conn, (week(1) + timedelta(days=index)).isoformat(), ["deadline"])
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertFalse(trend["alert"])
        self.assertEqual((trend["label"]["label"], trend["label"]["note"]), ("life", "Life-load tags"))

    def test_two_life_load_days_still_alert(self):
        self.seed_slide()
        for index in range(2):
            set_life_load_day(self.conn, (week(1) + timedelta(days=index)).isoformat(), ["travel"])
        self.assertTrue(build_volume_trend(self.conn, today=TODAY)["alert"])

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


    def add_checkins(self, offset, sleep, stress, energy=3, days=5):
        for index in range(days):
            self.conn.execute(
                "INSERT INTO daily_checkins (date, energy, muscle_soreness, stress, sleep_quality) VALUES (?, ?, 2, ?, ?)",
                ((week(offset) + timedelta(days=index)).isoformat(), energy, stress, sleep),
            )

    def add_session_plan(self, offset, dates):
        days = [{"date": (week(offset) + timedelta(days=index)).isoformat(), "session_type": kind, "target_duration_min": 60}
                for index, kind in dates]
        self.conn.execute("INSERT INTO weekly_plans VALUES (?, ?, ?)", (week(offset).isoformat(), "Normal week", json.dumps(days)))

    def test_reason_reads_busy_days_and_low_sleep_as_life_not_motivation(self):
        self.seed_slide()
        for offset in (5, 4):
            self.add_checkins(offset, sleep=4, stress=2)
        self.add_checkins(2, sleep=2, stress=3)
        self.add_checkins(1, sleep=2, stress=3)
        set_life_load_day(self.conn, week(2).isoformat(), ["deadline"])
        set_life_load_day(self.conn, (week(1) + timedelta(days=3)).isoformat(), ["deadline"])
        # Planned Thursday ride in W2 fell on no tag; Thursday in W1 is the tagged deadline day.
        self.add_session_plan(1, [(0, "ride"), (1, "ride"), (3, "run")])
        trend = build_volume_trend(self.conn, today=TODAY)
        reason = trend["reason"]
        self.assertTrue(trend["alert"])
        self.assertEqual(reason["cause"], "life")
        self.assertIn("2 weeks down, mostly deadline (2 days), low sleep", reason["summary"])
        self.assertIn("not lost motivation", reason["summary"])
        self.assertEqual((reason["signals"]["skipped_sessions"], reason["signals"]["skipped_on_busy_days"]), (1, 1))
        self.assertIn("minimum week", reason["next_step"])
        self.assertIn("best-slept day", reason["next_step"])

    def test_reason_calls_out_skips_on_ordinary_days(self):
        self.seed_slide()
        self.add_session_plan(2, [(0, "ride"), (1, "ride"), (3, "run"), (5, "run")])
        self.add_session_plan(1, [(0, "ride"), (1, "ride"), (4, "run")])
        reason = build_volume_trend(self.conn, today=TODAY)["reason"]
        self.assertEqual(reason["cause"], "skipped")
        self.assertEqual(reason["signals"]["skipped_by_type"], {"Run": 3})
        self.assertIn("3 of 7 planned sessions skipped (mostly runs)", reason["summary"])
        self.assertIn("run you keep missing", reason["next_step"])
        self.assertNotIn("motivation", reason["summary"])

    def test_moved_sessions_are_not_counted_as_skipped(self):
        self.seed_slide()
        # Planned Thursday, trained Tuesday instead: one unmatched day offset by one unplanned day.
        self.add_session_plan(1, [(0, "ride"), (3, "ride")])
        reason = build_volume_trend(self.conn, today=TODAY)["reason"]
        self.assertEqual(reason["signals"]["skipped_sessions"], 0)
        self.assertEqual(reason["cause"], "shorter")

    def test_fewer_sessions_with_no_plan_or_signals_is_unclear(self):
        for offset in (7, 6, 5, 4):
            self.add_week(offset, 650, sessions=4)
        for offset, minutes in zip((3, 2, 1), (700, 460, 340)):
            self.add_week(offset, minutes, sessions=2)
        reason = build_volume_trend(self.conn, today=TODAY)["reason"]
        self.assertEqual(reason["cause"], "unclear")
        self.assertIn("nothing logged to explain it", reason["summary"])

    def test_reason_reads_sick_weeks_as_illness(self):
        self.seed_slide()
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date, severity) VALUES (?, ?, 'below_neck')",
                          (week(1).isoformat(), (week(1) + timedelta(days=4)).isoformat()))
        trend = build_volume_trend(self.conn, today=TODAY)
        self.assertFalse(trend["alert"])
        self.assertEqual(trend["reason"]["cause"], "illness")
        self.assertIn("illness (5 sick days)", trend["reason"]["summary"])
        self.assertIn("Ease back in", trend["reason"]["next_step"])
        # 60% of the usual 650 min, since that is below 1.2x last week (408).
        self.assertIn("around 390 min", trend["reason"]["next_step"])

    def test_illness_restart_stays_near_last_week(self):
        self.seed_slide(recent=(700, 300, 150))
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date, severity) VALUES (?, ?, 'below_neck')",
                          (week(1).isoformat(), (week(1) + timedelta(days=4)).isoformat()))
        self.assertIn("around 180 min", build_volume_trend(self.conn, today=TODAY)["reason"]["next_step"])

    def test_one_skip_does_not_explain_a_big_drop(self):
        self.seed_slide()
        self.add_session_plan(2, [(0, "ride"), (1, "ride"), (3, "strength")])
        self.add_session_plan(1, [(0, "ride"), (1, "ride")])
        reason = build_volume_trend(self.conn, today=TODAY)["reason"]
        self.assertEqual(reason["signals"]["skipped_sessions"], 1)
        self.assertEqual(reason["cause"], "shorter")
        self.assertIn("not from skipping", reason["summary"])
        self.assertIn("usual length", reason["next_step"])

    def test_steady_weeks_have_no_reason(self):
        self.seed_slide(recent=(660, 640, 620))
        self.assertNotIn("reason", build_volume_trend(self.conn, today=TODAY))


if __name__ == "__main__":
    unittest.main()
