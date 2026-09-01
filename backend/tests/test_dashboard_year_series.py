import sqlite3
import unittest
from datetime import datetime

from backend.app.services.dashboard import build_yearly_distance_series, build_yearly_duration_series


class DashboardYearSeriesTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE activities (
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                distance_km REAL,
                duration_min REAL
            )
            """
        )
        current_year = datetime.now().year
        self.conn.executemany(
            "INSERT INTO activities (date, type, distance_km, duration_min) VALUES (?, ?, ?, ?)",
            [
                (f"{current_year}-01-05", "Ride", 40.0, 120.0),
                (f"{current_year}-01-12", "Ride", 20.0, 60.0),
                (f"{current_year}-01-08", "WeightTraining", 0.0, 45.0),
            ],
        )

    def tearDown(self):
        self.conn.close()

    def test_distance_series_includes_monthly_time_and_session_counts(self):
        january = build_yearly_distance_series(self.conn, ("Ride",))[0]

        self.assertEqual(january["monthly_km"], 60.0)
        self.assertEqual(january["monthly_hours"], 3.0)
        self.assertEqual(january["monthly_sessions"], 2)
        self.assertEqual(january["cumulative_sessions"], 2)

    def test_duration_series_includes_monthly_and_cumulative_session_counts(self):
        january = build_yearly_duration_series(self.conn, ("WeightTraining",))[0]

        self.assertEqual(january["monthly_hours"], 0.8)
        self.assertEqual(january["monthly_sessions"], 1)
        self.assertEqual(january["cumulative_sessions"], 1)


if __name__ == "__main__":
    unittest.main()
