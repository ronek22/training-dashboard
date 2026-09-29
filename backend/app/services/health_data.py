import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import ijson
from fastapi import HTTPException


TARGET_METRICS = {
    "Resting Heart Rate": "resting_hr",
    "Heart Rate Variability": "hrv",
    "Body Weight": "weight",
    "Steps": "steps",
    "Walking + Running Distance": "walking_running_distance",
    "Flights Climbed": "flights_climbed",
}
TARGET_CATEGORY_METRICS = {"Sleep Analysis": "sleep"}
TARGET_LABELS = {
    "resting_hr": "Resting heart rate",
    "hrv": "Heart-rate variability",
    "weight": "Body weight",
    "sleep": "Sleep",
    "steps": "Steps",
    "walking_running_distance": "Walking and running distance",
    "flights_climbed": "Flights climbed",
}
CURRENT_IMPORT_VERSION = 2
DEFAULT_TIMEZONE = "Europe/Warsaw"
SLEEP_STAGE_BY_VALUE = {
    0: "in_bed",
    1: "asleep_unspecified",
    2: "awake",
    3: "core",
    4: "deep",
    5: "rem",
}
SLEEP_VALUE_BY_STAGE = {stage: value for value, stage in SLEEP_STAGE_BY_VALUE.items()}

# Files written by the iOS Shortcut share the Health Data Export folder and are
# recognised by name. See docs/apple-health-shortcut.md for the payload format.
SHORTCUT_FILE_PREFIX = "shortcut"
SHORTCUT_DAILY_METRICS = {"steps", "walking_running_distance", "flights_climbed"}
SHORTCUT_DAILY_SOURCE_NAME = "iOS Shortcut (daily total)"
SHORTCUT_DAILY_SOURCE_BUNDLE = "shortcut.daily"
SHORTCUT_UNITS = {
    "resting_hr": "bpm",
    "hrv": "ms",
    "weight": "kg",
    "steps": "steps",
    "walking_running_distance": "km",
    "flights_climbed": "flights",
}
# Shortcuts prints sleep values in the phone's language; English and Polish are
# matched by substring, most specific first.
SHORTCUT_SLEEP_LABELS = (
    ("deep", "deep"), ("głęb", "deep"),
    ("rem", "rem"),
    ("core", "core"), ("podstaw", "core"), ("rdzen", "core"), ("rdzeń", "core"),
    ("awake", "awake"), ("przebudz", "awake"), ("czuwa", "awake"),
    ("bed", "in_bed"), ("łóżk", "in_bed"),
    ("unspecified", "asleep_unspecified"), ("asleep", "asleep_unspecified"), ("sen", "asleep_unspecified"),
)


class _HashingReader:
    def __init__(self, handle: BinaryIO):
        self.handle = handle
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.handle.read(size)
        if data:
            self.digest.update(data)
        return data

    def hexdigest(self) -> str:
        return self.digest.hexdigest()


def health_data_directory() -> Path:
    return Path(os.getenv("HEALTH_DATA_EXPORT_DIR", "/health-data-export"))


def _local_date(timestamp: str) -> str:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timezone_name = os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)
        return parsed.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return str(timestamp)[:10]


def _sleep_date(timestamp: str) -> str:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone(ZoneInfo(os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)))
        if local.hour >= 18:
            local += timedelta(days=1)
        return local.date().isoformat()
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return _local_date(timestamp)


