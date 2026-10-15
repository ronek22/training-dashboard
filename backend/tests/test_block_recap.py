import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.models.plans import WinterArc
from backend.app.services.block_recap import build_block_recap, decide_block_suggestion
from backend.app.services.winter_arc import list_blocks, save_winter_arc

# Base (4 weeks at 6 h, Z2 only, lighter week 4), Build (4 weeks at 7 h, one sweet spot a week),
# then Peak (two sweet-spot rides and one VO2 a week).
ARC = {"blocks": [
    {"start_date": "2026-01-05", "end_date": "2026-02-01", "focus": "base", "label": "Base", "weekly_hours": 6,
     "ride_mix": {"z2": 3, "sweet_spot": 0, "vo2": 0}, "lighter_every": 4},
    {"start_date": "2026-02-02", "end_date": "2026-03-01", "focus": "sweet_spot", "label": "Build", "weekly_hours": 7,
     "ride_mix": {"z2": 2, "sweet_spot": 1, "vo2": 0}, "lighter_every": 0},
    {"start_date": "2026-03-02", "end_date": "2026-03-29", "focus": "vo2", "label": "Peak", "weekly_hours": 7,
     "ride_mix": {"z2": 2, "sweet_spot": 2, "vo2": 1}, "lighter_every": 0},
]}
BASE, BUILD = "2026-01-05", "2026-02-02"
AFTER_BASE = date(2026, 2, 4)
AFTER_BUILD = date(2026, 3, 4)


def day(week_start, offset):
    return (date.fromisoformat(week_start) + timedelta(days=offset)).isoformat()


