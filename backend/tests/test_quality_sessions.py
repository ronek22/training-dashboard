import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from backend.app import db
from backend.app.services.goal_history import build_goal_period_history
from backend.app.services.goal_outcomes import outcome_keys_for_goal
from backend.app.services.goal_review import calibrated_target
from backend.app.services.goals import (
    build_goal_requirements,
    create_goal_data,
    draft_goal_data,
    get_goal_data,
    goal_metric_label,
    goal_metric_unit,
    goal_value_for_window,
)


class QualitySessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", str(Path(self.directory.name) / "quality.db"))
        self.db_patch.start()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def add_activity(
        self,
        activity_id,
        *,
        intent=None,
        activity_type="Ride",
        date="2026-09-20",
        streams=None,
        device_watts=True,
        source_status="test",
        avg_watts=None,
        duration_min=30,
    ):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, workout_intent, duration_min, avg_watts) VALUES (?, ?, ?, ?, ?, ?)",
            (activity_id, date, activity_type, intent, duration_min, avg_watts),
        )
        if streams is not None:
            self.conn.execute(
                "INSERT INTO activity_details (activity_id, fetched_at, source_status, detail_json, streams_json) VALUES (?, ?, ?, ?, ?)",
                (activity_id, date, source_status, json.dumps({"device_watts": device_watts}) if device_watts is not None else None, json.dumps(streams)),
            )
        self.conn.commit()

    @staticmethod
    def streams(seconds, watts):
        return {"time": {"data": list(range(seconds + 1))}, "watts": {"data": [watts] * (seconds + 1)}}

    @staticmethod
    def quality_goal(**changes):
        return {
            "goal_family": "process",
            "metric_type": "quality_sessions",
            "period_type": "week",
            "target_value": 2,
            "activity_type": "Ride",
            **changes,
        }

    def test_explicit_quality_intents_are_counted_without_streams(self):
        for index, intent in enumerate(("tempo", "interval", "sweet_spot", "race_specific")):
            self.add_activity(f"intent-{index}", intent=intent)
        self.add_activity("easy", intent="easy")

        value = goal_value_for_window(
            self.conn,
            self.quality_goal(),
            start_date="2026-09-01",
            end_date="2026-09-30",
        )
        self.assertEqual(value, 4)

    def test_power_fallback_requires_twenty_minutes_above_ftp_and_missing_intent(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-09-01', 'ftp', 230)")
        self.conn.commit()
        self.add_activity("power-quality", streams=self.streams(20 * 60, 205))
        self.add_activity("power-short", streams=self.streams(19 * 60 + 59, 250))
        self.add_activity("power-easy", intent="easy", streams=self.streams(30 * 60, 250))
        self.add_activity("power-low", streams=self.streams(30 * 60, 200))

        value = goal_value_for_window(
            self.conn,
            self.quality_goal(),
            start_date="2026-09-01",
            end_date="2026-09-30",
        )
        self.assertEqual(value, 1)

    def test_power_fallback_is_conservative_for_sparse_streams(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-09-01', 'ftp', 230)")
        self.conn.commit()
        self.add_activity("sparse", streams={"time": {"data": [0, 1200]}, "watts": {"data": [210, 210]}})

        value = goal_value_for_window(
            self.conn,
            self.quality_goal(),
            start_date="2026-09-01",
            end_date="2026-09-30",
        )
        self.assertEqual(value, 0)

    def test_power_fallback_requires_verified_provenance_and_valid_stream_segments(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-09-01', 'ftp', 230)")
        self.conn.commit()
        self.add_activity("estimated", streams=self.streams(30 * 60, 210), device_watts=False)
        self.add_activity("missing-detail", streams=self.streams(30 * 60, 210), device_watts=None)
        self.add_activity(
            "gap",
            streams={"time": {"data": [*range(600), 700, *range(701, 1301)]}, "watts": {"data": [210] * 1301}},
        )
        self.add_activity(
            "non-monotonic",
            streams={"time": {"data": [*range(600), 500, *range(501, 1301)]}, "watts": {"data": [210] * 1400}},
        )
        self.assertEqual(
            goal_value_for_window(self.conn, self.quality_goal(), start_date="2026-09-01", end_date="2026-09-30"),
            0,
        )

    def test_virtual_ride_stream_backfill_is_eligible(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2026-09-01', 'ftp', 230)")
        self.conn.commit()
        self.add_activity(
            "virtual-quality",
            activity_type="VirtualRide",
            source_status="streams_backfill",
            device_watts=None,
            streams=self.streams(20 * 60, 205),
        )
        self.assertEqual(
            goal_value_for_window(self.conn, self.quality_goal(), start_date="2026-09-01", end_date="2026-09-30"),
            1,
        )

    def test_activities_count_ride_includes_virtual_ride(self):
        self.add_activity("outdoor", activity_type="Ride")
        self.add_activity("indoor", activity_type="VirtualRide")
        goal = {"metric_type": "activities_count", "activity_type": "Ride"}
        self.assertEqual(
            goal_value_for_window(self.conn, goal, start_date="2026-09-01", end_date="2026-09-30"),
            2,
        )

    def test_power_stream_benchmark_uses_exact_cached_twenty_minute_effort(self):
        watts = [120] * 1801
        watts[600:1801] = [240] * 1201
        self.add_activity(
            "long-ride",
            streams=self.streams(1800, 120),
            avg_watts=120,
            duration_min=30,
        )
        self.conn.execute(
            "UPDATE activity_details SET streams_json = ?, detail_json = ? WHERE activity_id = ?",
            (json.dumps({"time": {"data": list(range(1801))}, "watts": {"data": watts}}), json.dumps({"device_watts": True}), "long-ride"),
        )
        self.conn.commit()
        result = create_goal_data(
            self.conn,
            title="Hold 220 W for 20 min",
            period_type="year",
            goal_family="benchmark",
            activity_type="Ride",
            target_config={"duration_min": 20, "target_watts": 220, "measurement": "power_stream"},
        )
        goal = get_goal_data(self.conn, result["id"])
        self.assertEqual(goal["target_config"]["measurement"], "power_stream")
        self.assertEqual(goal["current_value"], 240.0)
        self.assertEqual(goal["performance_snapshot"]["measurement"], "power_stream")
        self.assertEqual(goal["benchmark_history"]["entries"][0]["value_label"], "240 W for 20 min")

    def test_metric_registry_requirements_history_and_outcome_link(self):
        goal = self.quality_goal()
        self.assertEqual(goal_metric_unit("quality_sessions"), "sessions")
        self.assertEqual(goal_metric_label("quality_sessions"), "quality sessions")
        requirements = build_goal_requirements(
            goal_family="process",
            metric_type="quality_sessions",
            activity_type="Ride",
            target_value=2,
        )
        self.assertEqual(requirements[0]["type"], "quality_sessions")
        self.assertEqual(requirements[0]["minimum_sessions"], 2)
        self.assertIn("sweet_spot", requirements[0]["preferred_intents"])
        self.assertEqual(build_goal_period_history(self.conn, goal, periods=4, today=date(2026, 9, 28))["kind"], "recurring")
        self.assertEqual(outcome_keys_for_goal(goal), ["cycling_power_20m"])
        self.assertEqual(calibrated_target("quality_sessions", 2.1), 3.0)

    def test_simple_quality_draft_is_ready(self):
        draft = draft_goal_data("2 structured quality rides per week")
        self.assertTrue(draft["is_ready"])
        self.assertEqual(draft["goal"]["metric_type"], "quality_sessions")
        self.assertEqual(draft["goal"]["activity_type"], "Ride")
        self.assertEqual(draft["goal"]["target_value"], 2)


if __name__ == "__main__":
    unittest.main()
