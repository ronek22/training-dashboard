import sqlite3
import unittest
import json
from datetime import datetime, timedelta

from backend.app.services.activities import _attach_strength_plan_identity
from backend.app.services.plans import build_plan_day_comparison


def make_activity_row(
    conn: sqlite3.Connection,
    *,
    activity_id: str,
    date: str,
    activity_type: str,
    workout_intent: str | None = None,
    name: str = "Test activity",
    distance_km: float | None = None,
    duration_min: float | None = None,
    avg_pace: str | None = None,
    avg_watts: float | None = None,
    linked_planned_session_id: str | None = None,
) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT
            ? AS id,
            ? AS date,
            ? AS type,
            ? AS workout_intent,
            ? AS name,
            ? AS distance_km,
            ? AS duration_min,
            ? AS avg_pace,
            ? AS avg_watts,
            ? AS linked_planned_session_id
        """,
        (
            activity_id,
            date,
            activity_type,
            workout_intent,
            name,
            distance_km,
            duration_min,
            avg_pace,
            avg_watts,
            linked_planned_session_id,
        ),
    ).fetchone()


class PlanDayComparisonTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE weekly_plans (
                week_start TEXT PRIMARY KEY,
                title TEXT,
                focus TEXT,
                overview TEXT,
                days_json TEXT NOT NULL,
                notes TEXT
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def add_plan_days(self, days: list[dict]) -> None:
        self.conn.execute(
            "INSERT INTO weekly_plans (week_start, days_json) VALUES (?, ?)",
            ("2026-07-20", json.dumps(days)),
        )

    def test_strength_activity_uses_unique_same_day_template_as_display_identity(self):
        self.add_plan_days([{
            "date": "2026-07-22",
            "session_id": "strength-a",
            "session_type": "WeightTraining",
            "template_id": "workout-a",
            "template_label": "Workout A · Upper Chest",
            "title": "Workout A · Upper Chest",
        }])

        enriched = _attach_strength_plan_identity(self.conn, {
            "id": "healthfit:1",
            "date": "2026-07-22",
            "type": "WeightTraining",
            "name": "Functional Strength Training",
            "linked_planned_session_id": None,
        })

        self.assertEqual(enriched["source_name"], "Functional Strength Training")
        self.assertEqual(enriched["display_name"], "Workout A · Upper Chest")
        self.assertEqual(enriched["planned_strength_identity"]["match_strategy"], "inferred")

    def test_explicit_strength_link_takes_priority(self):
        self.add_plan_days([
            {
                "date": "2026-07-22", "session_id": "strength-a", "session_type": "WeightTraining",
                "template_id": "workout-a", "template_label": "Workout A · Upper Chest", "title": "Workout A",
            },
            {
                "date": "2026-07-22", "session_id": "strength-b", "session_type": "WeightTraining",
                "template_id": "workout-b", "template_label": "Workout B · Back + Arms", "title": "Workout B",
            },
        ])

        enriched = _attach_strength_plan_identity(self.conn, {
            "id": "healthfit:1",
            "date": "2026-07-22",
            "type": "WeightTraining",
            "name": "Functional Strength Training",
            "linked_planned_session_id": "strength-b",
        })

        self.assertEqual(enriched["display_name"], "Workout B · Back + Arms")
        self.assertEqual(enriched["planned_strength_identity"]["match_strategy"], "explicit")

    def test_ambiguous_same_day_strength_sessions_keep_source_title(self):
        self.add_plan_days([
            {
                "date": "2026-07-22", "session_id": "strength-a", "session_type": "WeightTraining",
                "template_id": "workout-a", "template_label": "Workout A", "title": "Workout A",
            },
            {
                "date": "2026-07-22", "session_id": "strength-b", "session_type": "WeightTraining",
                "template_id": "workout-b", "template_label": "Workout B", "title": "Workout B",
            },
        ])

        enriched = _attach_strength_plan_identity(self.conn, {
            "id": "healthfit:1",
            "date": "2026-07-22",
            "type": "WeightTraining",
            "name": "Functional Strength Training",
            "linked_planned_session_id": None,
        })

        self.assertEqual(enriched["display_name"], "Functional Strength Training")
        self.assertIsNone(enriched["planned_strength_identity"])

    def test_today_is_not_marked_moved_by_yesterdays_extra_matching_activity(self):
        today = datetime.now().date().isoformat()
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        week_days_by_date = {
            yesterday: {"date": yesterday, "session_type": "WeightTraining"},
            today: {"date": today, "session_type": "Ride"},
        }
        by_date = {
            yesterday: [
                make_activity_row(
                    self.conn,
                    activity_id="ride-yesterday",
                    date=yesterday,
                    activity_type="Ride",
                    workout_intent="easy",
                    duration_min=50,
                )
            ]
        }

        comparison = build_plan_day_comparison(
            self.conn,
            {"date": today, "session_type": "Ride", "session_id": "ride-today"},
            [],
            by_date,
            week_days_by_date,
            [],
        )

        self.assertEqual(comparison["status"], "not_completed_yet")
        self.assertEqual(comparison["completed_activities"], [])

    def test_past_day_can_still_be_marked_moved_when_done_on_nearby_day(self):
        today = datetime.now().date().isoformat()
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        week_days_by_date = {
            yesterday: {"date": yesterday, "session_type": "Ride"},
            today: {"date": today, "session_type": "WeightTraining"},
        }
        moved_activity = make_activity_row(
            self.conn,
            activity_id="ride-today",
            date=today,
            activity_type="Ride",
            workout_intent="easy",
            duration_min=50,
        )
        by_date = {today: [moved_activity]}

        comparison = build_plan_day_comparison(
            self.conn,
            {"date": yesterday, "session_type": "Ride", "session_id": "ride-yesterday"},
            [],
            by_date,
            week_days_by_date,
            [],
        )

        self.assertEqual(comparison["status"], "moved")
        self.assertEqual(comparison["moved_to_date"], today)
        self.assertEqual(len(comparison["completed_activities"]), 1)

    def test_activity_completed_early_only_fulfills_its_explicit_planned_session(self):
        today = datetime.now().date().isoformat()
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        ride = make_activity_row(
            self.conn,
            activity_id="ride-today",
            date=today,
            activity_type="Ride",
            workout_intent="easy",
            duration_min=60,
        )
        early_strength = make_activity_row(
            self.conn,
            activity_id="strength-today",
            date=today,
            activity_type="WeightTraining",
            workout_intent="strength_general",
            duration_min=45,
            linked_planned_session_id="strength-tomorrow",
        )
        by_date = {today: [ride, early_strength]}
        week_days_by_date = {
            today: {"date": today, "session_type": "Ride", "session_id": "ride-today"},
            tomorrow: {
                "date": tomorrow,
                "session_type": "WeightTraining",
                "session_id": "strength-tomorrow",
            },
        }

        ride_comparison = build_plan_day_comparison(
            self.conn,
            week_days_by_date[today],
            by_date[today],
            by_date,
            week_days_by_date,
            [],
        )
        strength_comparison = build_plan_day_comparison(
            self.conn,
            week_days_by_date[tomorrow],
            [],
            by_date,
            week_days_by_date,
            [early_strength],
        )

        self.assertEqual(ride_comparison["status"], "matched")
        self.assertEqual(
            [activity["id"] for activity in ride_comparison["completed_activities"]],
            ["ride-today"],
        )
        self.assertEqual(strength_comparison["status"], "linked")
        self.assertEqual(strength_comparison["label"], "Completed early")
        self.assertEqual(strength_comparison["fulfilled_on_date"], today)
        self.assertEqual(strength_comparison["schedule_timing"], "early")
        self.assertEqual(
            [activity["id"] for activity in strength_comparison["completed_activities"]],
            ["strength-today"],
        )
