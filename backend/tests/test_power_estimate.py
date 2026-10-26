import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from backend.app import db
from backend.app.services import dashboard, power_estimate
from backend.app.services.personal_records import build_personal_records
from backend.app.services.power_estimate import (
    AIR_DENSITY,
    BIKE_PROFILES,
    G,
    calibration_report,
    estimable,
    estimate_from_streams,
    estimated_tss,
    estimated_watts,
    instant_power,
)
from backend.app.services.ride_balance import classify_ride

HYBRID = BIKE_PROFILES["hybrid"]


def _streams(segments, *, watts=None):
    """segments: [(seconds, speed m/s, grade)] at 1 Hz; returns Strava-shaped streams."""
    times, speeds, distances, altitudes = [], [], [], []
    distance = altitude = 0.0
    second = 0
    for seconds, speed, grade in segments:
        for _ in range(seconds):
            times.append(second)
            speeds.append(speed)
            distances.append(distance)
            altitudes.append(altitude)
            distance += speed
            altitude += speed * grade
            second += 1
    streams = {
        "time": {"data": times}, "velocity_smooth": {"data": speeds},
        "distance": {"data": distances}, "altitude": {"data": altitudes},
    }
    if watts is not None:
        streams["watts"] = {"data": watts(speeds, len(times))}
    return streams


class PhysicsModelTests(unittest.TestCase):
    def test_flat_road_is_rolling_resistance_plus_drag(self):
        mass = 80 + HYBRID["bike_kg"]
        expected = (mass * G * HYBRID["crr"] * 10 + 0.5 * AIR_DENSITY * HYBRID["cda"] * 10 ** 3) / HYBRID["efficiency"]
        self.assertAlmostEqual(instant_power(10, 10, 1, 0.0, mass, HYBRID), expected, places=6)
        self.assertAlmostEqual(expected, 303.8, delta=0.5)

    def test_climbing_adds_the_weight_lifted(self):
        mass = 93.0
        flat = instant_power(4, 4, 1, 0.0, mass, HYBRID)
        climb = instant_power(4, 4, 1, 0.06, mass, HYBRID)
        # ~6% of the weight lifted at 4 m/s, divided by drivetrain efficiency.
        self.assertAlmostEqual(climb - flat, mass * G * 4 * 0.06 / HYBRID["efficiency"], delta=2.0)
        self.assertGreater(instant_power(4, 4, 1, 0.06, 100.0, HYBRID), climb)

    def test_coasting_and_stops_are_zero_never_negative(self):
        self.assertEqual(instant_power(12, 12, 1, -0.08, 93.0, HYBRID), 0.0)
        self.assertEqual(instant_power(0.2, 0.2, 1, 0.0, 93.0, HYBRID), 0.0)
        self.assertEqual(instant_power(8, 10, 1, 0.0, 93.0, HYBRID), 0.0)  # braking

    def test_acceleration_costs_kinetic_energy(self):
        steady = instant_power(8, 8, 1, 0.0, 93.0, HYBRID)
        speeding_up = instant_power(8, 7, 1, 0.0, 93.0, HYBRID)
        self.assertAlmostEqual(speeding_up - steady, 93.0 * (64 - 49) / 2 / HYBRID["efficiency"], places=6)

    def test_grade_is_capped(self):
        self.assertEqual(instant_power(3, 3, 1, 0.9, 93.0, HYBRID), instant_power(3, 3, 1, 0.25, 93.0, HYBRID))


class RideEstimateTests(unittest.TestCase):
    def test_steady_ride_average_and_np_match_the_instant_power(self):
        estimate = estimate_from_streams(_streams([(1800, 8.0, 0.0)]), 80)
        expected = instant_power(8, 8, 1, 0.0, 93.0, HYBRID)
        self.assertAlmostEqual(estimate["avg_watts"], expected, delta=0.2)
        self.assertAlmostEqual(estimate["normalized_power"], expected, delta=0.2)
        self.assertTrue(estimate["estimated"])
        self.assertEqual(estimate["model"], power_estimate.MODEL_VERSION)

    def test_hills_raise_np_above_average(self):
        estimate = estimate_from_streams(_streams([(300, 9.0, 0.0), (300, 4.0, 0.07), (300, 14.0, -0.07)] * 4), 80)
        self.assertGreater(estimate["normalized_power"], estimate["avg_watts"] * 1.1)

    def test_short_or_incomplete_streams_are_not_estimated(self):
        self.assertIsNone(estimate_from_streams(_streams([(300, 8.0, 0.0)]), 80))
        streams = _streams([(1800, 8.0, 0.0)])
        del streams["altitude"]
        self.assertIsNone(estimated_watts(streams, 80))

    def test_estimating_never_touches_the_stored_streams(self):
        streams = _streams([(1800, 8.0, 0.0)])
        before = json.dumps(streams, sort_keys=True)
        estimate_from_streams(streams, 80)
        self.assertEqual(json.dumps(streams, sort_keys=True), before)
        self.assertNotIn("watts", streams)

    def test_tss_scores_like_a_measured_ride(self):
        estimate = {"normalized_power": 200.0, "moving_seconds": 3600}
        self.assertAlmostEqual(estimated_tss(estimate, 200.0), 100.0)
        self.assertAlmostEqual(estimated_tss(estimate, 250.0), 64.0)
        self.assertIsNone(estimated_tss(estimate, None))

    def test_only_outdoor_rides_without_a_meter(self):
        streams = _streams([(1800, 8.0, 0.0)])
        self.assertTrue(estimable("Ride", json.dumps({"device_watts": False}), "fetched", streams))
        self.assertFalse(estimable("VirtualRide", None, "streams_backfill", streams))
        self.assertFalse(estimable("Ride", json.dumps({"trainer": True}), "fetched", streams))
        metered = _streams([(1800, 8.0, 0.0)], watts=lambda speeds, n: [180] * n)
        self.assertFalse(estimable("Ride", json.dumps({"device_watts": True}), "fetched", metered))
        no_speed = _streams([(1800, 8.0, 0.0)])
        del no_speed["velocity_smooth"]
        self.assertFalse(estimable("Ride", None, "strava_export", no_speed))


