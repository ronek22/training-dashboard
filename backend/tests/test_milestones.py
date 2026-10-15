import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.milestones import build_milestones, detect_milestones, mark_seen, milestone_detail


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE activities (id TEXT, date TEXT, type TEXT, name TEXT, distance_km REAL, duration_min REAL, elevation_m INTEGER);
        CREATE TABLE sick_session_completions (date TEXT);
        CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    return conn


def add(conn, day, kind="Ride", km=20.0, minutes=60.0):
    conn.execute("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, 0)", (f"{day}-{kind}-{km}", day.isoformat(), kind, kind, km, minutes))


class StreakMilestoneTests(unittest.TestCase):
    def test_streak_reaches_100_and_300_with_light_and_guided_days(self):
        conn = make_conn()
        start = date(2026, 1, 3)
        for offset in range(300):
            day = start + timedelta(days=offset)
            if offset == 50:
                conn.execute("INSERT INTO sick_session_completions VALUES (?)", (day.isoformat(),))
            elif offset % 7 == 6:
                add(conn, day, "Walk", km=2.0, minutes=15)  # A light recovery day keeps the streak.
            else:
                add(conn, day, "Ride", km=0.0)
        items = {item["id"]: item for item in detect_milestones(conn, date(2026, 10, 29))}
        self.assertEqual(items["streak-100-2026-01-03"]["reached_on"], "2026-04-12")
        self.assertEqual(items["streak-300-2026-01-03"]["reached_on"], "2026-10-29")
        self.assertTrue(items["streak-300-2026-01-03"]["celebrate"])
        self.assertFalse(items["streak-100-2026-01-03"]["celebrate"])  # Long past: shelf only.

        detail = milestone_detail(conn, "streak-300-2026-01-03", date(2026, 10, 29))
        self.assertEqual(len(detail["grid"]), 300)
        self.assertEqual(detail["grid"][50]["sport"], "guided")
        self.assertTrue(detail["grid"][6]["light"])
        light = next(item for item in detail["highlights"] if item["key"] == "light")
        self.assertEqual(light["value"], 300 // 7 + 1)  # 42 walks plus the guided session.

    def test_broken_streak_does_not_reach_milestone(self):
        conn = make_conn()
        for offset in range(120):
            if offset != 60:
                add(conn, date(2026, 1, 1) + timedelta(days=offset), km=0.0)
        self.assertEqual([item for item in detect_milestones(conn, date(2026, 5, 1)) if item["kind"] == "streak"], [])

    def test_next_streak_milestone_date(self):
        conn = make_conn()
        start = date(2026, 1, 3)
        for offset in range(286):
            add(conn, start + timedelta(days=offset), km=0.0)
        upcoming = build_milestones(conn, date(2026, 10, 15))["next"]
        self.assertEqual(upcoming[0], {"kind": "streak", "label": "300-day streak", "current": 286, "target": 300,
                                       "to_go": 14, "unit": "days", "on": "2026-10-29"})


class LiftAndKmMilestoneTests(unittest.TestCase):
    def test_four_lift_weeks_in_a_row(self):
        conn = make_conn()
        monday = date(2026, 9, 14)
        for week in range(4):
            for day in (0, 2, 4):
                add(conn, monday + timedelta(weeks=week, days=day), "WeightTraining", km=0.0, minutes=45)
        add(conn, monday, "Ride", km=40.0, minutes=90)  # A longer ride on a lift day.
        add(conn, monday + timedelta(weeks=4), "WeightTraining", km=0.0)  # Only one session in week 5.
        lifts = [item for item in detect_milestones(conn, date(2026, 10, 15)) if item["kind"] == "lift"]
        self.assertEqual([item["id"] for item in lifts], ["lift3x-4-2026-09-14"])
        self.assertEqual(lifts[0]["reached_on"], "2026-10-09")  # The third session of the fourth week.
        grid = milestone_detail(conn, lifts[0]["id"], date(2026, 10, 15))["grid"]
        self.assertEqual(grid[0]["sport"], "strength")  # Lift days show as strength on the lift grid.

    def test_two_session_week_breaks_the_run(self):
        conn = make_conn()
        monday = date(2026, 9, 7)
        for week in range(5):
            for day in ((0, 2) if week == 2 else (0, 2, 4)):
                add(conn, monday + timedelta(weeks=week, days=day), "WeightTraining", km=0.0)
        self.assertEqual([item for item in detect_milestones(conn, date(2026, 10, 15)) if item["kind"] == "lift"], [])

    def test_year_km_crossing_resets_each_year(self):
        conn = make_conn()
        for offset in range(12):
            add(conn, date(2025, 12, 1) + timedelta(days=offset * 5), "Ride", km=100.0)
        items = {item["id"] for item in detect_milestones(conn, date(2026, 1, 31))}
        self.assertEqual(items, set())  # 700 km in 2025 and 500 km in 2026: 1,000 km spans two years.
        conn2 = make_conn()
        for offset in range(10):
            add(conn2, date(2026, 3, 1) + timedelta(days=offset), "VirtualRide", km=100.0)
        crossed = {item["id"]: item for item in detect_milestones(conn2, date(2026, 3, 20))}["year-2026-ride-1000"]
        self.assertEqual(crossed["reached_on"], "2026-03-10")


class CelebrateOnceTests(unittest.TestCase):
    def test_pending_until_seen_then_shelf_only(self):
        conn = make_conn()
        for offset in range(10):
            add(conn, date(2026, 10, 1) + timedelta(days=offset), "Ride", km=100.0)
        today = date(2026, 10, 15)
        self.assertEqual(build_milestones(conn, today)["pending"], "year-2026-ride-1000")
        mark_seen(conn, "year-2026-ride-1000", today)
        mark_seen(conn, "year-2026-ride-1000", date(2026, 10, 16))  # The first viewing date is kept.
        result = build_milestones(conn, today)
        self.assertIsNone(result["pending"])
        self.assertEqual(result["milestones"][0]["seen_on"], "2026-10-15")
        self.assertFalse(build_milestones(make_conn(), today)["milestones"])

    def test_old_unseen_milestone_does_not_pop_up(self):
        conn = make_conn()
        for offset in range(10):
            add(conn, date(2026, 3, 1) + timedelta(days=offset), "Ride", km=100.0)
        self.assertIsNone(build_milestones(conn, date(2026, 10, 15))["pending"])


if __name__ == "__main__":
    unittest.main()
