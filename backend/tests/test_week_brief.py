import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WinterArc
from backend.app.models.plans import WeeklyPlanAdjustment
from backend.app.services.plans import adjust_weekly_plan_data, upsert_weekly_plan_data
from backend.app.services.settings import get_workout_template_settings_for_conn, set_workout_template_settings_for_conn
from backend.app.services.week_brief import build_week_brief, reconcile_summary, week_brief_context
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

    def test_a_healed_knee_eases_the_lower_slot_back_in(self):
        self.use_slots()
        self.conn.execute("INSERT INTO recovery_issues (title, body_area, side, started_on, status, healed_on) "
                          "VALUES ('Outside of left knee, probably ITBS', 'outside of left knee', 'left', '2029-10-20', 'healed', '2029-11-28')")
        brief = build_week_brief(self.conn, WEEK, TODAY)
        self.assertEqual(brief["lifts"]["slots"][1]["template_id"], "strength-d", "no swap once healed")
        safety = [line["text"] for line in brief["lines"] if line["priority"] == "safety"]
        self.assertEqual(safety, ["Left knee healed 28 Nov: first lower-body lift at about 80% of last loads, 2+ reps in reserve"])

    def test_injury_lines_lead_with_a_short_label(self):
        self.conn.execute("INSERT INTO recovery_issues (title, body_area, side, started_on, status) "
                          "VALUES ('Outside of left knee, probably ITBS', 'outside of left knee', 'left', '2029-11-20', 'active')")
        line = build_week_brief(self.conn, WEEK, TODAY)["lines"][0]
        self.assertTrue(line["text"].startswith("Left knee: no lower-body lifts"))
        self.assertEqual(line["source"], "Recovery: Outside of left knee, probably ITBS")

    def test_sick_days_ride_quality_as_z2(self):
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES (?, ?)", (DATES[5], DATES[6]))
        tempo = WeeklyPlanDay(date=DATES[6], label="d", session_type="ride", workout_intent="tempo", title="Sweet spot 3 x 10", target_duration_min=70)
        upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=WEEK, title="Test", days=[tempo]))
        stored = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])
        self.assertEqual((stored[0]["workout_intent"], stored[0]["planning_rule_reason"]), ("easy", "Week brief: sick, so no hard rides"))

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

    def save_rotation_week(self):
        lift = lambda title: {"session_type": "strength", "workout_intent": "strength_upper", "title": title, "target_duration_min": 50}
        rest = {"session_type": "Rest", "title": "Rest"}
        days = [lift("Workout B"), rest, lift("Workout C"), rest, lift("Workout A"), rest, rest]
        upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=WEEK, title="Test", days=[WeeklyPlanDay(date=DATES[i], label="d", **day) for i, day in enumerate(days)]))

    def stored_templates(self):
        stored = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])
        return [stored[i].get("template_id") for i in (0, 2, 4)], stored

    def coach_friday(self):
        return WeeklyPlanDay(date=DATES[4], label="d", session_type="strength", workout_intent="strength_upper",
                             title="Upper-body lift (Workout A style)", target_duration_min=50,
                             exercises=[{"name": "Dumbbell Bench Press", "sets": 3, "reps": "10"}])

    def test_coach_edits_get_the_slots_and_a_custom_gym_lift_takes_its_slot(self):
        self.save_rotation_week()  # Saved before slots existed: B, C, A.
        self.use_slots()
        self.injure_knee()
        adjust_weekly_plan_data(self.conn, WeeklyPlanAdjustment(week_start=WEEK, effective_from=DATES[0], days=[self.coach_friday()]), fit_lift_slots=True)
        templates, stored = self.stored_templates()
        self.assertEqual(templates, ["strength-a", "strength-c", "strength-b"])
        self.assertEqual(stored[4]["exercises"], [])

    def test_coach_edits_ride_extra_quality_as_z2_in_a_base_week(self):
        save_winter_arc(self.conn, WinterArc(**BASE), TODAY)
        self.save_rotation_week()
        sweet_spot = WeeklyPlanDay(date=DATES[1], label="d", session_type="ride", workout_intent="tempo", title="Sweet spot 3 x 10", target_duration_min=70)
        adjust_weekly_plan_data(self.conn, WeeklyPlanAdjustment(week_start=WEEK, effective_from=DATES[0], days=[sweet_spot]), fit_lift_slots=True)
        _, stored = self.stored_templates()
        self.assertEqual((stored[1]["title"], stored[1]["workout_intent"]), ("Endurance 70", "easy"))

    def test_a_protected_knee_rides_quality_as_z2_even_without_an_arc(self):
        self.injure_knee()
        tempo = {"session_type": "ride", "workout_intent": "tempo", "title": "Sweet spot 3 x 10 (knee-gated)", "target_duration_min": 70}
        rest = {"session_type": "Rest", "title": "Rest"}
        days = [rest] * 6 + [tempo]
        result = upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=WEEK, title="Test", days=[WeeklyPlanDay(date=DATES[i], label="d", **day) for i, day in enumerate(days)]))
        _, stored = self.stored_templates()
        self.assertEqual((stored[6]["title"], stored[6]["workout_intent"], stored[6]["target_duration_min"]), ("Endurance 70", "easy", 70))
        self.assertEqual(stored[6]["planning_rule_reason"], "Week brief: knee protected, so no hard rides")
        self.assertEqual([change["kind"] for change in result["arc_changes"]], ["safety"])

    def test_the_coachs_headline_drops_a_hard_ride_the_rules_took_out(self):
        self.injure_knee()
        tempo = WeeklyPlanDay(date=DATES[1], label="d", session_type="ride", workout_intent="tempo", title="Sweet spot 3 x 10", target_duration_min=70)
        plan = WeeklyPlan(week_start=WEEK, title="Three upper lifts, one gated quality ride, knee stays protected",
                          focus="Hold the 3-lift anchor. One knee-gated sweet-spot ride on Tuesday. Gentle ride-volume step.",
                          days=[tempo])
        upsert_weekly_plan_data(self.conn, plan)
        row = self.conn.execute("SELECT title, focus FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()
        self.assertEqual(row["title"], "Three upper lifts, knee stays protected")
        self.assertEqual(row["focus"], "Hold the 3-lift anchor. Gentle ride-volume step.")

    def test_headline_stays_when_a_hard_ride_is_still_planned(self):
        days = [{"session_type": "ride", "workout_intent": "tempo", "title": "Sweet spot"}]
        self.assertEqual(reconcile_summary({"title": "One quality ride"}, days, [{"kind": "too_hard"}]), {})
        self.assertEqual(reconcile_summary({"title": "One quality ride"}, [], []), {})

    def test_without_a_protected_leg_quality_rides_stay(self):
        tempo = WeeklyPlanDay(date=DATES[6], label="d", session_type="ride", workout_intent="tempo", title="Sweet spot 3 x 10", target_duration_min=70)
        upsert_weekly_plan_data(self.conn, WeeklyPlan(week_start=WEEK, title="Test", days=[tempo]))
        stored = json.loads(self.conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (WEEK,)).fetchone()[0])
        self.assertEqual(stored[0]["workout_intent"], "tempo")

    def test_the_athletes_own_edits_stay_as_made(self):
        self.save_rotation_week()
        self.use_slots()
        adjust_weekly_plan_data(self.conn, WeeklyPlanAdjustment(week_start=WEEK, effective_from=DATES[0], days=[self.coach_friday()]))
        templates, _ = self.stored_templates()
        self.assertEqual(templates[0], "strength-b")

    def test_plan_workouts_link_to_workout_studio_by_id_and_follow_renames(self):
        from backend.app.models.strength_workouts import StrengthTemplateInput
        from backend.app.services.strength_workouts import save_template

        workout = save_template(self.conn, StrengthTemplateInput(name="Workout B · Back + Arms", exercises=[{"exercise_name": "Chin Up", "set_count": 3, "target_reps": 8}]))
        b = next(t for t in get_workout_template_settings_for_conn(self.conn)["programs"]["strength"]["templates"] if t["id"] == "strength-b")
        self.assertEqual(b["workout_template_id"], workout["id"], "matched by name once")
        save_template(self.conn, StrengthTemplateInput(name="Workout B · Upper Pull", exercises=[{"exercise_name": "Chin Up", "set_count": 3, "target_reps": 8}]), workout["id"])
        b = next(t for t in get_workout_template_settings_for_conn(self.conn)["programs"]["strength"]["templates"] if t["id"] == "strength-b")
        self.assertEqual((b["display_name"], b["workout_template_id"]), ("Workout B · Upper Pull", workout["id"]))

    def test_planner_context_has_this_and_next_week(self):
        context = week_brief_context(self.conn, TODAY)
        self.assertEqual((context["this_week"]["week_start"], context["next_week"]["week_start"]), ("2029-11-26", "2029-12-03"))
        self.assertIn("top to bottom", context["instruction"])


if __name__ == "__main__":
    unittest.main()
