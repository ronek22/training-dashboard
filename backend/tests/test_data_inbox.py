import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from backend.app import db
from backend.app.services.data_inbox import build_inbox, dismiss

TODAY = date.today()


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


class DataInboxTests(unittest.TestCase):
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

    def activity(self, activity_id, day, kind="Ride", name=None, avg_hr=None, linked=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, avg_hr, linked_planned_session_id) VALUES (?, ?, ?, ?, 60, ?, ?)",
            (activity_id, day, kind, name or f"{kind} {day}", avg_hr, linked),
        )

    def feedback(self, activity_id):
        self.conn.execute(
            "INSERT INTO activity_feedback (activity_id, rpe, energy, muscle_soreness) VALUES (?, 5, 3, 2)", (activity_id,)
        )

    def streams(self, activity_id, heartrate=True):
        self.conn.execute(
            "INSERT INTO activity_details (activity_id, fetched_at, source_status, streams_json) VALUES (?, 'now', 'ok', '{}')",
            (activity_id,),
        )
        self.conn.execute(
            "INSERT INTO activity_stream_summaries (activity_id, fetched_at, source, has_heartrate) VALUES (?, 'now', 'strava', ?)",
            (activity_id, int(heartrate)),
        )

    def keys(self, kind=None):
        return [item["key"] for item in build_inbox(self.conn)["items"] if kind is None or item["kind"] == kind]

    def test_missing_feedback_within_the_window(self):
        self.activity("ride-new", ago(2))
        self.activity("ride-done", ago(3))
        self.feedback("ride-done")
        self.activity("ride-old", ago(40))
        self.activity("walk", ago(1), kind="Walk")
        self.activity("lift-studio", ago(4), kind="WeightTraining")
        self.conn.execute(
            "INSERT INTO strength_workout_sessions (template_name, status, started_at, linked_activity_id) VALUES ('A', 'completed', ?, 'lift-studio')",
            (ago(4),),
        )
        self.activity("lift-manual", ago(5), kind="WeightTraining")
        self.assertEqual(self.keys("feedback"), ["feedback:ride-new", "feedback:lift-manual"])

    def test_unmatched_planned_sessions_offer_nearby_activities(self):
        monday = TODAY - timedelta(days=TODAY.weekday() + 7)  # Last week, fully in the past.
        days = [
            {"date": (monday + timedelta(days=i)).isoformat(), "session_type": kind, "title": title}
            for i, (kind, title) in enumerate([
                ("Ride", "Sweet spot"), ("Rest", "Rest"), ("Run", "Easy run"), ("Rest", "Rest"),
                ("Rest", "Rest"), ("Rest", "Rest"), ("Rest", "Rest"),
            ])
        ]
        self.conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES (?, ?)", (monday.isoformat(), json.dumps(days)))
        # The run was planned on Wednesday; a ride three days later is too far to infer, so Monday is unmatched.
        self.activity("run-wed", days[2]["date"], kind="Run")
        self.activity("ride-tue", days[1]["date"], kind="Ride")
        self.conn.commit()
        inbox = build_inbox(self.conn)
        unmatched = [item for item in inbox["items"] if item["kind"] == "unmatched_session"]
        self.assertEqual([item["title"] for item in unmatched], [])  # Tuesday's ride counts as moved.

        self.conn.execute("DELETE FROM activities WHERE id = 'ride-tue'")
        self.activity("ride-sat", days[5]["date"], kind="Ride")
        self.activity("ride-linked", days[1]["date"], kind="VirtualRide", linked="plan-elsewhere")
        self.activity("run-rest-day", days[1]["date"], kind="Run")  # Another sport, so Monday does not count as moved.
        self.conn.commit()
        unmatched = [item for item in build_inbox(self.conn)["items"] if item["kind"] == "unmatched_session"]
        self.assertEqual([item["title"] for item in unmatched], ["Sweet spot"])
        self.assertEqual(unmatched[0]["session_id"], f"plan-{monday.isoformat()}-{days[0]['date']}-1")
        # Saturday is too far, the virtual ride is linked elsewhere and the run already fulfils Wednesday.
        # A run on a rest day fulfils nothing, so it is offered.
        self.assertEqual([item["id"] for item in unmatched[0]["candidates"]], ["run-rest-day"])

        self.conn.execute("UPDATE activities SET linked_planned_session_id = ? WHERE id = 'ride-sat'", (unmatched[0]["session_id"],))
        self.conn.commit()
        self.assertEqual(self.keys("unmatched_session"), [])

    def test_missing_heart_rate_streams(self):
        self.activity("no-streams", ago(1), avg_hr=140)
        self.activity("hr-lost", ago(2), avg_hr=140)
        self.streams("hr-lost", heartrate=False)
        self.activity("no-strap", ago(3))
        self.streams("no-strap", heartrate=False)
        self.activity("complete", ago(4), avg_hr=140)
        self.streams("complete")
        self.activity("healthfit:abc", ago(5), avg_hr=140)
        self.activity("lift", ago(1), kind="WeightTraining", avg_hr=110)
        self.activity("old", ago(45), avg_hr=140)
        self.assertEqual(self.keys("missing_streams"), ["streams:no-streams", "streams:hr-lost"])

    def test_stale_ftp_benchmark(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES (?, 'ftp', 242, 'W')", (ago(70),))
        self.conn.commit()
        items = [item for item in build_inbox(self.conn)["items"] if item["kind"] == "stale_benchmark"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["key"], f"ftp:stored:{ago(70)}")
        self.assertIn("242 W", items[0]["title"])

        self.conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES (?, 'ftp', 245, 'W')", (ago(10),))
        self.conn.commit()
        self.assertEqual(self.keys("stale_benchmark"), [])

    def test_dismissed_items_stay_dismissed_and_count_matches(self):
        self.activity("ride-a", ago(1))
        self.activity("ride-b", ago(2))
        self.conn.commit()
        self.assertEqual(build_inbox(self.conn)["count"], 2 + len(self.keys("missing_streams")))
        result = dismiss(self.conn, "feedback:ride-a")
        self.assertNotIn("feedback:ride-a", [item["key"] for item in result["items"]])
        self.assertEqual(self.keys("feedback"), ["feedback:ride-b"])
        self.assertEqual(build_inbox(self.conn)["counts"]["feedback"], 1)
        with self.assertRaises(LookupError):
            dismiss(self.conn, "feedback:does-not-exist")

    def test_resolving_the_gap_clears_the_item(self):
        self.activity("ride", ago(1), avg_hr=140)
        self.conn.commit()
        self.assertEqual(set(self.keys()), {"feedback:ride", "streams:ride"})
        self.feedback("ride")
        self.streams("ride")
        self.conn.commit()
        inbox = build_inbox(self.conn)
        self.assertEqual(inbox["count"], 0)
        self.assertEqual(inbox["items"], [])


if __name__ == "__main__":
    unittest.main()
