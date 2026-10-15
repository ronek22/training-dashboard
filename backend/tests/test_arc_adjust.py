import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.models.plans import WeeklyPlan, WeeklyPlanDay, WinterArc
from backend.app.repositories.plans import upsert_weekly_plan_row
from backend.app.services.arc_adjust import apply_arc_adjustment, build_suggestion, undo_arc_adjustment, winter_arc_payload
from backend.app.services.life_load import set_life_load_day
from backend.app.services.winter_arc import block_progress, list_blocks, save_winter_arc

# Base (4 weeks, lighter week 4) then Build (4 weeks, lighter week 3), 6 h a week each.
ARC = {"blocks": [
    {"start_date": "2026-01-05", "end_date": "2026-02-01", "focus": "base", "label": "Base", "weekly_hours": 6,
     "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 4},
    {"start_date": "2026-02-02", "end_date": "2026-03-01", "focus": "sweet_spot", "label": "Build", "weekly_hours": 6,
     "ride_mix": {"z2": 2, "sweet_spot": 1, "vo2": 0}, "lighter_every": 3},
]}
TODAY = date(2026, 1, 21)  # Wednesday of Base week 3: weeks 1 and 2 are finished.
WEEK1, WEEK2 = "2026-01-05", "2026-01-12"


def dates(first, last):
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


class ArcAdjustTests(unittest.TestCase):
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
        save_winter_arc(self.conn, WinterArc(**ARC), date(2026, 1, 1))

    def ride(self, day, minutes):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min) VALUES (?, ?, 'Ride', 'Ride', ?)", (f"ride-{day}", day, minutes),
        )
        self.conn.commit()

    def sick(self, start, end):
        self.conn.execute("INSERT INTO sick_periods (start_date, end_date, severity) VALUES (?, ?, 'below_neck')", (start, end))
        self.conn.commit()

    def tag(self, first, last, tag):
        for day in dates(first, last):
            set_life_load_day(self.conn, day, [tag])
        self.conn.commit()

    def ranges(self):
        return [(block["start_date"], block["end_date"], block["lighter_weeks"]) for block in list_blocks(self.conn)]

    def test_illness_suggests_extending_and_shifts_later_blocks(self):
        for day in (WEEK1, "2026-01-07", "2026-01-10"):
            self.ride(day, 120)  # Week 1 went to plan.
        self.sick("2026-01-13", "2026-01-17")  # Five sick days, then the return window.

        suggestion = build_suggestion(self.conn, TODAY)

        self.assertEqual([week["week_start"] for week in suggestion["lost_weeks"]], [WEEK2])
        self.assertEqual(suggestion["lost_weeks"][0]["reasons"], ["5 sick days", "1 illness return day"])
        self.assertEqual(suggestion["extend_weeks"], 1)
        self.assertIn("to illness", suggestion["message"])
        before, after = suggestion["before"], suggestion["after"]
        self.assertEqual([(b["start_date"], b["end_date"]) for b in after], [("2026-01-05", "2026-02-08"), ("2026-02-09", "2026-03-08")])
        # Lighter weeks keep their place in each block: Base week 4, Build week 3.
        self.assertEqual(after[0]["lighter_weeks"], before[0]["lighter_weeks"])
        self.assertEqual(before[1]["lighter_weeks"], ["2026-02-16"])
        self.assertEqual(after[1]["lighter_weeks"], ["2026-02-23"])
        self.assertEqual(self.ranges()[1][:2], ("2026-02-02", "2026-03-01"))  # Nothing moved yet.

        payload = apply_arc_adjustment(self.conn, "extend", "2026-01-05", 1, TODAY)

        self.assertEqual(self.ranges(), [
            ("2026-01-05", "2026-02-08", ["2026-01-26"]),
            ("2026-02-09", "2026-03-08", ["2026-02-23"]),
        ])
        self.assertIsNone(payload["adjustment"]["suggestion"])
        self.assertTrue(payload["adjustment"]["last"]["can_undo"])
        self.assertEqual(payload["end_date"], "2026-03-08")

        undone = undo_arc_adjustment(self.conn, payload["adjustment"]["last"]["id"], TODAY)

        self.assertEqual([r[:2] for r in self.ranges()], [("2026-01-05", "2026-02-01"), ("2026-02-02", "2026-03-01")])
        self.assertIsNotNone(undone["adjustment"]["suggestion"])  # The card is back.
        self.assertIsNone(undone["adjustment"]["last"])

    def test_mountain_trip_and_reentry_lose_a_week(self):
        self.tag("2026-01-15", "2026-01-18", "mountains")  # Thu-Sun trip; re-entry Mon-Tue of week 3.

        suggestion = build_suggestion(self.conn, TODAY)

        self.assertEqual([week["week_start"] for week in suggestion["lost_weeks"]], [WEEK2])
        self.assertEqual(suggestion["lost_weeks"][0]["reasons"], ["4 Mountains days"])
        self.assertIn("to a mountain trip", suggestion["message"])
        # The re-entry days count too once their week is over (two of them, and no riding).
        later = build_suggestion(self.conn, date(2026, 1, 28))["lost_weeks"]
        self.assertEqual((later[1]["week_start"], later[1]["reasons"]), ("2026-01-19", ["2 mountain re-entry days"]))

    def test_busy_fortnight_extends_by_two_and_accept_keeps_dates(self):
        self.tag("2026-01-05", "2026-01-06", "travel")  # Two busy days and no riding: lost.
        self.tag("2026-01-12", "2026-01-15", "deadline")  # Four busy days: lost on their own.
        for day in ("2026-01-17", "2026-01-18"):
            self.ride(day, 180)

        suggestion = build_suggestion(self.conn, TODAY)

        self.assertEqual([week["week_start"] for week in suggestion["lost_weeks"]], [WEEK1, WEEK2])
        self.assertTrue(suggestion["lost_weeks"][0]["low_ride_hours"])
        self.assertEqual(suggestion["extend_weeks"], 2)
        self.assertIn("to busy days", suggestion["message"])
        with self.assertRaises(HTTPException) as stale:
            apply_arc_adjustment(self.conn, "extend", "2026-01-05", 1, TODAY)
        self.assertEqual(stale.exception.status_code, 409)

        payload = apply_arc_adjustment(self.conn, "accept", "2026-01-05", 0, TODAY)

        self.assertEqual([r[:2] for r in self.ranges()], [("2026-01-05", "2026-02-01"), ("2026-02-02", "2026-03-01")])
        self.assertIsNone(payload["adjustment"]["suggestion"])
        self.assertEqual(payload["adjustment"]["last"]["action"], "accept")
        # A new lost week after accepting brings a new suggestion for that week only.
        self.tag("2026-01-19", "2026-01-23", "family")
        later = build_suggestion(self.conn, date(2026, 1, 28))
        self.assertEqual([week["week_start"] for week in later["lost_weeks"]], ["2026-01-19"])

    def test_light_disruption_is_not_a_lost_week(self):
        self.tag("2026-01-12", "2026-01-13", "poor_sleep")
        for day in ("2026-01-14", "2026-01-17"):
            self.ride(day, 120)  # 4 of 6 h: more than half.

        self.assertIsNone(build_suggestion(self.conn, TODAY))

    def test_lost_week_does_not_carry_its_key_ride(self):
        save_winter_arc(self.conn, WinterArc(blocks=[{**ARC["blocks"][1], "start_date": "2026-01-05", "end_date": "2026-02-01", "lighter_every": 0}]), date(2026, 1, 1))
        start = date.fromisoformat(WEEK2)
        days = [{"date": (start + timedelta(days=i)).isoformat(), "label": "Day", "session_type": "Rest", "title": "Rest"} for i in range(7)]
        days[1] = {**days[1], "session_type": "Ride", "workout_intent": "tempo", "title": "Sweet spot",
                   "cycling_workout_id": "sweet-spot-3x10", "target_duration_min": 60}
        upsert_weekly_plan_row(self.conn, WeeklyPlan(week_start=WEEK2, title="Test", days=[WeeklyPlanDay(**day) for day in days]))
        self.conn.commit()
        self.sick("2026-01-14", "2026-01-18")

        progress = block_progress(self.conn, "2026-01-19")

        self.assertIsNone(progress["carry_over"])
        self.assertEqual(progress["carry_blocked"], "that week was lost")
        self.assertIn("not carried (that week was lost)", progress["note"])

    def test_edit_after_extend_blocks_undo_and_routes(self):
        from backend.app.main import app

        self.sick("2026-01-13", "2026-01-17")
        client = TestClient(app)
        body = client.get("/plans/winter-arc", params={"day": TODAY.isoformat()}).json()
        self.assertEqual(body["adjustment"]["suggestion"]["extend_weeks"], 1)
        response = client.post("/plans/winter-arc/adjustment", params={"day": TODAY.isoformat()},
                               json={"action": "extend", "block_start": "2026-01-05", "weeks": 1})
        self.assertEqual(response.status_code, 200)
        last = response.json()["adjustment"]["last"]

        blocks = [{**block, "end_date": "2026-03-15"} if block["label"] == "Build" else block for block in ARC["blocks"]]
        blocks[0] = {**blocks[0], "end_date": "2026-02-08"}
        blocks[1] = {**blocks[1], "start_date": "2026-02-09"}
        save_winter_arc(self.conn, WinterArc(blocks=blocks), TODAY)  # Edited by hand since.

        self.assertFalse(winter_arc_payload(self.conn, TODAY)["adjustment"]["last"]["can_undo"])
        undo = client.post("/plans/winter-arc/adjustment/undo", params={"day": TODAY.isoformat()}, json={"id": last["id"]})
        self.assertEqual(undo.status_code, 409)
        cleared = client.delete("/plans/winter-arc", params={"day": TODAY.isoformat()}).json()
        self.assertEqual(cleared["adjustment"], {"suggestion": None, "last": None})


if __name__ == "__main__":
    unittest.main()
