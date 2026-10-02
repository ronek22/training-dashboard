import unittest
from datetime import date, timedelta

from backend.app.services.sleep_debt import build_sleep_debt

TODAY = date(2026, 10, 2)


def nights(baseline_hours: float, recent: list[float], baseline_nights: int = 30) -> list[dict]:
    """`recent` is newest first, ending today; baseline nights sit before them."""
    history = [{"date": (TODAY - timedelta(days=i)).isoformat(), "value": hours} for i, hours in enumerate(recent)]
    for offset in range(len(recent), len(recent) + baseline_nights):
        history.append({"date": (TODAY - timedelta(days=offset)).isoformat(), "value": baseline_hours})
    return history


class SleepDebtTests(unittest.TestCase):
    def test_normal_week_has_no_debt(self):
        debt = build_sleep_debt(nights(7.5, [7.5] * 7), TODAY)
        self.assertTrue(debt["available"])
        self.assertEqual(debt["debt_hours"], 0)
        self.assertEqual(debt["status"], "ok")
        self.assertEqual(debt["baseline_hours"], 7.5)

    def test_short_week_builds_debt_against_own_median(self):
        debt = build_sleep_debt(nights(7.5, [6.5] * 7), TODAY)
        self.assertEqual(debt["debt_hours"], 7.0)
        self.assertEqual(debt["status"], "risk")

    def test_moderate_debt_is_caution(self):
        debt = build_sleep_debt(nights(7.5, [7.0] * 7), TODAY)
        self.assertEqual(debt["debt_hours"], 3.5)
        self.assertEqual(debt["status"], "caution")

    def test_long_night_pays_back_half(self):
        # Six nights 1 h short, one night 2 h long: 6 - 0.5 * 2 = 5 h.
        debt = build_sleep_debt(nights(7.5, [9.5] + [6.5] * 6), TODAY)
        self.assertEqual(debt["debt_hours"], 5.0)

    def test_debt_never_goes_negative(self):
        self.assertEqual(build_sleep_debt(nights(7.0, [9.0] * 7), TODAY)["debt_hours"], 0)

    def test_baseline_ignores_current_window(self):
        # A rough week does not lower its own yardstick.
        self.assertEqual(build_sleep_debt(nights(8.0, [5.0] * 7), TODAY)["baseline_hours"], 8.0)

    def test_too_few_recent_nights_is_not_judged(self):
        history = [item for item in nights(7.5, [6.0] * 7) if item["date"] not in {
            (TODAY - timedelta(days=d)).isoformat() for d in (1, 2, 3)
        }]
        debt = build_sleep_debt(history, TODAY)
        self.assertFalse(debt["available"])
        self.assertEqual(debt["status"], "insufficient_data")

    def test_short_baseline_is_not_judged(self):
        self.assertFalse(build_sleep_debt(nights(7.5, [6.0] * 7, baseline_nights=10), TODAY)["available"])

    def test_unsynced_last_night_still_reads_this_week(self):
        history = nights(7.5, [6.5] * 7)[1:]
        debt = build_sleep_debt(history, TODAY)
        self.assertTrue(debt["available"])
        self.assertEqual(debt["nights"], 6)
        self.assertEqual(debt["debt_hours"], 6.0)

    def test_history_series_is_newest_first(self):
        debt = build_sleep_debt(nights(7.5, [6.5] * 7, baseline_nights=40), TODAY, series_days=14)
        dates = [point["date"] for point in debt["history"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(dates[0], TODAY.isoformat())


if __name__ == "__main__":
    unittest.main()
