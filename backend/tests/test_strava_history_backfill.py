import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta

from fastapi import HTTPException

from backend.app import db
from backend.app.services import strava_history_backfill as backfill

NOW = datetime(2026, 10, 14, 9, 0)


def limits(short_used=10, daily_used=100):
    return {"short_limit": 100, "daily_limit": 1000, "short_usage": short_used, "daily_usage": daily_used,
            "short_remaining": 100 - short_used, "daily_remaining": 1000 - daily_used}


def streams(hr=False):
    data = {"time": {"data": [0, 60, 120]}, "distance": {"data": [0, 250, 500]}}
    if hr:
        data["heartrate"] = {"data": [140, 150, 155]}
    return data


class HistoryBackfillTests(unittest.TestCase):
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
        self.calls = []
        self.responses = {}

    def add(self, activity_id, day, kind="Run", avg_hr=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, avg_hr) VALUES (?, ?, ?, ?, 30, 5, ?)",
            (activity_id, day, kind, kind, avg_hr),
        )
        self.conn.commit()

    def fetch(self, client, strava_id, keys):
        self.calls.append(strava_id)
        response = self.responses.get(strava_id, (streams(), limits()))
        if isinstance(response, Exception):
            raise response
        return response

    def batch(self, **kwargs):
        return backfill.run_batch(
            self.conn, now=kwargs.pop("now", NOW), get_setting_fn=lambda key: None, set_setting_fn=lambda key, value: None,
            fetch_streams_fn=self.fetch, token_fn=lambda get, set_: "token", client_factory=lambda token: nullcontext(object()), **kwargs,
        )

    def test_nothing_happens_until_it_is_switched_on(self):
        self.add("old-run", "2015-05-01")
        self.assertEqual(self.batch(), {"ran": False, "reason": "disabled"})
        self.assertEqual(self.calls, [])

    def test_runs_without_heart_rate_are_fetched_runs_first_newest_first(self):
        self.add("ride", "2016-05-01", "Ride")
        self.add("run-2014", "2014-05-01")
        self.add("run-2016", "2016-06-01")
        backfill.set_enabled(self.conn, True)

        result = self.batch()

        self.assertEqual(self.calls, ["run-2016", "run-2014", "ride"])
        self.assertEqual(result["fetched"], 3)
        cached = self.conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = 'run-2014'").fetchone()
        self.assertEqual(json.loads(cached["streams_json"])["distance"]["data"], [0, 250, 500])
        # No heart rate or power: streams are kept, but no training-load summary is invented.
        self.assertIsNone(self.conn.execute("SELECT 1 FROM activity_stream_summaries WHERE activity_id = 'run-2014'").fetchone())
        status = backfill.status(self.conn)
        self.assertEqual((status["remaining"], status["fetched"]), (0, 3))
        self.assertIsNone(status["next_run_at"])  # Nothing left to wait for.
        self.assertFalse(status["running"])

    def test_heart_rate_streams_also_store_a_summary(self):
        self.add("hr-run", "2023-05-01", avg_hr=150)
        self.responses["hr-run"] = (streams(hr=True), limits())
        backfill.set_enabled(self.conn, True)

        self.batch()

        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM activity_stream_summaries WHERE activity_id = 'hr-run'").fetchone())

    def test_stops_at_the_reserve_and_waits_for_the_next_window(self):
        for index in range(5):
            self.add(f"run-{index}", f"2015-05-0{index + 1}")
        self.responses["run-4"] = (streams(), limits(short_used=66))  # Newest first: the first call already hits the reserve.
        backfill.set_enabled(self.conn, True)

        result = self.batch()

        self.assertEqual(self.calls, ["run-4"])
        self.assertEqual(result["paused_reason"], "Waiting for Strava's 15-minute limit.")
        self.assertEqual(self.batch(now=NOW + timedelta(minutes=5)), {"ran": False, "reason": "not due"})
        self.batch(now=NOW + timedelta(minutes=17))
        self.assertEqual(len(self.calls), 5)

    def test_daily_reserve_names_tomorrow(self):
        self.add("run", "2015-05-01")
        self.add("run-2", "2015-05-02")
        self.responses["run-2"] = (streams(), limits(daily_used=660))
        backfill.set_enabled(self.conn, True)

        self.assertIn("continues tomorrow", self.batch()["paused_reason"])

    def test_manual_entries_are_marked_and_not_tried_again(self):
        self.add("manual", "2015-05-01")
        self.responses["manual"] = (None, limits())
        backfill.set_enabled(self.conn, True)

        self.batch()
        self.batch(now=NOW + timedelta(minutes=17))

        self.assertEqual(self.calls, ["manual"])
        self.assertEqual(backfill.status(self.conn)["no_streams"], 1)

    def test_rate_limit_error_pauses_without_marking_and_other_errors_retry_three_times(self):
        self.add("limited", "2015-05-02")
        self.add("broken", "2015-05-01")
        self.responses["limited"] = HTTPException(502, "Strava streams fetch failed: Rate Limit Exceeded")
        backfill.set_enabled(self.conn, True)

        result = self.batch()
        self.assertIn("rate limit", result["paused_reason"])
        self.assertEqual(backfill.status(self.conn)["remaining"], 2)

        self.responses["limited"] = (streams(), limits())
        self.responses["broken"] = HTTPException(502, "Strava streams fetch failed: server error")
        for step in range(1, 5):
            self.batch(now=NOW + timedelta(minutes=17 * step))
        self.assertEqual(self.calls.count("broken"), 3)
        self.assertEqual(backfill.status(self.conn)["failed"], 1)

    def test_switches_itself_off_when_everything_is_fetched_and_can_be_paused(self):
        self.add("run", "2015-05-01")
        backfill.set_enabled(self.conn, True)
        self.batch()
        self.batch(now=NOW + timedelta(minutes=17))
        self.assertFalse(backfill.status(self.conn)["enabled"])

        self.add("another", "2015-06-01")
        backfill.set_enabled(self.conn, True)
        paused = backfill.set_enabled(self.conn, False)
        self.assertEqual(paused["paused_reason"], "Paused by you.")
        self.assertEqual(self.batch(now=NOW + timedelta(hours=1))["reason"], "disabled")


if __name__ == "__main__":
    unittest.main()
