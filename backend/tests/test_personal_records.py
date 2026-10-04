import json
import sqlite3
import unittest
from datetime import date

from backend.app.services.personal_records import (
    _endurance_sections,
    _rank,
    _streak_section,
    epley_1rm,
    estimate_ftp,
    extract_activity_efforts,
    fastest_distance_window,
)


def steady_streams(distance_m, speed_mps, *, watts=None, hr=140):
    seconds = int(distance_m / speed_mps) + 1
    streams = {
        "time": {"data": list(range(seconds))},
        "distance": {"data": [min(distance_m, t * speed_mps) for t in range(seconds)]},
        "heartrate": {"data": [hr] * seconds},
    }
    if watts is not None:
        streams["watts"] = {"data": [watts] * seconds}
    return streams


class DistanceWindowTests(unittest.TestCase):
    def test_finds_fastest_segment_inside_a_longer_activity(self):
        # 2 km at 4 m/s, then 1 km at 5 m/s, then 2 km at 4 m/s.
        distance, points, t = 0.0, [], 0
        for speed, length in ((4.0, 2000), (5.0, 1000), (4.0, 2000)):
            end = distance + length
            while distance < end:
                points.append((distance, float(t), t))
                distance += speed
                t += 1
        points.append((distance, float(t), t))
        best = fastest_distance_window(points, 1000.0)
        self.assertAlmostEqual(best["duration_s"], 200.0, delta=1.0)

    def test_activity_just_short_of_target_still_counts(self):
        points = [(float(d), float(d), i) for i, d in enumerate(range(0, 4925, 5))]
        self.assertIsNotNone(fastest_distance_window(points, 5000.0))
        self.assertIsNone(fastest_distance_window(points[:900], 5000.0))

    def test_implausible_speed_is_rejected(self):
        efforts = extract_activity_efforts("Run", steady_streams(5000, 10.0), power_meter=False)
        self.assertEqual(efforts["distance"], [])

    def test_run_targets_and_sprint_power(self):
        run = extract_activity_efforts("Run", steady_streams(5100, 3.3), power_meter=False)
        self.assertEqual([e["label"] for e in run["distance"]], ["400m", "1/2 mile", "1K", "1 mile", "2 mile", "5K"])
        ride = extract_activity_efforts("VirtualRide", steady_streams(21000, 9.0, watts=250), power_meter=True)
        self.assertEqual(ride["sprint_power"]["watts"], 250)
        self.assertIn("20K", [e["label"] for e in ride["distance"]])


class RankingTests(unittest.TestCase):
    def entry(self, value, day, activity_id):
        return {"value": value, "display": str(value), "date": day, "activity_id": activity_id}

    def test_tie_goes_to_earlier_date_and_previous_is_reported(self):
        ranked = _rank(
            [self.entry(200, "2026-01-01", "a"), self.entry(220, "2026-02-01", "b"), self.entry(220, "2026-03-01", "c")],
            higher_is_better=True,
        )
        self.assertEqual(ranked["record"]["activity_id"], "b")
        self.assertEqual(ranked["record"]["previous"]["activity_id"], "a")
        self.assertEqual([item["activity_id"] for item in ranked["top"]], ["b", "c", "a"])
        self.assertEqual([item["value"] for item in ranked["progression"]], [200, 220])

    def test_lower_is_better_for_times(self):
        ranked = _rank([self.entry(1500, "2026-01-01", "a"), self.entry(1450, "2026-02-01", "b")], higher_is_better=False)
        self.assertEqual(ranked["record"]["activity_id"], "b")
        self.assertEqual(ranked["record"]["improvement"], 50)


class FtpEstimateTests(unittest.TestCase):
    stored = {"available": True, "watts": 230.0}

    def test_uses_only_recent_efforts(self):
        by_duration = {
            1200: [
                {"value": 260.0, "display": "260 W", "date": "2026-03-01", "activity_id": "old"},
                {"value": 220.0, "display": "220 W", "date": "2026-09-20", "activity_id": "new"},
            ]
        }
        estimate = estimate_ftp(by_duration, self.stored, date(2026, 10, 2))
        self.assertEqual(estimate["watts"], 209)
        self.assertEqual(estimate["source"]["activity_id"], "new")
        self.assertEqual(estimate["difference_from_stored"], -21)

    def test_hour_effort_wins_when_higher(self):
        by_duration = {
            1200: [{"value": 220.0, "display": "", "date": "2026-09-20", "activity_id": "a"}],
            3600: [{"value": 212.0, "display": "", "date": "2026-09-25", "activity_id": "b"}],
        }
        self.assertEqual(estimate_ftp(by_duration, self.stored, date(2026, 10, 2))["basis"], "best 60 min")

    def test_unavailable_without_recent_efforts(self):
        self.assertFalse(estimate_ftp({}, self.stored, date(2026, 10, 2))["available"])


