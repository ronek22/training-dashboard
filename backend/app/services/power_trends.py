"""Deterministic cycling power efforts derived from cached activity streams.

This module intentionally does not use the activity summary's average power or
the ride name to decide whether power was measured.  The Strava activity
detail's ``device_watts`` flag is the source of truth for that decision.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional


POWER_EFFORT_DURATIONS = (15, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 2700, 3600)
POWER_EFFORT_LABELS = {
    15: "15 sec",
    30: "30 sec",
    60: "1 min",
    120: "2 min",
    180: "3 min",
    300: "5 min",
    600: "10 min",
    900: "15 min",
    1200: "20 min",
    1800: "30 min",
    2700: "45 min",
    3600: "60 min",
}
POWER_SKILL_LEVEL_NAMES = {1: "Aspiring", 2: "Intermediate", 3: "Athletic", 4: "Sport", 5: "Elite", 6: "Semi-Pro", 7: "National Star", 8: "World Class"}
# Transcribed from the supplied Strava benchmark panels (men, age 24–29,
# 75 kg). Strava adjusts these tables for the athlete profile; this profile is
# explicit so the UI never presents them as universal thresholds.
POWER_SKILL_THRESHOLDS = {
    15: (358, 536, 611, 659, 735, 840, 1024, 1148), 30: (312, 468, 533, 575, 641, 733, 894, 1001), 60: (214, 320, 365, 394, 439, 502, 612, 686),
    120: (192, 288, 329, 354, 395, 452, 550, 617), 180: (180, 269, 307, 331, 369, 422, 515, 576), 300: (159, 238, 271, 292, 326, 372, 454, 508),
    600: (150, 225, 256, 277, 308, 352, 430, 481), 900: (145, 217, 248, 267, 298, 341, 415, 465), 1200: (143, 214, 244, 263, 294, 336, 409, 458),
    1800: (135, 202, 230, 249, 277, 317, 386, 432), 2700: (125, 187, 213, 229, 256, 292, 356, 399), 3600: (115, 173, 197, 212, 237, 271, 330, 369),
}
POWER_SKILL_PROFILE = "Men · age 24–29 · 75 kg"
MAX_STREAM_GAP_SECONDS = 2.0
_MONTH_RE = re.compile(r"^\d{4}-\d{2}")
_POWER_CACHE_KEY = "all_time"
_POWER_CACHE_VERSION = "power-trends-v2"
_POWER_CACHE_TABLE = "cycling_power_trends_cache"
_POWER_REVISION_TABLE = "cycling_power_trends_revision"


def _power_trends_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _ensure_power_trends_cache_schema(conn: sqlite3.Connection) -> None:
    """Create the small persistent cache metadata and invalidation hooks.

    The revision is bumped by SQLite triggers, so checking whether a cached
    profile is current never requires reading the (potentially very large)
    stream JSON blobs.  These objects are created lazily to keep this service
    usable with the compact in-memory schemas used by unit tests and older
    local databases.
    """
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_POWER_REVISION_TABLE} (
            cache_key TEXT PRIMARY KEY,
            revision INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        f"""
        INSERT OR IGNORE INTO {_POWER_REVISION_TABLE} (cache_key, revision)
        VALUES (?, 0)
        """,
        (_POWER_CACHE_KEY,),
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_POWER_CACHE_TABLE} (
            cache_key TEXT PRIMARY KEY,
            revision INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            result_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    trigger_tables = ("activities", "activity_details", "app_settings")
    for table_name in trigger_tables:
        if not _power_trends_table_exists(conn, table_name):
            continue
        safe_table_name = table_name.replace("'", "''")
        for operation, suffix in (("INSERT", "ai"), ("UPDATE", "au"), ("DELETE", "ad")):
            if table_name == "activities":
                condition = {
                    "INSERT": "NEW.type IN ('Ride', 'VirtualRide')",
                    "UPDATE": "OLD.type IN ('Ride', 'VirtualRide') OR NEW.type IN ('Ride', 'VirtualRide')",
                    "DELETE": "OLD.type IN ('Ride', 'VirtualRide')",
                }[operation]
            elif table_name == "activity_details":
                activity_ref = "NEW.activity_id, OLD.activity_id" if operation == "UPDATE" else ("NEW.activity_id" if operation == "INSERT" else "OLD.activity_id")
                condition = (
                    "EXISTS (SELECT 1 FROM activities AS cycling_activity "
                    f"WHERE cycling_activity.id IN ({activity_ref}) "
                    "AND cycling_activity.type IN ('Ride', 'VirtualRide'))"
                )
            else:
                condition = "NEW.key = 'performance_settings'" if operation != "DELETE" else "OLD.key = 'performance_settings'"
            conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS cycling_power_trends_{table_name}_{suffix}
                AFTER {operation} ON {safe_table_name}
                WHEN {condition}
                BEGIN
                    UPDATE {_POWER_REVISION_TABLE}
                    SET revision = revision + 1
                    WHERE cache_key = '{_POWER_CACHE_KEY}';
                END
                """
            )


