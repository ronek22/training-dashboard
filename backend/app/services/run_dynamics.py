"""Apple Watch running dynamics from HealthFit FIT files.

HealthFit exports every Apple Watch run to iCloud as a FIT file that carries the
watch's running dynamics: cadence, step length, vertical oscillation, vertical
ratio, ground contact time and running power. Strava drops all of these, and the
HealthFit activity import keeps only heart rate, power, cadence, speed and
altitude streams. This module reads every running FIT file once, stores the
session averages, per-kilometre splits and best power for a few durations in
``run_dynamics`` (keyed by file name), and attaches the row to the matching run,
whichever source created it (usually Strava).

Files are matched like the HealthFit import does (start time, then same-day
duration, distance and heart rate). A file whose run is not imported yet is
stored unmatched and tried again on later scans for ``RETRY_UNMATCHED_DAYS``.
Scans are cheap after the first: known file names are skipped without opening.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import fitdecode

from .activity_sources import find_activity_match
from .healthfit import FILENAME_PATTERN, HEALTHFIT_SOURCE, healthfit_directory

PARSER_VERSION = 1
RETRY_UNMATCHED_DAYS = 21
POWER_DURATIONS = (60, 180, 300, 720, 1200, 1800, 3600)
SPLIT_METRICS = ("heart_rate", "cadence_spm", "stance_time_ms", "vertical_oscillation_cm", "step_length_m", "vertical_ratio_pct", "power_w")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS run_dynamics (
            file_name TEXT PRIMARY KEY,
            activity_id TEXT,
            date TEXT NOT NULL,
            started_at TEXT,
            indoor INTEGER NOT NULL DEFAULT 0,
            distance_km REAL,
            duration_min REAL,
            avg_hr REAL,
            cadence_spm REAL,
            step_length_m REAL,
            vertical_oscillation_cm REAL,
            vertical_ratio_pct REAL,
            stance_time_ms REAL,
            avg_power_w REAL,
            max_power_w REAL,
            splits_json TEXT,
            power_bests_json TEXT,
            parser_version INTEGER NOT NULL,
            scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_run_dynamics_activity ON run_dynamics(activity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_run_dynamics_date ON run_dynamics(date)")


def is_running_file(name: str) -> bool:
    match = FILENAME_PATTERN.match(name)
    title = (match.group(3) if match else name).lower()
    return "running" in title or title.endswith(" run")


def _num(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _cadence_spm(cadence: Any, fraction: Any) -> Optional[float]:
    """FIT running cadence counts one leg (strides per minute); steps per minute is double."""
    whole = _num(cadence)
    if not whole:
        return None
    return round((whole + (_num(fraction) or 0.0)) * 2, 1)


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _record_values(row: dict) -> dict[str, Optional[float]]:
    vo = _num(row.get("vertical_oscillation"))
    step = _num(row.get("step_length"))
    return {
        "heart_rate": _num(row.get("heart_rate")),
        "cadence_spm": _cadence_spm(row.get("cadence"), row.get("fractional_cadence")),
        "stance_time_ms": _num(row.get("stance_time")),
        "vertical_oscillation_cm": vo / 10 if vo else None,
        "step_length_m": step / 1000 if step else None,
        "vertical_ratio_pct": _num(row.get("vertical_ratio")),
        "power_w": _num(row.get("power")),
    }


def km_splits(records: list[dict]) -> list[dict]:
    """Average of each dynamics metric per completed kilometre."""
    splits: list[dict] = []
    bucket: list[dict] = []
    km = 1
    start_time = None
    for row in records:
        distance = _num(row.get("distance"))
        stamp = row.get("timestamp")
        if distance is None or not isinstance(stamp, datetime):
            continue
        if start_time is None:
            start_time = stamp
        bucket.append(row)
        if distance >= km * 1000:
            values = [_record_values(item) for item in bucket]
            split = {"km": km, "seconds": round((stamp - start_time).total_seconds())}
            for key in SPLIT_METRICS:
                avg = _mean([value[key] for value in values if value[key]])
                split[key] = round(avg, 3) if avg is not None else None
            splits.append(split)
            km += 1
            bucket = []
            start_time = stamp
    return splits


def power_bests(records: list[dict], durations: tuple[int, ...] = POWER_DURATIONS) -> dict[str, float]:
    """Best average power for each duration, from a 1 Hz forward-filled series."""
    points = [
        (row["timestamp"], _num(row.get("power")))
        for row in records
        if isinstance(row.get("timestamp"), datetime) and _num(row.get("power")) is not None
    ]
    if len(points) < 2:
        return {}
    start = points[0][0]
    total = int((points[-1][0] - start).total_seconds())
    if total <= 0:
        return {}
    series = [0.0] * (total + 1)
    index = 0
    current = points[0][1] or 0.0
    for second in range(total + 1):
        while index < len(points) and (points[index][0] - start).total_seconds() <= second:
            current = points[index][1] or 0.0
            index += 1
        series[second] = current
    prefix = [0.0]
    for value in series:
        prefix.append(prefix[-1] + value)
    bests: dict[str, float] = {}
    for duration in durations:
        if duration > len(series):
            continue
        best = max(prefix[end] - prefix[end - duration] for end in range(duration, len(series) + 1))
        bests[str(duration)] = round(best / duration, 1)
    return bests


def parse_run_file(path: Path) -> dict:
    session: dict = {}
    records: list[dict] = []
    try:
        with fitdecode.FitReader(path) as fit:
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "session" and not session:
                    session = {field.name: field.value for field in frame.fields}
                elif frame.name == "record":
                    records.append({field.name: field.value for field in frame.fields})
    except (OSError, fitdecode.FitError) as exc:
        raise ValueError(f"Could not decode {path.name}: {exc}") from exc
    if not session:
        raise ValueError(f"No FIT session found in {path.name}")
    name_match = FILENAME_PATTERN.match(path.name)
    start = session.get("start_time")
    if isinstance(start, datetime) and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    day = name_match.group(1) if name_match else (start.date().isoformat() if isinstance(start, datetime) else None)
    if not day:
        raise ValueError(f"No workout date found in {path.name}")
    distance = _num(session.get("total_distance"))
    duration = _num(session.get("total_timer_time")) or _num(session.get("total_elapsed_time"))
    vo = _num(session.get("avg_vertical_oscillation"))
    step = _num(session.get("avg_step_length"))
    title = (name_match.group(3) if name_match else path.stem).lower()
    has_gps = any(row.get("position_lat") is not None for row in records[:200])
    return {
        "file_name": path.name,
        "date": day,
        "started_at": start.isoformat() if isinstance(start, datetime) else None,
        "indoor": "indoor" in title or not has_gps,
        "distance_km": round(distance / 1000, 2) if distance else None,
        "duration_min": round(duration / 60, 1) if duration else None,
        "avg_hr": _num(session.get("avg_heart_rate")),
        "cadence_spm": _cadence_spm(session.get("avg_running_cadence") or session.get("avg_cadence"), session.get("avg_fractional_cadence")),
        "step_length_m": round(step / 1000, 3) if step else None,
        "vertical_oscillation_cm": round(vo / 10, 2) if vo else None,
        "vertical_ratio_pct": _num(session.get("avg_vertical_ratio")),
        "stance_time_ms": _num(session.get("avg_stance_time")),
        "avg_power_w": _num(session.get("avg_power")),
        "max_power_w": _num(session.get("max_power")),
        "splits": km_splits(records),
        "power_bests": power_bests(records),
    }


def _match_activity(conn: sqlite3.Connection, parsed: dict) -> Optional[str]:
    ref = conn.execute(
        "SELECT activity_id FROM activity_source_refs WHERE source = ? AND file_name = ? AND activity_id IS NOT NULL",
        (HEALTHFIT_SOURCE, parsed["file_name"]),
    ).fetchone()
    if ref:
        return ref["activity_id"]
    candidate = {
        "date": parsed["date"], "type": "Run", "started_at": parsed["started_at"],
        "duration_min": parsed["duration_min"], "distance_km": parsed["distance_km"], "avg_hr": parsed["avg_hr"],
    }
    match = find_activity_match(conn, candidate)
    return match["activity"]["id"] if match["status"] == "matched" else None


def _store(conn: sqlite3.Connection, parsed: dict, activity_id: Optional[str]) -> None:
    conn.execute(
        """
        INSERT INTO run_dynamics (
            file_name, activity_id, date, started_at, indoor, distance_km, duration_min, avg_hr,
            cadence_spm, step_length_m, vertical_oscillation_cm, vertical_ratio_pct, stance_time_ms,
            avg_power_w, max_power_w, splits_json, power_bests_json, parser_version, scanned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(file_name) DO UPDATE SET
            activity_id = excluded.activity_id, date = excluded.date, started_at = excluded.started_at,
            indoor = excluded.indoor, distance_km = excluded.distance_km, duration_min = excluded.duration_min,
            avg_hr = excluded.avg_hr, cadence_spm = excluded.cadence_spm, step_length_m = excluded.step_length_m,
            vertical_oscillation_cm = excluded.vertical_oscillation_cm, vertical_ratio_pct = excluded.vertical_ratio_pct,
            stance_time_ms = excluded.stance_time_ms, avg_power_w = excluded.avg_power_w, max_power_w = excluded.max_power_w,
            splits_json = excluded.splits_json, power_bests_json = excluded.power_bests_json,
            parser_version = excluded.parser_version, scanned_at = CURRENT_TIMESTAMP
        """,
        (
            parsed["file_name"], activity_id, parsed["date"], parsed["started_at"], int(parsed["indoor"]),
            parsed["distance_km"], parsed["duration_min"], parsed["avg_hr"], parsed["cadence_spm"],
            parsed["step_length_m"], parsed["vertical_oscillation_cm"], parsed["vertical_ratio_pct"],
            parsed["stance_time_ms"], parsed["avg_power_w"], parsed["max_power_w"],
            json.dumps(parsed["splits"], separators=(",", ":")), json.dumps(parsed["power_bests"], separators=(",", ":")),
            PARSER_VERSION,
        ),
    )


def scan_run_dynamics(conn: sqlite3.Connection, directory: Optional[Path] = None, today: Optional[date] = None) -> dict:
    """Read new running FIT files and retry recent unmatched ones. Returns counts."""
    init_schema(conn)
    directory = directory or healthfit_directory()
    result = {"configured": directory.is_dir(), "scanned": 0, "matched": 0, "unmatched": 0, "rematched": 0, "errors": 0}
    if not result["configured"]:
        return result
    known = {
        row["file_name"]: row
        for row in conn.execute("SELECT file_name, activity_id, date, parser_version FROM run_dynamics")
    }
    retry_since = ((today or date.today()) - timedelta(days=RETRY_UNMATCHED_DAYS)).isoformat()
    for path in sorted(directory.glob("*.fit")):
        if not is_running_file(path.name):
            continue
        existing = known.get(path.name)
        if existing and existing["parser_version"] == PARSER_VERSION:
            if existing["activity_id"] is None and existing["date"] >= retry_since:
                parsed = {"file_name": path.name, **_retry_candidate(conn, path.name)}
                activity_id = _match_activity(conn, parsed) if parsed.get("date") else None
                if activity_id:
                    conn.execute("UPDATE run_dynamics SET activity_id = ? WHERE file_name = ?", (activity_id, path.name))
                    result["rematched"] += 1
            continue
        try:
            parsed = parse_run_file(path)
        except ValueError:
            result["errors"] += 1
            continue
        activity_id = _match_activity(conn, parsed)
        _store(conn, parsed, activity_id)
        result["scanned"] += 1
        result["matched" if activity_id else "unmatched"] += 1
    conn.commit()
    return result


def _retry_candidate(conn: sqlite3.Connection, file_name: str) -> dict:
    row = conn.execute(
        "SELECT date, started_at, duration_min, distance_km, avg_hr FROM run_dynamics WHERE file_name = ?",
        (file_name,),
    ).fetchone()
    return dict(row) if row else {}


def dynamics_rows(conn: sqlite3.Connection, since: Optional[str] = None) -> list[dict]:
    """Matched dynamics rows joined to their run, oldest first."""
    init_schema(conn)
    rows = conn.execute(
        """
        SELECT r.*, a.name AS activity_name, a.distance_km AS activity_distance_km,
               a.duration_min AS activity_duration_min, a.avg_hr AS activity_avg_hr
        FROM run_dynamics r
        JOIN activities a ON a.id = r.activity_id
        WHERE a.type = 'Run' AND (? IS NULL OR r.date >= ?)
        ORDER BY r.date ASC, r.started_at ASC
        """,
        (since, since),
    ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["indoor"] = bool(item["indoor"])
        item["splits"] = json.loads(item.pop("splits_json") or "[]")
        item["power_bests"] = json.loads(item.pop("power_bests_json") or "{}")
        out.append(item)
    return out


def activity_ids_with_dynamics(conn: sqlite3.Connection) -> set[str]:
    init_schema(conn)
    return {row[0] for row in conn.execute("SELECT activity_id FROM run_dynamics WHERE activity_id IS NOT NULL")}


def first_dynamics_date(conn: sqlite3.Connection) -> Optional[str]:
    init_schema(conn)
    row = conn.execute("SELECT MIN(date) FROM run_dynamics WHERE vertical_oscillation_cm IS NOT NULL").fetchone()
    return row[0] if row else None
