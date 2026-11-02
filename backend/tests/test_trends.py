import sqlite3
import unittest
from datetime import date

from backend.app.services.trends import get_trends


class TrendsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE activities (date TEXT NOT NULL, type TEXT NOT NULL, distance_km REAL, duration_min REAL)")
        self.conn.executemany(
            "INSERT INTO activities (date, type, distance_km, duration_min) VALUES (?, ?, ?, ?)",
            [
                ("2026-11-02T07:00:00", "Ride", 30.0, 60.0),  # this week (Monday)
                ("2026-10-27", "WeightTraining", 0.0, 45.0),
                ("2026-10-28", "Workout", 0.0, 30.0),  # rehab routine
                ("2026-10-21", "Hike", 12.0, 300.0),
                ("2026-10-22", "Hike", 10.0, 240.0),
                ("2026-10-23", "WeightTraining", 0.0, 60.0),
                ("2026-08-01", "Ride", 100.0, 200.0),  # before the 12 weeks
                ("2025-03-10", "Ride", 50.0, 120.0),
                ("2025-12-01", "Ride", 70.0, 150.0),  # after today's date last year
                ("2026-09-14", "Run", 5.0, 30.0),
            ],
        )
        self.trends = get_trends(self.conn, today=date(2026, 11, 2))

    def tearDown(self):
        self.conn.close()

    def test_twelve_weeks_oldest_first_ending_this_week(self):
        weeks = self.trends["weeks"]
        self.assertEqual(len(weeks), 12)
        self.assertEqual(weeks[0]["start"], "2026-08-17")
        self.assertEqual(weeks[-1]["start"], "2026-11-02")
        self.assertEqual(weeks[-1]["hours"]["ride"], 1.0)

    def test_week_hours_split_by_group(self):
        last = self.trends["weeks"][-2]
        self.assertEqual(last["hours"]["strength"], 0.75)
        self.assertEqual(last["hours"]["mobility"], 0.5)
        self.assertEqual(last["sessions"], 2)

    def test_week_top_type_names_a_dominant_activity(self):
        trip = self.trends["weeks"][-3]
        self.assertEqual(trip["hours"]["other"], 9.0)
        self.assertEqual(trip["top"], {"type": "Hike", "sessions": 2, "share": 0.9})
        self.assertIsNone(self.trends["weeks"][0]["top"])

    def test_year_so_far_against_same_date_last_year(self):
        ride = next(sport for sport in self.trends["sports"] if sport["sport"] == "ride")
        self.assertEqual(ride["total"], 130.0)
        self.assertEqual(ride["last_year_to_date"], 50.0)
        self.assertEqual(ride["last_year_months"][2], 50.0)
        self.assertEqual(ride["last_year_months"][11], 70.0)

    def test_strength_counts_hours_and_run_keeps_last_date(self):
        sports = {sport["sport"]: sport for sport in self.trends["sports"]}
        self.assertEqual(sports["strength"]["unit"], "h")
        self.assertEqual(sports["strength"]["total"], 1.8)
        self.assertEqual(sports["run"]["last_date"], "2026-09-14")


if __name__ == "__main__":
    unittest.main()