def _file_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _matching_import(conn: sqlite3.Connection, path: Path):
    size, modified_ns = _file_signature(path)
    return conn.execute(
        """
        SELECT * FROM health_data_imports
        WHERE file_name = ? AND file_size = ? AND file_modified_ns = ?
          AND status = 'imported' AND import_version >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (path.name, size, modified_ns, CURRENT_IMPORT_VERSION),
    ).fetchone()


def preview_health_data_import(conn: sqlite3.Connection) -> dict:
    directory = health_data_directory()
    if not directory.is_dir():
        return {"configured": False, "directory": str(directory), "counts": {}, "items": [], "last_import": None}

    items = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        size, modified_ns = _file_signature(path)
        existing = _matching_import(conn, path)
        items.append({
            "file_name": path.name,
            "format": "shortcut" if is_shortcut_export(path) else "health_data_export",
            "file_size": size,
            "file_size_mb": round(size / (1024 * 1024), 1),
            "file_modified_ns": modified_ns,
            "action": "already_processed" if existing else "import",
            "samples_inserted": int(existing["samples_inserted"] or 0) if existing else None,
            "imported_at": existing["imported_at"] if existing else None,
        })

    counts = defaultdict(int)
    for item in items:
        counts[item["action"]] += 1
    last_import = conn.execute(
        "SELECT * FROM health_data_imports WHERE status = 'imported' ORDER BY imported_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return {
        "configured": True,
        "directory": str(directory),
        "counts": dict(counts),
        "items": items,
        "target_metrics": [*TARGET_METRICS, *TARGET_CATEGORY_METRICS],
        "last_import": dict(last_import) if last_import else None,
    }


def _scan_metadata(path: Path) -> dict:
    metric_index = -1
    category_metric_index = -1
    metric_names = {}
    category_metric_names = {}
    export_date = None
    with path.open("rb") as raw_handle:
        handle = _HashingReader(raw_handle)
        for prefix, event, value in ijson.parse(handle):
            if prefix == "metrics.item" and event == "start_map":
                metric_index += 1
            elif prefix == "metrics.item.display_name" and event == "string":
                metric_names[metric_index] = str(value)
            elif prefix == "category_metrics.item" and event == "start_map":
                category_metric_index += 1
            elif prefix == "category_metrics.item.display_name" and event == "string":
                category_metric_names[category_metric_index] = str(value)
            elif prefix == "export_date" and event in {"string", "number"}:
                export_date = str(value)
        file_hash = handle.hexdigest()
    return {
        "file_hash": file_hash,
        "export_date": export_date,
        "metric_names": metric_names,
        "category_metric_names": category_metric_names,
    }


def _sample_key(
    metric: str,
    timestamp: str,
    end_timestamp: Optional[str],
    value: float,
    unit: Optional[str],
    category_label: Optional[str],
    source: dict,
) -> str:
    # Export-wide and daily Health Data Export files can describe the same
    # HealthKit sample with different raw labels or units. Build identity from
    # the normalized fields we persist so overlapping exports stay idempotent.
    identity_parts = [
        metric,
        timestamp,
        end_timestamp or "",
        repr(value),
        unit or "",
        category_label or "",
        str(source.get("bundle_identifier") or ""),
        str(source.get("name") or ""),
    ]
    identity = "|".join(identity_parts)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _sample_row(metric: str, point: dict, import_id: int) -> Optional[tuple]:
    timestamp = point.get("timestamp") or point.get("start_date")
    end_timestamp = point.get("end_date")
    value = point.get("value")
    if not timestamp or value is None:
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    source = point.get("source") if isinstance(point.get("source"), dict) else {}
    category_label = None
    duration_seconds = None
    date_timestamp = str(timestamp)
    unit = str(point.get("unit") or "") or None
    if metric == "walking_running_distance":
        # Health Data Export labels these raw samples as km but emits metre-sized values.
        numeric_value /= 1000.0
        unit = "km"
    elif metric == "steps":
        unit = "steps"
    elif metric == "flights_climbed":
        unit = "flights"
    elif metric == "sleep":
        category_label = SLEEP_STAGE_BY_VALUE.get(int(numeric_value), str(point.get("label") or "unknown"))
        unit = "seconds"
        if end_timestamp:
            try:
                start_dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(end_timestamp).replace("Z", "+00:00"))
                duration_seconds = max(0.0, (end_dt - start_dt).total_seconds())
            except (TypeError, ValueError):
                duration_seconds = None
            date_timestamp = str(end_timestamp)
    return (
        _sample_key(
            metric,
            str(timestamp),
            str(end_timestamp) if end_timestamp else None,
            numeric_value,
            unit,
            category_label,
            source,
        ),
        metric,
        str(timestamp),
        str(end_timestamp) if end_timestamp else None,
        _sleep_date(date_timestamp) if metric == "sleep" else _local_date(date_timestamp),
        numeric_value,
        unit,
        category_label,
        duration_seconds,
        source.get("name"),
        source.get("bundle_identifier"),
        source.get("device"),
        import_id,
    )


def _insert_batch(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    if not rows:
        return 0
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO health_metric_samples
            (sample_key, metric, timestamp, end_timestamp, date, value, unit, category_label,
             duration_seconds, source_name, source_bundle, source_device, import_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return conn.total_changes - before


def _import_selected_metrics(
    conn: sqlite3.Connection,
    path: Path,
    import_id: int,
    metric_names: dict[int, str],
    category_metric_names: dict[int, str],
) -> tuple[int, int, dict[str, int]]:
    target_indices = {
        index: TARGET_METRICS[name]
        for index, name in metric_names.items()
        if name in TARGET_METRICS
    }
    category_target_indices = {
        index: TARGET_CATEGORY_METRICS[name]
        for index, name in category_metric_names.items()
        if name in TARGET_CATEGORY_METRICS
    }
    indices = {"metrics": -1, "category_metrics": -1}
    current_point = None
    batch = []
    seen = 0
    inserted = 0
    metric_counts = defaultdict(int)

    with path.open("rb") as handle:
        for prefix, event, value in ijson.parse(handle):
            section = "category_metrics" if prefix.startswith("category_metrics.") else "metrics" if prefix.startswith("metrics.") else None
            if not section:
                continue
            if prefix == f"{section}.item" and event == "start_map":
                indices[section] += 1
                continue
            section_targets = category_target_indices if section == "category_metrics" else target_indices
            metric = section_targets.get(indices[section])
            if not metric:
                continue
            item_prefix = f"{section}.item.data_points.item"
            if prefix == item_prefix and event == "start_map":
                current_point = {"source": {}}
                continue
            if current_point is None:
                continue
            if prefix == item_prefix and event == "end_map":
                seen += 1
                row = _sample_row(metric, current_point, import_id)
                if row:
                    batch.append(row)
                    metric_counts[metric] += 1
                current_point = None
                if len(batch) >= 1000:
                    inserted += _insert_batch(conn, batch)
                    batch.clear()
                continue
            base = f"{item_prefix}."
            if not prefix.startswith(base) or event not in {"string", "number", "boolean", "null"}:
                continue
            field = prefix[len(base):]
            if field.startswith("source."):
                current_point["source"][field.removeprefix("source.")] = value
            elif "." not in field:
                current_point[field] = value

    inserted += _insert_batch(conn, batch)
    return seen, inserted, dict(metric_counts)


def is_shortcut_export(path: Path) -> bool:
    return path.name.lower().startswith(SHORTCUT_FILE_PREFIX)


def _shortcut_number(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = "".join(str(value).split()).replace(" ", "")
    if "," in text and "." in text:
        # Whichever separator comes last is the decimal one.
        text = text.replace(",", "") if text.rfind(".") > text.rfind(",") else text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    digits = []
    for char in text:
        if char.isdigit() or char in ".-+":
            digits.append(char)
        elif digits:
            break
    try:
        return float("".join(digits))
    except ValueError:
        return None


def _shortcut_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)))
        except ZoneInfoNotFoundError:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _utc_timestamp(value: datetime) -> str:
    # Same textual form Health Data Export uses, so both sources compare equal.
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _shortcut_sleep_stage(value) -> Optional[str]:
    number = _shortcut_number(value)
    if number is not None and int(number) in SLEEP_STAGE_BY_VALUE:
        return SLEEP_STAGE_BY_VALUE[int(number)]
    text = str(value or "").strip().lower()
    for needle, stage in SHORTCUT_SLEEP_LABELS:
        if needle in text:
            return stage
    return None


def _shortcut_source(conn: sqlite3.Connection, name: Optional[str], cache: dict) -> dict:
    # Shortcuts only exposes the source's display name. Reuse the bundle id that
    # Health Data Export recorded for that name so sleep stays one nightly source.
    if not name:
        return {}
    if name not in cache:
        row = conn.execute(
            """
            SELECT source_bundle, source_device FROM health_metric_samples
            WHERE source_name = ? AND COALESCE(source_bundle, '') != '' AND source_bundle != ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (name, SHORTCUT_DAILY_SOURCE_BUNDLE),
        ).fetchone()
        cache[name] = {
            "name": name,
            "bundle_identifier": row["source_bundle"] if row else None,
            "device": row["source_device"] if row else None,
        }
    return cache[name]


