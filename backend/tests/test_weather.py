import unittest

from app.services.weather import summarize_weather_payload


class WeatherSummaryTests(unittest.TestCase):
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
