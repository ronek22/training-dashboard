import unittest

from backend.app.services.activities import _build_activity_charts, _downsample_series, _moving_timeline


class MovingTimelineTests(unittest.TestCase):
    def test_auto_pause_gap_is_removed_and_marked(self):
        times = [0, 1, 2, 3, 303, 304, 305]
        moving, pauses = _moving_timeline(times, [])
        self.assertEqual(moving, [0, 1, 2, 3, 3, 4, 5])
        self.assertEqual(pauses, [{"x": 0.05, "elapsed_min": 0.05, "duration_s": 300}])

    def test_recorded_stop_drops_samples_and_short_stops_get_no_marker(self):
        times = list(range(10))
        speeds = [5, 5, 5, 0, 0, 0, 5, 5, 5, 5]
        moving, pauses = _moving_timeline(times, speeds)
        self.assertEqual(moving[3:6], [None, None, None])
        # The stop (3 s plus the step back into motion) does not advance the clock.
        self.assertEqual(moving[:3] + moving[6:], [0, 1, 2, 2, 3, 4, 5])
        self.assertEqual(pauses, [])

    def test_long_recorded_stop_is_marked(self):
        times = list(range(100))
        speeds = [5] * 10 + [0] * 80 + [5] * 10
        _, pauses = _moving_timeline(times, speeds)
        self.assertEqual(len(pauses), 1)
        self.assertEqual(pauses[0]["duration_s"], 81)

    def test_charts_use_moving_minutes_and_keep_elapsed(self):
        times = [0, 6, 12, 1212, 1218]
        streams = {
            "time": {"data": times},
            "velocity_smooth": {"data": [5, 5, 5, 5, 5]},
            "heartrate": {"data": [120, 130, 140, 125, 135]},
        }
        charts = {chart["key"]: chart for chart in _build_activity_charts({"type": "Ride"}, {}, streams)}
        heart = charts["heartrate"]
        self.assertEqual(heart["axis"], "moving")
        self.assertEqual([point["x"] for point in heart["points"]], [0, 0.1, 0.2, 0.2, 0.3])
        self.assertEqual(heart["points"][3]["t"], 20.2)
        self.assertEqual(len(heart["pauses"]), 1)

    def test_virtual_ride_ignores_zero_speed(self):
        streams = {
            "time": {"data": [0, 1, 2]},
            "velocity_smooth": {"data": [0, 0, 0]},
            "watts": {"data": [150, 160, 170]},
        }
        charts = {chart["key"]: chart for chart in _build_activity_charts({"type": "VirtualRide"}, {}, streams)}
        self.assertEqual(len(charts["watts"]["points"]), 3)

    def test_downsample_averages_buckets(self):
        points = [{"x": index, "t": index, "y": 100 if index % 2 else 0} for index in range(480)]
        sampled = _downsample_series(points, limit=240)
        self.assertEqual(len(sampled), 240)
        self.assertTrue(all(point["y"] == 50 for point in sampled))

    def test_pace_averages_speed_before_converting(self):
        times = list(range(480))
        speeds = [4.0] * 480
        speeds[1] = 0.6  # a slow GPS sample inside the first bucket
        from backend.app.services.activities import _build_stream_chart

        pace = _build_stream_chart("pace", "Pace", "min/km", speeds, times, transform=lambda value: 1000 / value / 60)
        # Mean speed of the bucket is 2.3 m/s -> 7.25 min/km, not the mean of 4.17 and 27.8.
        self.assertAlmostEqual(pace["points"][0]["y"], round(1000 / 2.3 / 60, 2), places=2)
        self.assertEqual(pace["points"][1]["y"], round(1000 / 4.0 / 60, 2))

    def test_rolling_mean_smooths_over_the_window(self):
        from backend.app.services.activities import _rolling_mean

        points = [{"x": second / 60, "t": second / 60, "y": 4.0 if second % 2 else 3.0} for second in range(120)]
        smoothed = _rolling_mean(points, 30)
        self.assertTrue(all(abs(point["y"] - 3.5) < 0.05 for point in smoothed[20:100]))
        self.assertEqual(_rolling_mean(points, 0), points)


if __name__ == "__main__":
    unittest.main()