def _sample_exists(conn: sqlite3.Connection, metric: str, timestamp: str, category_label: Optional[str]) -> bool:
    return conn.execute(
        """
        SELECT 1 FROM health_metric_samples
        WHERE metric = ? AND timestamp = ? AND COALESCE(category_label, '') = ?
        LIMIT 1
        """,
        (metric, timestamp, category_label or ""),
    ).fetchone() is not None


def _import_shortcut_payload(conn: sqlite3.Connection, payload: dict, import_id: int) -> tuple[int, int, dict]:
    if not isinstance(payload, dict):
        raise ValueError("Shortcut export must be a JSON object")
    seen = 0
    inserted = 0
    metric_counts = defaultdict(int)
    unrecognized_sleep = set()
    source_cache = {}
    raw_rows = []
    daily_totals = defaultdict(float)
    daily_bounds = {}

    for metric in TARGET_LABELS:
        points = payload.get(metric)
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            seen += 1
            start = _shortcut_datetime(point.get("start") or point.get("date"))
            end = _shortcut_datetime(point.get("end")) or start
            if start is None:
                continue

            if metric == "sleep":
                stage = _shortcut_sleep_stage(point.get("value"))
                if stage is None:
                    unrecognized_sleep.add(str(point.get("value")))
                    continue
                value = float(SLEEP_VALUE_BY_STAGE[stage])
                unit = "seconds"
                duration_seconds = max(0.0, (end - start).total_seconds())
                date = _sleep_date(_utc_timestamp(end))
            else:
                value = _shortcut_number(point.get("value"))
                if value is None:
                    continue
                stage = None
                duration_seconds = None
                raw_unit = str(point.get("unit") or "").strip().lower()
                if metric == "walking_running_distance" and raw_unit == "m":
                    value /= 1000.0
                elif metric == "weight" and raw_unit in {"lb", "lbs"}:
                    value *= 0.45359237
                unit = SHORTCUT_UNITS.get(metric)
                # Take the calendar day as written by the phone, not a UTC conversion.
                date = start.date().isoformat() if metric in SHORTCUT_DAILY_METRICS else _local_date(_utc_timestamp(start))

            if metric in SHORTCUT_DAILY_METRICS:
                daily_totals[(metric, date)] += value
                daily_bounds.setdefault((metric, date), (start, end))
                metric_counts[metric] += 1
                continue

            timestamp = _utc_timestamp(start)
            if _sample_exists(conn, metric, timestamp, stage):
                continue
            source = _shortcut_source(conn, point.get("source"), source_cache)
            end_timestamp = _utc_timestamp(end)
            raw_rows.append((
                _sample_key(metric, timestamp, end_timestamp, value, unit, stage, source),
                metric, timestamp, end_timestamp, date, value, unit, stage, duration_seconds,
                source.get("name"), source.get("bundle_identifier"), source.get("device"), import_id,
            ))
            metric_counts[metric] += 1

    inserted += _insert_batch(conn, raw_rows)

    # A daily total is re-sent (and grows) on every run, so it replaces the
    # previous total for that day instead of accumulating.
    for (metric, date), total in daily_totals.items():
        start, end = daily_bounds[(metric, date)]
        key = hashlib.sha256(f"shortcut-daily|{metric}|{date}".encode("utf-8")).hexdigest()
        before = conn.total_changes
        conn.execute(
            """
            INSERT INTO health_metric_samples
                (sample_key, metric, timestamp, end_timestamp, date, value, unit, category_label,
                 duration_seconds, source_name, source_bundle, source_device, import_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL, ?)
            ON CONFLICT(sample_key) DO UPDATE SET
                timestamp = excluded.timestamp, end_timestamp = excluded.end_timestamp,
                value = excluded.value, import_id = excluded.import_id
            WHERE health_metric_samples.value != excluded.value
            """,
            (key, metric, _utc_timestamp(start), _utc_timestamp(end), date, total, SHORTCUT_UNITS[metric],
             SHORTCUT_DAILY_SOURCE_NAME, SHORTCUT_DAILY_SOURCE_BUNDLE, import_id),
        )
        inserted += conn.total_changes - before

    extra = {"unrecognized_sleep_labels": sorted(unrecognized_sleep)} if unrecognized_sleep else {}
    return seen, inserted, {**dict(metric_counts), **extra}


