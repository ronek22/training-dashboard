"""Personal best wall: endurance, lift and streak records with their context.

Records are derived from local data only. Distance bests are scanned from the
cached Strava/HealthFit streams of every ride and run (not just the activities
whose detail page was opened), and each activity's result is cached in
``activity_record_efforts`` keyed by the detail row's ``updated_at`` so a warm
read never re-parses stream JSON. Power records reuse the measured-power
profile from ``power_trends`` so both pages always agree; 5 s power, which the
benchmark radar does not chart, is cached alongside the distance efforts.

Progressions are derived chronologically from those efforts, so there is no
event table to keep in sync with imports or deletions.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional

from .activity_times import start_times as _start_times, time_of_day as _time_of_day
from .ftp import stored_ftp
from .guided_sessions import guided_completion_dates
from .power_trends import (
    POWER_EFFORT_LABELS,
    _best_effort_from_runs,
    _build_segments,
    _confirmed_power_meter,
    _decode_json,
    _finite_number,
    _stream_values,
    get_cycling_power_trends_data,
)
from .strength import _filtered_sessions, _match_pr_pattern


ALGORITHM_VERSION = "records-v1"
RIDE_TYPES = ("Ride", "VirtualRide")
RUN_TYPES = ("Run",)
RIDE_DISTANCES = (
    ("5K", 5000.0),
    ("10K", 10000.0),
    ("20K", 20000.0),
    ("40K", 40000.0),
    ("50K", 50000.0),
    ("100K", 100000.0),
)
# Strava's running best-effort distances.
RUN_DISTANCES = (
    ("400m", 400.0),
    ("1/2 mile", 804.67),
    ("1K", 1000.0),
    ("1 mile", 1609.34),
    ("2 mile", 3218.69),
    ("5K", 5000.0),
    ("10K", 10000.0),
    ("15K", 15000.0),
    ("10 mile", 16093.4),
    ("20K", 20000.0),
    ("Half marathon", 21097.5),
    ("30K", 30000.0),
    ("Marathon", 42195.0),
)
# Faster than this over a whole target distance is a GPS or sensor artefact.
MAX_PLAUSIBLE_KMH = {"ride": 70.0, "run": 25.0}
# A stream that ends slightly short still counts (GPS rounding), like Strava.
DISTANCE_TOLERANCE = 0.98
SPRINT_POWER_SECONDS = 5
FTP_ESTIMATE_WINDOW_DAYS = 90
RECENT_DAYS = 30
TOP_N = 3
LIFT_MIN_SESSIONS = 3
E1RM_MAX_REPS = 12
STREAK_MILESTONES = (7, 14, 30, 50, 100, 200, 365)
# Bodyweight movements: load is added weight, so a 1RM estimate is meaningless.
BODYWEIGHT_TOKENS = ("pullup", "chinup", "dip", "pushup", "muscleup")

_CACHE_TABLE = "activity_record_efforts"


# ---------------------------------------------------------------------------
# Per-activity effort extraction (cached)
# ---------------------------------------------------------------------------


def _distance_points(streams: Any) -> list[tuple[float, float, int]]:
    distances = _stream_values(streams, "distance")
    times = _stream_values(streams, "time")
    points: list[tuple[float, float, int]] = []
    last_distance = -1.0
    last_time = -1.0
    for index in range(min(len(distances), len(times))):
        distance_value = _finite_number(distances[index])
        time_value = _finite_number(times[index])
        if distance_value is None or time_value is None or distance_value < 0 or time_value < 0:
            continue
        if distance_value < last_distance or time_value < last_time:
            continue
        points.append((distance_value, time_value, index))
        last_distance = distance_value
        last_time = time_value
    return points


def fastest_distance_window(points: list[tuple[float, float, int]], target_m: float) -> Optional[dict[str, Any]]:
    """Return the shortest elapsed time covering ``target_m`` (two-pointer, O(n))."""
    if len(points) < 2 or points[-1][0] - points[0][0] < target_m * DISTANCE_TOLERANCE:
        return None
    best: Optional[dict[str, Any]] = None
    end = 1
    total = len(points)
    for start in range(total - 1):
        start_distance, start_time, start_index = points[start]
        goal = start_distance + target_m
        while end < total and points[end][0] < goal:
            end += 1
        if end >= total:
            break
        left_distance, left_time, _ = points[max(start, end - 1)]
        right_distance, right_time, end_index = points[end]
        span = right_distance - left_distance
        end_time = right_time if span <= 0 else left_time + (right_time - left_time) * (goal - left_distance) / span
        duration = end_time - start_time
        if duration <= 0:
            continue
        if best is None or duration < best["duration_s"]:
            best = {"duration_s": duration, "start_index": start_index, "end_index": end_index, "start_s": start_time}
    if best is None and points[-1][0] - points[0][0] >= target_m * DISTANCE_TOLERANCE:
        # The whole activity is within tolerance of the target but just short.
        duration = points[-1][1] - points[0][1]
        if duration > 0:
            best = {"duration_s": duration, "start_index": points[0][2], "end_index": points[-1][2], "start_s": points[0][1]}
    return best


def _window_hr(streams: Any, start_index: int, end_index: int) -> Optional[float]:
    values = [
        number
        for number in (_finite_number(value) for value in _stream_values(streams, "heartrate")[start_index : end_index + 1])
        if number is not None and number > 0
    ]
    return round(sum(values) / len(values)) if values else None


def _window_gain(streams: Any, start_index: int, end_index: int) -> Optional[int]:
    altitudes = [_finite_number(value) for value in _stream_values(streams, "altitude")[start_index : end_index + 1]]
    altitudes = [value for value in altitudes if value is not None]
    if len(altitudes) < 2:
        return None
    return round(sum(max(0.0, b - a) for a, b in zip(altitudes, altitudes[1:])))


def extract_activity_efforts(activity_type: str, streams: Any, *, power_meter: bool) -> dict[str, Any]:
    kind = "run" if activity_type in RUN_TYPES else "ride"
    targets = RUN_DISTANCES if kind == "run" else RIDE_DISTANCES
    points = _distance_points(streams)
    distance_efforts = []
    for label, target_m in targets:
        window = fastest_distance_window(points, target_m)
        if window is None:
            continue
        kmh = (target_m / window["duration_s"]) * 3.6
        if kmh > MAX_PLAUSIBLE_KMH[kind]:
            continue
        distance_efforts.append(
            {
                "label": label,
                "distance_m": target_m,
                "duration_s": round(window["duration_s"], 1),
                "start_s": round(window["start_s"], 1),
                "avg_hr": _window_hr(streams, window["start_index"], window["end_index"]),
                "elevation_gain_m": _window_gain(streams, window["start_index"], window["end_index"]),
            }
        )
    sprint = None
    if power_meter:
        effort = _best_effort_from_runs(_build_segments(streams), SPRINT_POWER_SECONDS)
        if effort is not None:
            sprint = {
                "watts": round(float(effort["watts"]), 1),
                "avg_hr": round(float(effort["avg_hr"])) if effort.get("avg_hr") is not None else None,
                "start_s": round(float(effort["start_seconds"]), 1),
            }
    return {"distance": distance_efforts, "sprint_power": sprint}


def _ensure_cache_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_CACHE_TABLE} (
            activity_id TEXT PRIMARY KEY,
            algorithm_version TEXT NOT NULL,
            source_updated_at TEXT,
            efforts_json TEXT NOT NULL
        )
        """
    )


