import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from fastapi import HTTPException

from backend.app import db
from backend.app.services import today_options

WEEK = "2030-01-07"  # A Monday in the future, so no day is locked as past.
DAYS = [
    ("2030-01-07", "Mon", "WeightTraining", None, "Workout A", 45),
    ("2030-01-08", "Tue", "Ride", "easy", "Easy aerobic ride", 45),
    ("2030-01-09", "Wed", "Rest", None, "Rest", None),
    ("2030-01-10", "Thu", "WeightTraining", None, "Workout B", 45),
    ("2030-01-11", "Fri", "Ride", "interval", "VO2 intervals", 60),
    ("2030-01-12", "Sat", "Rest", None, "Rest", None),
    ("2030-01-13", "Sun", "Ride", "easy", "Easy ride", 25),
]


class TodayOptionsTests(unittest.TestCase):
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
        days = [
            {"date": day, "label": label, "session_type": kind, "workout_intent": intent, "title": title, "target_duration_min": minutes}
            for day, label, kind, intent, title, minutes in DAYS
        ]
        self.conn.execute(
            "INSERT INTO weekly_plans (week_start, title, days_json) VALUES (?, ?, ?)",
            (WEEK, "Test week", json.dumps(days)),
        )
        self.conn.commit()

    def options(self, reason, day):
        return today_options.build_today_options(self.conn, reason, date.fromisoformat(day))

    def plan_day(self, day):
        days = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])
        return next(item for item in days if item["date"] == day)

    def test_a_flat_hard_ride_gets_an_easy_version_a_move_to_rest_and_rest(self):
        state = self.options("flat", "2030-01-11")
        self.assertEqual([option["key"] for option in state["options"]], ["easy", "move", "rest"])
        easy = state["options"][0]
        self.assertEqual(easy["label"], "Easy version")
        self.assertEqual(easy["day"]["workout_intent"], "easy")
        self.assertEqual(easy["day"]["target_duration_min"], 35)
        self.assertEqual(easy["summary"], "35 min in Zone 2 instead of 60 min of interval.")
        self.assertEqual(state["options"][1]["to_date"], "2030-01-12")

    def test_a_flat_lift_stays_a_lift_and_is_never_rested(self):
        state = self.options("flat", "2030-01-07")
        keys = [option["key"] for option in state["options"]]
        self.assertNotIn("rest", keys)
        self.assertEqual(state["options"][0]["label"], "Lighter version")
        self.assertEqual(state["options"][0]["day"]["session_type"], "WeightTraining")
        # Tuesday's easy ride is lighter, so today becomes the ride and the lift moves a day.
        move = next(option for option in state["options"] if option["key"] == "move")
        self.assertEqual(move["to_date"], "2030-01-08")
        self.assertEqual(move["summary"], "Swap with Tuesday (easy aerobic ride), so today gets Tuesday's plan.")
        # From Tuesday, Wednesday's rest sits next to Thursday's lift, so the lift goes to Saturday.
        self.conn.execute("UPDATE weekly_plans SET days_json = replace(days_json, '\"Ride\", \"workout_intent\": \"easy\", \"title\": \"Easy aerobic ride\"', '\"WeightTraining\", \"workout_intent\": null, \"title\": \"Workout A\"')")
        tuesday = self.options("flat", "2030-01-08")
        self.assertEqual(next(o for o in tuesday["options"] if o["key"] == "move")["to_date"], "2030-01-12")

    def test_short_on_time_offers_a_quick_version_unless_today_is_already_short(self):
        self.assertEqual([option["key"] for option in self.options("short", "2030-01-08")["options"]], ["quick", "move", "minimum_week"])
        sunday = self.options("short", "2030-01-13")
        self.assertEqual([option["key"] for option in sunday["options"]], ["minimum_week"])
        self.assertIn("already short", sunday["message"])

    def test_a_walk_does_not_lock_today_and_undo_puts_the_session_back(self):
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('walk', '2030-01-08', 'Walk', 'Walk', 30)")
        before = self.plan_day("2030-01-08")
        result = today_options.apply_today_option(self.conn, "flat", "rest", date(2030, 1, 8))
        self.assertEqual(result["applied"], "Feeling flat: rest today")
        self.assertEqual(self.plan_day("2030-01-08")["session_type"], "Rest")

        today_options.undo_today_option(self.conn, result["undo"], date(2030, 1, 8))
        after = self.plan_day("2030-01-08")
        self.assertEqual({k: after[k] for k in ("session_type", "workout_intent", "title", "target_duration_min")},
                         {k: before[k] for k in ("session_type", "workout_intent", "title", "target_duration_min")})
        reasons = [row[0] for row in self.conn.execute("SELECT adaptation_reason FROM plan_revisions ORDER BY id")]
        self.assertEqual(reasons, ["Feeling flat: rest today", "Undid today's change"])

    def test_a_move_swaps_and_undo_swaps_back(self):
        result = today_options.apply_today_option(self.conn, "flat", "move", date(2030, 1, 11))
        self.assertEqual(self.plan_day("2030-01-11")["title"], "Rest")
        self.assertEqual(self.plan_day("2030-01-12")["title"], "VO2 intervals")
        today_options.undo_today_option(self.conn, result["undo"], date(2030, 1, 11))
        self.assertEqual(self.plan_day("2030-01-11")["title"], "VO2 intervals")

    def test_nothing_to_change_after_training_or_on_a_rest_day(self):
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('r', '2030-01-08', 'Ride', 'Ride', 45)")
        self.assertFalse(self.options("flat", "2030-01-08")["available"])
        self.assertFalse(self.options("flat", "2030-01-09")["available"])
        with self.assertRaises(HTTPException):
            today_options.apply_today_option(self.conn, "flat", "rest", date(2030, 1, 8))
        with self.assertRaises(HTTPException):
            today_options.undo_today_option(self.conn, {"action": "adjust", "effective_from": "2030-01-10", "days": []}, date(2030, 1, 8))


if __name__ == "__main__":
    unittest.main()