def apply_health_data_import(conn: sqlite3.Connection) -> dict:
    preview = preview_health_data_import(conn)
    if not preview["configured"]:
        raise HTTPException(status_code=400, detail=f"Health Data Export directory is unavailable: {preview['directory']}")

    applied = {"files_imported": 0, "files_skipped": 0, "samples_seen": 0, "samples_inserted": 0, "errors": []}
    directory = health_data_directory()
    for item in preview["items"]:
        if item["action"] == "already_processed":
            applied["files_skipped"] += 1
            continue
        path = directory / item["file_name"]
        try:
            shortcut_payload = None
            if is_shortcut_export(path):
                raw = path.read_bytes()
                shortcut_payload = json.loads(raw)
                exported_at = shortcut_payload.get("exported_at") if isinstance(shortcut_payload, dict) else None
                metadata = {
                    "file_hash": hashlib.sha256(raw).hexdigest(),
                    "export_date": str(exported_at) if exported_at else None,
                    "metric_names": {},
                    "category_metric_names": {},
                    "format": "shortcut",
                }
            else:
                metadata = _scan_metadata(path)
            duplicate = conn.execute(
                "SELECT * FROM health_data_imports WHERE file_hash = ? AND status = 'imported'",
                (metadata["file_hash"],),
            ).fetchone()
            if duplicate and int(duplicate["import_version"] or 1) >= CURRENT_IMPORT_VERSION:
                applied["files_skipped"] += 1
                continue
            size, modified_ns = _file_signature(path)
            metadata_payload = {
                "format": metadata.get("format", "health_data_export"),
                "metric_names": metadata["metric_names"],
                "category_metric_names": metadata["category_metric_names"],
            }
            if duplicate:
                import_id = duplicate["id"]
                conn.execute(
                    """
                    UPDATE health_data_imports
                    SET status = 'processing', file_name = ?, file_size = ?, file_modified_ns = ?,
                        export_date = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (path.name, size, modified_ns, metadata["export_date"], json.dumps(metadata_payload), import_id),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO health_data_imports
                        (file_name, file_hash, file_size, file_modified_ns, export_date, status, import_version, metadata_json)
                    VALUES (?, ?, ?, ?, ?, 'processing', ?, ?)
                    """,
                    (path.name, metadata["file_hash"], size, modified_ns, metadata["export_date"], CURRENT_IMPORT_VERSION, json.dumps(metadata_payload)),
                )
                import_id = cursor.lastrowid
            if shortcut_payload is not None:
                seen, inserted, metric_counts = _import_shortcut_payload(conn, shortcut_payload, import_id)
            else:
                seen, inserted, metric_counts = _import_selected_metrics(
                    conn, path, import_id, metadata["metric_names"], metadata["category_metric_names"]
                )
            conn.execute(
                """
                UPDATE health_data_imports
                SET status = 'imported', samples_seen = ?, samples_inserted = ?, import_version = ?,
                    metadata_json = ?, imported_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (seen, inserted, CURRENT_IMPORT_VERSION, json.dumps({**metadata_payload, "target_counts": metric_counts}), import_id),
            )
            conn.commit()
            applied["files_imported"] += 1
            applied["samples_seen"] += seen
            applied["samples_inserted"] += inserted
        except (OSError, ValueError, ijson.JSONError, sqlite3.Error) as exc:
            conn.rollback()
            applied["errors"].append({"file_name": path.name, "reason": str(exc)})

    return {**preview_health_data_import(conn), "applied": applied}


def get_health_metric_history(conn: sqlite3.Connection, metric: str, days: int = 90) -> list[dict]:
    if metric == "sleep":
        return get_sleep_history(conn, days)
    safe_days = max(7, min(days, 730))
    rows = conn.execute(
        """
        SELECT DISTINCT date, value, unit, timestamp, end_timestamp, source_name, source_bundle
        FROM health_metric_samples
        WHERE metric = ? AND date >= date('now', ?)
        ORDER BY date DESC, timestamp DESC
        """,
        (metric, f"-{safe_days - 1} days"),
    ).fetchall()
    by_date = defaultdict(list)
    for row in rows:
        by_date[row["date"]].append(row)

    history = []
    for date in sorted(by_date, reverse=True):
        samples = by_date[date]
        # A Shortcut daily total is HealthKit's de-duplicated sum for the day, so
        # it supersedes any Health Data Export buckets for the same date.
        daily_totals = [row for row in samples if row["source_bundle"] == SHORTCUT_DAILY_SOURCE_BUNDLE]
        if daily_totals:
            samples = daily_totals
        values = [float(row["value"]) for row in samples]
        if metric == "weight":
            value = values[0]
        elif metric in {"steps", "walking_running_distance", "flights_climbed"}:
            value = sum(values)
        else:
            value = sum(values) / len(values)
        history.append({
            "date": date,
            "value": round(value) if metric in {"steps", "flights_climbed"} else round(value, 2 if metric == "walking_running_distance" else 1),
            "unit": samples[0]["unit"],
            "sample_count": len(samples),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
        })
    return history


def get_sleep_history(conn: sqlite3.Connection, days: int = 90) -> list[dict]:
    safe_days = max(7, min(days, 730))
    rows = conn.execute(
        """
        SELECT DISTINCT date, timestamp, end_timestamp, category_label, duration_seconds, source_name, source_bundle
        FROM health_metric_samples
        WHERE metric = 'sleep' AND date >= date('now', ?)
          AND duration_seconds IS NOT NULL AND duration_seconds > 0
        ORDER BY date DESC, timestamp ASC
        """,
        (f"-{safe_days - 1} days",),
    ).fetchall()
    by_date_source = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for row in rows:
        source_key = row["source_bundle"] or row["source_name"] or "unknown"
        by_date_source[row["date"]][source_key][row["category_label"] or "unknown"] += float(row["duration_seconds"] or 0)

    asleep_stages = {"asleep", "asleep_unspecified", "core", "deep", "rem"}
    detailed_stages = {"core", "deep", "rem"}
    history = []
    for date in sorted(by_date_source, reverse=True):
        candidates = []
        for stages in by_date_source[date].values():
            asleep_seconds = sum(stages.get(stage, 0) for stage in asleep_stages)
            detailed_seconds = sum(stages.get(stage, 0) for stage in detailed_stages)
            candidates.append((1 if detailed_seconds > 0 else 0, asleep_seconds, stages))
        _, total_seconds, stages = max(candidates, key=lambda item: (item[0], item[1]))
        if total_seconds <= 0:
            continue
        stage_hours = {
            stage: round(stages.get(stage, 0) / 3600.0, 2)
            for stage in ("core", "deep", "rem", "awake")
        }
        history.append({
            "date": date,
            "value": round(total_seconds / 3600.0, 2),
            "unit": "h",
            "sample_count": sum(1 for row in rows if row["date"] == date),
            "stages": stage_hours,
            "awake_minutes": round(stages.get("awake", 0) / 60.0),
        })
    return history


def get_health_summary(conn: sqlite3.Connection, days: int = 90) -> dict:
    metrics = {}
    for metric, label in TARGET_LABELS.items():
        history = get_health_metric_history(conn, metric, days)
        metrics[metric] = {
            "label": label,
            "available": bool(history),
            "latest": history[0] if history else None,
            "history": history,
        }
    last_import = conn.execute(
        "SELECT file_name, export_date, samples_inserted, imported_at FROM health_data_imports WHERE status = 'imported' ORDER BY imported_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return {"metrics": metrics, "last_import": dict(last_import) if last_import else None}
