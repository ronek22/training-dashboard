import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.services.arc_suggest import default_window, suggestion_context
from backend.app.services.life_load import set_life_load_day

TODAY = date(2026, 11, 5)  # Thursday


class ArcSuggestTests(unittest.TestCase):
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

    def add(self, day, kind, minutes):
        self.conn.execute("INSERT INTO activities (date, type, name, duration_min) VALUES (?, ?, 'x', ?)", (day, kind, minutes))

    def test_window_starts_next_monday_after_tuesday_and_ends_last_sunday_of_february(self):
        self.assertEqual(default_window(TODAY), ("2026-11-09", "2027-02-28"))
        self.assertEqual(default_window(date(2026, 11, 3)), ("2026-11-02", "2027-02-28"))
        self.assertEqual(default_window(date(2027, 1, 14)), ("2027-01-18", "2027-02-28"))

    def test_weeks_count_rides_runs_and_lifts_per_week_and_skip_this_week(self):
        self.add("2026-10-27", "Ride", 90)
        self.add("2026-10-29", "VirtualRide", 60)
        self.add("2026-10-30", "Run", 30)
        self.add("2026-10-31", "WeightTraining", 50)
        self.add("2026-11-04", "Ride", 120)  # This week: not a full week yet.
        context = suggestion_context(self.conn, TODAY)
        self.assertEqual(len(context["weeks"]), 12)
        last = context["weeks"][-1]
        self.assertEqual(last, {"week_start": "2026-10-26", "ride_hours": 2.5, "rides": 2, "runs": 1, "lifts": 1})
        self.assertEqual(context["window"], {"start": "2026-11-09", "end": "2027-02-28"})
        self.assertEqual(context["current_arc"], [])

    def test_busy_weeks_group_tagged_days_ahead(self):
        set_life_load_day(self.conn, "2026-12-01", ["travel"])
        set_life_load_day(self.conn, "2026-12-03", ["travel"])
        context = suggestion_context(self.conn, TODAY)
        self.assertEqual(context["busy_weeks"], [{"week_start": "2026-11-30", "days": 2, "tags": ["travel"]}])


if __name__ == "__main__":
    unittest.main()
