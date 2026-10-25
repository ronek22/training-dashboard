import json
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.models.recovery import AIResult, CheckinCreate, IssueCreate, MessageCreate, RoutineTick
from backend.app.repositories.recovery import delete_issue, init_recovery_schema
from backend.app.services import recovery as service

PLAN = {"summary": "Settle the knee, then reload it.",
        "exercises": [{"name": "Wall sit", "dose": "5 x 30 s, daily", "how": "Knees at 60 degrees."}],
        "do": ["Easy spinning"], "avoid": ["Hills"]}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_recovery_schema(self.conn)
        patcher = patch.object(service, "training_context", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.conn.close()

    def test_body_area_detection_handles_polish_and_english_notes(self):
        self.assertEqual(service.detect_body_areas("Tightness in lower back after run"), ["lower_back"])
        self.assertEqual(service.detect_body_areas("Ból w lewym kolanie i barku"), ["knee", "shoulder"])
        self.assertEqual(service.detect_body_areas("Napięcie w dolnych plecach"), ["lower_back"])

    def create(self, **values):
        return service.create_issue(self.conn, IssueCreate(**{"body_area": "knee", "side": "left", **values}))

    def reply(self, issue_id, **values):
        request = service.add_message(self.conn, issue_id, MessageCreate(content="Outside of my knee hurts on climbs."))
        service.finish_request(self.conn, issue_id, request["request_id"], AIResult(**{"reply": "Got it.", **values}))
        return service.get_issue(self.conn, issue_id)

    def test_create_names_issue_and_records_starting_pain(self):
        issue = self.create(pain=4)
        self.assertEqual(issue["title"], "Left knee")
        self.assertEqual(issue["current_pain"], 4)
        self.assertEqual(issue["status"], "active")

    def test_reply_saves_message_plan_and_professional_flag(self):
        issue_id = self.create()["id"]
        issue = self.reply(issue_id, plan=PLAN, see_professional=True)
        self.assertEqual([m["role"] for m in issue["messages"]], ["user", "assistant"])
        self.assertEqual(issue["current_plan"]["exercises"][0]["name"], "Wall sit")
        self.assertTrue(issue["see_professional"])
        # A reply without a plan keeps the current plan; a new plan replaces it.
        issue = self.reply(issue_id)
        self.assertEqual(issue["current_plan"]["summary"], PLAN["summary"])
        issue = self.reply(issue_id, plan={**PLAN, "summary": "Progress to single-leg work."})
        self.assertEqual(issue["current_plan"]["summary"], "Progress to single-leg work.")
        self.assertEqual([p["status"] for p in issue["plans"]], ["replaced", "current"])

    def test_superseded_request_is_rejected(self):
        issue_id = self.create()["id"]
        first = service.add_message(self.conn, issue_id, MessageCreate(content="one"))
        service.add_message(self.conn, issue_id, MessageCreate(content="two"))
        with self.assertRaises(ValueError):
            service.finish_request(self.conn, issue_id, first["request_id"], AIResult(reply="late"))

    def test_checkin_links_current_plan(self):
        issue_id = self.create()["id"]
        self.reply(issue_id, plan=PLAN)
        issue = service.add_checkin(self.conn, issue_id, CheckinCreate(pain=2, did_plan=True, note="Better"))
        self.assertEqual(issue["current_pain"], 2)
        self.assertTrue(issue["checkins"][-1]["did_plan"])

    def test_recurrence_context_shows_what_helped_before(self):
        old = self.create(body_area="outside of knee", pain=5)
        self.reply(old["id"], plan=PLAN)
        service.heal(self.conn, old["id"], "Wall sits and fewer hills")
        with self.assertRaises(ValueError):
            service.add_message(self.conn, old["id"], MessageCreate(content="again?"))
        unrelated = self.create(body_area="calves", side="both")
        service.heal(self.conn, unrelated["id"], "Rest")
        self.assertEqual(service.related_issues(self.conn, "Left knee")[0]["id"], old["id"])

        again = self.create(body_area="patella", previous_issue_id=old["id"])
        self.assertEqual([item["id"] for item in again["related"]], [old["id"]])
        request = service.add_message(self.conn, again["id"], MessageCreate(content="It is back"))
        context = service.ai_context(self.conn, again["id"], request["request_id"])
        episode = context["previous_episodes_same_area"][0]
        self.assertEqual(episode["what_helped"], "Wall sits and fewer hills")
        self.assertEqual(episode["plans"][0]["exercises"][0]["name"], "Wall sit")
        self.assertEqual(episode["checkins"][0]["pain"], 5)
        self.assertEqual(len(context["previous_episodes_same_area"]), 1)
        self.assertEqual([item["body_area"] for item in context["other_past_injuries"]], ["calves"])

    def test_coaching_summary_lists_active_issues_without_conversation(self):
        issue_id = self.create(pain=3)["id"]
        self.reply(issue_id, plan=PLAN)
        summary = service.coaching_summary(self.conn)["issues"]
        self.assertEqual(summary[0]["avoid"], ["Hills"])
        self.assertEqual(summary[0]["rehab_exercises"], [{"name": "Wall sit", "dose": "5 x 30 s, daily"}])
        self.assertEqual(summary[0]["protected_areas"], ["knee"])
        self.assertEqual(service.issue_body_areas(self.conn)[0] | {"since": None},
                         {"area": "knee", "side": "left", "since": None, "recovery_issue_id": issue_id})
        self.assertNotIn("climbs", json.dumps(summary))
        service.heal(self.conn, issue_id, "")
        self.assertEqual(service.coaching_summary(self.conn)["issues"], [])
        self.assertEqual(service.issue_body_areas(self.conn), [])

    def test_delete_removes_children(self):
        issue_id = self.create(pain=3)["id"]
        self.reply(issue_id, plan=PLAN)
        delete_issue(self.conn, issue_id)
        for table in ("messages", "routines", "checkins", "requests", "status_history"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM recovery_{table}").fetchone()[0], 0)

    def test_legacy_intake_is_migrated(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE recovery_issues (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', intake_json TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1,
            needs_review INTEGER NOT NULL DEFAULT 1, concern TEXT NOT NULL DEFAULT 'none',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("INSERT INTO recovery_issues (title, status, intake_json) VALUES ('Knee', 'archived', ?)",
                     (json.dumps({"location": "outside of knee", "side": "left", "onset_date": "2026-09-01"}),))
        init_recovery_schema(conn)
        row = dict(conn.execute("SELECT * FROM recovery_issues").fetchone())
        self.assertEqual((row["body_area"], row["side"], row["started_on"], row["status"]),
                         ("outside of knee", "left", "2026-09-01", "healed"))
        conn.close()


if __name__ == "__main__":
    unittest.main()

    def test_rehab_days_carry_the_routine_and_ticks_are_kept_per_day(self):
        issue_id = self.create(pain=3)["id"]
        self.reply(issue_id, plan={**PLAN, "exercises": PLAN["exercises"] + [{"name": "Glute bridge", "dose": "3 x 12"}]})
        today = date.today().isoformat()
        routines = service.rehab_routines(self.conn)
        self.assertEqual([item["name"] for item in routines[0]["exercises"]], ["Wall sit", "Glute bridge"])
        self.assertEqual(service.rehab_for_day(self.conn, {"date": today, "title": "Workout A"}, routines), [])

        result = service.set_tick(self.conn, issue_id, RoutineTick(day=today, index=1))
        self.assertEqual((result["ticked"], result["total"]), ([1], 2))
        day = service.rehab_for_day(self.conn, {"date": today, "title": "Easy spin", "details": "Add the rehab routine after."}, routines)
        self.assertEqual(day[0]["ticked"], [1])
        self.assertEqual(service.get_issue(self.conn, issue_id)["ticked_today"], [1])
        self.assertEqual(len(service.rehab_for_day(self.conn, {"date": today, "title": "Easy spin", "steps": ["Rehab routine (checklist below)"]}, routines)), 1)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(service.rehab_for_day(self.conn, {"date": yesterday, "title": "Rehab: knee"}, routines)[0]["ticked"], [])

        self.assertEqual(service.set_tick(self.conn, issue_id, RoutineTick(day=today, index=1, done=False))["ticked"], [])
        with self.assertRaisesRegex(ValueError, "on the day"):
            service.set_tick(self.conn, issue_id, RoutineTick(day=(date.today() + timedelta(days=1)).isoformat(), index=0))
        with self.assertRaises(LookupError):
            service.set_tick(self.conn, issue_id, RoutineTick(day=today, index=5))
        service.heal(self.conn, issue_id, "")
        self.assertEqual(service.rehab_routines(self.conn), [])
