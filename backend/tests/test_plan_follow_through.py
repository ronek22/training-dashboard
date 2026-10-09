import unittest
from datetime import date, timedelta

from backend.app.services.plan_follow_through import classify_planned_day, summarize_follow_through

QUALITY_GOAL = {"metric_type": "quality_sessions", "period_type": "week", "activity_type": "Ride", "target_value": 1}


def _day(day: date, session_type: str, intent=None, status="matched", replaced_with=None, **extra):
    activities = [{"type": replaced_with, "duration_min": 60}] if replaced_with else []
    return {
        "date": day.isoformat(),
        "session_type": session_type,
        "workout_intent": intent,
        "comparison": {"status": status, "completed_activities": activities},
        **extra,
    }


def _week(monday: date, days: list[dict]) -> dict:
    return {"week_start": monday.isoformat(), "days": days}


def _weeks(count: int, build) -> list[dict]:
    start = date(2026, 7, 6)
    return [_week(start + timedelta(weeks=index), build(start + timedelta(weeks=index), index)) for index in range(count)]


class ClassifyPlannedDayTests(unittest.TestCase):
    def test_ride_kinds(self):
        self.assertEqual(classify_planned_day({"session_type": "ride", "workout_intent": "tempo"}), "quality_ride")
        self.assertEqual(classify_planned_day({"session_type": "Ride", "cycling_workout_id": "sweet-spot-3x10"}), "quality_ride")
        self.assertEqual(classify_planned_day({"session_type": "ride", "workout_intent": "long"}), "long_ride")
        self.assertEqual(classify_planned_day({"session_type": "ride", "workout_intent": "recovery"}), "recovery")
        self.assertEqual(classify_planned_day({"session_type": "ride"}), "easy_ride")

    def test_lifts_runs_and_rest(self):
        self.assertEqual(classify_planned_day({"session_type": "strength", "workout_intent": "strength_lower"}), "lift_lower")
        self.assertEqual(classify_planned_day({"session_type": "WeightTraining", "workout_intent": "strength_upper"}), "lift_upper")
        self.assertEqual(classify_planned_day({"session_type": "strength"}), "lift_general")
        self.assertEqual(classify_planned_day({"session_type": "run", "workout_intent": "easy"}), "run")
        self.assertIsNone(classify_planned_day({"session_type": "rest"}))
        self.assertIsNone(classify_planned_day({"session_type": "walk"}))


class SummarizeFollowThroughTests(unittest.TestCase):
    def test_counts_outcomes_and_replacements_per_kind(self):
        def build(monday, index):
            return [
                _day(monday, "ride", "easy"),
                _day(monday + timedelta(days=4), "strength", "strength_lower",
                     status="replaced" if index < 3 else "matched", replaced_with="Ride"),
            ]

        summary = summarize_follow_through(_weeks(4, build))
        lower = next(kind for kind in summary["kinds"] if kind["kind"] == "lift_lower")
        self.assertEqual((lower["planned"], lower["done"], lower["replaced"]), (4, 1, 3))
        self.assertEqual(lower["replaced_by"], [{"sport": "ride", "count": 3}])
        self.assertIn("Lower-body lifts happened as planned 1 of 4 times. Replaced by a ride 3 times.",
                      [item["text"] for item in summary["findings"]])

    def test_future_days_and_rest_are_ignored(self):
        monday = date(2026, 10, 5)
        summary = summarize_follow_through([_week(monday, [
            _day(monday, "ride", "easy"),
            _day(monday + timedelta(days=1), "rest", status="rest_day_changed"),
            _day(monday + timedelta(days=2), "ride", "easy", status="not_completed_yet"),
        ])])
        self.assertEqual([(kind["kind"], kind["planned"]) for kind in summary["kinds"]], [("easy_ride", 1)])
        self.assertEqual(summary["weekdays"][2]["planned"], 0)

    def test_flags_goal_sessions_that_are_never_planned(self):
        summary = summarize_follow_through(_weeks(6, lambda monday, index: [_day(monday, "ride", "easy")]), [QUALITY_GOAL])
        self.assertEqual(summary["quality_rides"], {"weeks_planned": 0, "weeks": 6, "weekly_target": 1.0})
        self.assertEqual(summary["findings"][0]["key"], "quality_not_planned")
        self.assertIn("planned in only 0 of 6 weeks", summary["findings"][0]["text"])

    def test_planned_but_skipped_quality_is_not_an_under_planning_finding(self):
        def build(monday, index):
            return [_day(monday + timedelta(days=1), "ride", "interval", status="skipped")]

        summary = summarize_follow_through(_weeks(4, build), [QUALITY_GOAL])
        keys = [item["key"] for item in summary["findings"]]
        self.assertNotIn("quality_not_planned", keys)
        self.assertIn("dropped_quality_ride", keys)

    def test_reliable_and_shaky_weekdays(self):
        def build(monday, index):
            return [
                _day(monday, "ride", "easy"),
                _day(monday + timedelta(days=6), "strength", "strength_upper", status="skipped"),
            ]

        summary = summarize_follow_through(_weeks(4, build), [QUALITY_GOAL])
        self.assertEqual(summary["reliable_weekdays"], ["Monday"])
        self.assertEqual(summary["shaky_weekdays"], ["Sunday"])
        texts = [item["text"] for item in summary["findings"]]
        self.assertIn("Monday is your most reliable day (100% done). Put the quality ride there.", texts)
        self.assertIn("Plans for Sunday held only 0 of 4 times. Keep key sessions off them.", texts)

    def test_too_few_samples_give_no_weekday_verdict(self):
        summary = summarize_follow_through(_weeks(2, lambda monday, index: [_day(monday, "ride", "easy")]))
        self.assertEqual((summary["reliable_weekdays"], summary["shaky_weekdays"]), ([], []))

    def test_empty(self):
        summary = summarize_follow_through([])
        self.assertEqual((summary["weeks"], summary["kinds"], summary["findings"]), (0, [], []))


if __name__ == "__main__":
    unittest.main()
