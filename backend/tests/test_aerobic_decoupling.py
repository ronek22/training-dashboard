import json
import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.aerobic_decoupling import (
    aerobic_decoupling_coaching_context,
    analyse_ride,
    build_aerobic_decoupling,
)

TODAY = date(2026, 10, 5)


def steady_streams(minutes=60, watts=150, hr_first=140, hr_second=None, *, zero_every=0, surge_every=0, hr_missing_from=None):
    """One sample per second; heart rate steps from hr_first to hr_second at the halfway point."""
    seconds = minutes * 60
    hr_second = hr_first if hr_second is None else hr_second
    times = list(range(seconds + 1))
    power = []
    for second in times:
        value = watts
        if zero_every and second % zero_every < zero_every // 4:
            value = 0
        if surge_every and second % surge_every < 30:
            value = watts * 3
        power.append(value)
    heart = [hr_first if second < seconds / 2 else hr_second for second in times]
    if hr_missing_from is not None:
        heart = [None if second >= hr_missing_from else value for second, value in zip(times, heart)]
    return {"time": {"data": times}, "watts": {"data": power}, "heartrate": {"data": heart}}


class AnalyseRideTests(unittest.TestCase):
    def test_steady_ride_reports_efficiency_and_drift(self):
        result = analyse_ride(steady_streams(hr_first=140, hr_second=147))
        self.assertTrue(result["qualifies"])
        self.assertEqual(result["avg_watts"], 150)
        # Trimmed window is 10..55 min (halves split at 32.5), so the HR step at 30 min puts 2.5 min of 147 in the first half.
        self.assertAlmostEqual(result["first_half"]["avg_hr"], (20 * 140 + 2.5 * 147) / 22.5, places=1)
        self.assertAlmostEqual(result["second_half"]["efficiency"], 150 / 147, places=3)
        first_ef = 150 / ((20 * 140 + 2.5 * 147) / 22.5)
        self.assertAlmostEqual(result["decoupling_pct"], (first_ef - 150 / 147) / first_ef * 100, places=1)
        self.assertEqual(result["analysed_min"], 45)

    def test_no_drift_on_constant_heart_rate(self):
        result = analyse_ride(steady_streams(hr_first=140))
        self.assertEqual(result["decoupling_pct"], 0)
        self.assertAlmostEqual(result["efficiency"], 150 / 140, places=3)

    def test_rules(self):
        cases = {
            "too_short": steady_streams(minutes=40),
            "coasting": steady_streams(zero_every=60),
            "not_steady": steady_streams(surge_every=120),
            "missing_heart_rate": steady_streams(hr_missing_from=40 * 60),
        }
        for reason, streams in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(analyse_ride(streams)["reason"], reason)
        self.assertEqual(analyse_ride(steady_streams(watts=200), ftp_watts=230)["reason"], "too_hard")
        self.assertTrue(analyse_ride(steady_streams(watts=180), ftp_watts=230)["qualifies"])

    def test_gaps_disqualify(self):
        streams = steady_streams()
        # Drop 10 minutes in the middle of the analysed window.
        keep = [index for index in range(len(streams["time"]["data"])) if not 1800 <= index < 2400]
        gappy = {key: {"data": [value["data"][index] for index in keep]} for key, value in streams.items()}
        self.assertEqual(analyse_ride(gappy)["reason"], "gappy_data")


class BuildAerobicDecouplingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT, workout_intent TEXT, duration_min REAL);
            CREATE TABLE activity_details (activity_id TEXT PRIMARY KEY, detail_json TEXT, streams_json TEXT, source_status TEXT);
            CREATE TABLE metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, metric TEXT, value REAL, unit TEXT, notes TEXT);
            """
        )
        self.addCleanup(self.conn.close)

    def add_ride(self, activity_id, days_ago, streams=None, *, activity_type="VirtualRide", intent=None, detail=None, minutes=60):
        self.conn.execute(
            "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?)",
            (activity_id, (TODAY - timedelta(days=days_ago)).isoformat(), activity_type, activity_id, intent, minutes),
        )
        self.conn.execute(
            "INSERT INTO activity_details VALUES (?, ?, ?, ?)",
            (activity_id, json.dumps(detail) if detail else None, json.dumps(streams) if streams else None, "streams_backfill"),
        )

    def test_trend_needs_three_rides(self):
        self.add_ride("a", 40, steady_streams(hr_first=145))
        self.add_ride("b", 20, steady_streams(hr_first=140))
        data = build_aerobic_decoupling(self.conn, today=TODAY)
        self.assertEqual(data["status"], "unavailable")
        self.assertEqual(data["environments"]["indoor"]["status"], "unavailable")
        self.assertEqual(len(data["rides"]), 2)

    def test_improving_trend_with_same_power_comparison(self):
        self.add_ride("a", 60, steady_streams(hr_first=146))
        self.add_ride("b", 30, steady_streams(hr_first=143))
        self.add_ride("c", 2, steady_streams(hr_first=140))
        self.add_ride("hard", 10, steady_streams(), intent="interval")
        self.add_ride("short", 5, steady_streams(minutes=30), minutes=30)
        self.add_ride("old", 120, steady_streams())
        data = build_aerobic_decoupling(self.conn, today=TODAY)
        indoor = data["environments"]["indoor"]
        self.assertEqual(indoor["status"], "available")
        self.assertEqual(indoor["direction"], "improving")
        self.assertEqual(indoor["comparison"]["hr_delta_bpm"], -6)
        self.assertTrue(indoor["comparison"]["text"].startswith("Same power, 6 bpm lower than on"))
        self.assertEqual({item["activity_id"]: item["reason"] for item in data["excluded"]}, {"hard": "hard_session", "short": "too_short"})
        self.assertEqual([ride["activity_id"] for ride in data["rides"]], ["a", "b", "c"])

    def test_harder_rides_alone_do_not_count_as_improvement(self):
        # Heart rate follows power exactly (HR = 80 + 0.4 W) and never changes at the same power,
        # but rides get harder, so raw power per heartbeat climbs.
        for index, watts in enumerate((120, 130, 125, 140, 150, 145)):
            self.add_ride(f"r{index}", 60 - index * 10, steady_streams(watts=watts, hr_first=80 + 0.4 * watts))
        indoor = build_aerobic_decoupling(self.conn, today=TODAY)["environments"]["indoor"]
        self.assertGreater(indoor["efficiency_change_pct"], 2)
        self.assertEqual(indoor["direction_basis"], "hr_at_same_power")
        self.assertAlmostEqual(indoor["hr_change_at_same_power_bpm"], 0, places=1)
        self.assertEqual(indoor["direction"], "steady")

    def test_lower_heart_rate_at_same_power_is_improving(self):
        for index, watts in enumerate((120, 140, 125, 145, 130, 150)):
            self.add_ride(f"r{index}", 60 - index * 10, steady_streams(watts=watts, hr_first=90 + 0.4 * watts - index))
        indoor = build_aerobic_decoupling(self.conn, today=TODAY)["environments"]["indoor"]
        self.assertAlmostEqual(indoor["hr_change_at_same_power_bpm"], -5, places=1)
        self.assertEqual(indoor["direction"], "improving")

    def test_environments_are_separate_and_outdoor_needs_a_power_meter(self):
        for index in range(3):
            self.add_ride(f"in{index}", 10 + index, steady_streams())
        self.add_ride("trainer", 4, steady_streams(), activity_type="Ride", detail={"device_watts": True, "trainer": True})
        self.add_ride("road", 3, steady_streams(), activity_type="Ride", detail={"device_watts": True})
        self.add_ride("estimated", 1, steady_streams(), activity_type="Ride", detail={"device_watts": False})
        data = build_aerobic_decoupling(self.conn, today=TODAY)
        self.assertEqual(data["environments"]["indoor"]["rides"], 4)
        self.assertEqual(data["environments"]["outdoor"]["rides"], 1)
        self.assertEqual(data["environments"]["outdoor"]["status"], "unavailable")
        self.assertEqual(data["excluded"][0]["reason"], "no_measured_power")

    def test_stored_ftp_is_only_a_ceiling(self):
        self.conn.execute("INSERT INTO metrics (date, metric, value, unit) VALUES ('2026-03-12', 'ftp', 200, 'W')")
        self.add_ride("z2", 3, steady_streams(watts=150))
        self.add_ride("tempo", 2, steady_streams(watts=180))
        data = build_aerobic_decoupling(self.conn, today=TODAY)
        self.assertEqual([ride["activity_id"] for ride in data["rides"]], ["z2"])
        self.assertEqual(data["excluded"][0]["reason"], "too_hard")
        self.assertEqual(data["ftp_ceiling_watts"], 160)
        context = aerobic_decoupling_coaching_context(self.conn, today=TODAY)
        self.assertEqual(context["recent_rides"][0]["date"], (TODAY - timedelta(days=3)).isoformat())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
