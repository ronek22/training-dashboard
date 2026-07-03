import sqlite3
import unittest
from datetime import datetime, timedelta

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

    def tearDown(self):
        self.conn.close()

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
            {"date": yesterday, "session_type": "Ride", "session_id": "ride-yesterday"},
            [],
            by_date,
            week_days_by_date,
            [],
        )

        self.assertEqual(comparison["status"], "moved")
        self.assertEqual(comparison["moved_to_date"], today)
        self.assertEqual(len(comparison["completed_activities"]), 1)
