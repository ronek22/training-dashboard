import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.services import cycling_season

TODAY = date(2030, 6, 15)


class CyclingSeasonTests(unittest.TestCase):
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

    def add(self, activity_id, day, kind="Ride", minutes=60, distance=None, elevation=None, trainer=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, elevation_m) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, f"{kind} {activity_id}", minutes, distance, elevation),
        )
        if trainer is not None:
            self.conn.execute(
                "INSERT INTO activity_details (activity_id, fetched_at, source_status, detail_json) VALUES (?, ?, 'ok', ?)",
                (activity_id, "2030-01-01", json.dumps({"trainer": trainer})),
            )
        self.conn.commit()

    def season(self):
        return cycling_season.build_cycling_season(self.conn, today=TODAY)

    def test_outdoor_totals_compare_with_the_same_stretch_of_last_year(self):
        self.add("a", "2030-03-02T08:00:00", "Ride", 120, 50.0, 400)
        self.add("b", "2030-05-20", "GravelRide", 60, 25.0, 100)
        self.add("zwift", "2030-01-10", "VirtualRide", 90, 40.0, 300)
        self.add("trainer", "2030-02-10", "Ride", 60, 30.0, 0, trainer=True)
        self.add("last", "2029-04-01", "Ride", 180, 80.0, 900)
        self.add("later", "2029-08-01", "Ride", 300, 140.0, 1500)
        self.add("future", "2030-07-01", "Ride", 60, 30.0)

        result = self.season()

        self.assertEqual(result["outdoor"], {"rides": 2, "km": 75.0, "elevation": 500, "hours": 3.0})
        self.assertEqual(result["last_year"], {"rides": 1, "km": 80.0, "elevation": 900, "hours": 3.0})
        self.assertEqual(result["longest"]["id"], "a")
        self.assertEqual(result["longest_last_year"]["id"], "last")

    def test_months_cover_the_last_year_split_by_hours_indoors_and_out(self):
        self.add("old", "2029-06-30", "Ride", 60, 30.0)
        self.add("zwift", "2030-01-10", "VirtualRide", 90, 40.0)
        self.add("trainer", "2030-01-12", "Ride", 30, 15.0, trainer=True)
        self.add("road", "2030-06-01", "Ride", 120, 50.0)

        months = self.season()["months"]

        self.assertEqual([m["month"] for m in months][0], "2029-07")
        self.assertEqual(months[-1]["month"], "2030-06")
        self.assertEqual(len(months), 12)
        january = next(m for m in months if m["month"] == "2030-01")
        self.assertEqual((january["indoor_hours"], january["outdoor_hours"], january["indoor_km"]), (2.0, 0.0, 55))
        self.assertEqual(months[-1]["outdoor_hours"], 2.0)

    def test_empty_season(self):
        result = self.season()
        self.assertEqual(result["outdoor"]["rides"], 0)
        self.assertIsNone(result["longest"])


if __name__ == "__main__":
    unittest.main()
