import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from backend.app import db
from backend.app.services import run_dynamics
from backend.app.services.data_inbox import build_inbox
from backend.app.services.running_fitness import (
    build_running_fitness,
    heart_rate_vdot,
    pick_peak,
    projection,
    race_seconds,
    training_paces,
    vdot_from_performance,
)

TODAY = date(2026, 10, 27)


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


class DanielsMathTests(unittest.TestCase):
    def test_vdot_matches_daniels_tables(self):
        # Daniels: VDOT 50 runs 5K in 19:57 and 10K in 41:21.
        self.assertAlmostEqual(vdot_from_performance(5000, 19 * 60 + 57), 50.0, delta=0.15)
        self.assertAlmostEqual(race_seconds(50, 10000), 41 * 60 + 21, delta=10)
        self.assertAlmostEqual(race_seconds(50, 42195), 3 * 3600 + 10 * 60 + 49, delta=60)

    def test_race_seconds_round_trips(self):
        for vdot in (35, 45, 60):
            seconds = race_seconds(vdot, 21097.5)
            self.assertAlmostEqual(vdot_from_performance(21097.5, seconds), vdot, places=2)

    def test_training_paces_follow_daniels(self):
        paces = training_paces(50)
        # VDOT 50: threshold about 4:15/km, interval about 3:55/km, easy roughly 4:55–5:30/km.
        self.assertAlmostEqual(paces["threshold"]["pace_s"], 255, delta=4)
        self.assertAlmostEqual(paces["interval"]["pace_s"], 235, delta=5)
        self.assertLess(paces["easy"]["from_s"], paces["easy"]["to_s"])
        self.assertTrue(285 <= paces["easy"]["from_s"] <= 300)
        self.assertLess(paces["repetition"]["pace_s"], paces["interval"]["pace_s"])

    def test_heart_rate_vdot_uses_heart_rate_reserve(self):
        run = {"avg_hr": 160, "distance_km": 10.0, "duration_min": 55.0, "elevation_m": 40}
        value = heart_rate_vdot(run, 55, 195)
        # 10 km in 55 min costs ~32.0 ml/kg/min at 75 % of heart-rate reserve.
        self.assertAlmostEqual(value, 41.5, delta=0.2)
        self.assertIsNone(heart_rate_vdot({**run, "elevation_m": 400}, 55, 195), "hilly runs are skipped")
        self.assertIsNone(heart_rate_vdot({**run, "avg_hr": 100}, 55, 195), "walk-level heart rate is skipped")
        self.assertIsNone(heart_rate_vdot({**run, "distance_km": 2.0}, 55, 195))

    def test_peak_needs_a_confirming_run(self):
        points = [
            {"date": "2015-01-01", "vdot": 70.0},  # GPS glitch, nothing near it
            {"date": "2016-05-01", "vdot": 55.0},
            {"date": "2016-05-20", "vdot": 54.0},
            {"date": "2020-01-01", "vdot": 40.0},
        ]
        self.assertEqual(pick_peak(points)["vdot"], 55.0)

    def test_projection_is_capped_by_the_gap_to_peak(self):
        self.assertEqual(projection(40, 55), 43)
        self.assertEqual(projection(53, 55), 54)
        self.assertEqual(projection(45, None), 45)


class RunDynamicsParsingTests(unittest.TestCase):
    def records(self, seconds=900, speed=3.0, power=lambda s: 250.0):
        start = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
        return [
            {
                "timestamp": start + timedelta(seconds=s), "distance": s * speed, "heart_rate": 150,
                "cadence": 80, "fractional_cadence": 0.5, "stance_time": 240.0, "vertical_oscillation": 95.0,
                "step_length": 1100.0, "vertical_ratio": 8.5, "power": power(s),
            }
            for s in range(seconds + 1)
        ]

    def test_km_splits_average_each_kilometre(self):
        splits = run_dynamics.km_splits(self.records())
        self.assertEqual([split["km"] for split in splits], [1, 2])
        first = splits[0]
        self.assertEqual(first["cadence_spm"], 161.0, "one-leg FIT cadence doubles to steps per minute")
        self.assertAlmostEqual(first["vertical_oscillation_cm"], 9.5)
        self.assertAlmostEqual(first["step_length_m"], 1.1)
        self.assertAlmostEqual(first["seconds"], 333, delta=1)

    def test_power_bests_find_the_hardest_window(self):
        bests = run_dynamics.power_bests(self.records(power=lambda s: 400.0 if 300 <= s < 360 else 200.0))
        self.assertAlmostEqual(bests["60"], 400.0, delta=4)
        self.assertLess(bests["300"], 300)
        self.assertNotIn("1200", bests, "a 15-minute run has no 20-minute best")


class RunningFitnessDbTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        previous = db.DB_PATH
        db.DB_PATH = str(self.temp / "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def run_row(self, activity_id, day, km, minutes, avg_hr=None, max_hr=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, distance_km, duration_min, avg_hr, max_hr, elevation_m) VALUES (?, ?, 'Run', ?, ?, ?, ?, ?, 20)",
            (activity_id, day, f"Run {day}", km, minutes, avg_hr, max_hr),
        )

    def dynamics(self, file_name, activity_id, day, vo=10.0):
        parsed = {
            "file_name": file_name, "date": day, "started_at": f"{day}T08:00:00+00:00", "indoor": False,
            "distance_km": 8.0, "duration_min": 45.0, "avg_hr": 150, "cadence_spm": 160, "step_length_m": 1.1,
            "vertical_oscillation_cm": vo, "vertical_ratio_pct": 8.5, "stance_time_ms": 250, "avg_power_w": 240,
            "max_power_w": 300, "splits": [], "power_bests": {"180": 270.0, "720": 255.0},
        }
        run_dynamics._store(self.conn, parsed, activity_id)

    def test_payload_estimates_vdot_predictions_and_guard(self):
        # Peak era: two fast 5Ks (no streams, so the whole run counts).
        self.run_row("old1", "2016-05-01", 5.0, 20.0)
        self.run_row("old2", "2016-05-20", 5.0, 20.2)
        # Comeback: easy runs with heart rate, the latest this week.
        for index, days in enumerate((40, 30, 20, 10, 3)):
            self.run_row(f"new{index}", ago(days), 8.0, 48.0, avg_hr=150, max_hr=185)
        self.conn.commit()
        data = build_running_fitness(self.conn, TODAY)
        self.assertTrue(data["available"])
        vdot = data["vdot"]
        self.assertAlmostEqual(vdot["peak"]["vdot"], vdot_from_performance(5000, 1200), places=1)
        self.assertEqual(vdot["basis"], "heart_rate")
        self.assertGreater(vdot["current"], data["vdot"]["estimates"]["effort"]["vdot"], "easy-run efforts understate fitness")
        self.assertLess(vdot["current"], vdot["peak"]["vdot"])
        self.assertGreater(vdot["projected"], vdot["current"])
        five = data["predictions"][0]
        self.assertEqual(five["key"], "5k")
        self.assertGreater(five["now_s"], five["projected_s"])
        self.assertGreater(five["projected_s"], five["peak_s"])
        self.assertEqual(data["build_up"]["status"], "ok")
        self.assertEqual(len(data["build_up"]["weeks"]), 10)
        self.assertTrue(data["paces"]["quality_allowed"])
        self.assertFalse(data["form"]["available"])

    def test_build_up_guard_flags_a_big_jump(self):
        self.run_row("a", ago(20), 3.0, 20.0)
        self.run_row("b", ago(2), 12.0, 70.0)
        self.run_row("c", ago(1), 10.0, 60.0)
        self.conn.commit()
        guard = build_running_fitness(self.conn, TODAY)["build_up"]
        self.assertEqual(guard["status"], "caution")
        self.assertEqual(guard["last7_km"], 22.0)

    def test_form_and_power_come_from_matched_dynamics(self):
        self.run_row("r1", ago(30), 8.0, 45.0, avg_hr=150)
        self.run_row("r2", ago(5), 8.0, 45.0, avg_hr=150)
        self.dynamics("f1.fit", "r1", ago(30), vo=10.0)
        self.dynamics("f2.fit", "r2", ago(5), vo=9.0)
        self.conn.commit()
        data = build_running_fitness(self.conn, TODAY)
        self.assertTrue(data["form"]["available"])
        self.assertEqual(data["form"]["latest"]["vertical_oscillation_cm"], 9.0)
        self.assertEqual(data["form"]["baseline"]["vertical_oscillation_cm"], 10.0)
        self.assertEqual(data["power"]["critical_power"]["watts"], 250)
        self.assertFalse(data["power"]["critical_power"]["steady_only"], "W' of 3.6 kJ is a real hard effort")
        self.assertEqual(data["healthfit"]["missing"], [])

    def test_activity_dynamics_returns_one_runs_form_and_splits(self):
        self.run_row("r1", ago(5), 8.0, 45.0, avg_hr=150)
        self.dynamics("f1.fit", "r1", ago(5), vo=9.5)
        self.conn.execute("UPDATE run_dynamics SET splits_json = ? WHERE file_name = 'f1.fit'",
                          (json.dumps([{"km": 1, "seconds": 340, "heart_rate": 150.0}]),))
        self.conn.commit()
        data = run_dynamics.activity_dynamics(self.conn, "r1")
        self.assertEqual(data["vertical_oscillation_cm"], 9.5)
        self.assertEqual(data["cadence_spm"], 160)
        self.assertEqual(data["avg_power_w"], 240)
        self.assertEqual(data["splits"], [{"km": 1, "seconds": 340, "heart_rate": 150.0}])
        self.assertIsNone(run_dynamics.activity_dynamics(self.conn, "nofile"))

    def test_strava_run_without_healthfit_file_reaches_the_inbox(self):
        self.run_row("old", ago(60), 8.0, 45.0)
        self.dynamics("old.fit", "old", ago(60))
        self.run_row("fresh", ago(2), 6.0, 35.0)
        self.conn.commit()
        inbox = build_inbox(self.conn, TODAY)
        keys = [item["key"] for item in inbox["items"] if item["kind"] == "missing_dynamics"]
        self.assertEqual(keys, ["dynamics:fresh"])
        self.assertEqual(inbox["counts"]["missing_dynamics"], 1)
        # Before any HealthFit file was ever read, nothing is asked for.
        self.conn.execute("DELETE FROM run_dynamics")
        self.assertEqual(build_inbox(self.conn, TODAY)["counts"]["missing_dynamics"], 0)

    def test_scan_matches_files_and_retries_unmatched_ones(self):
        folder = self.temp / "healthfit"
        folder.mkdir()
        name = f"{ago(1)}-080000-Outdoor Running-Apple Watch.fit"
        (folder / name).write_bytes(b"fit")
        (folder / f"{ago(1)}-090000-Outdoor Cycling-Apple Watch.fit").write_bytes(b"fit")
        parsed = {
            "file_name": name, "date": ago(1), "started_at": None, "indoor": False, "distance_km": 6.0,
            "duration_min": 35.0, "avg_hr": 150.0, "cadence_spm": 160, "step_length_m": 1.1,
            "vertical_oscillation_cm": 10.0, "vertical_ratio_pct": 8.5, "stance_time_ms": 250,
            "avg_power_w": 240, "max_power_w": 300, "splits": [], "power_bests": {},
        }
        with mock.patch.object(run_dynamics, "parse_run_file", return_value=parsed) as parse:
            first = run_dynamics.scan_run_dynamics(self.conn, folder, TODAY)
            self.assertEqual((first["scanned"], first["unmatched"]), (1, 1))
            self.assertEqual(parse.call_count, 1, "cycling files are never opened")
            # The Strava run arrives later; the next scan links it without reopening the file.
            self.run_row("strava1", ago(1), 6.02, 35.2, avg_hr=151)
            self.conn.commit()
            second = run_dynamics.scan_run_dynamics(self.conn, folder, TODAY)
            self.assertEqual(second["rematched"], 1)
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(run_dynamics.activity_ids_with_dynamics(self.conn), {"strava1"})


if __name__ == "__main__":
    unittest.main()
