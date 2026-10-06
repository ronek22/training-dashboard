import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest import mock

from backend.app import db
from backend.app.services import week_wins

WEEK = date(2030, 1, 7)  # A Monday.


class WeekWinsTests(unittest.TestCase):
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
        week_wins._CACHE.clear()
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2029-01-01', '2031-01-01', 1, 'active', 'anchor')"
        )

    def add(self, activity_id, day, kind="WeightTraining", minutes=45):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, ?, ?, ?)",
            (activity_id, day, kind, kind, minutes),
        )
        self.conn.commit()

    def wins(self, today, week=WEEK):
        return week_wins.build_week_wins(self.conn, week, today=today)

    def test_an_anchor_goal_met_is_a_win_and_the_review_sets_the_focus(self):
        for index, day in enumerate(("2030-01-07", "2030-01-09", "2030-01-11")):
            self.add(f"l{index}", day)
        self.conn.execute(
            "INSERT INTO weekly_reviews (week_start, improved, missed, proposed_change, generator, outcome_reason) "
            "VALUES ('2030-01-07', 'x', 'y', 'Keep Tuesday easy.', 'codex-cli', 'z')"
        )
        result = self.wins(date(2030, 1, 14))

        self.assertTrue(result["finished"])
        self.assertEqual(result["wins"][0]["headline"], "Lift three times per week: done")
        self.assertEqual(result["wins"][0]["detail"], "3 of 3 this week. That's the anchor goal kept.")
        self.assertEqual(result["focus"], {"source": "review", "headline": "One change for next week", "detail": "Keep Tuesday easy."})

    def test_mid_week_the_open_anchor_is_the_focus_and_showing_up_is_a_win(self):
        self.add("l1", "2030-01-07")
        self.add("w1", "2030-01-08", "Walk", 30)
        self.add("w2", "2030-01-09", "Walk", 30)
        result = self.wins(date(2030, 1, 9))

        self.assertFalse(result["finished"])
        self.assertEqual(result["focus"]["headline"], "Lift three times per week: 2 to go")
        self.assertEqual(result["focus"]["detail"], "1 of 3 done with 4 days left. Pick the days now so it happens.")
        self.assertEqual(result["wins"][0]["headline"], "Moved every day so far (3 of 3)")

    def test_there_is_always_something_once_anything_is_logged(self):
        self.add("w1", "2030-01-08", "Walk", 30)
        result = self.wins(date(2030, 1, 14))
        self.assertEqual(result["wins"][0]["headline"], "30 min of movement in the bank")
        self.assertEqual(result["focus"]["source"], "default")
        self.assertEqual(self.wins(date(2030, 1, 14), date(2030, 1, 21))["wins"], [])

    def test_at_most_three_wins_one_per_session(self):
        session_wins = [
            {"activity": {"id": f"a{index}", "date": "2030-01-08"}, "read": {"available": False},
             "win": {"score": score, "kind": "progress", "headline": f"Win {index}", "detail": "d"}}
            for index, score in enumerate((95, 90, 70, 60))
        ]
        with mock.patch.object(week_wins, "_session_items", return_value=session_wins):
            result = self.wins(date(2030, 1, 14))
        self.assertEqual([win["headline"] for win in result["wins"]], ["Win 0", "Win 1", "Win 2"])
        self.assertEqual(result["wins"][0]["activity_id"], "a0")

    def test_the_cache_notices_a_new_session(self):
        self.add("l1", "2030-01-07")
        first = self.wins(date(2030, 1, 9))
        self.assertIs(self.wins(date(2030, 1, 9)), first)
        self.add("l2", "2030-01-08")
        self.assertEqual(self.wins(date(2030, 1, 9))["focus"]["headline"], "Lift three times per week: 1 to go")


if __name__ == "__main__":
    unittest.main()
