import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.app import db
from backend.app.models.plans import WinterArc
from backend.app.services import load_forecast
from backend.app.services.dashboard import build_training_load_summary, stream_power_tss_on_day
from backend.app.services.life_load import set_life_load_day
from backend.app.services.winter_arc import arc_week, save_winter_arc

TODAY = date(2029, 12, 5)  # Wednesday; this week is Mon 2029-12-03, previews start Mon 2029-12-10.
MONDAY = date(2029, 12, 3)


class LoadForecastTests(unittest.TestCase):
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

    def ftp(self, day, watts):
        self.conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES (?, 'ftp', ?, 'W')", (day, watts))
        self.conn.commit()

    def ride(self, activity_id, day, minutes=60, avg_watts=None, stream=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, avg_watts) VALUES (?, ?, 'Ride', 'Ride', ?, 30, ?)",
            (activity_id, day, minutes, avg_watts),
        )
        if stream:
            self.conn.execute(
                "INSERT INTO activity_stream_summaries (activity_id, fetched_at, source, power_tss, normalized_power) VALUES (?, ?, 'power_tss', ?, ?)",
                (activity_id, stream["fetched_at"], stream["tss"], stream["np"]),
            )
        self.conn.commit()

    def steady_history(self, weeks=10, minutes=60, avg_watts=150):
        """A ride every day before today at a steady load, so fitness has settled."""
        for offset in range(1, weeks * 7 + 1):
            day = (TODAY - timedelta(days=offset)).isoformat()
            self.ride(f"h-{offset}", day, minutes=minutes, avg_watts=avg_watts)

    def plan(self, week_start, days):
        self.conn.execute(
            "INSERT OR REPLACE INTO weekly_plans (week_start, title, days_json) VALUES (?, 'Plan', ?)",
            (week_start.isoformat(), json.dumps(days)),
        )
        self.conn.commit()

    def week_of_rides(self, week_start, minutes, workout_id=None, intent="easy"):
        return [
            {"date": (week_start + timedelta(days=offset)).isoformat(), "session_type": "ride", "title": "Ride",
             "target_duration_min": minutes, "workout_intent": intent, "cycling_workout_id": workout_id}
            for offset in range(7)
        ]

    # --- Past load uses the FTP valid on each date -------------------------------------------

    def test_stream_tss_is_rescored_with_the_ftp_of_the_ride_day(self):
        # Fetched when FTP was 250: 1 h at NP 180 -> IF 0.72 -> 51.8 TSS. On its day FTP was 200 -> IF 0.9 -> 81.
        self.assertAlmostEqual(stream_power_tss_on_day(51.84, 180, 250, 200), 81.0, places=1)
        self.assertEqual(stream_power_tss_on_day(51.84, 180, 250, 250), 51.84)
        self.assertEqual(stream_power_tss_on_day(51.84, None, 250, 200), 51.84)

        self.ftp("2029-09-01", 200)
        self.ftp("2029-11-20", 250)
        self.ride("old", "2029-11-10", stream={"fetched_at": "2029-12-04T08:00:00", "tss": 51.84, "np": 180})
        self.ride("avg-only", "2029-11-12", minutes=60, avg_watts=150)
        chart = {item["date"]: item for item in build_training_load_summary(self.conn, days=42, today=TODAY)["chart"]}

        self.assertEqual(chart["2029-11-10"]["load"], 81.0)
        # Without a stream, average power is scored with the 200 W FTP of that day: IF 0.7725 -> 59.7.
        self.assertEqual(chart["2029-11-12"]["load"], 59.7)

    # --- Planned sessions -----------------------------------------------------------------------

    def test_planned_session_load_by_session_type(self):
        sweet = load_forecast.planned_session_load({"session_type": "ride", "target_duration_min": 70, "cycling_workout_id": "sweet-spot-3x10"})
        easy = load_forecast.planned_session_load({"session_type": "ride", "target_duration_min": 70, "workout_intent": "easy"})
        self.assertGreater(sweet["ride"], easy["ride"])
        self.assertAlmostEqual(easy["ride"], 70 / 60 * 0.68 ** 2 * 100, places=3)
        self.assertEqual(load_forecast.planned_session_load({"session_type": "strength", "target_duration_min": 50}), {"ride": 0.0, "other": 40.0})
        self.assertEqual(load_forecast.planned_session_load({"session_type": "run", "target_duration_min": 30}, run_rate=2.0)["other"], 60.0)
        self.assertEqual(load_forecast.planned_session_load({"session_type": "rest"}), {"ride": 0.0, "other": 0.0})

    def test_arc_ride_load_counts_key_rides_harder_than_z2(self):
        save_winter_arc(self.conn, WinterArc(blocks=[
            {"start_date": "2029-12-10", "end_date": "2029-12-16", "focus": "base", "weekly_hours": 6, "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}},
            {"start_date": "2029-12-17", "end_date": "2029-12-23", "focus": "sweet_spot", "weekly_hours": 6, "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 0}},
        ]), TODAY)
        base = load_forecast.arc_ride_load(arc_week(self.conn, "2029-12-10"))
        build = load_forecast.arc_ride_load(arc_week(self.conn, "2029-12-17"))
        self.assertAlmostEqual(base, 6 * 0.68 ** 2 * 100, places=3)
        self.assertGreater(build, base)

    # --- Projection -----------------------------------------------------------------------------

    def test_projection_continues_from_today_and_is_marked_estimated(self):
        self.steady_history()
        self.plan(MONDAY, self.week_of_rides(MONDAY, 60))
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)

        self.assertEqual(forecast["history"][-1]["date"], TODAY.isoformat())
        self.assertEqual(forecast["projection"][0]["date"], "2029-12-06")
        self.assertEqual(forecast["projection"][-1]["date"], "2030-01-06")  # this week + 4 preview Sundays
        self.assertTrue(all(item["estimated"] for item in forecast["projection"]))
        self.assertEqual([week["kind"] for week in forecast["weeks"]], ["current"] + ["preview"] * 4)
        self.assertTrue(all(week["basis"] == "plan" for week in forecast["weeks"]))
        # The first projected day steps from today's fitness, not from zero.
        today_ctl = forecast["history"][-1]["ctl"]
        self.assertLess(abs(forecast["projection"][0]["ctl"] - today_ctl), 2)
        self.assertEqual(forecast["status"], "ok")
        self.assertIn("a week", forecast["message"])

    def test_a_steep_planned_ramp_is_flagged(self):
        self.steady_history(minutes=45)
        self.plan(MONDAY, self.week_of_rides(MONDAY, 180, intent="tempo"))
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)

        steep = [week for week in forecast["weeks"] if week["flag"] == "steep"]
        self.assertTrue(steep)
        self.assertTrue(all(week["ramp"] > load_forecast.RAMP_STEEP for week in steep))
        self.assertEqual(forecast["status"], "steep")
        self.assertIn(f"above the safe {load_forecast.RAMP_STEEP:g} a week", forecast["message"])

    def test_a_build_block_that_does_not_build_is_flat(self):
        self.steady_history(minutes=90)
        self.plan(MONDAY, self.week_of_rides(MONDAY, 90))
        save_winter_arc(self.conn, WinterArc(blocks=[
            {"start_date": "2029-12-10", "end_date": "2030-01-06", "focus": "sweet_spot", "label": "SS build", "weekly_hours": 3,
             "ride_mix": {"z2": 1, "sweet_spot": 1, "vo2": 0}},
        ]), TODAY)
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)

        previews = forecast["weeks"][1:]
        self.assertTrue(all(week["basis"] == "arc" and week["flag"] == "flat" for week in previews))
        self.assertIsNone(forecast["weeks"][0]["flag"])  # the current week is outside the arc
        self.assertEqual(forecast["status"], "flat")
        self.assertIn("SS build", forecast["message"])

    def test_a_maintain_block_holding_steady_is_not_flat(self):
        self.steady_history(minutes=60)
        self.plan(MONDAY, self.week_of_rides(MONDAY, 60))
        save_winter_arc(self.conn, WinterArc(blocks=[
            {"start_date": "2029-12-10", "end_date": "2030-01-06", "focus": "maintain", "weekly_hours": 7,
             "ride_mix": {"z2": 4, "sweet_spot": 0, "vo2": 0}},
        ]), TODAY)
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)
        self.assertFalse(any(week["flag"] for week in forecast["weeks"]))

    def test_mountains_days_shrink_rides_and_add_trip_load(self):
        self.steady_history()
        self.plan(MONDAY, self.week_of_rides(MONDAY, 60))
        before = load_forecast.build_load_forecast(self.conn, TODAY)["weeks"][2]["load"]
        for offset in range(3):
            set_life_load_day(self.conn, (date(2029, 12, 17) + timedelta(days=offset)).isoformat(), ["mountains"], None)
        week = load_forecast.build_load_forecast(self.conn, TODAY)["weeks"][2]

        self.assertEqual(week["trip_days"], 3)
        ride_week = 7 * 60 / 60 * 0.68 ** 2 * 100
        trip_day = load_forecast.generic_load_details({"type": "Hike", "duration_min": load_forecast.TRIP_DAY_HIKE_MIN})["load"]
        self.assertAlmostEqual(week["load"], round(ride_week * 4 / 7 + 3 * trip_day), delta=1)
        self.assertNotEqual(week["load"], before)

    def test_without_a_plan_the_recent_weeks_carry_forward(self):
        self.steady_history()
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)
        self.assertTrue(all(week["basis"] == "recent" for week in forecast["weeks"]))
        self.assertIn("recent load", forecast["message"])

    def test_no_history_is_unknown(self):
        forecast = load_forecast.build_load_forecast(self.conn, TODAY)
        self.assertEqual(forecast["status"], "unknown")

    def test_endpoint(self):
        from backend.app.main import app

        self.steady_history(weeks=2)
        response = TestClient(app).get("/plans/load-forecast", params={"day": TODAY.isoformat(), "weeks": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["weeks"]), 3)


if __name__ == "__main__":
    unittest.main()