class BlockRecapTests(unittest.TestCase):
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

    def ride(self, value, minutes, intent="easy"):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, workout_intent) VALUES (?, ?, 'Ride', 'Ride', ?, ?)",
            (f"ride-{value}-{minutes}-{intent}", value, minutes, intent),
        )
        self.conn.commit()

    def block(self, label):
        return next(block for block in list_blocks(self.conn) if block["label"] == label)

    def ride_base(self):
        """Week 1 to plan (5 h), weeks 2-3 at 4 h, the lighter week at 2 h 40: every Z2 ride, hours 27% under."""
        for offset in (0, 2, 5):
            self.ride(day(BASE, offset), 100)
        for week in ("2026-01-12", "2026-01-19"):
            for offset in (0, 2, 5):
                self.ride(day(week, offset), 80)
        for offset in (1, 5):
            self.ride(day("2026-01-26", offset), 80)

    def test_short_hours_suggest_holding_the_next_block_until_confirmed(self):
        self.ride_base()

        recap = build_block_recap(self.conn, BASE, AFTER_BASE)

        self.assertEqual(recap["status"], "ok")
        totals = recap["totals"]
        self.assertEqual((totals["ride_hours_done"], totals["ride_hours_target"], totals["hours_pct"]), (15.7, 21.6, 73))
        self.assertEqual((totals["key_rides"]["done"], totals["key_rides"]["planned"]), (11, 11))
        self.assertEqual(totals["key_rides"]["by_type"]["z2"], {"label": "Z2", "planned": 11, "done": 11})
        self.assertEqual((totals["on_target_weeks"], totals["longest_streak"], totals["ride_days"]), (1, 1, 11))
        self.assertEqual([week["on_target"] for week in recap["weeks"]], [True, False, False, False])
        self.assertEqual(recap["power"]["status"], "unavailable")
        self.assertEqual(recap["decoupling"]["status"], "unavailable")

        [hours] = recap["suggestions"]
        self.assertEqual(hours["id"], "hours")
        self.assertIsNone(hours["decision"])
        self.assertEqual(hours["change"], {"block_start": BUILD, "block_label": "Build", "field": "weekly_hours", "from": 7.0, "to": 6.0})
        self.assertIn("Hours were 27% under", hours["message"])
        self.assertEqual(self.block("Build")["weekly_hours"], 7.0)  # Nothing changes on its own.

        with self.assertRaises(HTTPException) as stale:
            decide_block_suggestion(self.conn, BASE, "hours", "apply", 5.5, AFTER_BASE)
        self.assertEqual(stale.exception.status_code, 409)

        after = decide_block_suggestion(self.conn, BASE, "hours", "apply", 6.0, AFTER_BASE)

        self.assertEqual(self.block("Build")["weekly_hours"], 6.0)
        self.assertEqual(self.block("Peak")["weekly_hours"], 7.0)
        self.assertEqual([(s["id"], s["decision"]) for s in after["suggestions"]], [("hours", "applied")])
        with self.assertRaises(HTTPException):
            decide_block_suggestion(self.conn, BASE, "hours", "apply", 6.0, AFTER_BASE)

    def test_missed_key_rides_suggest_one_fewer_and_dismiss_keeps_the_arc(self):
        for week in ("2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23"):
            for offset in (1, 3, 5):
                self.ride(day(week, offset), 140)  # 7 h a week, all easy.
        self.ride(day("2026-02-09", 2), 60, "tempo")  # One sweet-spot ride in four weeks.

        recap = build_block_recap(self.conn, BUILD, AFTER_BUILD)

        self.assertEqual((recap["totals"]["key_rides"]["done"], recap["totals"]["key_rides"]["planned"]), (1, 4))
        self.assertEqual(recap["headline"], "Build had the hours, not the key rides.")
        [keys] = recap["suggestions"]
        self.assertEqual(keys["id"], "key_rides")
        self.assertEqual((keys["change"]["field"], keys["change"]["from"], keys["change"]["to"]), ("ride_mix.sweet_spot", 2, 1))
        self.assertIn("1 of 4 key rides happened", keys["message"])

        after = decide_block_suggestion(self.conn, BUILD, "key_rides", "dismiss", None, AFTER_BUILD)

        self.assertEqual(self.block("Peak")["ride_mix"], {"z2": 2, "sweet_spot": 2, "vo2": 1})
        self.assertEqual(after["suggestions"][0]["decision"], "dismissed")

    def test_thin_block_says_not_enough_data(self):
        self.ride(day(BASE, 0), 60)

        recap = build_block_recap(self.conn, BASE, AFTER_BASE)

        self.assertEqual(recap["status"], "thin")
        self.assertEqual(recap["suggestions"], [])
        self.assertIsNone(recap["power"])
        self.assertEqual(recap["headline"], "Base left too little riding to read.")

    def test_running_and_unknown_blocks(self):
        with self.assertRaises(HTTPException) as running:
            build_block_recap(self.conn, BASE, date(2026, 2, 1))
        self.assertEqual(running.exception.status_code, 409)
        self.assertIn("opens on 2 Feb", running.exception.detail)
        with self.assertRaises(HTTPException) as unknown:
            build_block_recap(self.conn, "2026-01-12", AFTER_BASE)
        self.assertEqual(unknown.exception.status_code, 404)

    def test_last_block_has_no_suggestions_and_routes(self):
        from backend.app.main import app

        self.ride_base()
        client = TestClient(app)
        body = client.get(f"/plans/winter-arc/blocks/{BASE}/recap", params={"day": AFTER_BASE.isoformat()}).json()
        self.assertEqual(body["next_block"]["label"], "Build")
        response = client.post(f"/plans/winter-arc/blocks/{BASE}/recap/decision", params={"day": AFTER_BASE.isoformat()},
                               json={"suggestion": "hours", "action": "apply", "to": 6})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.text)["suggestions"][0]["decision"], "applied")

        save_winter_arc(self.conn, WinterArc(blocks=ARC["blocks"][:1]), date(2026, 1, 1))
        self.assertEqual(build_block_recap(self.conn, BASE, AFTER_BASE)["suggestions"][0]["decision"], "applied")