class LiftAndStreakTests(unittest.TestCase):
    def test_epley(self):
        self.assertEqual(epley_1rm(100, 1), 100)
        self.assertAlmostEqual(epley_1rm(80, 10), 106.67, places=2)

    def test_streak_and_milestones(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE activities (id TEXT, date TEXT)")
        days = [f"2026-09-{d:02d}" for d in range(1, 11)] + [f"2026-09-{d:02d}" for d in range(20, 31)] + ["2026-10-01"]
        conn.executemany("INSERT INTO activities VALUES (?, ?)", [(day, day) for day in days])
        streaks = _streak_section(conn, date(2026, 10, 2))
        self.assertEqual(streaks["current"]["days"], 12)
        self.assertEqual(streaks["longest"]["start"], "2026-09-20")
        self.assertEqual(streaks["milestones"][0], {"days": 7, "reached_on": "2026-09-07"})
        self.assertEqual(streaks["next_milestone"], {"days": 14, "days_to_go": 2})


class EnduranceSectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, distance_km REAL,
                duration_min REAL, elevation_m INTEGER, avg_hr INTEGER);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, detail_json TEXT, streams_json TEXT,
                source_status TEXT, updated_at TEXT);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric TEXT, value REAL, date TEXT);
            """
        )
        self.addCleanup(self.conn.close)

    def add(self, activity_id, day, activity_type, streams, detail=None):
        distance = streams["distance"]["data"][-1] / 1000
        self.conn.execute(
            "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, activity_type, activity_id, distance, len(streams["time"]["data"]) / 60, 100, 140),
        )
        self.conn.execute(
            "INSERT INTO activity_details VALUES (?, ?, ?, ?, ?)",
            (activity_id, json.dumps(detail) if detail else None, json.dumps(streams), "streams_backfill", day),
        )

    def test_indoor_distance_is_separate_and_power_counts_everywhere(self):
        self.add("outdoor", "2026-09-01", "Ride", steady_streams(21000, 7.0, watts=200), {"device_watts": True, "trainer": False})
        self.add("zwift", "2026-09-02", "VirtualRide", steady_streams(21000, 10.0, watts=240))
        sections = _endurance_sections(self.conn, date(2026, 10, 2))
        outdoor = {r["label"]: r for r in sections["cycling_distance"]["outdoor"]["records"]}
        indoor = {r["label"]: r for r in sections["cycling_distance"]["indoor"]["records"]}
        self.assertEqual(outdoor["20K"]["record"]["activity_id"], "outdoor")
        self.assertEqual(indoor["20K"]["record"]["activity_id"], "zwift")
        self.assertTrue(outdoor["100K"]["locked"])
        power = {r["duration_seconds"]: r for r in sections["cycling_power"]["records"]}
        self.assertEqual(power[5]["record"]["activity_id"], "zwift")
        self.assertEqual([item["activity_id"] for item in power[60]["top"]], ["zwift", "outdoor"])

    def test_cached_efforts_refresh_when_streams_change(self):
        self.add("run", "2026-09-01", "Run", steady_streams(5000, 3.0))
        first = _endurance_sections(self.conn, date(2026, 10, 2))
        self.conn.execute(
            "UPDATE activity_details SET streams_json = ?, updated_at = ? WHERE activity_id = 'run'",
            (json.dumps(steady_streams(5000, 3.5)), "2026-09-02"),
        )
        second = _endurance_sections(self.conn, date(2026, 10, 2))
        five_k = lambda data: next(r for r in data["running"]["records"] if r["label"] == "5K")["record"]["value"]
        self.assertLess(five_k(second), five_k(first))


if __name__ == "__main__":
    unittest.main()
