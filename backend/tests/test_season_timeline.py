import os
import sqlite3
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend.app import db
from backend.app.models.plans import WinterArc
from backend.app.services import stall_blocks
from backend.app.services.life_load import set_life_load_day
from backend.app.services.season_timeline import build_season_timeline
from backend.app.services.winter_arc import save_winter_arc

TODAY = date(2029, 12, 5)  # Wednesday; this week starts Mon 2029-12-03.
ARC = {
    "blocks": [
        {"start_date": "2029-11-05", "end_date": "2029-12-30", "focus": "base", "weekly_hours": 6,
         "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 4},
        {"start_date": "2029-12-31", "end_date": "2030-05-12", "focus": "sweet_spot", "weekly_hours": 7,
         "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 0}, "lighter_every": 3},
    ]
}


class SeasonTimelineTests(unittest.TestCase):
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

    def goal(self, title, period, end, review_on=None):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, commitment, review_on) "
            "VALUES (?, ?, 'ride_km', 100, '2029-01-01', ?, 'flexible', ?)",
            (title, period, end, review_on),
        )
        self.conn.commit()

    def timeline(self):
        return build_season_timeline(self.conn, TODAY)

    def test_empty_season_still_has_weeks_around_today(self):
        result = self.timeline()
        self.assertFalse(result["has_content"])
        self.assertEqual((result["start_date"], len(result["weeks"])), ("2029-11-19", 20))
        current = [week for week in result["weeks"] if week["current"]]
        self.assertEqual([week["week_start"] for week in current], ["2029-12-03"])
        self.assertEqual(current[0]["link"], "plan")
        self.assertEqual(result["weeks"][0]["link"], None)  # past week with no saved plan
        self.assertEqual(result["weeks"][-1]["link"], "preview")

    def test_arc_sets_window_bands_and_lighter_weeks(self):
        save_winter_arc(self.conn, WinterArc(**ARC), TODAY)
        result = self.timeline()
        # Starts at the arc (4 weeks back), runs to its end but no more than 26 weeks.
        self.assertEqual(result["start_date"], "2029-11-05")
        self.assertEqual(len(result["weeks"]), 26)
        self.assertEqual(result["end_date"], "2030-05-05")
        self.assertEqual([block["focus"] for block in result["blocks"]], ["base", "sweet_spot"])
        self.assertEqual(result["blocks"][1]["visible_end"], "2030-05-05")
        lighter = [week["week_start"] for week in result["weeks"] if week["lighter"]]
        self.assertIn("2029-11-26", lighter)  # base week 4
        self.assertIn("2030-01-14", lighter)  # sweet-spot week 3
        self.assertTrue(all(week["block_id"] for week in result["weeks"]))

    def test_trips_goals_and_stall_block_become_pins_and_bars(self):
        for day in ("2029-12-20", "2029-12-21", "2029-12-22"):
            set_life_load_day(self.conn, day, ["mountains"])
        self.goal("Climb power", "month", "2030-02-28", review_on="2029-12-15")
        self.goal("Weekly km", "week", "2029-12-09")  # weekly goals have no target date pin
        self.goal("Far target", "season", "2030-09-30")
        stall_blocks.ensure_table(self.conn)
        self.conn.execute(
            "INSERT INTO strength_stall_blocks (exercise_name, applied_name, kind, label, text, plan_json, scope, status, "
            "started_on, ends_on, stall_json) VALUES ('Upright Row', 'Upright Row', 'reps', 'Rep scheme', 'x', "
            "'{\"weeks\": 3}', 'block', 'active', '2029-11-26', '2029-12-17', '{}')"
        )
        self.conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES ('2029-12-10', '[]')")
        self.conn.commit()

        result = self.timeline()
        self.assertTrue(result["has_content"])
        self.assertEqual(
            [(pin["kind"], pin["date"]) for pin in result["pins"]],
            [("review", "2029-12-15"), ("trip", "2029-12-20"), ("goal", "2030-02-28")],
        )
        self.assertEqual(result["pins"][1]["end_date"], "2029-12-22")
        self.assertEqual([pin["label"] for pin in result["later"]], ["Far target"])
        self.assertEqual(result["stall_block"]["exercise_name"], "Upright Row")
        self.assertEqual(result["stall_block"]["week"], 2)
        links = {week["week_start"]: week["link"] for week in result["weeks"]}
        self.assertEqual((links["2029-12-10"], links["2029-12-17"]), ("plan", "preview"))

    def test_route_and_longer_preview(self):
        from backend.app.main import app

        client = TestClient(app)
        response = client.get("/plans/season-timeline", params={"day": TODAY.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["today"], TODAY.isoformat())
        save_winter_arc(self.conn, WinterArc(**ARC), TODAY)
        preview = client.get("/plans/week-preview", params={"day": TODAY.isoformat(), "weeks": 10}).json()
        self.assertEqual(len(preview["weeks"]), 10)
        self.assertEqual(client.get("/plans/week-preview", params={"weeks": 40}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
