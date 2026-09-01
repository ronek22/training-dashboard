import unittest

from app.services.weather import summarize_daily_forecast_payload, summarize_weather_payload


class WeatherSummaryTests(unittest.TestCase):
    def test_summarizes_daily_forecast(self):
        payload = {
            "timezone": "Europe/Warsaw",
            "daily": {
                "time": ["2026-09-01", "2026-09-02"],
                "weather_code": [2, 61],
                "temperature_2m_max": [21.6, 17.2],
                "temperature_2m_min": [13.4, 11.8],
                "precipitation_sum": [0, 4.26],
                "precipitation_probability_max": [10, 82],
                "wind_speed_10m_max": [14.7, 27.2],
            },
        }

        result = summarize_daily_forecast_payload(payload, 54.352, 18.6466)

        self.assertEqual(len(result["days"]), 2)
        self.assertEqual(result["days"][0]["description"], "Partly cloudy")
        self.assertEqual(result["days"][0]["temperature_max_c"], 22)
        self.assertEqual(result["days"][1]["precipitation_mm"], 4.3)
        self.assertEqual(result["days"][1]["precipitation_probability"], 82)
        self.assertEqual(result["days"][1]["wind_speed_max_kmh"], 27)

    def test_summarizes_current_conditions_and_upcoming_rain(self):
        payload = {
            "timezone": "Europe/Warsaw",
            "current": {
                "time": "2026-09-01T10:30",
                "temperature_2m": 17.6,
                "apparent_temperature": 16.8,
                "precipitation": 0,
                "weather_code": 2,
                "is_day": 1,
            },
            "hourly": {
                "time": [
                    "2026-09-01T10:00",
                    "2026-09-01T11:00",
                    "2026-09-01T12:00",
                    "2026-09-01T13:00",
                    "2026-09-01T14:00",
                    "2026-09-01T15:00",
                    "2026-09-01T16:00",
                    "2026-09-01T17:00",
                ],
                "precipitation": [0, 0, 0.2, 0.8, 0.1, 0, 0, 2.0],
                "precipitation_probability": [5, 10, 45, 80, 55, 20, 10, 90],
            },
        }

        result = summarize_weather_payload(payload, 54.352, 18.6466)

        self.assertEqual(result["current"]["temperature_c"], 18)
        self.assertEqual(result["current"]["description"], "Partly cloudy")
        self.assertEqual(result["upcoming"]["hours"], 6)
        self.assertTrue(result["upcoming"]["rain_expected"])
        self.assertEqual(result["upcoming"]["precipitation_mm"], 1.1)
        self.assertEqual(result["upcoming"]["peak_probability"], 80)
        self.assertEqual(result["upcoming"]["starts_at"], "2026-09-01T12:00")

    def test_handles_a_dry_forecast(self):
        payload = {
            "current": {"time": "2026-09-01T10:00", "temperature_2m": 21, "weather_code": 0},
            "hourly": {
                "time": ["2026-09-01T10:00", "2026-09-01T11:00"],
                "precipitation": [0, 0],
                "precipitation_probability": [0, 10],
            },
        }

        result = summarize_weather_payload(payload, 54.352, 18.6466)

        self.assertFalse(result["upcoming"]["rain_expected"])
        self.assertEqual(result["upcoming"]["precipitation_mm"], 0)
        self.assertIsNone(result["upcoming"]["starts_at"])


if __name__ == "__main__":
    unittest.main()
