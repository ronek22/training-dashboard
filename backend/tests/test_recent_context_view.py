import unittest

from backend.app.services.recent_context_view import compact_recent_context


def goal(goal_id):
    return {
        "id": goal_id,
        "title": f"Goal {goal_id}",
        "status": "behind_pace",
        "compact_summary": "Slipping.",
        "risk_summary": {"status": "at_risk", "label": "At risk", "summary": "Trending short."},
        "forecast": {"projected": 1.0},
        "goal_readiness": {"state": "ready"},
        "target_config": None,
    }


def plan_day(date):
    return {
        "session_id": f"plan-{date}",
        "date": date,
        "title": "Workout B",
        "details": "Rows and chin-ups.",
        "modality_restriction": {"modality": "strength", "status": "allowed"},
        "link_candidates": [{"id": "a", "name": "Candidate"}] * 10,
        "goal_links": [{"goal_id": 4, "goal_title": "Lift 3x", "support_level": "strong", "requirement_type": "x"}],
        "comparison": {
            "status": "matched",
            "label": "Matched",
            "completed_activities": [{"id": "a1", "type": "WeightTraining", "name": "Lift", "source_name": "Lift"}],
            "execution_quality": {"status": "completed", "headline": "Done", "reasons": ["long"]},
        },
    }


class CompactRecentContextTests(unittest.TestCase):
    def setUp(self):
        goals = [goal(1), goal(2)]
        self.full = {
            "sick_mode": None,
            "minimum_week": None,
            "return_to_run": {"active": False},
            "workout_template_settings": {"programs": {"a": [1, 2, 3]}},
            "active_goals": goals,
            "goal_planning_summary": {"count": 2, "most_urgent": goals, "conflicts": [{"type": "x"}]},
            "goal_risk_summary": {"status": "at_risk", "most_pressured": goals},
            "active_plan": {
                "week_start": "2026-10-05",
                "title": "Week",
                "days": [plan_day("2026-10-05"), plan_day("2026-10-06")],
                "goal_context": {"active_goals": goals},
                "workout_template_programs": {"a": {}},
                "revisions": [{"id": 1}],
                "latest_revision": {"id": 1, "adaptation_reason": "Moved", "preserved_dates": ["2026-10-05"]},
                "lift_volume": {"target_min": 8, "groups": [{"key": "legs", "label": "Legs", "total_sets": 8, "done_sets": 4}]},
            },
            "training_load": {
                "current": {"fitness": 80},
                "model": {"name": "hybrid", "ftp": 242, "coverage": {"pct": 50}},
                "chart": [{"date": f"2026-09-{day:02d}", "load": day, "run_load": 0} for day in range(1, 29)],
            },
            "cycling_power": {
                "category_levels": {"Sprint": {"level": 5}},
                "records": [{"duration_seconds": 15, "watts": 750, "activity_id": "x", "level_name": "Elite"}],
                "monthly_coverage": [{"month": "2026-09"}],
                "methodology": "long text",
            },
            "daily_recommendation": {
                "status": "go",
                "today_plan": plan_day("2026-10-08"),
                "signals": {"latest_feedback": {"rpe": 9}, "modality_restrictions": {"modalities": {}}},
            },
            "recent_activities": [
                {"id": "a1", "type": "Ride", "avg_pace": None, "feedback": {"rpe": 6, "note": "ok", "created_at": "t"}, "session_tags": {}}
            ],
            "readiness": {
                "state": "watch",
                "latest_feedback": {"rpe": 9},
                "score": {"level": "red", "factors": [{"key": "sleep", "label": "Sleep", "detail": "7 h", "tone": "steady", "summary": {"x": 1}}]},
            },
        }

    def test_keeps_summaries_and_drops_bulk(self):
        compact = compact_recent_context(self.full)

        self.assertEqual(compact["detail"], "compact")
        self.assertIn("get_cycling_power_profile", compact["detail_tools"]["cycling_power"])
        self.assertNotIn("workout_template_settings", compact)
        self.assertEqual([g["title"] for g in compact["active_goals"]], ["Goal 1", "Goal 2"])
        self.assertNotIn("forecast", compact["active_goals"][0])
        self.assertEqual(compact["goal_planning_summary"]["most_urgent"][0], {"id": 1, "title": "Goal 1", "status": "behind_pace", "risk": "At risk"})
        self.assertEqual(compact["goal_risk_summary"]["most_pressured"][1]["id"], 2)

        plan = compact["active_plan"]
        self.assertNotIn("goal_context", plan)
        self.assertNotIn("revisions", plan)
        self.assertEqual(plan["latest_revision"], {"adaptation_reason": "Moved"})
        day = plan["days"][0]
        self.assertNotIn("link_candidates", day)
        self.assertNotIn("modality_restriction", day)
        self.assertEqual(day["goal_links"], [{"goal_id": 4, "goal_title": "Lift 3x", "support_level": "strong"}])
        self.assertEqual(day["comparison"]["completed"], [{"id": "a1", "type": "WeightTraining", "name": "Lift"}])
        self.assertEqual(day["comparison"]["execution_quality"], {"status": "completed", "headline": "Done"})
        self.assertEqual(plan["lift_volume"]["groups"], [{"label": "Legs", "total_sets": 8}])

        load = compact["training_load"]
        self.assertEqual(len(load["recent_days"]), 7)
        self.assertEqual(load["recent_days"][-1], {"date": "2026-09-28", "load": 28})
        self.assertEqual(load["model"], {"name": "hybrid", "ftp": 242})

        self.assertEqual(compact["cycling_power"]["records"], [{"duration_seconds": 15, "watts": 750, "level_name": "Elite"}])
        self.assertNotIn("monthly_coverage", compact["cycling_power"])
        self.assertNotIn("modality_restrictions", compact["daily_recommendation"]["signals"])
        self.assertEqual(compact["daily_recommendation"]["today_plan"]["date"], "2026-10-08")
        self.assertEqual(compact["recent_activities"][0], {"id": "a1", "type": "Ride", "feedback": {"rpe": 6, "note": "ok"}})
        self.assertNotIn("latest_feedback", compact["readiness"])
        self.assertEqual(compact["readiness"]["score"]["factors"], [{"label": "Sleep", "detail": "7 h", "tone": "steady"}])

    def test_null_sections_stay_explicit(self):
        compact = compact_recent_context(self.full)

        self.assertIsNone(compact["sick_mode"])
        self.assertIsNone(compact["minimum_week"])
        self.assertEqual(compact["return_to_run"], {"active": False})

    def test_does_not_mutate_full_context(self):
        compact_recent_context(self.full)

        self.assertIn("link_candidates", self.full["active_plan"]["days"][0])
        self.assertIn("workout_template_settings", self.full)


if __name__ == "__main__":
    unittest.main()