class DatabaseTests(unittest.TestCase):
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
        self.today = date.today()
        power_estimate._CACHE.clear()

    def add(self, activity_id, kind, streams, *, days_ago=1, name=None, detail=None, minutes=None):
        day = (self.today - timedelta(days=days_ago)).isoformat()
        seconds = len(streams["time"]["data"])
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km, avg_hr) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, name or kind, minutes or seconds / 60, 20.0, 140),
        )
        self.conn.execute(
            "INSERT INTO activity_details (activity_id, fetched_at, source_status, detail_json, streams_json) VALUES (?, ?, ?, ?, ?)",
            (activity_id, day, "fetched", json.dumps(detail or {"device_watts": False}), json.dumps(streams)),
        )
        self.conn.commit()

    def set_ftp(self, watts):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES (?, 'ftp', ?)", ((self.today - timedelta(days=400)).isoformat(), watts))
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES (?, 'weight', 80)", ((self.today - timedelta(days=400)).isoformat(),))
        self.conn.commit()

    def test_outdoor_ride_load_uses_estimated_power_tss(self):
        self.set_ftp(240)
        streams = _streams([(3600, 9.0, 0.0)])
        self.add("outdoor", "Ride", streams)
        estimate = estimate_from_streams(streams, 80)

        summary = dashboard.build_training_load_summary(self.conn, days=14)

        day = next(item for item in summary["chart"] if item["date"] == (self.today - timedelta(days=1)).isoformat())
        self.assertEqual(day["load_source"], "estimated_power_tss")
        self.assertAlmostEqual(day["load"], round(estimated_tss(estimate, 240, 60), 1), delta=0.11)
        self.assertEqual(summary["model"]["sources"]["estimated_power_tss"], 1)
        self.assertEqual(summary["model"]["estimated_power"]["rides"], 1)

    def test_without_ftp_the_ride_keeps_the_heart_rate_fallback(self):
        self.add("outdoor", "Ride", _streams([(3600, 9.0, 0.0)]))
        summary = dashboard.build_training_load_summary(self.conn, days=14)
        self.assertEqual(summary["model"]["sources"]["estimated_power_tss"], 0)

    def test_estimates_never_reach_records_power_curve_or_ftp(self):
        self.set_ftp(240)
        # A long, hard outdoor ride: well over FTP if the estimate were counted as power.
        self.add("hard", "Ride", _streams([(1800, 5.0, 0.08), (1800, 12.0, 0.0)]))
        self.assertGreater(power_estimate.estimates_for(self.conn, ["hard"])["hard"]["normalized_power"], 240)

        power = build_personal_records(self.conn)["cycling_power"]

        self.assertEqual(power["records"], [])
        self.assertFalse(power["ftp_estimate"]["available"])
        stored = json.loads(self.conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = 'hard'").fetchone()[0])
        self.assertNotIn("watts", stored)

    def test_ride_type_reads_estimated_power(self):
        streams = _streams([(600, 8.0, 0.0), (1500, 3.6, 0.06), (600, 8.0, 0.0)])
        row = {"detail_json": json.dumps({"device_watts": False}), "streams_json": json.dumps(streams), "source_status": "fetched"}
        ride = {"type": "Ride", "duration_min": 45, "workout_intent": None, "avg_hr": 150}
        result = classify_ride(ride, row, 240.0, None, 80.0)
        self.assertEqual((result["type"], result["basis"]), ("sweet_spot", "estimated_power"))
        self.assertIn("estimated power", result["reason"])
        # Without a weight (or FTP) the ride falls back as before.
        self.assertNotEqual(classify_ride(ride, row, 240.0, None)["basis"], "estimated_power")

    def _virtual(self, activity_id, error, name="Zwift - Watopia"):
        mass = 80 + BIKE_PROFILES["virtual"]["bike_kg"]

        def watts(speeds, n):
            return [instant_power(speeds[i], speeds[i - 1] if i else speeds[i], 1, 0.0, mass, BIKE_PROFILES["virtual"]) * (1 + error) for i in range(n)]

        self.add(activity_id, "VirtualRide", _streams([(1800, 10.0, 0.0), (600, 11.0, 0.0)], watts=watts), name=name, detail={"device_watts": True})

    def test_calibration_on_rides_with_both_is_within_the_band(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2000-01-01', 'weight', 80)")
        for index, error in enumerate((-0.08, -0.03, 0.02, 0.05, 0.1)):
            self._virtual(f"v{index}", error)
        # Drafting makes group rides need far less power than the physics says; they are left out.
        self._virtual("group", -0.4, name="Zwift - Group Ride: Coffee Ride")

        report = calibration_report(self.conn)

        self.assertEqual(report["rides"], 5)
        self.assertTrue(report["within_band"])
        self.assertLessEqual(report["np_median_abs_error"], power_estimate.CALIBRATION_BAND)

    def test_calibration_flags_a_model_outside_the_band(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES ('2000-01-01', 'weight', 80)")
        for index in range(3):
            self._virtual(f"v{index}", -0.3)
        self.assertFalse(calibration_report(self.conn)["within_band"])


if __name__ == "__main__":
    unittest.main()
