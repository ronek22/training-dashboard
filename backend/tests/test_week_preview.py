import os
import sqlite3
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend.app import db
from backend.app.models.plans import WinterArc
from backend.app.services.life_load import set_life_load_day
from backend.app.services.week_preview import build_week_preview
from backend.app.services.winter_arc import arc_week, save_winter_arc

TODAY = date(2029, 12, 5)  # Wednesday; preview weeks start Mon 2029-12-10.
ARC = {
    "blocks": [
        {"start_date": "2029-12-03", "end_date": "2029-12-30", "focus": "base", "weekly_hours": 6,
         "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 4},
        {"start_date": "2029-12-31", "end_date": "2030-02-10", "focus": "sweet_spot", "weekly_hours": 7,
         "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 0}, "lighter_every": 3},
    ]
}


class WeekPreviewTests(unittest.TestCase):
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

    def goal(self, title, period, metric, target, commitment="flexible", end="2030-06-30", review_on=None):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, commitment, review_on) "
            "VALUES (?, ?, ?, ?, '2029-01-01', ?, ?, ?)",
            (title, period, metric, target, end, commitment, review_on),
        )
        self.conn.commit()

    def preview(self):
        return build_week_preview(self.conn, TODAY)["weeks"]

    def test_rows_match_arc_week_targets(self):
        save_winter_arc(self.conn, WinterArc(**ARC), TODAY)
        weeks = self.preview()
        self.assertEqual([week["week_start"] for week in weeks], ["2029-12-10", "2029-12-17", "2029-12-24", "2029-12-31"])
        for week in weeks:
            target = arc_week(self.conn, week["week_start"])
            self.assertEqual(week["ride_hours"], target["ride_hours"])
            self.assertEqual(week["lighter"], target["lighter"])
            self.assertEqual(week["block"]["week_number"], target["week_number"])
            self.assertEqual({ride["type"]: ride["count"] for ride in week["key_rides"]}, {key: target["ride_mix"][key] for key in target["key_types"]})
        base_lighter, sweet_spot = weeks[2], weeks[3]
        self.assertEqual((base_lighter["block"]["week_number"], base_lighter["lighter"], base_lighter["ride_hours"]), (4, True, 3.6))
        self.assertEqual((base_lighter["summary"], base_lighter["normal"]), (["3.6 h rides", "2× z2"], False))
        self.assertEqual(sweet_spot["block"]["label"], "Sweet-spot build")
        self.assertTrue(sweet_spot["new_block"])
        self.assertEqual(sweet_spot["key_rides"], [{"type": "sweet_spot", "label": "Sweet spot", "count": 2, "source": "arc"}])
        self.assertEqual((sweet_spot["summary"], sweet_spot["normal"]), (["7 h rides", "2× sweet spot"], True))

    def test_trip_reentry_and_life_load_bend_their_weeks(self):
        save_winter_arc(self.conn, WinterArc(**ARC), TODAY)
        self.goal("Lift three times per week", "week", "strength_sessions", 3, commitment="anchor")
        for day in ("2029-12-13", "2029-12-14", "2029-12-15", "2029-12-16"):
            set_life_load_day(self.conn, day, ["mountains"])
        for day in ("2029-12-26", "2029-12-27", "2029-12-28"):
            set_life_load_day(self.conn, day, ["family"], "Christmas")
        for day in ("2029-12-31", "2030-01-01", "2030-01-02"):
            set_life_load_day(self.conn, day, ["deadline"])
        trip, reentry, busy, deadline = self.preview()

        # 4 of 7 days hiking: ride hours shrink to the 3 days off the trip; Z2 is not restricted.
        self.assertEqual([event["label"] for event in trip["events"]], ["Mountains Dec 13–16"])
        self.assertEqual(trip["summary"], ["~2.6 h rides", "3× z2", "3 lifts, travel version on trip days"])
        self.assertEqual(trip["notes"], ["Hikes Thu–Sun"])
        self.assertFalse(trip["normal"])

        # 4 hiking days -> 2-day re-entry window (1 easy day), which falls in the next week.
        self.assertEqual([(event["kind"], event["dates"]) for event in reentry["events"]], [("reentry", ["2029-12-17", "2029-12-18"])])
        self.assertEqual(reentry["notes"], ["Easy only Mon", "no intervals until Wed"])
        self.assertEqual(reentry["summary"], ["6 h rides", "3× z2", "3 lifts, legs at pre-trip loads"])

        self.assertTrue(busy["busy"])
        self.assertEqual((busy["events"][0]["label"], busy["events"][0]["detail"]), ("Family Wed–Fri", "Christmas"))

        # Sweet spot rides only go on the days left open.
        self.assertEqual(deadline["summary"], ["7 h rides", "2× sweet spot, Thu–Sun"])

    def test_open_illness_window_reaches_the_next_week(self):
        self.goal("Lift three times per week", "week", "strength_sessions", 3, commitment="anchor")
        # Sick 7 days ending Dec 3 -> 7-day return window to Dec 10.
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date) VALUES ('2029-11-27', '2029-12-03')")
        self.conn.commit()
        weeks = self.preview()
        self.assertEqual([(event["kind"], event["dates"]) for event in weeks[0]["events"]], [("illness", ["2029-12-10"])])
        self.assertEqual(weeks[0]["notes"], ["Effort capped Mon, no intervals"])
        self.assertTrue(weeks[1]["normal"])

    def test_without_arc_only_bent_weeks_say_anything(self):
        self.goal("Lift three times per week", "week", "strength_sessions", 3, commitment="anchor")
        self.goal("Ride 100km weekly", "week", "ride_km", 100, review_on="2029-12-26")
        self.goal("1 quality ride per week", "week", "quality_sessions", 1)
        self.goal("Climb power", "month", "benchmark_power", 210, end="2030-01-02")
        for offset in range(7):
            set_life_load_day(self.conn, f"2029-12-{10 + offset}", ["mountains"])
        trip, reentry, review, ends = self.preview()

        self.assertIsNone(trip["block"])
        self.assertEqual(trip["summary"], ["Hikes instead of rides", "3 short travel lifts"])
        # 7 hiking days -> 4-day re-entry Mon–Thu, first 2 easy; the quality ride fits Fri–Sun.
        self.assertEqual(reentry["summary"], ["1× quality ride, Fri–Sun", "3 lifts, legs at pre-trip loads"])
        self.assertEqual(reentry["notes"], ["Easy only Mon–Tue", "no intervals until Fri"])
        # Normal weeks do not repeat the weekly goals.
        self.assertEqual((review["normal"], review["summary"]), (True, []))
        self.assertEqual([event["label"] for event in review["events"]], ["Goal review: Ride 100km weekly"])
        self.assertEqual([event["label"] for event in ends["events"]], ["Goal ends: Climb power"])

    def test_partial_trip_shrinks_goal_km(self):
        self.goal("Ride 100km weekly", "week", "ride_km", 100)
        for day in ("2029-12-14", "2029-12-15", "2029-12-16"):
            set_life_load_day(self.conn, day, ["mountains"])
        self.assertEqual(self.preview()[0]["summary"], ["~55 km rides"])

    def test_hides_cleanly_with_nothing_known(self):
        from backend.app.main import app

        self.assertEqual(self.preview(), [])
        # Weekly goals alone are the same every week: still nothing to preview.
        self.goal("Ride 100km weekly", "week", "ride_km", 100)
        self.goal("Lift three times per week", "week", "strength_sessions", 3, commitment="anchor")
        self.assertEqual(self.preview(), [])
        response = TestClient(app).get("/plans/week-preview", params={"day": TODAY.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["weeks"], [])


if __name__ == "__main__":
    unittest.main()