def _power_trends_revision(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        f"SELECT revision FROM {_POWER_REVISION_TABLE} WHERE cache_key = ?",
        (_POWER_CACHE_KEY,),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _cached_power_trends_result(
    conn: sqlite3.Connection,
    revision: int,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        f"""
        SELECT result_json
        FROM {_POWER_CACHE_TABLE}
        WHERE cache_key = ? AND revision = ? AND algorithm_version = ?
        """,
        (_POWER_CACHE_KEY, revision, _POWER_CACHE_VERSION),
    ).fetchone()
    if not row:
        return None
    try:
        result = json.loads(row[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return result if isinstance(result, dict) else None


def _store_power_trends_result(
    conn: sqlite3.Connection,
    revision: int,
    result: dict[str, Any],
) -> None:
    conn.execute(
        f"""
        INSERT INTO {_POWER_CACHE_TABLE}
            (cache_key, revision, algorithm_version, result_json, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(cache_key) DO UPDATE SET
            revision = excluded.revision,
            algorithm_version = excluded.algorithm_version,
            result_json = excluded.result_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (_POWER_CACHE_KEY, revision, _POWER_CACHE_VERSION, json.dumps(result, separators=(",", ":"))),
    )


@dataclass(frozen=True)
class _Segment:
    """A valid, time-weighted stream interval.

    A stream sample is held until the next sample timestamp.  This is a
    conservative interpretation of an instantaneous power stream: no power is
    invented after the last sample, and each interval is weighted by its real
    elapsed duration.
    """

    start: float
    end: float
    watts: float
    hr: Optional[float]
    hr_complete: bool


def _stream_values(streams: Any, key: str) -> list[Any]:
    if not isinstance(streams, dict):
        return []
    value = streams.get(key)
    if isinstance(value, dict):
        value = value.get("data")
    if not isinstance(value, (list, tuple)):
        return []
    return list(value)


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _valid_power(value: Any) -> Optional[float]:
    number = _finite_number(value)
    if number is None or number < 0:
        return None
    return number


def _valid_hr(value: Any) -> Optional[float]:
    number = _finite_number(value)
    if number is None or number <= 0:
        return None
    return number


def _decode_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _confirmed_power_meter(
    detail_json: Any,
    *,
    activity_type: str,
    source_status: Any,
    streams_json: Any,
) -> bool:
    detail = _decode_json(detail_json)
    # Strava returns a JSON boolean.  Keep this strict so values such as a
    # summary average, the string "true", or an integer cannot certify a
    # meter accidentally.
    if isinstance(detail, dict) and detail.get("device_watts") is True:
        return True

    # Stream backfill intentionally stores only the streams, not the activity
    # detail payload. Strava's VirtualRide stream is still a trainer-platform
    # ride, and a real watts stream is the measured signal we need. Keep this
    # exception limited to VirtualRide + the explicit backfill provenance so a
    # normal outdoor Ride with an estimated watts field cannot qualify.
    if activity_type == "VirtualRide" and source_status == "streams_backfill":
        streams = _decode_json(streams_json)
        watts = _stream_values(streams, "watts")
        return len(watts) >= 2 and any(_valid_power(value) is not None for value in watts)
    return False


def _build_segments(streams_json: Any) -> list[list[_Segment]]:
    """Return contiguous valid stream runs.

    A run ends at a non-monotonic timestamp, an invalid power sample, or a
    gap over two seconds.  Splitting here prevents a later valid interval from
    being stitched across missing data.
    """

    streams = _decode_json(streams_json)
    times = _stream_values(streams, "time")
    watts = _stream_values(streams, "watts")
    heart_rates = _stream_values(streams, "heartrate")
    if len(times) < 2 or len(watts) < 2:
        return []

    sample_count = min(len(times), len(watts))
    runs: list[list[_Segment]] = []
    current: list[_Segment] = []

    def finish_run() -> None:
        nonlocal current
        if current:
            runs.append(current)
            current = []

    for index in range(sample_count - 1):
        start = _finite_number(times[index])
        end = _finite_number(times[index + 1])
        power = _valid_power(watts[index])
        next_power = _valid_power(watts[index + 1])
        if start is None or end is None or power is None or next_power is None:
            finish_run()
            continue

        elapsed = end - start
        if elapsed <= 0 or elapsed > MAX_STREAM_GAP_SECONDS:
            finish_run()
            continue

        # We require the stream value at both ends of every interval.  That
        # keeps an invalid/missing sample from being hidden at a boundary,
        # while zero watts remains a valid measured value.
        hr = _valid_hr(heart_rates[index]) if index < len(heart_rates) else None
        next_hr = _valid_hr(heart_rates[index + 1]) if index + 1 < len(heart_rates) else None
        current.append(
            _Segment(
                start=start,
                end=end,
                watts=power,
                hr=hr,
                hr_complete=hr is not None and next_hr is not None,
            )
        )

    finish_run()
    return runs


def _prefix_areas(run: list[_Segment], key: str) -> list[float]:
    prefix = [0.0]
    total = 0.0
    for segment in run:
        value = getattr(segment, key)
        total += float(value) * (segment.end - segment.start)
        prefix.append(total)
    return prefix


def _segment_index_for_start(starts: list[float], point: float) -> int:
    return bisect_right(starts, point + 1e-9) - 1


def _segment_index_for_end(starts: list[float], point: float) -> int:
    # At an exact segment boundary, the segment before the boundary is the
    # final one touched by a half-open [start, end] window.
    return bisect_left(starts, point - 1e-9) - 1


def _cumulative_area(
    run: list[_Segment],
    starts: list[float],
    prefix: list[float],
    point: float,
    key: str,
) -> float:
    index = _segment_index_for_start(starts, point)
    if index < 0:
        return 0.0
    index = min(index, len(run) - 1)
    return prefix[index] + (point - run[index].start) * float(getattr(run[index], key))


def _window_area(
    run: list[_Segment],
    starts: list[float],
    prefix: list[float],
    start: float,
    end: float,
    key: str,
) -> float:
    return _cumulative_area(run, starts, prefix, end, key) - _cumulative_area(run, starts, prefix, start, key)


def _best_effort_for_duration(run: list[_Segment], duration: int) -> Optional[dict[str, Any]]:
    if not run:
        return None
    if run[-1].end - run[0].start < duration:
        return None

    starts = [segment.start for segment in run]
    power_prefix = _prefix_areas(run, "watts")
    hr_prefix = [0.0]
    hr_incomplete_prefix = [0]
    for segment in run:
        hr_prefix.append(hr_prefix[-1] + (segment.hr or 0.0) * (segment.end - segment.start))
        hr_incomplete_prefix.append(hr_incomplete_prefix[-1] + (0 if segment.hr_complete else 1))

    # For a piecewise-constant stream, an optimum can occur when either the
    # window starts at a sample boundary or its end lands on one.  Evaluating
    # both sets avoids missing the best interval in irregularly sampled data
    # (for example, [1, 6] can beat [0, 5]).
    candidate_starts = {segment.start for segment in run}
    latest_start = run[-1].end - duration
    for segment in run:
        shifted_start = segment.end - duration
        if run[0].start - 1e-9 <= shifted_start <= latest_start + 1e-9:
            candidate_starts.add(shifted_start)

    best: Optional[dict[str, Any]] = None

    for start in sorted(candidate_starts):
        target_end = start + duration
        if target_end > run[-1].end + 1e-9:
            continue

        start_index = _segment_index_for_start(starts, start)
        end_index = _segment_index_for_end(starts, target_end)
        if start_index < 0 or end_index < start_index:
            continue

        power_area = _window_area(run, starts, power_prefix, start, target_end, "watts")
        average_watts = power_area / duration
        average_hr: Optional[float] = None
        hr_complete = (
            hr_incomplete_prefix[end_index + 1] - hr_incomplete_prefix[start_index] == 0
        )
        if hr_complete:
            hr_area = _window_area(run, starts, hr_prefix, start, target_end, "hr")
            average_hr = hr_area / duration

        candidate = {
            "watts": average_watts,
            "avg_hr": average_hr,
            "start_seconds": start,
            "end_seconds": target_end,
        }
        # Ties retain the earliest interval, making results stable for flat
        # streams and avoiding churn when a ride is re-imported.
        if best is None or average_watts > best["watts"] + 1e-9:
            best = candidate

    return best


def _best_effort_from_runs(runs: list[list[_Segment]], duration: int) -> Optional[dict[str, Any]]:
    best: Optional[dict[str, Any]] = None
    for run in runs:
        candidate = _best_effort_for_duration(run, duration)
        if candidate is None:
            continue
        if best is None or candidate["watts"] > best["watts"] + 1e-9:
            best = candidate
    return best


def _normalise_output_number(value: float) -> int | float:
    rounded = round(float(value), 3)
    return int(rounded) if rounded.is_integer() else rounded


def _month_for_date(value: Any) -> Optional[str]:
    date = str(value or "")
    match = _MONTH_RE.match(date)
    return match.group(0) if match else None


def _effort_output(
    activity: sqlite3.Row,
    duration: int,
    effort: dict[str, Any],
) -> dict[str, Any]:
    average_hr = effort.get("avg_hr")
    thresholds = POWER_SKILL_THRESHOLDS.get(duration, ())
    level = max((index + 1 for index, threshold in enumerate(thresholds) if effort["watts"] >= threshold), default=0)
    next_level = level + 1 if level < len(thresholds) else None
    next_threshold = thresholds[level] if next_level is not None else None
    watts_to_next = round(float(next_threshold) - float(effort["watts"]), 1) if next_threshold is not None else None
    if not thresholds or level == 0:
        level_percent = 0.0
    elif next_threshold is None:
        level_percent = 100.0
    else:
        lower = float(thresholds[level - 1])
        within_level = min(1.0, max(0.0, (float(effort["watts"]) - lower) / (float(next_threshold) - lower)))
        level_percent = round(((level - 1 + within_level) / len(thresholds)) * 100, 1)
    return {
        "duration_seconds": duration,
        "watts": round(float(effort["watts"]), 1),
        "avg_hr": round(float(average_hr), 1) if average_hr is not None else None,
        "start_seconds": _normalise_output_number(effort["start_seconds"]),
        "end_seconds": _normalise_output_number(effort["end_seconds"]),
        "activity_id": activity["id"],
        "activity_name": activity["name"],
        "date": activity["date"],
        "level": level or None,
        "level_name": POWER_SKILL_LEVEL_NAMES.get(level),
        "next_level": next_level,
        "next_level_name": POWER_SKILL_LEVEL_NAMES.get(next_level) if next_level is not None else None,
        "watts_to_next": watts_to_next,
        "level_percent": level_percent,
        "level_thresholds": list(thresholds),
    }


def _prefer_effort(candidate: dict[str, Any], current: Optional[dict[str, Any]]) -> bool:
    if current is None:
        return True
    candidate_watts = float(candidate["watts"])
    current_watts = float(current["watts"])
    if candidate_watts > current_watts + 1e-9:
        return True
    if abs(candidate_watts - current_watts) > 1e-9:
        return False
    # For equal power, expose the more recent ride as the current record.
    return (str(candidate.get("date") or ""), str(candidate.get("activity_id") or "")) > (
        str(current.get("date") or ""),
        str(current.get("activity_id") or ""),
    )


def _category_level(records: dict[int, dict[str, Any]], durations: tuple[int, ...]) -> Optional[dict[str, Any]]:
    levels = [records[duration]["level"] for duration in durations if duration in records and records[duration].get("level") is not None]
    if not levels:
        return None
    level = min(levels)
    # A category advances only when every interval in it reaches the next
    # benchmark. Use the same target level for each interval, then surface the
    # largest remaining gap and the duration that limits progression.
    target_gaps = []
    for duration in durations:
        if duration not in records:
            continue
        thresholds = POWER_SKILL_THRESHOLDS.get(duration, ())
        if level >= len(thresholds):
            continue
        gap = max(0.0, float(thresholds[level]) - float(records[duration]["watts"]))
        target_gaps.append((gap, duration))
    next_gap, limiting_duration = max(target_gaps, default=(None, None))
    return {
        "level": level,
        "name": POWER_SKILL_LEVEL_NAMES[level],
        "intervals_available": len(levels),
        "intervals_total": len(durations),
        "watts_to_next": round(next_gap, 1) if next_gap is not None else None,
        "next_level": level + 1 if next_gap is not None else None,
        "next_level_name": POWER_SKILL_LEVEL_NAMES.get(level + 1) if next_gap is not None else None,
        "limiting_duration_seconds": limiting_duration,
    }


def _build_cycling_power_trends_data(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build all-time measured cycling power efforts from local cache rows."""

    rows = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name, d.detail_json, d.streams_json, d.source_status
        FROM activities AS a
        LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ('Ride', 'VirtualRide')
        ORDER BY a.date ASC, a.id ASC
        """
    ).fetchall()

    cycling_activities = len(rows)
    measured_power_activities = 0
    analyzed_activities = 0
    missing_streams = 0
    unverified_activities = 0
    efforts: list[dict[str, Any]] = []
    records_by_duration: dict[int, dict[str, Any]] = {}
    monthly_by_month: dict[str, dict[int, dict[str, Any]]] = {}

    for row in rows:
        if not _confirmed_power_meter(
            row["detail_json"],
            activity_type=row["type"],
            source_status=row["source_status"],
            streams_json=row["streams_json"],
        ):
            unverified_activities += 1
            continue

        measured_power_activities += 1
        runs = _build_segments(row["streams_json"])
        activity_efforts = 0
        for duration in POWER_EFFORT_DURATIONS:
            effort = _best_effort_from_runs(runs, duration)
            if effort is None:
                continue
            output = _effort_output(row, duration, effort)
            efforts.append(output)
            activity_efforts += 1
            if _prefer_effort(output, records_by_duration.get(duration)):
                records_by_duration[duration] = output

            month = _month_for_date(row["date"])
            if month:
                month_efforts = monthly_by_month.setdefault(month, {})
                if _prefer_effort(output, month_efforts.get(duration)):
                    month_efforts[duration] = output

        if activity_efforts:
            analyzed_activities += 1
        else:
            missing_streams += 1

    efforts.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("activity_id") or ""), item["duration_seconds"]))
    records = [records_by_duration[duration] for duration in POWER_EFFORT_DURATIONS if duration in records_by_duration]
    monthly = [
        {
            "month": month,
            "efforts": [month_efforts[duration] for duration in POWER_EFFORT_DURATIONS if duration in month_efforts],
        }
        for month, month_efforts in sorted(monthly_by_month.items())
    ]

    return {
        "durations": [
            {"seconds": duration, "label": POWER_EFFORT_LABELS[duration]}
            for duration in POWER_EFFORT_DURATIONS
        ],
        "records": records,
        "monthly": monthly,
        "efforts": efforts,
        "coverage": {
            "cycling_activities": cycling_activities,
            "measured_power_activities": measured_power_activities,
            "analyzed_activities": analyzed_activities,
            "missing_streams": missing_streams,
            "unverified_activities": unverified_activities,
        },
        "skill_profile": POWER_SKILL_PROFILE,
        "category_levels": {
            category: _category_level(records_by_duration, durations)
            for category, durations in {
                "Sprint": (15, 30, 60),
                "Attack": (120, 180, 300, 600),
                "Climb": (900, 1200, 1800, 2700, 3600),
            }.items()
        },
        "methodology": (
            "Ride activities require cached Strava activity detail with device_watts=true. "
            "VirtualRide activities from the explicit streams_backfill path qualify when "
            "they have a cached watts stream; Strava's VirtualRide source is the trainer "
            "platform record even when the backfill did not cache detail_json. Power streams "
            "are read from the local cache only. Each valid sample is held until the next "
            "timestamp and weighted by "
            "elapsed time; windows with missing or invalid power, non-monotonic timestamps, "
            "or gaps over 2 seconds are rejected. Zero watts is valid measured power. "
            "For a winning power window, average heart rate is shown only when every "
            "corresponding heart-rate sample is valid."
        ),
    }


def get_cycling_power_trends_data(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the cached profile, rebuilding it when source data changes.

    The cache is intentionally keyed by a database revision rather than by
    stream contents.  Activity/detail triggers increment that revision on
    cycling inserts, updates, and deletes, so a warm read does not deserialize
    every stream just to discover that nothing changed.
    """
    owns_transaction = not conn.in_transaction
    _ensure_power_trends_cache_schema(conn)
    if owns_transaction and conn.in_transaction:
        # Persist the lazy schema and trigger installation without committing
        # a transaction that the caller already had in progress.
        conn.commit()

    # A write can race the initial revision read. Recheck after a rebuild and
    # retry once so a profile produced during an import is never stored under
    # an older revision. A concurrent writer may still commit after the final
    # check; the next request will then miss the stale revision safely.
    for _ in range(2):
        revision = _power_trends_revision(conn)
        cached = _cached_power_trends_result(conn, revision)
        if cached is not None:
            return cached

        result = _build_cycling_power_trends_data(conn)
        if _power_trends_revision(conn) != revision:
            continue
        _store_power_trends_result(conn, revision, result)
        if owns_transaction:
            conn.commit()
        return result

    # Keep the response useful under a continuously changing import without
    # writing a result whose revision is already stale.
    return _build_cycling_power_trends_data(conn)


# The shorter name is useful for callers that use the ``build_*`` convention
# used by other deterministic services in this project.
build_cycling_power_trends = get_cycling_power_trends_data


def build_cycling_power_coaching_context(
    conn: sqlite3.Connection, *, include_thresholds: bool = True
) -> dict[str, Any]:
    """Expose the UI's measured efforts and their limits without inferring fitness."""
    profile = get_cycling_power_trends_data(conn)
    today = date.today()
    recent_start = (today - timedelta(days=89)).isoformat()
    recent_end = today.isoformat()
    recent_records: dict[int, dict[str, Any]] = {}
    by_duration: dict[int, list[dict[str, Any]]] = {}
    for effort in profile["efforts"]:
        duration = effort["duration_seconds"]
        by_duration.setdefault(duration, []).append(effort)
        if recent_start <= str(effort["date"])[:10] <= recent_end:
            if _prefer_effort(effort, recent_records.get(duration)):
                recent_records[duration] = effort

    # Reuse the exact record fields, omitting only repeated benchmark tables.
    def compact_record(effort: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in effort.items() if key != "level_thresholds"}

    duration_coverage = []
    for duration in profile["durations"]:
        efforts = by_duration.get(duration["seconds"], [])
        dates = sorted(str(effort["date"])[:10] for effort in efforts)
        duration_coverage.append({
            "duration_seconds": duration["seconds"],
            "recorded_efforts": len(efforts),
            "recent_recorded_efforts": sum(recent_start <= day <= recent_end for day in dates),
            "first_effort_date": dates[0] if dates else None,
            "latest_effort_date": dates[-1] if dates else None,
        })

    months = {month["month"]: month["efforts"] for month in profile["monthly"]}
    monthly_coverage = []
    recording_gaps: list[dict[str, str]] = []
    if months:
        first_month = min(months)
        last_month = max(months)
        cursor = date.fromisoformat(f"{first_month}-01")
        gap: dict[str, str] | None = None
        while cursor.isoformat()[:7] <= last_month:
            month = cursor.isoformat()[:7]
            recorded = {effort["duration_seconds"] for effort in months.get(month, [])}
            monthly_coverage.append({
                "month": month,
                "recorded_durations_seconds": sorted(recorded),
                "missing_durations_seconds": [
                    duration["seconds"] for duration in profile["durations"]
                    if duration["seconds"] not in recorded
                ],
            })
            if not recorded:
                if gap is None:
                    gap = {"first_month": month, "last_month": month}
                    recording_gaps.append(gap)
                else:
                    gap["last_month"] = month
            else:
                gap = None
            cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)

    benchmarks = {
        "profile": profile["skill_profile"],
        "source": "Fixed table transcribed from supplied Strava benchmark panels; not a live Strava ranking.",
        "automatically_personalized": False,
        "units": "absolute watts, not watts per kilogram",
        "level_names": {str(level): name for level, name in POWER_SKILL_LEVEL_NAMES.items()},
        "category_durations_seconds": {
            "Sprint": [d for d in POWER_EFFORT_DURATIONS if d <= 60],
            "Attack": [d for d in POWER_EFFORT_DURATIONS if 60 < d <= 600],
            "Climb": [d for d in POWER_EFFORT_DURATIONS if d > 600],
        },
        "scale": "level_percent is the API benchmark score on a 0–100 scale, not a population percentile. Below the first level is 0; the highest level is 100.",
        "category_rule": "Category level is the lowest non-null attained level among available records. Missing and below-first-level durations are excluded from that minimum; intervals_available counts ranked durations. Inspect individual records and coverage before interpreting a category.",
    }
    if include_thresholds:
        benchmarks["thresholds"] = [
            {"duration_seconds": seconds, "watts_by_level": list(POWER_SKILL_THRESHOLDS.get(seconds, ()))}
            for seconds in POWER_EFFORT_DURATIONS
        ]
    else:
        benchmarks["thresholds_tool"] = "get_cycling_power_profile"

    return {
        "status": "available" if profile["records"] else "no_measured_efforts",
        "as_of_date": recent_end,
        "record_scope": "All-time best recorded efforts in locally cached, eligible power streams.",
        "durations": profile["durations"],
        "records": [compact_record(effort) for effort in profile["records"]],
        "recent_window": {"start_date": recent_start, "end_date": recent_end, "days": 90},
        "recent_records": [compact_record(recent_records[seconds]) for seconds in sorted(recent_records)],
        "category_levels": profile["category_levels"],
        "benchmarks": benchmarks,
        "coverage": profile["coverage"],
        "duration_coverage": duration_coverage,
        "monthly_coverage": monthly_coverage,
        "recording_gaps": recording_gaps,
        "coverage_scope": "Monthly coverage spans the first through last recorded effort only. Gaps mean no eligible complete power effort, not no riding; the cause is unknown.",
        "methodology": profile["methodology"],
        "interpretation_limits": [
            "Best recorded efforts are not necessarily maximal tests. Lower long-duration scores can reflect a lack of hard sustained efforts rather than an endurance weakness.",
            "Outdoor rides without measured power do not contribute to this profile. Seasonal indoor-only recordings can omit substantial training; do not infer detraining from missing data.",
            "All-time records may come from different rides and seasons. Use their dates, recent records and effort counts before making claims about current ability or progress.",
            "Sprint, Attack and Climb are duration groups, not diagnoses or proof of climbing performance. Check whether the fixed benchmark profile fits the athlete.",
            "Heart rate comes from each ride's best power window, not a controlled test. Cooling, fatigue and heart-rate lag affect it; lower HR alone does not establish improved fitness.",
            "Treat a profile imbalance as a hypothesis. Consider goals, current plan, load and recovery, and ask about maximal-effort opportunities before recommending changes. Do not automatically modify the plan.",
        ],
    }
