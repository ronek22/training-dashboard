import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.services import health_data


SCHEMA = """
CREATE TABLE health_data_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    file_modified_ns INTEGER NOT NULL,
    export_date TEXT,
    status TEXT NOT NULL DEFAULT 'imported',
    samples_seen INTEGER NOT NULL DEFAULT 0,
    samples_inserted INTEGER NOT NULL DEFAULT 0,
    import_version INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE health_metric_samples (
    sample_key TEXT PRIMARY KEY,
    metric TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    category_label TEXT,
    duration_seconds REAL,
    source_name TEXT,
    source_bundle TEXT,
    source_device TEXT,
    import_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def point(timestamp: str, value: float, unit: str) -> dict:
    return {
        "timestamp": timestamp,
        "start_date": timestamp,
        "end_date": timestamp,
        "value": value,
        "unit": unit,
        "source": {
            "name": "Apple Watch",
            "bundle_identifier": "com.apple.health.watch",
            "device": "Watch7,5",
        },
    }


def export_payload(resting_points: list[dict], *, include_large_ignored_metric: bool = True) -> dict:
    metrics = []
    if include_large_ignored_metric:
        metrics.append({
            "aggregation_level": "raw",
            "category": "Activity",
            "data_points": [point("2026-08-28T10:00:00Z", value, "count/min") for value in range(100)],
            "display_name": "Heart Rate",
        })
    metrics.extend([
        {
            "aggregation_level": "raw",
            "category": "Vitals",
            "data_points": resting_points,
            "display_name": "Resting Heart Rate",
        },
        {
            "aggregation_level": "raw",
            "category": "Vitals",
            "data_points": [point("2026-08-28T05:30:00Z", 48.2, "ms")],
            "display_name": "Heart Rate Variability",
        },
        {
            "aggregation_level": "raw",
            "category": "Body Measurements",
            "data_points": [point("2026-08-28T06:00:00Z", 75.6, "kg")],
            "display_name": "Body Weight",
        },
    ])
    return {"category_metrics": [], "metrics": metrics, "export_date": "2026-08-29T19:49:06Z", "workouts": []}


def sleep_point(start: str, end: str, value: int, label: str) -> dict:
    item = point(start, value, "")
    item["end_date"] = end
    item["label"] = label
    return item


class HealthDataImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def write_export(self, name: str, payload: dict) -> Path:
        path = self.directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_streaming_import_ignores_raw_heart_rate_and_imports_compact_metrics(self):
        self.write_export(
            "initial.json",
            export_payload([
                point("2026-08-28T04:00:00Z", 51, "count/min"),
                point("2026-08-29T04:00:00Z", 53, "count/min"),
            ]),
        )
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            preview = health_data.preview_health_data_import(self.conn)
            result = health_data.apply_health_data_import(self.conn)

        self.assertEqual(preview["counts"]["import"], 1)
        self.assertEqual(result["applied"]["files_imported"], 1)
        self.assertEqual(result["applied"]["samples_seen"], 4)
        self.assertEqual(result["applied"]["samples_inserted"], 4)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM health_metric_samples WHERE metric = 'resting_hr'").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM health_metric_samples WHERE metric = 'hrv'").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM health_metric_samples WHERE metric = 'weight'").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM health_metric_samples WHERE metric = 'heart_rate'").fetchone()[0], 0)

    def test_repeated_file_and_overlapping_daily_export_are_idempotent(self):
        repeated = point("2026-08-29T04:00:00Z", 53, "count/min")
        self.write_export("initial.json", export_payload([repeated]))
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            first = health_data.apply_health_data_import(self.conn)
            second = health_data.apply_health_data_import(self.conn)
            self.write_export("daily.json", export_payload([repeated], include_large_ignored_metric=False))
            daily = health_data.apply_health_data_import(self.conn)

        self.assertGreater(first["applied"]["samples_inserted"], 0)
        self.assertEqual(second["applied"]["files_imported"], 0)
        self.assertEqual(daily["applied"]["files_imported"], 1)
        self.assertEqual(daily["applied"]["samples_inserted"], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM health_metric_samples").fetchone()[0], 3)

    def test_overlapping_exports_dedupe_after_raw_labels_and_units_change(self):
        initial = export_payload([], include_large_ignored_metric=False)
        initial["metrics"].append({
            "data_points": [point("2026-08-29T08:00:00Z", 1200, "")],
            "display_name": "Steps",
        })
        initial["category_metrics"] = [{
            "data_points": [sleep_point("2026-08-28T22:00:00Z", "2026-08-28T23:00:00Z", 3, "asleepCore")],
            "display_name": "Sleep Analysis",
        }]
        daily = json.loads(json.dumps(initial))
        daily["metrics"][-1]["data_points"][0]["unit"] = "count"
        daily["category_metrics"][0]["data_points"][0]["label"] = "core"

        self.write_export("initial.json", initial)
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            first = health_data.apply_health_data_import(self.conn)
            self.write_export("daily.json", daily)
            second = health_data.apply_health_data_import(self.conn)

        self.assertGreater(first["applied"]["samples_inserted"], 0)
        self.assertEqual(second["applied"]["samples_inserted"], 0)
        self.assertEqual(health_data.get_health_metric_history(self.conn, "steps", 730)[0]["value"], 1200)
        self.assertEqual(health_data.get_sleep_history(self.conn, 730)[0]["value"], 1.0)

    def test_summary_collapses_legacy_exact_duplicates(self):
        columns = """sample_key, metric, timestamp, end_timestamp, date, value, unit,
                     category_label, duration_seconds, source_name, source_bundle, source_device, import_id"""
        step = ("steps", "2026-08-29T08:00:00Z", "2026-08-29T08:00:00Z", "2026-08-29", 1200, "steps", None, None, "HealthKit", "", None, 1)
        sleep = ("sleep", "2026-08-28T22:00:00Z", "2026-08-28T23:00:00Z", "2026-08-29", 3, "seconds", "core", 3600, "Apple Watch", "watch.bundle", "Watch7,5", 1)
        self.conn.executemany(f"INSERT INTO health_metric_samples ({columns}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [("old-step-a", *step), ("old-step-b", *step), ("old-sleep-a", *sleep), ("old-sleep-b", *sleep)])

        self.assertEqual(health_data.get_health_metric_history(self.conn, "steps", 730)[0]["value"], 1200)
        self.assertEqual(health_data.get_sleep_history(self.conn, 730)[0]["value"], 1.0)

    def test_health_summary_aggregates_multiple_resting_hr_samples_by_local_day(self):
        self.write_export(
            "daily.json",
            export_payload([
                point("2026-08-29T04:00:00Z", 52, "count/min"),
                point("2026-08-29T05:00:00Z", 54, "count/min"),
            ], include_large_ignored_metric=False),
        )
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            health_data.apply_health_data_import(self.conn)
        summary = health_data.get_health_summary(self.conn, days=730)

        resting = summary["metrics"]["resting_hr"]
        self.assertTrue(resting["available"])
        self.assertEqual(resting["latest"]["value"], 53.0)
        self.assertEqual(resting["latest"]["sample_count"], 2)

    def test_imports_daily_movement_and_normalizes_sleep_stages(self):
        payload = export_payload([], include_large_ignored_metric=False)
        payload["metrics"].extend([
            {"data_points": [point("2026-08-29T08:00:00Z", 1200, "")], "display_name": "Steps"},
            {"data_points": [point("2026-08-29T08:00:00Z", 850, "km")], "display_name": "Walking + Running Distance"},
            {"data_points": [point("2026-08-29T08:00:00Z", 3, "")], "display_name": "Flights Climbed"},
        ])
        payload["category_metrics"] = [{
            "data_points": [
                sleep_point("2026-08-28T21:00:00Z", "2026-08-28T22:00:00Z", 3, "asleepUnspecified"),
                sleep_point("2026-08-28T22:00:00Z", "2026-08-29T04:00:00Z", 4, "unknown"),
                sleep_point("2026-08-29T04:00:00Z", "2026-08-29T05:00:00Z", 5, "unknown"),
            ],
            "display_name": "Sleep Analysis",
        }]
        self.write_export("daily.json", payload)
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            result = health_data.apply_health_data_import(self.conn)
        summary = health_data.get_health_summary(self.conn, days=730)

        self.assertEqual(result["applied"]["files_imported"], 1)
        self.assertEqual(summary["metrics"]["steps"]["latest"]["value"], 1200)
        self.assertEqual(summary["metrics"]["walking_running_distance"]["latest"]["value"], 0.85)
        self.assertEqual(summary["metrics"]["flights_climbed"]["latest"]["value"], 3)
        self.assertEqual(summary["metrics"]["sleep"]["latest"]["value"], 8.0)
        self.assertEqual(summary["metrics"]["sleep"]["latest"]["stages"]["deep"], 6.0)

    def test_old_import_version_is_reprocessed_without_duplicate_samples(self):
        self.write_export("initial.json", export_payload([point("2026-08-29T04:00:00Z", 53, "count/min")]))
        with patch.object(health_data, "health_data_directory", return_value=self.directory):
            health_data.apply_health_data_import(self.conn)
            before = self.conn.execute("SELECT COUNT(*) FROM health_metric_samples").fetchone()[0]
            self.conn.execute("UPDATE health_data_imports SET import_version = 1")
            self.conn.commit()
            result = health_data.apply_health_data_import(self.conn)

        after = self.conn.execute("SELECT COUNT(*) FROM health_metric_samples").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(result["applied"]["samples_inserted"], 0)
        self.assertEqual(self.conn.execute("SELECT import_version FROM health_data_imports").fetchone()[0], health_data.CURRENT_IMPORT_VERSION)


if __name__ == "__main__":
    unittest.main()
