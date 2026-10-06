import sqlite3
import unittest
from unittest import mock

from backend.app.services import session_read, session_win
from backend.app.services.notes import (
    create_chat_message_data,
    list_chat_conversations_data,
    list_chat_messages_data,
    open_context_conversation_data,
)
from backend.tests.test_session_read import _connection


def _ride(activity_id, day, drift, watts, hr):
    return {"activity_id": activity_id, "date": day, "environment": "indoor", "decoupling_pct": drift,
            "avg_watts": watts, "avg_hr": hr, "duration_min": 90}


class SessionWinTests(unittest.TestCase):
    def setUp(self):
        self.conn = _connection()
        self.addCleanup(self.conn.close)
        patcher = mock.patch.object(session_win, "build_activity_record_ranks", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        streak = mock.patch.object(session_win, "_streak_section", return_value={"current": None})
        streak.start()
        self.addCleanup(streak.stop)

    def ride_payload(self):
        rides = [
            _ride("r1", "2026-09-01", 6.0, 150, 134),
            _ride("r2", "2026-09-10", 4.1, 152, 132),
            _ride("r3", "2026-09-20", 2.8, 151, 129),
        ]
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('r3', '2026-09-20', 'VirtualRide', 90)")
        payload = {
            "activity": {"id": "r3", "date": "2026-09-20", "type": "VirtualRide", "workout_intent": "easy", "duration_min": 90},
            "cycling": {"power_source": "measured", "environment": "indoor", "power_efforts": []},
        }
        with mock.patch.object(session_read, "build_aerobic_decoupling", return_value={"rides": rides}):
            read = session_read.build_session_read(self.conn, payload)
        return payload, read

    def test_lower_heart_rate_at_the_same_power_is_the_win(self):
        payload, read = self.ride_payload()
        win = session_win.build_session_win(self.conn, payload, read)

        self.assertEqual(win["kind"], "progress")
        self.assertEqual(win["headline"], "5 bpm lower at 151 W than on 1 Sep")
        self.assertEqual(win["also"][0], "Least heart-rate drift of your last 3 steady rides")
        # The opener leads with the win, carries the next step and invites a question.
        self.assertTrue(win["opener"].startswith("5 bpm lower at 151 W than on 1 Sep."))
        self.assertIn("Next time:", win["opener"])
        self.assertIn("indoor ride", win["opener"])

    def test_an_all_time_record_beats_progress(self):
        payload, read = self.ride_payload()
        ranks = {"r3": [{"category": "Bike power", "label": "20 min", "rank": 1, "display": "236 W"}]}
        with mock.patch.object(session_win, "build_activity_record_ranks", return_value=ranks):
            win = session_win.build_session_win(self.conn, payload, read)
        self.assertEqual(win["kind"], "record")
        self.assertEqual(win["headline"], "All-time best 20 min power: 236 W")

    def test_there_is_always_a_win_for_showing_up(self):
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('a', '2026-10-05T07:00:00', 'Walk', 40)")
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('b', '2026-10-06T07:00:00', 'Yoga', 30)")
        payload = {"activity": {"id": "b", "date": "2026-10-06T07:00:00", "type": "Yoga", "duration_min": 30}}
        win = session_win.build_session_win(self.conn, payload, {"available": False})
        self.assertEqual(win["headline"], "Second session of the week in the bank")
        self.assertEqual(win["kind"], "consistency")

    def test_a_tough_day_counts(self):
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('b', '2026-10-06', 'Run', 30)")
        payload = {"activity": {"id": "b", "date": "2026-10-06", "type": "Run", "duration_min": 30}}
        read = {"available": True, "signals": [
            {"key": "going_in", "label": "Going in", "value": "Energy 2/5", "detail": "stress 4/5 · travel", "tone": "warn"},
        ], "wins": []}
        win = session_win.build_session_win(self.conn, payload, read)
        self.assertEqual(win["headline"], "Showed up on a tough day")
        self.assertEqual(win["detail"], "Going in: energy 2/5, stress 4/5, travel. You still got it done.")


    def test_streak_milestones_are_big_and_other_days_count_down(self):
        self.conn.execute("INSERT INTO activities (id, date, type, duration_min) VALUES ('b', '2026-10-06', 'Walk', 30)")
        payload = {"activity": {"id": "b", "date": "2026-10-06", "type": "Walk", "duration_min": 30}}
        for start, headline, detail in (
            ("2025-10-07", "365 days in a row", "A streak milestone. Every single day counted to get here."),
            ("2026-01-03", "Day 277 of your streak", "88 days to 365 in a row."),
        ):
            current = {"current": {"days": 1, "start": start, "end": "2026-10-06"}}
            with mock.patch.object(session_win, "_streak_section", return_value=current):
                win = session_win.build_session_win(self.conn, payload, {"available": False})
            self.assertEqual((win["headline"], win["detail"]), (headline, detail))


class LinkedConversationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript(
            """
            CREATE TABLE coach_chat_conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                context_kind TEXT, context_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE coach_chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, role TEXT NOT NULL,
                content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """
        )

    def test_opening_a_session_chat_creates_it_once_with_the_coach_opener(self):
        first = open_context_conversation_data(self.conn, "activity", "16001", "Ride · 4 Oct: Win", "Nice ride.")
        self.assertTrue(first["created"])
        self.assertEqual(first["message_count"], 1)
        messages = list_chat_messages_data(self.conn, first["id"])
        self.assertEqual([(m["role"], m["content"]) for m in messages], [("assistant", "Nice ride.")])

        create_chat_message_data(self.conn, first["id"], "user", "Why the drift?")
        again = open_context_conversation_data(self.conn, "activity", "16001", "Other title", "Other opener")
        self.assertFalse(again["created"])
        self.assertEqual(again["id"], first["id"])
        # A linked chat keeps its title after the first athlete message.
        self.assertEqual(again["title"], "Ride · 4 Oct: Win")
        self.assertEqual(again["message_count"], 2)

    def test_listing_filters_by_context_and_rejects_unknown_kinds(self):
        open_context_conversation_data(self.conn, "activity", "a1", "One")
        open_context_conversation_data(self.conn, "activity", "a2", "Two")
        self.assertEqual([c["title"] for c in list_chat_conversations_data(self.conn, "activity", "a2")], ["Two"])
        self.assertEqual(len(list_chat_conversations_data(self.conn)), 2)
        with self.assertRaisesRegex(ValueError, "context_kind"):
            open_context_conversation_data(self.conn, "goal", "1", "Nope")

    def test_a_chat_can_be_about_a_day(self):
        day = open_context_conversation_data(self.conn, "day", "2026-10-07", "Today · 7 Oct: Feeling flat", "Flat days happen.")
        self.assertEqual((day["context_kind"], day["context_id"]), ("day", "2026-10-07"))
        with self.assertRaisesRegex(ValueError, "ISO date"):
            open_context_conversation_data(self.conn, "day", "today", "Nope")
        week = open_context_conversation_data(self.conn, "week", "2026-10-05", "Week of 5 Oct: wins and focus")
        self.assertEqual(week["context_kind"], "week")
        with self.assertRaisesRegex(ValueError, "Monday"):
            open_context_conversation_data(self.conn, "week", "2026-10-07", "Nope")


if __name__ == "__main__":
    unittest.main()
