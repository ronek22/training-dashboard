import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from backend.app import db
from backend.app.services import monthly_letters

TODAY = date(2030, 10, 3)  # The letter for September 2030 is on offer.


class MonthlyLetterTests(unittest.TestCase):
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
        sleep = mock.patch.object(monthly_letters, "get_sleep_history", return_value=[])
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def add(self, activity_id, day, kind="WeightTraining", minutes=45, distance=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, f"{kind} {activity_id}", minutes, distance),
        )
        self.conn.commit()

    def letter(self, month="2030-09"):
        return monthly_letters.build_monthly_letter(self.conn, month, today=TODAY)

    def test_an_empty_month_gets_a_short_honest_letter(self):
        result = self.letter()

        self.assertTrue(result["thin"])
        self.assertEqual(result["wins"], [])
        self.assertIsNone(result["pattern"])
        self.assertIn("Nothing was logged in September", result["opening"])
        self.assertEqual(result["focus"]["source"], "restart")

    def test_a_thin_month_does_not_turn_showing_up_into_a_win(self):
        self.add("a", "2030-09-03")
        self.add("b", "2030-09-20", "Run", 30)

        result = self.letter()

        self.assertTrue(result["thin"])
        self.assertEqual(result["wins"], [])
        self.assertIn("2 training sessions", result["opening"])
        self.assertIn("stays short", result["opening"])

    def test_a_record_beaten_cites_the_old_best_and_links_the_activity(self):
        self.add("aug", "2030-08-10", "Ride", 120, 60.0)
        self.add("sep", "2030-09-14", "Ride", 150, 82.5)
        # A first ever run is not a beaten record.
        self.add("run", "2030-09-15", "Run", 30, 5.0)

        result = self.letter()

        record = next(win for win in result["wins"] if win["kind"] == "record")
        self.assertIn("82.5 km", record["headline"])
        self.assertIn("up from 60.0 km", record["detail"])
        self.assertIn({"to": "/activities/sep", "label": "Longest ride · 14 Sep"}, record["links"])
        self.assertNotIn("run", record["headline"].lower())

    def test_kept_anchor_goal_streak_and_consistency_are_the_three_wins(self):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2029-01-07', '2029-01-13', 1, 'active', 'anchor')"
        )
        self.add("jul", "2030-07-10", "Ride", 60)
        start = date(2030, 9, 1)
        for offset in range(30):
            day = (start + timedelta(days=offset)).isoformat()
            self.add(f"d{offset}", day, "WeightTraining" if offset % 2 else "Walk", 40)

        result = self.letter()

        kinds = [win["kind"] for win in result["wins"]]
        self.assertEqual(kinds, ["streak", "goal", "consistency"])
        self.assertEqual(result["wins"][0]["headline"], "First 30-day streak")
        goal = result["wins"][1]
        self.assertEqual(goal["headline"], "Lift three times per week: kept")
        self.assertIn("Kept in 4 of 4 full weeks", goal["detail"])
        self.assertIn("anchor goal", goal["detail"])
        self.assertIn("on 30 of 30 days", result["wins"][2]["detail"])
        self.assertFalse(result["thin"])

    def test_a_streak_carried_in_from_last_month_shows_its_full_length(self):
        for offset in range(60):  # Every milestone up to 50 days was reached back in March.
            self.add(f"m{offset}", (date(2030, 3, 1) + timedelta(days=offset)).isoformat(), "Walk", 30)
        for offset in range(42):
            self.add(f"s{offset}", (date(2030, 8, 20) + timedelta(days=offset)).isoformat(), "Walk", 30)

        streak = next(win for win in self.letter()["wins"] if win["kind"] == "streak")

        self.assertEqual(streak["headline"], "Active every day of September")
        self.assertEqual(streak["detail"], "Active every day from 1 Sep to 30 Sep, a streak of 42 days by then.")

    def test_a_missed_weekly_goal_becomes_the_focus(self):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2029-01-07', '2029-01-13', 1, 'active', 'anchor')"
        )
        for offset in (1, 3, 8, 10, 15, 17, 22, 23, 24):
            self.add(f"l{offset}", (date(2030, 9, 1) + timedelta(days=offset)).isoformat())

        focus = self.letter()["focus"]

        self.assertEqual(focus["headline"], "Protect Lift three times per week")
        self.assertIn("Kept in 1 of 4 full weeks", focus["detail"])

    def test_short_sleep_is_the_pattern_with_its_numbers(self):
        nights = [{"date": (date(2030, 7, 1) + timedelta(days=offset)).isoformat(), "value": 7.5} for offset in range(62)]
        nights += [{"date": (date(2030, 9, 1) + timedelta(days=offset)).isoformat(), "value": 6.5} for offset in range(30)]
        self.sleep.return_value = list(reversed(nights))
        for offset in range(0, 30, 3):
            self.add(f"s{offset}", (date(2030, 9, 1) + timedelta(days=offset)).isoformat())

        result = self.letter()

        self.assertEqual(result["pattern"]["source"], "sleep")
        self.assertEqual(result["pattern"]["headline"], "Sleep ran about 60 min a night short")
        self.assertIn("6.5 h a night over 30 nights against your usual 7.5 h", result["pattern"]["detail"])
        self.assertEqual(result["focus"]["source"], "sleep")

    def test_a_saved_letter_never_changes_and_only_finished_months_are_written(self):
        self.add("a", "2030-09-03")
        first, created = monthly_letters.write_letter(self.conn, "2030-09", today=TODAY)
        self.assertTrue(created)

        for offset in range(10):
            self.add(f"late{offset}", f"2030-09-{10 + offset}")
        again, created = monthly_letters.write_letter(self.conn, "2030-09", today=TODAY)

        self.assertFalse(created)
        self.assertEqual(again, first)
        self.assertEqual([item["month"] for item in monthly_letters.list_letters(self.conn)], ["2030-09"])
        with self.assertRaises(ValueError):
            monthly_letters.write_letter(self.conn, "2030-10", today=TODAY)
        with self.assertRaises(ValueError):
            monthly_letters.write_letter(self.conn, "September", today=TODAY)

    def test_the_letter_is_offered_only_on_the_first_days_and_until_written(self):
        status = monthly_letters.letter_status(self.conn, today=TODAY)
        self.assertEqual((status["due_month"], status["offer"]), ("2030-09", True))
        self.assertFalse(monthly_letters.letter_status(self.conn, today=date(2030, 10, 8))["offer"])
        self.assertEqual(monthly_letters.letter_status(self.conn, today=date(2031, 1, 2))["due_month"], "2030-12")

        monthly_letters.write_letter(self.conn, "2030-09", today=TODAY)
        status = monthly_letters.letter_status(self.conn, today=TODAY)
        self.assertEqual((status["written"], status["offer"]), (True, False))


if __name__ == "__main__":
    unittest.main()
