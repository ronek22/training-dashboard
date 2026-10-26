import sqlite3
import unittest
from datetime import date

from backend.app.models.checkins import AcheFollowupAcceptInput
from backend.app.repositories.recovery import init_recovery_schema
from backend.app.services import ache_followups as service
from backend.app.services.checkins import upsert_daily_checkin
from backend.app.services.recovery import issue_body_areas

NOTED = "2026-10-15"
NEXT = date(2026, 10, 16)
CHECKIN_SCHEMA = """
CREATE TABLE daily_checkins (
    date TEXT PRIMARY KEY, energy INTEGER NOT NULL, muscle_soreness INTEGER NOT NULL,
    stress INTEGER NOT NULL, sleep_quality INTEGER NOT NULL, pain_level INTEGER NOT NULL DEFAULT 0,
    note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


class AcheFollowupTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_recovery_schema(self.conn)
        self.conn.execute(CHECKIN_SCHEMA)

    def tearDown(self):
        self.conn.close()

    def mention(self, note, pain=2, ref="a1", day=NOTED):
        return service.note_mention(self.conn, "feedback", ref, day, pain, note)

    def test_detects_areas_in_english_and_polish_notes(self):
        self.assertEqual(self.mention("Tightness in lower back, probably stress", ref="en"), ["lower_back"])
        self.assertEqual(self.mention("Lekki ból w lewym kolanie", ref="pl1"), ["knee"])
        self.assertEqual(self.mention("Spięty kark i bark po pracy", ref="pl2"), ["shoulder", "neck"])
        self.assertEqual(self.mention("Boli łokieć przy chwycie", ref="pl3"), ["elbow"])

    def test_only_mild_pain_with_a_named_area_opens_a_thread(self):
        self.assertEqual(self.mention("lower back tight", pain=0, ref="none"), [])
        self.assertEqual(self.mention("lower back tight", pain=5, ref="loud"), [])
        self.assertEqual(self.mention("felt heavy all ride", ref="vague"), [])
        self.assertEqual(service.pending(self.conn, NEXT), [])

    def test_running_thread_or_active_issue_is_not_duplicated(self):
        self.mention("lower back tight", ref="a1")
        self.assertEqual(self.mention("plecy dalej spięte", ref="a2"), [])
        self.conn.execute("INSERT INTO recovery_issues (title, body_area, status) VALUES ('Knee', 'knee', 'active')")
        self.assertEqual(self.mention("knee a bit sore", ref="a3"), [])

    def test_question_waits_for_the_next_morning(self):
        self.mention("lower back tight")
        self.assertEqual(service.pending(self.conn, date(2026, 10, 15)), [])
        [item] = service.pending(self.conn, NEXT)
        self.assertEqual(item["question"], "Lower back: better, same or worse?")
        self.assertEqual(item["mobility"]["key"], "gentle_stretch")
        self.assertIsNone(item["offer"])

    def test_checkin_note_opens_a_thread(self):
        base = {"date": NOTED, "energy": 3, "muscle_soreness": 2, "stress": 3, "sleep_quality": 3}
        upsert_daily_checkin(self.conn, {**base, "pain_level": 2, "note": "Niggle: hip"})
        self.assertEqual([item["area"] for item in service.pending(self.conn, NEXT)], ["hip"])

    def test_better_closes_quietly(self):
        self.mention("lower back tight")
        [item] = service.pending(self.conn, NEXT)
        self.assertEqual(service.answer(self.conn, item["id"], "better", NEXT)["status"], "closed")
        self.assertEqual(service.pending(self.conn, date(2026, 10, 17)), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM recovery_issues").fetchone()[0], 0)

    def test_two_sames_offer_a_prefilled_issue_without_creating_it(self):
        self.mention("lower back tight")
        followup_id = service.pending(self.conn, NEXT)[0]["id"]
        self.assertEqual(service.answer(self.conn, followup_id, "same", NEXT)["status"], "open")
        with self.assertRaises(ValueError):
            service.answer(self.conn, followup_id, "same", NEXT)
        offered = service.answer(self.conn, followup_id, "same", date(2026, 10, 17))
        self.assertEqual(offered["status"], "offered")
        self.assertEqual(offered["offer"]["title"], "Lower back niggle")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM recovery_issues").fetchone()[0], 0)

    def test_one_worse_offers_the_issue(self):
        self.mention("kolano boli")
        followup_id = service.pending(self.conn, NEXT)[0]["id"]
        self.assertEqual(service.answer(self.conn, followup_id, "worse", NEXT)["status"], "offered")

    def accept(self, protect_days):
        self.mention("lower back tight")
        followup_id = service.pending(self.conn, NEXT)[0]["id"]
        service.answer(self.conn, followup_id, "worse", NEXT)
        payload = AcheFollowupAcceptInput(title="Lower back niggle", body_area="lower back", pain=2,
                                          protect_days=protect_days)
        return service.accept(self.conn, followup_id, payload, NEXT)

    def test_accepting_without_protection_leaves_the_lift_top_up_alone(self):
        result = self.accept(0)
        self.assertIsNone(result["protect_until"])
        issue = self.conn.execute("SELECT title, status FROM recovery_issues").fetchone()
        self.assertEqual(tuple(issue), ("Lower back niggle", "active"))
        self.assertEqual(issue_body_areas(self.conn), [])
        self.assertEqual(service.protected_areas(self.conn, NEXT), [])

    def test_protection_is_explicit_and_expires(self):
        result = self.accept(3)
        self.assertEqual(result["protect_until"], "2026-10-18")
        self.assertEqual([item["area"] for item in service.protected_areas(self.conn, date(2026, 10, 18))], ["lower_back"])
        self.assertEqual(service.protected_areas(self.conn, date(2026, 10, 19)), [])
        self.assertEqual(service.pending(self.conn, date(2026, 10, 17)), [])

    def test_unanswered_thread_goes_quiet(self):
        self.mention("neck stiff")
        self.assertEqual(service.pending(self.conn, date(2026, 10, 23)), [])


if __name__ == "__main__":
    unittest.main()