def _activity_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    detail_columns = {row[1] for row in conn.execute("PRAGMA table_info(activity_details)")}
    updated = "d.updated_at" if "updated_at" in detail_columns else "NULL"
    types = RIDE_TYPES + RUN_TYPES
    return conn.execute(
        f"""
        SELECT a.id, a.date, a.type, a.name, a.distance_km, a.duration_min, a.elevation_m, a.avg_hr,
               d.detail_json, d.source_status, {updated} AS detail_updated_at,
               d.streams_json IS NOT NULL AS has_streams
        FROM activities AS a
        LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ({",".join("?" for _ in types)})
        ORDER BY a.date ASC, a.id ASC
        """,
        types,
    ).fetchall()


def _load_efforts(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
    """Return cached efforts per activity, computing only stale entries."""
    _ensure_cache_table(conn)
    cached = {
        row["activity_id"]: row
        for row in conn.execute(f"SELECT activity_id, algorithm_version, source_updated_at, efforts_json FROM {_CACHE_TABLE}")
    }
    result: dict[str, dict[str, Any]] = {}
    wrote = False
    for row in rows:
        if not row["has_streams"]:
            continue
        hit = cached.get(row["id"])
        source_stamp = str(row["detail_updated_at"]) if row["detail_updated_at"] is not None else None
        if hit and hit["algorithm_version"] == ALGORITHM_VERSION and hit["source_updated_at"] == source_stamp:
            try:
                result[row["id"]] = json.loads(hit["efforts_json"])
                continue
            except (TypeError, ValueError):
                pass
        streams_row = conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = ?", (row["id"],)).fetchone()
        streams = _decode_json(streams_row["streams_json"]) if streams_row else None
        power_meter = row["type"] in RIDE_TYPES and _confirmed_power_meter(
            row["detail_json"],
            activity_type=row["type"],
            source_status=row["source_status"],
            streams_json=streams,
        )
        efforts = extract_activity_efforts(row["type"], streams, power_meter=power_meter)
        conn.execute(
            f"""
            INSERT INTO {_CACHE_TABLE} (activity_id, algorithm_version, source_updated_at, efforts_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(activity_id) DO UPDATE SET
                algorithm_version = excluded.algorithm_version,
                source_updated_at = excluded.source_updated_at,
                efforts_json = excluded.efforts_json
            """,
            (row["id"], ALGORITHM_VERSION, source_stamp, json.dumps(efforts, separators=(",", ":"))),
        )
        wrote = True
        result[row["id"]] = efforts
    if wrote:
        conn.commit()
    return result


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _is_indoor(row: sqlite3.Row) -> bool:
    if row["type"] == "VirtualRide":
        return True
    detail = _decode_json(row["detail_json"])
    return isinstance(detail, dict) and detail.get("trainer") is True


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _pace(duration_s: float, distance_m: float) -> str:
    seconds_per_km = duration_s / (distance_m / 1000.0)
    minutes, secs = divmod(int(round(seconds_per_km)), 60)
    return f"{minutes}:{secs:02d} /km"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _rank(entries: list[dict[str, Any]], *, higher_is_better: bool) -> dict[str, Any]:
    """Build top-N, the chronological progression and the current record.

    ``entries`` hold one candidate per activity (or session). Ties go to the
    earlier date, like Strava: matching a record is not a new record.
    """
    sign = -1 if higher_is_better else 1
    ordered = sorted(entries, key=lambda item: (sign * item["value"], item["date"], item["activity_id"] or ""))
    top = [{**item, "rank": index + 1} for index, item in enumerate(ordered[:TOP_N])]
    progression: list[dict[str, Any]] = []
    for item in sorted(entries, key=lambda entry: (entry["date"], entry.get("sort_time") or "", entry["activity_id"] or "")):
        if not progression:
            progression.append(item)
            continue
        best = progression[-1]["value"]
        if (item["value"] > best) if higher_is_better else (item["value"] < best):
            progression.append(item)
    record = dict(top[0]) if top else None
    if record:
        previous = progression[-2] if len(progression) >= 2 and progression[-1]["activity_id"] == record["activity_id"] else None
        record["previous"] = _compact(previous) if previous else None
        if previous:
            delta = record["value"] - previous["value"]
            record["improvement"] = round(abs(delta), 1)
            record["improvement_percent"] = round(abs(delta) / previous["value"] * 100, 1) if previous["value"] else None
    return {
        "record": record,
        "top": [_compact(item) for item in top],
        "progression": [{"date": item["date"], "value": item["value"], "display": item["display"], "activity_id": item["activity_id"]} for item in progression],
        "attempts": len(entries),
    }


def _compact(item: dict[str, Any]) -> dict[str, Any]:
    keys = ("rank", "value", "display", "date", "activity_id", "activity_name", "context", "detail")
    return {key: item[key] for key in keys if key in item}


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _distance_section(
    rows: list[sqlite3.Row],
    efforts: dict[str, dict[str, Any]],
    starts: dict[str, datetime],
    targets: tuple[tuple[str, float], ...],
    *,
    kind: str,
) -> dict[str, Any]:
    by_label: dict[str, list[dict[str, Any]]] = {label: [] for label, _ in targets}
    for row in rows:
        for effort in (efforts.get(row["id"]) or {}).get("distance", []):
            if effort["label"] not in by_label:
                continue
            duration = effort["duration_s"]
            kmh = effort["distance_m"] / duration * 3.6
            by_label[effort["label"]].append(
                {
                    "value": duration,
                    "display": format_duration(duration),
                    "detail": _pace(duration, effort["distance_m"]) if kind == "run" else f"{kmh:.1f} km/h",
                    "date": row["date"],
                    "sort_time": starts[row["id"]].isoformat() if row["id"] in starts else "",
                    "activity_id": row["id"],
                    "activity_name": row["name"],
                    "context": {
                        "indoor": _is_indoor(row),
                        "avg_hr": effort.get("avg_hr"),
                        "elevation_gain_m": effort.get("elevation_gain_m"),
                        "time_of_day": _time_of_day(starts.get(row["id"]), effort.get("start_s") or 0.0),
                    },
                }
            )
    longest_km = max((float(row["distance_km"] or 0) for row in rows), default=0.0)
    records = []
    for label, distance_m in targets:
        ranked = _rank(by_label[label], higher_is_better=False)
        records.append(
            {
                "key": f"{kind}-{label.lower().replace(' ', '-').replace('/', '-')}",
                "label": label,
                "distance_m": distance_m,
                **ranked,
                "locked": ranked["record"] is None,
                "unlock_hint": None if ranked["record"] else f"Longest {kind} so far: {longest_km:.1f} km",
            }
        )
    return {"records": records, "longest": _longest(rows, starts), "biggest_climb": _biggest_climb(rows, starts)}


def _activity_entry(row: sqlite3.Row, starts: dict[str, datetime], value: float, display: str, detail: Optional[str] = None) -> dict[str, Any]:
    return {
        "value": value,
        "display": display,
        "detail": detail,
        "date": row["date"],
        "activity_id": row["id"],
        "activity_name": row["name"],
        "context": {"indoor": _is_indoor(row), "avg_hr": row["avg_hr"], "time_of_day": _time_of_day(starts.get(row["id"]))},
    }


def _longest(rows: list[sqlite3.Row], starts: dict[str, datetime]) -> Optional[dict[str, Any]]:
    entries = [
        _activity_entry(row, starts, float(row["distance_km"]), f"{float(row['distance_km']):.1f} km", format_duration((row["duration_min"] or 0) * 60))
        for row in rows
        if row["distance_km"]
    ]
    return _rank(entries, higher_is_better=True) if entries else None


def _biggest_climb(rows: list[sqlite3.Row], starts: dict[str, datetime]) -> Optional[dict[str, Any]]:
    entries = [
        _activity_entry(row, starts, float(row["elevation_m"]), f"{int(row['elevation_m'])} m", f"{float(row['distance_km'] or 0):.1f} km")
        for row in rows
        if row["elevation_m"] and not _is_indoor(row)
    ]
    return _rank(entries, higher_is_better=True) if entries else None


def _power_section(
    conn: sqlite3.Connection,
    ride_rows: list[sqlite3.Row],
    efforts: dict[str, dict[str, Any]],
    starts: dict[str, datetime],
    today: date,
) -> dict[str, Any]:
    rows_by_id = {row["id"]: row for row in ride_rows}
    profile = get_cycling_power_trends_data(conn)
    by_duration: dict[int, list[dict[str, Any]]] = {}

    def add(duration: int, row: sqlite3.Row, watts: float, avg_hr: Optional[float], start_s: float) -> None:
        by_duration.setdefault(duration, []).append(
            {
                "value": round(float(watts), 1),
                "display": f"{round(float(watts))} W",
                "date": row["date"],
                "sort_time": starts[row["id"]].isoformat() if row["id"] in starts else "",
                "activity_id": row["id"],
                "activity_name": row["name"],
                "context": {
                    "indoor": _is_indoor(row),
                    "avg_hr": round(avg_hr) if avg_hr is not None else None,
                    "time_of_day": _time_of_day(starts.get(row["id"]), start_s),
                },
            }
        )

    for row in ride_rows:
        sprint = (efforts.get(row["id"]) or {}).get("sprint_power")
        if sprint:
            add(SPRINT_POWER_SECONDS, row, sprint["watts"], sprint.get("avg_hr"), sprint.get("start_s") or 0.0)
    for effort in profile.get("efforts", []):
        row = rows_by_id.get(effort["activity_id"])
        if row is not None:
            add(effort["duration_seconds"], row, effort["watts"], effort.get("avg_hr"), effort.get("start_seconds") or 0.0)

    labels = {SPRINT_POWER_SECONDS: "5 sec", **POWER_EFFORT_LABELS}
    records = [
        {"key": f"power-{duration}", "label": labels.get(duration, f"{duration} s"), "duration_seconds": duration, **_rank(by_duration[duration], higher_is_better=True)}
        for duration in sorted(by_duration)
    ]
    return {
        "records": records,
        "ftp_estimate": estimate_ftp(by_duration, stored_ftp(conn, today), today),
        "coverage": profile.get("coverage"),
    }


def estimate_ftp(by_duration: dict[int, list[dict[str, Any]]], stored: dict[str, Any], today: date) -> dict[str, Any]:
    """FTP from recent records: max(95% of best 20 min, best 60 min).

    This is an estimate shown beside the stored FTP. It never replaces it.
    """
    cutoff = (today - timedelta(days=FTP_ESTIMATE_WINDOW_DAYS - 1)).isoformat()

    def recent_best(duration: int) -> Optional[dict[str, Any]]:
        candidates = [item for item in by_duration.get(duration, []) if item["date"] >= cutoff]
        return max(candidates, key=lambda item: (item["value"], item["date"]), default=None)

    best20 = recent_best(1200)
    best60 = recent_best(3600)
    options = []
    if best20:
        options.append((best20["value"] * 0.95, "95% of best 20 min", best20))
    if best60:
        options.append((best60["value"], "best 60 min", best60))
    base = {"window_days": FTP_ESTIMATE_WINDOW_DAYS, "stored": stored}
    if not options:
        return {**base, "available": False, "watts": None, "reason": f"No 20 or 60 min power effort in the last {FTP_ESTIMATE_WINDOW_DAYS} days."}
    watts, basis, source = max(options, key=lambda option: option[0])
    difference = round(watts - stored["watts"]) if stored.get("available") else None
    return {
        **base,
        "available": True,
        "watts": round(watts),
        "basis": basis,
        "source": _compact(source),
        "difference_from_stored": difference,
        "note": "Estimate from training efforts, not a test. Submaximal efforts make it a floor rather than a ceiling.",
    }


def epley_1rm(weight_kg: float, reps: int) -> float:
    return weight_kg if reps <= 1 else weight_kg * (1 + reps / 30.0)


def _lift_section(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        _, sessions = _filtered_sessions(conn, window_start=date(2000, 1, 1), body_part="all")
    except sqlite3.OperationalError:
        sessions = []
    by_exercise: dict[str, dict[str, Any]] = {}
    for session in sessions:
        matched = session.get("matched_activity") or {}
        for exercise in session.get("exercises", []):
            sets = [item for item in exercise.get("sets", []) if not item.get("is_warmup") and (item.get("reps") or 0) > 0]
            if not sets:
                continue
            bucket = by_exercise.setdefault(exercise["exercise_name"], {"sessions": 0, "strength": [], "heaviest": [], "reps": []})
            bucket["sessions"] += 1
            base = {
                "date": session["workout_date"][:10],
                "sort_time": session.get("workout_timestamp") or "",
                "activity_id": matched.get("id"),
                "activity_name": session.get("title") or matched.get("name"),
            }
            weighted = [item for item in sets if (item.get("weight_kg") or 0) > 0]
            if weighted:
                scored = [item for item in weighted if item["reps"] <= E1RM_MAX_REPS]
                if scored:
                    best = max(scored, key=lambda item: epley_1rm(item["weight_kg"], item["reps"]))
                    e1rm = round(epley_1rm(best["weight_kg"], best["reps"]), 1)
                    bucket["strength"].append({**base, "value": e1rm, "display": f"{e1rm:g} kg", "detail": f"{best['weight_kg']:g} kg × {best['reps']}"})
                heavy = max(weighted, key=lambda item: (item["weight_kg"], item["reps"]))
                bucket["heaviest"].append({**base, "value": float(heavy["weight_kg"]), "display": f"{heavy['weight_kg']:g} kg", "detail": f"× {heavy['reps']}"})
            else:
                most = max(sets, key=lambda item: item["reps"])
                bucket["reps"].append({**base, "value": float(most["reps"]), "display": f"{most['reps']} reps", "detail": "bodyweight"})

    records = []
    for name, bucket in by_exercise.items():
        if bucket["sessions"] < LIFT_MIN_SESSIONS:
            continue
        pattern = _match_pr_pattern(name)
        normalized = "".join(ch for ch in name.lower() if ch.isalnum())
        bodyweight = any(token in normalized for token in BODYWEIGHT_TOKENS)
        if bodyweight and bucket["reps"]:
            metric, entries, metric_label = "reps", bucket["reps"], "Most reps in a set"
        elif bodyweight and bucket["heaviest"]:
            metric, entries, metric_label = "heaviest", bucket["heaviest"], "Most added weight"
        elif bucket["strength"]:
            metric, entries, metric_label = "e1rm", bucket["strength"], "Estimated 1RM"
        elif bucket["heaviest"]:
            metric, entries, metric_label = "heaviest", bucket["heaviest"], "Heaviest set"
        elif bucket["reps"]:
            metric, entries, metric_label = "reps", bucket["reps"], "Most reps in a set"
        else:
            continue
        ranked = _rank(entries, higher_is_better=True)
        heaviest = _rank(bucket["heaviest"], higher_is_better=True)["record"] if bucket["heaviest"] else None
        if bodyweight and metric == "reps":
            metric_extra = heaviest
        else:
            metric_extra = heaviest if metric == "e1rm" else None
        records.append(
            {
                "key": f"lift-{''.join(ch for ch in name.lower() if ch.isalnum())}",
                "label": name,
                "metric": metric,
                "metric_label": metric_label,
                "key_lift": pattern is not None,
                "sessions": bucket["sessions"],
                "heaviest": _compact(metric_extra) if metric_extra else None,
                **ranked,
            }
        )
    records.sort(key=lambda item: (not item["key_lift"], -item["sessions"], item["label"]))
    return {
        "records": records,
        "method": f"Estimated 1RM uses the Epley formula on working sets of up to {E1RM_MAX_REPS} reps; warm-ups are excluded. Exercises need {LIFT_MIN_SESSIONS}+ sessions.",
    }


def _streak_section(conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    # A finished guided session (sick mode or downshift) keeps the streak like an activity.
    keys = {row[0][:10] for row in conn.execute("SELECT DISTINCT date FROM activities")} | guided_completion_dates(conn)
    dates = sorted(date.fromisoformat(key) for key in keys)
    runs: list[tuple[date, date]] = []
    for day in dates:
        if runs and day == runs[-1][1] + timedelta(days=1):
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))

    def describe(run: tuple[date, date]) -> dict[str, Any]:
        return {"days": (run[1] - run[0]).days + 1, "start": run[0].isoformat(), "end": run[1].isoformat()}

    current = None
    if runs and runs[-1][1] >= today - timedelta(days=1):
        current = describe(runs[-1])
    ranked = sorted(runs, key=lambda run: (-((run[1] - run[0]).days), run[0]))
    milestones = []
    for days in STREAK_MILESTONES:
        reached = next((run[0] + timedelta(days=days - 1) for run in runs if (run[1] - run[0]).days + 1 >= days), None)
        milestones.append({"days": days, "reached_on": reached.isoformat() if reached else None})
    current_days = current["days"] if current else 0
    next_milestone = next((days for days in STREAK_MILESTONES if days > current_days), None)
    return {
        "current": current,
        "longest": describe(ranked[0]) if ranked else None,
        "top": [describe(run) for run in ranked[:TOP_N]],
        "milestones": milestones,
        "next_milestone": {"days": next_milestone, "days_to_go": next_milestone - current_days} if next_milestone else None,
        "note": "A day counts when any activity or finished guided session (sick mode or downshift) is recorded.",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _endurance_sections(conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    rows = _activity_rows(conn)
    efforts = _load_efforts(conn, rows)
    starts = _start_times(conn, rows)
    rides = [row for row in rows if row["type"] in RIDE_TYPES]
    outdoor = [row for row in rides if not _is_indoor(row)]
    indoor = [row for row in rides if _is_indoor(row)]
    runs = [row for row in rows if row["type"] in RUN_TYPES]
    return {
        "cycling_power": _power_section(conn, rides, efforts, starts, today),
        "cycling_distance": {
            "outdoor": _distance_section(outdoor, efforts, starts, RIDE_DISTANCES, kind="ride"),
            "indoor": _distance_section(indoor, efforts, starts, RIDE_DISTANCES, kind="ride"),
            "note": "Indoor speed is simulated by the trainer platform, so indoor distance records are kept separate. Power counts from both.",
        },
        "running": _distance_section(runs, efforts, starts, RUN_DISTANCES, kind="run"),
    }


def _iter_ranked(sections: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    """Yield (category, label, ranked record) for every record on the wall."""
    for record in sections["cycling_power"]["records"]:
        yield "Bike power", record["label"], record
    for venue, title in (("outdoor", "Bike distance"), ("indoor", "Indoor bike distance")):
        section = sections["cycling_distance"][venue]
        for record in section["records"]:
            yield title, record["label"], record
        for name, key in (("Longest ride", "longest"), ("Biggest climb", "biggest_climb")):
            if section.get(key):
                yield title, name, section[key]
    for record in sections["running"]["records"]:
        yield "Run", record["label"], record
    if sections["running"].get("longest"):
        yield "Run", "Longest run", sections["running"]["longest"]
    for record in sections.get("lifts", {}).get("records", []):
        yield "Lift", record["label"], record


def _recent(sections: dict[str, Any], today: date) -> list[dict[str, Any]]:
    cutoff = (today - timedelta(days=RECENT_DAYS - 1)).isoformat()
    items = []
    for category, label, ranked in _iter_ranked(sections):
        for entry in ranked.get("top", []):
            if entry["date"] < cutoff:
                continue
            improved_from = None
            if entry["rank"] == 1 and (ranked.get("record") or {}).get("previous"):
                improved_from = ranked["record"]["previous"]
            items.append(
                {
                    "category": category,
                    "label": label,
                    "rank": entry["rank"],
                    "display": entry["display"],
                    "detail": entry.get("detail"),
                    "metric": ranked.get("metric"),
                    "date": entry["date"],
                    "activity_id": entry.get("activity_id"),
                    "activity_name": entry.get("activity_name"),
                    "previous": improved_from,
                    "first": ranked.get("attempts", 0) == 1,
                }
            )
    streaks = sections.get("streaks") or {}
    for milestone in streaks.get("milestones", []):
        if milestone["reached_on"] and milestone["reached_on"] >= cutoff:
            items.append({"category": "Streak", "label": f"{milestone['days']}-day streak", "rank": 1, "display": f"{milestone['days']} days", "date": milestone["reached_on"]})
    items.sort(key=lambda item: (item["date"], -item["rank"]), reverse=True)
    return items


def build_personal_records(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    sections = _endurance_sections(conn, today)
    sections["lifts"] = _lift_section(conn)
    sections["streaks"] = _streak_section(conn, today)
    return {
        "as_of": today.isoformat(),
        **sections,
        "recent": _recent(sections, today),
        "recent_days": RECENT_DAYS,
    }


def build_activity_record_ranks(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, list[dict[str, Any]]]:
    """Map activity id -> the all-time top-3 places it holds (endurance and lifts)."""
    today = today or date.today()
    sections = _endurance_sections(conn, today)
    sections["lifts"] = _lift_section(conn)
    ranks: dict[str, list[dict[str, Any]]] = {}
    for category, label, ranked in _iter_ranked(sections):
        for entry in ranked.get("top", []):
            if entry.get("activity_id"):
                ranks.setdefault(entry["activity_id"], []).append(
                    {"category": category, "label": label, "rank": entry["rank"], "display": entry["display"]}
                )
    for items in ranks.values():
        items.sort(key=lambda item: (item["rank"], item["category"], item["label"]))
    return ranks


def build_records_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    """Compact records for MCP/coach context: current bests, recent PRs, FTP estimate."""
    data = build_personal_records(conn, today)

    def headline(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"label": record["label"], "best": record["record"]["display"], "detail": record["record"].get("detail"), "date": record["record"]["date"]}
            for record in records
            if record.get("record")
        ]

    return {
        "as_of": data["as_of"],
        "bike_power": headline(data["cycling_power"]["records"]),
        "bike_distance_outdoor": headline(data["cycling_distance"]["outdoor"]["records"]),
        "bike_distance_indoor": headline(data["cycling_distance"]["indoor"]["records"]),
        "running": headline(data["running"]["records"]),
        "lifts": headline(data["lifts"]["records"])[:10],
        "streaks": {"current": data["streaks"]["current"], "longest": data["streaks"]["longest"]},
        "ftp_estimate": {key: data["cycling_power"]["ftp_estimate"].get(key) for key in ("available", "watts", "basis", "difference_from_stored", "note", "reason")},
        "recent_prs": data["recent"][:12],
        "guidance": "Celebrate recent PRs briefly. The FTP estimate comes from training efforts; do not overwrite the stored FTP or prescribe a test from it.",
    }


def build_recent_records_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    """Small slice for get_recent_context: new all-time bests and the FTP estimate."""
    data = build_personal_records(conn, today)
    estimate = data["cycling_power"]["ftp_estimate"]
    return {
        "window_days": RECENT_DAYS,
        "new_records": [
            {
                "record": f"{item['category']} {item['label']}",
                "value": item["display"],
                "previous": (item.get("previous") or {}).get("display"),
                "date": item["date"],
                "activity": item.get("activity_name"),
            }
            for item in data["recent"]
            if item["rank"] == 1
        ][:8],
        "ftp_estimate": {key: estimate.get(key) for key in ("available", "watts", "basis", "difference_from_stored")},
        "note": "Use get_personal_records for the full wall. Indoor distance records are kept separate from outdoor.",
    }
