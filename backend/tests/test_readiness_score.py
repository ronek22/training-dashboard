import sqlite3
import unittest
from datetime import datetime, timedelta

from backend.app.services.readiness_score import build_ramp_rate, build_readiness_score


def load_chart(prior_week: float, current_week: float) -> dict:
    daily = [prior_week / 7] * 7 + [current_week / 7] * 7
    return {"chart": [{"load": value} for value in daily]}


class RampRateTests(unittest.TestCase):
    def test_within_guideline_is_ok(self):
        ramp = build_ramp_rate(load_chart(300, 320))
        self.assertEqual(ramp["status"], "ok")
        self.assertEqual(ramp["change_pct"], 7)

    def test_above_ten_percent_is_caution(self):
        ramp = build_ramp_rate(load_chart(300, 345))
        self.assertEqual(ramp["status"], "caution")
        self.assertEqual(ramp["change_pct"], 15)

    def test_large_jump_is_high(self):
        self.assertEqual(build_ramp_rate(load_chart(300, 420))["status"], "high")

    def test_light_prior_week_is_not_judged(self):
        ramp = build_ramp_rate(load_chart(20, 200))
        self.assertEqual(ramp["status"], "insufficient_data")
        self.assertFalse(ramp["available"])

    def test_short_history_is_not_judged(self):
        self.assertEqual(build_ramp_rate({"chart": [{"load": 50}] * 5})["status"], "insufficient_data")


class ReadinessScoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE health_metric_samples (
                sample_key TEXT PRIMARY KEY, metric TEXT, timestamp TEXT, end_timestamp TEXT,
                date TEXT, value REAL, unit TEXT, category_label TEXT, duration_seconds REAL,
                source_name TEXT, source_bundle TEXT, source_device TEXT, import_id INTEGER
            )
            """
        )
        self.today = datetime.now().date()
        self.load = {"current": {"form": 5}, "ratio": {"status": "balanced"}, **load_chart(300, 300)}

    def tearDown(self):
        self.conn.close()

    def _add(self, metric, days_ago, value, **extra):
        day = (self.today - timedelta(days=days_ago)).isoformat()
        self.conn.execute(
            "INSERT INTO health_metric_samples (sample_key, metric, timestamp, date, value, unit, category_label, duration_seconds, import_id)"
            " VALUES (?, ?, ?, ?, ?, '', ?, ?, 1)",
            (f"{metric}-{days_ago}-{extra.get('label')}", metric, f"{day}T06:00:00", day, value, extra.get("label"), extra.get("seconds")),
        )

    def _baseline(self, hrv=60, rhr=50, start=1):
        for days_ago in range(start, start + 19):
            self._add("hrv", days_ago, hrv)
            self._add("resting_hr", days_ago, rhr)

    def _score(self, state="ready", feedback=None, load=None):
        return build_readiness_score(
            self.conn, state=state, latest_feedback=feedback, training_load_summary=self.load if load is None else load
        )

    def test_good_signals_are_green(self):
        self._baseline()
        self._add("hrv", 0, 61)
        self._add("resting_hr", 0, 50)
        self._add("sleep", 0, 0, label="asleep", seconds=8 * 3600)
        score = self._score()
        self.assertEqual(score["level"], "green")
        self.assertTrue(score["physiology_available"])
        self.assertFalse(score["suggests_swap"])

    def test_suppressed_hrv_and_short_sleep_are_amber_or_red(self):
        self._baseline(start=3)
        for days_ago in range(3):
            self._add("hrv", days_ago, 45)  # -25%
        self._add("sleep", 0, 0, label="asleep", seconds=5 * 3600)
        score = self._score()
        self.assertEqual(score["level"], "red")
        self.assertTrue(score["suggests_swap"])
        self.assertTrue(any(driver.startswith("HRV") for driver in score["drivers"]))

    def test_single_bad_hrv_morning_does_not_flag(self):
        self._baseline(start=3)
        self._add("hrv", 0, 35)
        self._add("hrv", 1, 62)
        self._add("hrv", 2, 66)
        self.assertEqual(self._score()["level"], "green")

    def test_single_moderate_signal_stays_green(self):
        self._baseline()
        self._add("resting_hr", 0, 53)  # +3 bpm -> 1 point
        self.assertEqual(self._score()["level"], "green")

    def test_stale_health_data_is_ignored(self):
        self._baseline(start=7)
        self._add("hrv", 6, 30)
        score = self._score()
        self.assertFalse(score["physiology_available"])
        self.assertEqual(score["level"], "green")

    def test_watch_state_alone_is_green_but_with_high_ramp_is_amber(self):
        load = {**self.load, **load_chart(300, 420)}
        self.assertEqual(self._score(state="watch", load=load)["level"], "amber")
        self.assertEqual(self._score(state="watch")["level"], "green")

    def test_pain_checkin_pushes_to_red_with_strained_load(self):
        feedback = {
            "activity_date": self.today.isoformat(), "energy": 3, "muscle_soreness": 2, "pain_level": 5,
        }
        self.assertEqual(self._score(state="strained", feedback=feedback)["level"], "red")

    def test_no_evidence_is_unknown(self):
        self.assertEqual(self._score(state="insufficient_data", load={})["level"], "unknown")

    def _checkin(self, days_ago=0, **overrides):
        return {
            "date": (self.today - timedelta(days=days_ago)).isoformat(),
            "energy": 4, "muscle_soreness": 2, "stress": 2, "sleep_quality": 4, "pain_level": 0,
            **overrides,
        }

    def _score_with_checkin(self, checkin):
        return build_readiness_score(
            self.conn, state="ready", latest_feedback=None, training_load_summary=self.load, daily_checkin=checkin
        )

    def test_good_morning_checkin_is_green(self):
        score = self._score_with_checkin(self._checkin())
        self.assertEqual(score["level"], "green")
        self.assertTrue(any(f["key"] == "check_in" and f["points"] == 0 for f in score["factors"]))

    def test_high_stress_and_poor_sleep_quality_reach_amber(self):
        score = self._score_with_checkin(self._checkin(stress=5, sleep_quality=2))
        self.assertEqual(score["level"], "amber")
        self.assertIn("stress 5/5", score["drivers"][0])

    def test_stale_morning_checkin_is_ignored(self):
        score = self._score_with_checkin(self._checkin(days_ago=3, stress=5, energy=1))
        self.assertEqual(score["level"], "green")

    def test_morning_checkin_is_preferred_over_activity_feedback(self):
        feedback = {"activity_date": self.today.isoformat(), "energy": 1, "muscle_soreness": 5, "pain_level": 6}
        score = build_readiness_score(
            self.conn, state="ready", latest_feedback=feedback, training_load_summary=self.load,
            daily_checkin=self._checkin(),
        )
        self.assertEqual(score["level"], "green")

    def test_missing_health_table_does_not_break_score(self):
        self.conn.execute("DROP TABLE health_metric_samples")
        self.assertEqual(self._score()["level"], "green")


if __name__ == "__main__":
    unittest.main()
