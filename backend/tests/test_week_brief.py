import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WinterArc
from backend.app.services.plans import upsert_weekly_plan_data
from backend.app.services.settings import set_workout_template_settings_for_conn
from backend.app.services.week_brief import build_week_brief, week_brief_context
from backend.app.services.winter_arc import save_winter_arc

TODAY = date(2029, 12, 1)
WEEK = "2029-12-10"
DATES = ["2029-12-10", "2029-12-11", "2029-12-12", "2029-12-13", "2029-12-14", "2029-12-15", "2029-12-16"]
BASE = {"blocks": [{"start_date": "2029-12-03", "end_date": "2029-12-30", "focus": "base", "label": "Base", "weekly_hours": 4,
                    "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 0}]}


class WeekBriefTests(unittest.TestCase):
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

    def goal(self, title, metric, commitment="flexible", period="week"):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, commitment) VALUES (?, ?, ?, 1, '2029-06-01', '2029-06-07', ?)",
            (title, period, metric, commitment),
        )

    def injure_knee(self):
        self.conn.execute("INSERT INTO recovery_issues (title, body_area, side, started_on, status) VALUES ('Left knee', 'knee', 'left', '2029-11-20', 'active')")

    def use_slots(self, slots=("strength-a", "strength-d", "strength-b")):
        set_workout_template_settings_for_conn(self.conn, {"programs": {"strength": {"rules": {"weekly_slots": list(slots)}}}})

    def lines(self, brief):
        return [(line["priority"], line["text"]) for line in brief["lines"]]

    def test_rules_come_in_priority_order_with_goals_resolved_against_the_block(self):
        save_winter_arc(self.conn, WinterArc(**BASE), TODAY)
        self.goal("Lift three times per week", "strength_sessions", "anchor")
        self.goal("1 quality ride per week", "quality_sessions")
        self.goal("Ride 100km weekly", "ride_km")
        self.injure_knee()
        brief = build_week_brief(self.conn, "2029-12-12", TODAY)  # Any day snaps to its Monday.
        self.assertEqual(brief["week_start"], WEEK)
        self.assertEqual([line["priority"] for line in brief["lines"]][:5], ["safety", "anchor", "block", "outcome", "outcome"])
        texts = dict(self.lines(brief))
        self.assertIn("no lower-body lifts", texts["safety"])
        self.assertEqual(texts["block"], "Rides about 4 h: 3× Z2, no sweet spot or VO2")
        outcomes = [text for priority, text in self.lines(brief) if priority == "outcome"]
        self.assertIn("1 quality ride per week: waits for a quality block (Base has none)", outcomes)
        self.assertIn("Ride 100km weekly: the block's 4 h sets the week", outcomes)
        self.assertEqual(brief["headline"], "Base wk 2/4 · 4 h rides · Z2 only · knee protected")

    def test_slots_swap_the_lower_lift_while_a_knee_is_protected(self):
        self.use_slots()
        self.goal("Lift three times per week", "strength_sessions", "anchor")
        brief = build_week_brief(self.conn, WEEK, TODAY)
        self.assertEqual([slot["slot"] for slot in brief["lifts"]["slots"]], ["Upper 1", "Lower", "Upper 2"])
        self.injure_knee()
        brief = build_week_brief(self.conn, WEEK, TODAY)
        lower = brief["lifts"]["slots"][1]
        self.assertEqual((lower["template_id"], lower["reason"]), ("strength-c", "Knee protected"))
        self.assertTrue(lower["swapped_from"].startswith("Workout D"))
        anchor = next(text for priority, text in self.lines(brief) if priority == "anchor")
        self.assertIn(f"(for {lower['swapped_from']})", anchor)

    def test_without_slots_the_rotation_stays(self):
        self.assertEqual(build_week_brief(self.conn, WEEK, TODAY)["lifts"]["mode"], "rotation")

    def test_saved_week_gets_the_slot_workouts_in_order(self):
        self.use_slots()
        self.injure_knee()
        lift = lambda title: {"session_type": "strength", "workout_intent": "strength_upper", "title": title, "target_duration_min": 50}
        rest = {"session_type": "Rest", "title": "Rest"}
        days = [lift("Workout B"), rest, lift("Workout C"), rest, lift("Upper-body lift"), rest, rest]
        plan = WeeklyPlan(week_start=WEEK, title="Test", days=[WeeklyPlanDay(date=DATES[i], label="d", **day) for i, day in enumerate(days)])
        result = upsert_weekly_plan_data(self.conn, plan)
        stored = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])
        self.assertEqual([stored[i]["template_id"] for i in (0, 2, 4)], ["strength-a", "strength-c", "strength-b"])
        self.assertTrue(stored[2]["planning_rule_reason"].startswith("Weekly lifts: Lower (Knee protected:"))
        self.assertEqual(sum(change["kind"] == "lift_slot" for change in result["arc_changes"]), 3)

    def test_planner_context_has_this_and_next_week(self):
        context = week_brief_context(self.conn, TODAY)
        self.assertEqual((context["this_week"]["week_start"], context["next_week"]["week_start"]), ("2029-11-26", "2029-12-03"))
        self.assertIn("top to bottom", context["instruction"])


if __name__ == "__main__":
    unittest.main()
