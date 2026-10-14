import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.services import season_history

TODAY = date(2030, 6, 15)


class SeasonHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def add(self, activity_id, day, kind="Ride", minutes=60, distance=None, elevation=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, elevation_m) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, f"{kind} {activity_id}", minutes, distance, elevation),
        )
        self.conn.commit()

    def history(self, sport="ride"):
        return season_history.build_season_history(self.conn, sport, today=TODAY)

    def test_rides_split_outdoor_and_trainer_with_empty_years_kept(self):
        self.add("a", "2027-05-02T08:00:00", "Ride", 120, 50.0, 400)
        self.add("b", "2027-05-20", "GravelRide", 60, 25.0, 100)
        self.add("c", "2030-01-10", "VirtualRide", 90, 40.0, 300)
        self.add("d", "2030-01-10", "Ride", 30, 10.0, None)
        self.add("run", "2030-02-01", "Run", 30, 5.0)
        self.add("future", "2030-07-01", "Ride", 60, 30.0)

        result = self.history()

        self.assertEqual([item["key"] for item in result["parts"]], ["outdoor", "trainer"])
        self.assertEqual([item["year"] for item in result["years"]], [2030, 2029, 2028, 2027])
        now, gap, _, first = result["years"]
        self.assertFalse(now["complete"])
        self.assertTrue(first["complete"])
        self.assertEqual(gap["total"]["sessions"], 0)
        self.assertEqual(first["total"], {"km": 75.0, "hours": 3.0, "elevation": 500, "sessions": 2})
        self.assertEqual(first["months"][4]["parts"]["outdoor"]["km"], 75.0)
        self.assertEqual(now["parts"]["trainer"]["km"], 40.0)
        self.assertEqual(now["parts"]["outdoor"]["km"], 10.0)
        self.assertEqual(now["days"], [["2030-01-10", 50.0, 2.0, 300, 2]])
        self.assertEqual(result["best"]["km"], {"year": 2027, "value": 75.0})

    def test_strength_shows_time_and_sessions_only(self):
        self.add("s", "2029-03-03", "WeightTraining", 45)

        result = self.history("strength")

        self.assertEqual([item["key"] for item in result["metrics"]], ["hours", "sessions"])
        self.assertEqual(result["years"][1]["total"], {"hours": 0.8, "sessions": 1})
        self.assertNotIn("km", result["best"])

    def test_no_activities_and_unknown_sport(self):
        self.assertEqual(self.history("hike")["years"], [])
        with self.assertRaises(ValueError):
            self.history("chess")


if __name__ == "__main__":
    unittest.main()
