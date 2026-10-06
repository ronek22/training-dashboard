import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from fastapi import HTTPException

from ..repositories.activity_details import (
    get_activity_detail_row,
    update_activity_detail_derived_row,
    upsert_activity_detail_row,
)
from ..repositories.plans import list_weekly_plan_rows
from ..repositories.activities import (
    get_activity_row,
    get_latest_activity_date,
    list_activity_rows,
    list_activity_stat_rows,
    list_calendar_activity_rows,
    update_activity_linked_session_id,
    update_activity_workout_intent,
    upsert_activity_row,
)
from .fitbod_imports import get_fitbod_strength_detail_for_activity
from .strength_progression import build_strength_progression
from .strength_workouts import get_trainlog_strength_detail_for_activity
from .activity_feedback import attach_feedback_by_activity_id, get_activity_feedback_data
from .activity_analysis import (
    fail_activity_analysis,
    get_activity_analysis_context_payload,
    get_activity_analysis_snapshot,
    request_activity_analysis,
    save_activity_analysis,
)
from .personal_records import RIDE_DISTANCES, RUN_DISTANCES, fastest_distance_window
from .session_win import build_session_win
from .benchmarks import attach_benchmark_from_lookup, build_benchmark_session_lookup
from .heart_rate_zones import build_activity_heart_rate_zone_summary
from .power_zones import build_activity_power_zone_summary
from .ride_detail import build_ride_detail
from .plans import (
    build_execution_quality_for_completed_session,
    ensure_plan_day_ids,
    find_planned_session_by_id,
    format_workout_intent_label,
    normalize_workout_intent,
)
from .guided_sessions import guided_session_for_activity
from .sick_mode import sick_dates
from .settings import (
    get_performance_settings_for_conn,
    get_workout_template_settings_for_conn,
    set_workout_template_settings_for_conn,
)

DETAIL_DERIVED_VERSION = "v6"


def _normalize_text_for_match(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _template_session_lookup_by_session_id(conn: sqlite3.Connection) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for row in list_weekly_plan_rows(conn, 200):
        days = ensure_plan_day_ids(row["week_start"], json.loads(row["days_json"]))
        for day in days:
            session_id = day.get("session_id")
            template_id = day.get("template_id")
            if session_id and template_id:
                lookup[session_id] = {
                    "session_id": session_id,
                    "template_id": template_id,
                    "date": day.get("date"),
                    "session_type": day.get("session_type"),
                    "template_label": day.get("template_label"),
                    "title": day.get("title"),
                }
    return lookup


def _infer_strength_template_id_for_activity(
    activity_row: sqlite3.Row,
    session_lookup: dict[str, dict],
    templates_by_id: dict[str, dict],
) -> Optional[str]:
    linked_session_id = activity_row["linked_planned_session_id"]
    if linked_session_id:
        linked = session_lookup.get(linked_session_id)
        if linked:
            return linked.get("template_id")

    if activity_row["type"] != "WeightTraining":
        return None

    activity_date = activity_row["date"]
    same_day_sessions = [
        session for session in session_lookup.values()
        if session.get("session_type") == "WeightTraining" and session.get("date") == activity_date
    ]
    normalized_name = _normalize_text_for_match(activity_row["name"])
    if normalized_name:
        matching_template_ids = []
        for template_id, template in templates_by_id.items():
            candidate_tokens = {
                _normalize_text_for_match(template.get("label")),
                _normalize_text_for_match(template.get("title")),
                _normalize_text_for_match(template.get("display_name")),
            }
            candidate_tokens.discard("")
            if any(token and token in normalized_name for token in candidate_tokens):
                matching_template_ids.append(template_id)

        if len(matching_template_ids) == 1:
            return matching_template_ids[0]

        if len(same_day_sessions) > 1 and len(matching_template_ids) >= 1:
            same_day_template_ids = {session.get("template_id") for session in same_day_sessions}
            overlap = [template_id for template_id in matching_template_ids if template_id in same_day_template_ids]
            if len(overlap) == 1:
                return overlap[0]

    if len(same_day_sessions) == 1:
        return same_day_sessions[0].get("template_id")

    return None


def _strength_plan_identity_for_activity(conn: sqlite3.Connection, activity: dict) -> Optional[dict]:
    """Resolve a strength activity's planned identity without changing its source title."""
    if activity.get("type") != "WeightTraining":
        return None

    session_lookup = _template_session_lookup_by_session_id(conn)
    linked_session_id = activity.get("linked_planned_session_id")
    if linked_session_id:
        linked = session_lookup.get(linked_session_id)
        if linked:
            return {
                "match_strategy": "explicit",
                "session_id": linked_session_id,
                "template_id": linked.get("template_id"),
                "template_label": linked.get("template_label"),
                "title": linked.get("title"),
            }

    same_day_sessions = [
        session for session in session_lookup.values()
        if session.get("session_type") == "WeightTraining" and session.get("date") == activity.get("date")
    ]
    if len(same_day_sessions) != 1:
        return None

    inferred = same_day_sessions[0]
    return {
        "match_strategy": "inferred",
        "session_id": inferred.get("session_id"),
        "template_id": inferred.get("template_id"),
        "template_label": inferred.get("template_label"),
        "title": inferred.get("title"),
    }


def _attach_strength_plan_identity(conn: sqlite3.Connection, activity: dict) -> dict:
    enriched = dict(activity)
    recorded_session = None
    if enriched.get("type") == "WeightTraining":
        row = conn.execute(
            """
            SELECT id, template_name, started_at, completed_at
            FROM strength_workout_sessions
            WHERE linked_activity_id = ? AND status = 'completed'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (enriched.get("id"),),
        ).fetchone()
        if row:
            recorded_session = {
                "id": int(row["id"]),
                "name": row["template_name"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
            }
    identity = _strength_plan_identity_for_activity(conn, enriched)
    enriched["source_name"] = enriched.get("name")
    enriched["recorded_strength_session"] = recorded_session
    enriched["planned_strength_identity"] = identity
    if recorded_session:
        enriched["display_name"] = recorded_session.get("name") or enriched.get("name")
    elif identity:
        enriched["display_name"] = identity.get("template_label") or identity.get("title") or enriched.get("name")
    else:
        enriched["display_name"] = enriched.get("name")
    return enriched


def reconcile_workout_template_rotation_state(conn: sqlite3.Connection) -> None:
    settings = get_workout_template_settings_for_conn(conn)
    strength_program = ((settings.get("programs") or {}).get("strength")) or {}
    if not strength_program.get("enabled", True):
        return

    templates = strength_program.get("templates") or []
    if not templates:
        return

    state = dict(strength_program.get("rotation_state") or {})
    processed_activity_ids = list(state.get("processed_activity_ids") or [])
    processed_lookup = set(processed_activity_ids)
    template_ids = [item.get("id") for item in templates if item.get("id")]
    template_order = {template_id: index for index, template_id in enumerate(template_ids)}
    templates_by_id = {item["id"]: item for item in templates if item.get("id")}
    session_lookup = _template_session_lookup_by_session_id(conn)
    if not session_lookup:
        return

    rows = conn.execute(
        """
        SELECT id, date, type, name, linked_planned_session_id, workout_intent
        FROM activities
        ORDER BY date ASC, created_at ASC, id ASC
        """
    ).fetchall()
    # Light sick-mode sessions (often synced as WeightTraining) are not planned lifts.
    excluded_dates = sick_dates(conn)

    changed = False
    for row in rows:
        activity_id = row["id"]
        if activity_id in processed_lookup:
            continue
        if not row["linked_planned_session_id"] and (row["workout_intent"] in ("recovery", "mobility") or row["date"] in excluded_dates):
            continue
        template_id = _infer_strength_template_id_for_activity(row, session_lookup, templates_by_id)
        if template_id not in template_order:
            continue
        state["last_completed_template_id"] = template_id
        state["last_completed_at"] = row["date"]
        state["last_completed_activity_id"] = activity_id
        if state.get("pending_template_id") in {None, template_id}:
            state["pending_template_id"] = template_id
        next_index = (template_order[template_id] + 1) % len(template_ids)
        state["next_template_id"] = template_ids[next_index]
        state["pending_template_id"] = state["next_template_id"]
        processed_activity_ids.append(activity_id)
        processed_lookup.add(activity_id)
        changed = True

    if not changed:
        return

    strength_program["rotation_state"] = {
        **strength_program.get("rotation_state", {}),
        **state,
        "processed_activity_ids": processed_activity_ids[-64:],
    }
    updated = {
        "programs": {
            **(settings.get("programs") or {}),
            "strength": strength_program,
        }
    }
    set_workout_template_settings_for_conn(conn, updated)


def create_activity_data(conn: sqlite3.Connection, activity: dict) -> dict:
    upsert_activity_row(conn, activity)
    reconcile_workout_template_rotation_state(conn)
    conn.commit()
    return {"status": "ok", "id": activity["id"]}


def list_activities_data(
    conn: sqlite3.Connection,
    limit: int = 50,
    activity_type: Optional[str] = None,
    days: Optional[int] = None,
) -> list[dict]:
    reconcile_workout_template_rotation_state(conn)
    benchmark_lookup = build_benchmark_session_lookup(conn)
    rows = list_activity_rows(conn, limit=limit, activity_type=activity_type, days=days)
    payload = []
    for row in rows:
        item = dict(row)
        normalized_intent = normalize_workout_intent(item.get("workout_intent"), item.get("type"))
        item["workout_intent"] = normalized_intent
        item["workout_intent_label"] = format_workout_intent_label(normalized_intent)
        item = attach_benchmark_from_lookup(item, benchmark_lookup)
        payload.append(_attach_strength_plan_identity(conn, item))
    return attach_feedback_by_activity_id(conn, payload)


def activity_stats_data(conn: sqlite3.Connection, days: int = 30) -> list[dict]:
    rows = list_activity_stat_rows(conn, days=days)
    return [dict(row) for row in rows]


def _load_json_blob(value: Optional[str]) -> Optional[dict]:
    if not value:
        return None
    return json.loads(value)


def _is_strava_backed_activity(activity_id: str) -> bool:
    return activity_id.isdigit()


def _encode_route_polyline(latlng: list) -> Optional[str]:
    """Encode a Strava lat/lng stream using Google's polyline format."""
    encoded: list[str] = []
    previous_lat = 0
    previous_lng = 0

    def encode_delta(delta: int) -> None:
        value = ~(delta << 1) if delta < 0 else delta << 1
        while value >= 0x20:
            encoded.append(chr((0x20 | (value & 0x1F)) + 63))
            value >>= 5
        encoded.append(chr(value + 63))

    for point in latlng:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            lat = round(float(point[0]) * 100_000)
            lng = round(float(point[1]) * 100_000)
        except (TypeError, ValueError):
            continue
        encode_delta(lat - previous_lat)
        encode_delta(lng - previous_lng)
        previous_lat = lat
        previous_lng = lng

    return "".join(encoded) or None


def _extract_route_polyline(detail: Optional[dict], streams: Optional[dict], cached_polyline: Optional[str]) -> Optional[str]:
    if cached_polyline:
        return cached_polyline
    map_data = detail.get("map") if detail else None
    if isinstance(map_data, dict):
        summary_polyline = map_data.get("summary_polyline") or map_data.get("polyline")
        if summary_polyline:
            return summary_polyline
    latlng = (streams or {}).get("latlng", {}).get("data") or []
    if latlng:
        return _encode_route_polyline(latlng)
    return None


# A gap this long between samples is an auto-pause; below this speed the device
# is still recording but the athlete is stopped (lights, a café, a gate).
PAUSE_GAP_SECONDS = 10.0
STOPPED_SPEED_MPS = 0.5
# Pauses shorter than this are dropped from the chart silently, without a marker.
PAUSE_MARKER_SECONDS = 60.0
CHART_POINT_LIMIT = 240
# GPS speed jitters second to second; runners read a ~45 s rolling pace, steady enough to see the effort, short enough to keep reps.
PACE_SMOOTHING_SECONDS = 45.0
SPEED_SMOOTHING_SECONDS = 30.0


def _moving_timeline(time_stream: list[object], velocity_stream: list[object]) -> tuple[list[Optional[float]], list[dict]]:
    """Moving seconds per sample (``None`` while stopped) and the pauses removed.

    Charts are plotted against moving time so auto-pause gaps and recorded
    stops do not draw long straight lines or drops to zero across the trace.
    """
    moving: list[Optional[float]] = []
    pauses: list[dict] = []
    clock = 0.0
    previous_time: Optional[float] = None
    previous_stopped = False
    pause: Optional[dict] = None

    for index, raw_time in enumerate(time_stream):
        try:
            current = float(raw_time)
        except (TypeError, ValueError):
            moving.append(None)
            continue
        delta = max(current - previous_time, 0.0) if previous_time is not None else 0.0
        speed = velocity_stream[index] if index < len(velocity_stream) else None
        try:
            stopped = speed is not None and float(speed) < STOPPED_SPEED_MPS
        except (TypeError, ValueError):
            stopped = False

        if delta > PAUSE_GAP_SECONDS or stopped or previous_stopped:
            if pause is None:
                pause = {"x": round(clock / 60.0, 2), "elapsed_min": round((previous_time or current) / 60.0, 2), "duration_s": 0.0}
            pause["duration_s"] += delta
        else:
            clock += delta
        if not stopped and pause is not None:
            if pause["duration_s"] >= PAUSE_MARKER_SECONDS:
                pauses.append({**pause, "duration_s": round(pause["duration_s"])})
            pause = None
        moving.append(None if stopped else clock)
        previous_time = current
        previous_stopped = stopped
    return moving, pauses


def _rolling_mean(points: list[dict], window_seconds: float) -> list[dict]:
    """Centered rolling mean of ``y`` over ``window_seconds`` of the chart axis (minutes in ``x``)."""
    if window_seconds <= 0 or len(points) < 3:
        return points
    half = window_seconds / 120.0
    smoothed = []
    start = end = 0
    total = 0.0
    for point in points:
        while end < len(points) and points[end]["x"] <= point["x"] + half:
            total += points[end]["y"]
            end += 1
        while points[start]["x"] < point["x"] - half:
            total -= points[start]["y"]
            start += 1
        smoothed.append({**point, "y": total / (end - start)})
    return smoothed


def _downsample_series(points: list[dict], limit: int = CHART_POINT_LIMIT) -> list[dict]:
    """Average consecutive samples into ``limit`` buckets.

    Averaging keeps the shape of a 1 Hz stream; picking every Nth sample made
    single noisy readings look like spikes and dips.
    """
    if len(points) <= limit:
        return points
    sampled = []
    size = len(points) / limit
    for bucket in range(limit):
        chunk = points[int(bucket * size):int((bucket + 1) * size)] or [points[min(int(bucket * size), len(points) - 1)]]
        middle = chunk[len(chunk) // 2]
        sampled.append({
            "x": middle["x"],
            "t": middle["t"],
            "y": sum(point["y"] for point in chunk) / len(chunk),
        })
    return sampled


def _build_stream_chart(
    key: str,
    label: str,
    unit: str,
    values: list[object],
    time_stream: list[object],
    transform: Callable[[float], float] = lambda value: value,
    *,
    moving: Optional[list[Optional[float]]] = None,
    pauses: Optional[list[dict]] = None,
    smooth_seconds: float = 0.0,
) -> Optional[dict]:
    """One trace on a moving-time axis: ``x`` is moving minutes, ``t`` elapsed minutes.

    Raw stream values are averaged before ``transform`` runs, so a non-linear
    transform such as speed to pace averages speed rather than letting one slow
    sample blow up a bucket's pace.
    """
    if not values or not time_stream:
        return None
    points = []
    for index, raw_value in enumerate(values):
        if raw_value is None or index >= len(time_stream):
            continue
        moving_seconds = moving[index] if moving is not None and index < len(moving) else None
        if moving is not None and moving_seconds is None:
            continue
        try:
            elapsed_minutes = float(time_stream[index]) / 60.0
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        x = moving_seconds / 60.0 if moving_seconds is not None else elapsed_minutes
        points.append({"x": x, "t": round(elapsed_minutes, 2), "y": value})
    if not points:
        return None
    # Peaks come from the raw stream; the drawn trace is smoothed for reading.
    y_values = [round(transform(point["y"]), 2) for point in points]
    sampled = [
        {**point, "x": round(point["x"], 2), "y": round(transform(point["y"]), 2)}
        for point in _downsample_series(_rolling_mean(points, smooth_seconds))
    ]
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "axis": "moving" if moving is not None else "elapsed",
        "points": sampled,
        "smoothing_s": smooth_seconds or None,
        "pauses": pauses or [],
        "min": round(min(y_values), 2),
        "max": round(max(y_values), 2),
        "latest": y_values[-1],
    }


def _best_effort_targets_for_activity(activity_type: Optional[str]) -> list[tuple[str, float]]:
    # Same distances as the personal best wall, so every effort can be ranked.
    if activity_type == "Run":
        return list(RUN_DISTANCES)
    if activity_type in {"Ride", "VirtualRide"}:
        return [("1K", 1000.0), *RIDE_DISTANCES]
    return []


def _sanitize_numeric_stream_pair(distance_stream: list[object], time_stream: list[object]) -> list[tuple[float, float, int]]:
    points: list[tuple[float, float, int]] = []
    last_distance = -1.0
    last_time = -1.0
    limit = min(len(distance_stream), len(time_stream))
    for index in range(limit):
        try:
            distance_value = float(distance_stream[index])
            time_value = float(time_stream[index])
        except (TypeError, ValueError):
            continue
        if distance_value < 0 or time_value < 0:
            continue
        if distance_value < last_distance or time_value < last_time:
            continue
        points.append((distance_value, time_value, index))
        last_distance = distance_value
        last_time = time_value
    return points


def _compute_best_effort_for_distance(
    distance_points: list[tuple[float, float, int]],
    target_distance_m: float,
    *,
    heartrate_stream: list[object],
    altitude_stream: list[object],
    latlng_stream: list[object],
    metric_label: str,
    metric_unit: str,
    value_transform: Callable[[float], float],
) -> Optional[dict]:
    # Find the fastest window first (linear), then summarise only that window.
    window = fastest_distance_window(distance_points, target_distance_m)
    if window is None:
        return None
    start_stream_index = window["start_index"]
    end_stream_index = window["end_index"]
    duration_s = window["duration_s"]
    start_time = window["start_s"]

    hr_values = []
    for raw_value in heartrate_stream[start_stream_index : end_stream_index + 1]:
        if raw_value is None:
            continue
        try:
            hr_values.append(float(raw_value))
        except (TypeError, ValueError):
            continue

    elevation_gain = None
    if altitude_stream:
        gain = 0.0
        previous_altitude = None
        for raw_value in altitude_stream[start_stream_index : end_stream_index + 1]:
            if raw_value is None:
                continue
            try:
                altitude_value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if previous_altitude is not None and altitude_value > previous_altitude:
                gain += altitude_value - previous_altitude
            previous_altitude = altitude_value
        elevation_gain = round(gain)

    effort = {
        "duration_s": round(duration_s, 1),
        "start_time_s": round(start_time, 1),
        "end_time_s": round(start_time + duration_s, 1),
        "start_stream_index": start_stream_index,
        "end_stream_index": end_stream_index,
        "metric_value": round(value_transform(duration_s), 2),
        "metric_unit": metric_unit,
        "metric_label": metric_label,
        "avg_hr": round(sum(hr_values) / len(hr_values)) if hr_values else None,
        "elevation_gain_m": elevation_gain,
    }
    segment_coordinates = []
    for raw_value in latlng_stream[start_stream_index : end_stream_index + 1]:
        if not isinstance(raw_value, (list, tuple)) or len(raw_value) < 2:
            continue
        try:
            segment_coordinates.append([float(raw_value[0]), float(raw_value[1])])
        except (TypeError, ValueError):
            continue
    if segment_coordinates:
        effort["route_segment"] = segment_coordinates
    return effort


def _session_tags(conn: sqlite3.Connection, activity_id: str) -> dict:
    from .what_worked import get_session_tags

    try:
        return get_session_tags(conn, activity_id)
    except sqlite3.OperationalError:
        return {"activity_id": activity_id, "verdict": None, "pre_fuel": None, "updated_at": None}


def _build_best_efforts(activity: dict, streams: Optional[dict]) -> Optional[dict]:
    if not streams:
        return None

    distance_stream = (streams.get("distance") or {}).get("data") or []
    time_stream = (streams.get("time") or {}).get("data") or []
    heartrate_stream = (streams.get("heartrate") or {}).get("data") or []
    altitude_stream = (streams.get("altitude") or {}).get("data") or []
    latlng_stream = (streams.get("latlng") or {}).get("data") or []
    distance_points = _sanitize_numeric_stream_pair(distance_stream, time_stream)
    if len(distance_points) < 2:
        return None

    total_distance_m = distance_points[-1][0]
    activity_type = activity.get("type")
    if activity_type == "Run":
        metric_label = "Pace"
        metric_unit = "min/km"
    else:
        metric_label = "Speed"
        metric_unit = "km/h"

    def effort_metric_transform(target_distance_m: float) -> Callable[[float], float]:
        if activity_type == "Run":
            return lambda duration_s: (duration_s / 60.0) / (target_distance_m / 1000.0)
        return lambda duration_s: (target_distance_m / duration_s) * 3.6

    efforts = []
    for label, target_distance_m in _best_effort_targets_for_activity(activity_type):
        if total_distance_m < target_distance_m * 0.98:
            continue
        best = _compute_best_effort_for_distance(
            distance_points,
            target_distance_m,
            heartrate_stream=heartrate_stream,
            altitude_stream=altitude_stream,
            latlng_stream=latlng_stream,
            metric_label=metric_label,
            metric_unit=metric_unit,
            value_transform=effort_metric_transform(target_distance_m),
        )
        if not best:
            continue
        efforts.append(
            {
                "label": label,
                "distance_m": round(target_distance_m, 2),
                **best,
            }
        )

    if not efforts:
        return None

    return {
        "title": "Best efforts",
        "subtitle": "Fastest rolling distance segments from this activity.",
        "metric_label": metric_label,
        "efforts": efforts,
    }


def _build_activity_stats(activity: dict, detail: Optional[dict], stream_summary: Optional[sqlite3.Row]) -> list[dict]:
    moving_time_min = detail.get("moving_time") / 60 if detail and detail.get("moving_time") is not None else activity.get("duration_min")
    elapsed_time_min = detail.get("elapsed_time") / 60 if detail and detail.get("elapsed_time") is not None else None
    average_speed_kmh = detail.get("average_speed") * 3.6 if detail and detail.get("average_speed") is not None else None
    if average_speed_kmh is None and moving_time_min and activity.get("distance_km") is not None:
        average_speed_kmh = float(activity["distance_km"]) / (float(moving_time_min) / 60)
    max_speed_kmh = detail.get("max_speed") * 3.6 if detail and detail.get("max_speed") is not None else None
    weighted_avg_watts = detail.get("weighted_average_watts") if detail else None
    average_cadence = detail.get("average_cadence") if detail else None
    kilojoules = detail.get("kilojoules") if detail else None
    stats = [
        {"key": "distance_km", "label": "Distance", "value": activity.get("distance_km"), "unit": "km"},
        {"key": "moving_time_min", "label": "Moving time", "value": round(moving_time_min, 1) if moving_time_min is not None else None, "unit": "min"},
        {"key": "elapsed_time_min", "label": "Elapsed time", "value": round(elapsed_time_min, 1) if elapsed_time_min is not None else None, "unit": "min"},
        {"key": "avg_pace", "label": "Avg pace", "value": activity.get("avg_pace"), "unit": None},
        {"key": "avg_speed_kmh", "label": "Avg speed", "value": round(average_speed_kmh, 1) if average_speed_kmh is not None else None, "unit": "km/h"},
        {"key": "avg_hr", "label": "Avg HR", "value": activity.get("avg_hr"), "unit": "bpm"},
        {"key": "max_hr", "label": "Max HR", "value": activity.get("max_hr"), "unit": "bpm"},
        {"key": "avg_watts", "label": "Avg power", "value": activity.get("avg_watts"), "unit": "W"},
        {"key": "weighted_avg_watts", "label": "Weighted power", "value": weighted_avg_watts, "unit": "W"},
        {"key": "normalized_power", "label": "Normalized power", "value": stream_summary["normalized_power"] if stream_summary else None, "unit": "W"},
        {"key": "average_cadence", "label": "Cadence", "value": round(average_cadence, 1) if average_cadence is not None else None, "unit": "rpm"},
        {"key": "elevation_m", "label": "Elevation", "value": activity.get("elevation_m"), "unit": "m"},
        {"key": "max_speed_kmh", "label": "Max speed", "value": round(max_speed_kmh, 1) if max_speed_kmh is not None else None, "unit": "km/h"},
        {"key": "kilojoules", "label": "Work", "value": round(kilojoules) if kilojoules is not None else None, "unit": "kJ"},
        {"key": "calories", "label": "Calories", "value": activity.get("calories"), "unit": "kcal"},
    ]
    return [item for item in stats if item["value"] not in (None, "")]


def _build_activity_charts(activity: dict, detail: Optional[dict], streams: Optional[dict]) -> list[dict]:
    if not detail and not streams:
        return []
    streams = streams or {}
    time_stream = (streams.get("time") or {}).get("data") or []
    velocity_stream = (streams.get("velocity_smooth") or {}).get("data") or []
    # Trainer rides report zero speed while pedalling, so only gaps count as pauses there.
    indoor = activity.get("type") == "VirtualRide" or (isinstance(detail, dict) and detail.get("trainer") is True)
    moving, pauses = _moving_timeline(time_stream, [] if indoor else velocity_stream)
    timeline = {"moving": moving, "pauses": pauses}
    charts = []
    if activity.get("type") == "Run":
        pace_chart = _build_stream_chart(
            "pace",
            "Pace",
            "min/km",
            (streams.get("velocity_smooth") or {}).get("data") or [],
            time_stream,
            transform=lambda value: 1000 / value / 60 if value > 0 else 0,
            smooth_seconds=PACE_SMOOTHING_SECONDS,
            **timeline,
        )
        if pace_chart:
            charts.append(pace_chart)
    else:
        speed_chart = _build_stream_chart(
            "speed",
            "Speed",
            "km/h",
            (streams.get("velocity_smooth") or {}).get("data") or [],
            time_stream,
            transform=lambda value: value * 3.6,
            smooth_seconds=SPEED_SMOOTHING_SECONDS,
            **timeline,
        )
        if speed_chart:
            charts.append(speed_chart)

    for key, label, unit in [
        ("heartrate", "Heart rate", "bpm"),
        ("altitude", "Elevation", "m"),
        ("watts", "Power", "W"),
        ("cadence", "Cadence", "rpm"),
        ("grade_smooth", "Grade", "%"),
    ]:
        chart = _build_stream_chart(
            key,
            label,
            unit,
            (streams.get(key) or {}).get("data") or [],
            time_stream,
            **timeline,
        )
        if chart:
            charts.append(chart)
    return charts


def _strength_target_reps(strength_detail: dict) -> dict[str, list]:
    targets = {}
    for exercise in (strength_detail.get("session") or {}).get("exercises", []):
        working = [item for item in exercise.get("sets", []) if not item.get("is_warmup") and (item.get("reps") or 0) > 0]
        key = "".join(ch for ch in exercise["exercise_name"].lower() if ch.isalnum())
        targets[key] = [item.get("target_reps") for item in working]
    return targets


def _build_activity_detail_payload(
    conn: sqlite3.Connection,
    activity_row: sqlite3.Row,
    detail_row: Optional[sqlite3.Row],
    *,
    cache_status_override: Optional[str] = None,
) -> dict:
    activity = dict(activity_row)
    performance_settings = get_performance_settings_for_conn(conn)
    normalized_intent = normalize_workout_intent(activity.get("workout_intent"), activity.get("type"))
    activity["workout_intent"] = normalized_intent
    activity["workout_intent_label"] = format_workout_intent_label(normalized_intent)
    benchmark_lookup = build_benchmark_session_lookup(conn)
    activity = attach_benchmark_from_lookup(activity, benchmark_lookup)
    activity = _attach_strength_plan_identity(conn, activity)

    detail = _load_json_blob(detail_row["detail_json"]) if detail_row else None
    streams = _load_json_blob(detail_row["streams_json"]) if detail_row else None
    route_polyline = _extract_route_polyline(detail, streams, detail_row["route_polyline"] if detail_row else None)
    cached_charts = _load_json_blob(detail_row["charts_json"]) if detail_row and "charts_json" in detail_row.keys() else None
    cached_best_efforts = _load_json_blob(detail_row["best_efforts_json"]) if detail_row and "best_efforts_json" in detail_row.keys() else None
    derived_version = detail_row["derived_version"] if detail_row and "derived_version" in detail_row.keys() else None
    stream_summary = conn.execute(
        """
        SELECT activity_id, fetched_at, source, hr_trimp, power_tss, normalized_power
        FROM activity_stream_summaries
        WHERE activity_id = ?
        """,
        (activity["id"],),
    ).fetchone()
    source_status = cache_status_override or ("cached" if detail_row else ("summary_only" if not _is_strava_backed_activity(activity["id"]) else "not_cached"))
    feedback = get_activity_feedback_data(conn, activity["id"])
    strength_detail = None
    sick_session = guided_session_for_activity(conn, activity["id"])
    if activity.get("type") == "WeightTraining" and not sick_session:
        strength_detail = (
            get_trainlog_strength_detail_for_activity(conn, activity["id"])
            or get_fitbod_strength_detail_for_activity(conn, activity["id"])
            or {"status": "not_linked"}
        )
        if strength_detail.get("status") == "enriched":
            strength_detail["progression"] = build_strength_progression(
                conn, activity["id"], _strength_target_reps(strength_detail)
            )
    linked_planned_session = None
    planned_session_match = activity.get("planned_strength_identity")
    execution_quality = None
    planned_session_id = (planned_session_match or {}).get("session_id")
    if planned_session_id:
        linked_planned_session = find_planned_session_by_id(conn, planned_session_id)
        if linked_planned_session:
            execution_quality = build_execution_quality_for_completed_session(conn, linked_planned_session, [activity])
    if detail_row and derived_version == DETAIL_DERIVED_VERSION:
        charts = cached_charts if isinstance(cached_charts, list) else []
        best_efforts = cached_best_efforts if isinstance(cached_best_efforts, dict) else None
    else:
        charts = _build_activity_charts(activity, detail, streams)
        best_efforts = _build_best_efforts(activity, streams)
        if detail_row:
            update_activity_detail_derived_row(
                conn,
                activity["id"],
                charts_json=json.dumps(charts),
                best_efforts_json=json.dumps(best_efforts) if best_efforts else None,
                derived_version=DETAIL_DERIVED_VERSION,
            )
            conn.commit()

    return {
        "activity": activity,
        "stats": _build_activity_stats(activity, detail, stream_summary),
        "heart_rate_zones": build_activity_heart_rate_zone_summary(
            conn,
            activity,
            detail_row,
            settings=performance_settings,
        ),
        "power_zones": build_activity_power_zone_summary(conn, activity, detail_row),
        "cycling": build_ride_detail(conn, activity, detail_row, stream_summary),
        "charts": charts,
        "best_efforts": best_efforts,
        "feedback": feedback,
        "session_tags": _session_tags(conn, activity["id"]),
        "route": {
            "polyline": route_polyline,
            "has_stream_latlng": bool((streams or {}).get("latlng", {}).get("data")),
        },
        "cache": {
            "status": source_status,
            "fetched_at": detail_row["fetched_at"] if detail_row else None,
            "is_cached": bool(detail_row),
        },
        "source_stream_summary": dict(stream_summary) if stream_summary else None,
        "detail_available": bool(detail_row and (detail or streams or route_polyline)),
        "strength_detail": strength_detail,
        "sick_session": sick_session,
        "linked_planned_session": linked_planned_session,
        "planned_session_match": planned_session_match,
        "execution_quality": execution_quality,
    }


def _attach_analysis(conn: sqlite3.Connection, payload: dict) -> None:
    payload["analysis"] = get_activity_analysis_snapshot(conn, payload)
    payload["win"] = build_session_win(conn, payload, payload["analysis"].get("session_read"))


def get_activity_detail_data(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    get_strava_access_token_fn: Callable[[Callable[[str], Optional[str]], Callable[[str, str], None]], str],
    fetch_strava_activity_detail_fn: Callable[[object, str], tuple[Optional[dict], Optional[dict]]],
    fetch_strava_activity_streams_fn: Callable[[object, str, str], tuple[Optional[dict], Optional[dict]]],
) -> dict:
    activity_row = get_activity_row(conn, activity_id)
    if not activity_row:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_id}")

    detail_row = get_activity_detail_row(conn, activity_id)
    if detail_row:
        payload = _build_activity_detail_payload(conn, activity_row, detail_row)
        _attach_analysis(conn, payload)
        return payload

    if not _is_strava_backed_activity(activity_id):
        payload = _build_activity_detail_payload(conn, activity_row, None)
        _attach_analysis(conn, payload)
        return payload

    import httpx

    access_token = get_strava_access_token_fn(get_setting_fn, set_setting_fn)
    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {access_token}"}) as client:
        detail, _ = fetch_strava_activity_detail_fn(client, activity_id)
        streams, _ = fetch_strava_activity_streams_fn(
            client,
            activity_id,
            "time,distance,latlng,altitude,heartrate,watts,velocity_smooth,cadence,grade_smooth",
        )

    if not detail and not streams:
        payload = _build_activity_detail_payload(conn, activity_row, None)
        _attach_analysis(conn, payload)
        return payload

    fetched_at = datetime.now().isoformat()
    source_status = "fetched"
    activity_payload = dict(activity_row)
    cached_charts = _build_activity_charts(activity_payload, detail, streams)
    cached_best_efforts = _build_best_efforts(activity_payload, streams)
    upsert_activity_detail_row(
        conn,
        activity_id=activity_id,
        fetched_at=fetched_at,
        source_status=source_status,
        detail_json=json.dumps(detail) if detail else None,
        streams_json=json.dumps(streams) if streams else None,
        charts_json=json.dumps(cached_charts),
        best_efforts_json=json.dumps(cached_best_efforts) if cached_best_efforts else None,
        derived_version=DETAIL_DERIVED_VERSION,
        route_polyline=_extract_route_polyline(detail, streams, None),
    )
    conn.commit()
    detail_row = get_activity_detail_row(conn, activity_id)
    payload = _build_activity_detail_payload(conn, activity_row, detail_row, cache_status_override="fetched")
    _attach_analysis(conn, payload)
    return payload


def analyze_activity_data(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    force_refresh: bool,
    question: Optional[str] = None,
    question_set: bool = False,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    get_strava_access_token_fn: Callable[[Callable[[str], Optional[str]], Callable[[str, str], None]], str],
    fetch_strava_activity_detail_fn: Callable[[object, str], tuple[Optional[dict], Optional[dict]]],
    fetch_strava_activity_streams_fn: Callable[[object, str, str], tuple[Optional[dict], Optional[dict]]],
) -> dict:
    detail_payload = get_activity_detail_data(
        conn,
        activity_id,
        get_setting_fn=get_setting_fn,
        set_setting_fn=set_setting_fn,
        get_strava_access_token_fn=get_strava_access_token_fn,
        fetch_strava_activity_detail_fn=fetch_strava_activity_detail_fn,
        fetch_strava_activity_streams_fn=fetch_strava_activity_streams_fn,
    )
    extra = {"question": question} if question_set else {}
    return request_activity_analysis(conn, detail_payload, force_refresh=force_refresh, requested_via="app", **extra)


def get_activity_analysis_context_data(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    get_strava_access_token_fn: Callable[[Callable[[str], Optional[str]], Callable[[str, str], None]], str],
    fetch_strava_activity_detail_fn: Callable[[object, str], tuple[Optional[dict], Optional[dict]]],
    fetch_strava_activity_streams_fn: Callable[[object, str, str], tuple[Optional[dict], Optional[dict]]],
) -> dict:
    detail_payload = get_activity_detail_data(
        conn,
        activity_id,
        get_setting_fn=get_setting_fn,
        set_setting_fn=set_setting_fn,
        get_strava_access_token_fn=get_strava_access_token_fn,
        fetch_strava_activity_detail_fn=fetch_strava_activity_detail_fn,
        fetch_strava_activity_streams_fn=fetch_strava_activity_streams_fn,
    )
    return get_activity_analysis_context_payload(conn, detail_payload)


def save_activity_analysis_data(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    headline: str,
    summary: str,
    key_observations: list[str],
    limitations: list[str],
    confidence_note: str,
    generator: str,
    model_name: Optional[str],
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    get_strava_access_token_fn: Callable[[Callable[[str], Optional[str]], Callable[[str, str], None]], str],
    fetch_strava_activity_detail_fn: Callable[[object, str], tuple[Optional[dict], Optional[dict]]],
    fetch_strava_activity_streams_fn: Callable[[object, str, str], tuple[Optional[dict], Optional[dict]]],
) -> dict:
    detail_payload = get_activity_detail_data(
        conn,
        activity_id,
        get_setting_fn=get_setting_fn,
        set_setting_fn=set_setting_fn,
        get_strava_access_token_fn=get_strava_access_token_fn,
        fetch_strava_activity_detail_fn=fetch_strava_activity_detail_fn,
        fetch_strava_activity_streams_fn=fetch_strava_activity_streams_fn,
    )
    return save_activity_analysis(
        conn,
        detail_payload,
        headline=headline,
        summary=summary,
        key_observations=key_observations,
        limitations=limitations,
        confidence_note=confidence_note,
        generator=generator,
        model_name=model_name,
    )


def fail_activity_analysis_data(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    error_message: str,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    get_strava_access_token_fn: Callable[[Callable[[str], Optional[str]], Callable[[str, str], None]], str],
    fetch_strava_activity_detail_fn: Callable[[object, str], tuple[Optional[dict], Optional[dict]]],
    fetch_strava_activity_streams_fn: Callable[[object, str, str], tuple[Optional[dict], Optional[dict]]],
) -> dict:
    detail_payload = get_activity_detail_data(
        conn,
        activity_id,
        get_setting_fn=get_setting_fn,
        set_setting_fn=set_setting_fn,
        get_strava_access_token_fn=get_strava_access_token_fn,
        fetch_strava_activity_detail_fn=fetch_strava_activity_detail_fn,
        fetch_strava_activity_streams_fn=fetch_strava_activity_streams_fn,
    )
    return fail_activity_analysis(conn, detail_payload, error_message=error_message)


def build_calendar_weeks_data(conn: sqlite3.Connection, weeks: int = 8) -> list[dict]:
    latest_activity = get_latest_activity_date(conn)
    if latest_activity:
        anchor_date = datetime.strptime(latest_activity, "%Y-%m-%d").date()
    else:
        anchor_date = datetime.now().date()

    latest_week_start = anchor_date - timedelta(days=anchor_date.weekday())
    earliest_week_start = latest_week_start - timedelta(weeks=max(weeks - 1, 0))
    range_start = earliest_week_start
    range_end = latest_week_start + timedelta(days=6)

    rows = list_calendar_activity_rows(conn, range_start.isoformat(), range_end.isoformat())
    benchmark_lookup = build_benchmark_session_lookup(conn)

    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    output = []
    for week_index in range(weeks):
        week_start = latest_week_start - timedelta(weeks=week_index)
        output.append(build_calendar_week_payload(conn, by_date, week_start, benchmark_lookup))

    return output


def get_calendar_weeks_data(conn: sqlite3.Connection, weeks: int = 8) -> list[dict]:
    safe_weeks = max(1, min(weeks, 16))
    return build_calendar_weeks_data(conn, safe_weeks)


def build_calendar_day_payload(day: date, activities: list[sqlite3.Row], benchmark_lookup: Optional[dict[str, dict]] = None) -> dict:
    day_distance = round(sum((activity["distance_km"] or 0) for activity in activities), 1)
    day_duration = round(sum((activity["duration_min"] or 0) for activity in activities), 1)
    day_elevation = round(sum((activity["elevation_m"] or 0) for activity in activities))
    type_counts: dict[str, int] = {}

    for activity in activities:
        activity_type = activity["type"]
        type_counts[activity_type] = type_counts.get(activity_type, 0) + 1

    return {
        "date": day.isoformat(),
        "weekday": day.strftime("%a"),
        "day_of_month": day.day,
        "total_distance_km": day_distance,
        "total_duration_min": day_duration,
        "total_elevation_m": day_elevation,
        "sessions": len(activities),
        "type_counts": type_counts,
        "activities": [
            attach_benchmark_from_lookup({
                "id": activity["id"],
                "type": activity["type"],
                "workout_intent": normalize_workout_intent(activity["workout_intent"], activity["type"]),
                "workout_intent_label": format_workout_intent_label(
                    normalize_workout_intent(activity["workout_intent"], activity["type"])
                ),
                "name": activity["name"],
                "source_name": activity["source_name"],
                "distance_km": activity["distance_km"],
                "duration_min": activity["duration_min"],
                "avg_hr": activity["avg_hr"],
                "avg_pace": activity["avg_pace"],
                "avg_watts": activity["avg_watts"],
                "zone2": bool(activity["zone2"]),
                "linked_planned_session_id": activity["linked_planned_session_id"],
            }, benchmark_lookup or {})
            for activity in activities
        ],
    }


def build_calendar_week_payload(
    conn: sqlite3.Connection,
    by_date: dict[str, list[sqlite3.Row]],
    week_start: date,
    benchmark_lookup: Optional[dict[str, dict]] = None,
) -> dict:
    week_end = week_start + timedelta(days=6)
    days = []
    total_duration = 0.0
    total_distance = 0.0
    total_elevation = 0
    total_sessions = 0
    run_km = 0.0
    ride_km = 0.0
    strength_sessions = 0

    for day_offset in range(7):
        day = week_start + timedelta(days=day_offset)
        activities = by_date.get(day.isoformat(), [])
        day_payload = build_calendar_day_payload(day, activities, benchmark_lookup)

        for activity in activities:
            activity_type = activity["type"]
            if activity_type == "Run":
                run_km += activity["distance_km"] or 0
            if activity_type in {"Ride", "VirtualRide"}:
                ride_km += activity["distance_km"] or 0
            if activity_type == "WeightTraining":
                strength_sessions += 1

        total_duration += day_payload["total_duration_min"]
        total_distance += day_payload["total_distance_km"]
        total_elevation += day_payload["total_elevation_m"]
        total_sessions += day_payload["sessions"]
        days.append(day_payload)

    for day in days:
        attach_feedback_by_activity_id(conn, day["activities"])

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_distance_km": round(total_distance, 1),
        "total_duration_min": round(total_duration, 1),
        "total_elevation_m": total_elevation,
        "total_sessions": total_sessions,
        "run_km": round(run_km, 1),
        "ride_km": round(ride_km, 1),
        "strength_sessions": strength_sessions,
        "days": days,
    }


def get_calendar_month_data(conn: sqlite3.Connection, month: Optional[str] = None) -> dict:
    if month:
        try:
            month_anchor = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.") from exc
    else:
        latest_activity = get_latest_activity_date(conn)
        if latest_activity:
            month_anchor = datetime.strptime(latest_activity, "%Y-%m-%d").date().replace(day=1)
        else:
            today = datetime.now().date()
            month_anchor = today.replace(day=1)

    month_start = month_anchor.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    grid_start = month_start - timedelta(days=month_start.weekday())
    grid_end = month_end + timedelta(days=(6 - month_end.weekday()))

    rows = list_calendar_activity_rows(conn, grid_start.isoformat(), grid_end.isoformat())
    benchmark_lookup = build_benchmark_session_lookup(conn)
    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        weeks.append(build_calendar_week_payload(conn, by_date, cursor, benchmark_lookup))
        cursor += timedelta(days=7)

    month_days = [day for week in weeks for day in week["days"] if month_start.isoformat() <= day["date"] <= month_end.isoformat()]

    return {
        "month": month_start.strftime("%Y-%m"),
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "weeks": weeks,
        "total_sessions": sum(day["sessions"] for day in month_days),
        "total_duration_min": round(sum(day["total_duration_min"] for day in month_days), 1),
        "total_distance_km": round(sum(day["total_distance_km"] for day in month_days), 1),
        "total_elevation_m": round(sum(day["total_elevation_m"] for day in month_days)),
    }


def upsert_activity(conn: sqlite3.Connection, activity: dict, preserve_annotations: bool = False) -> None:
    upsert_activity_row(conn, activity, preserve_annotations=preserve_annotations)


def linked_planned_session_exists(conn: sqlite3.Connection, planned_session_id: str) -> bool:
    for row in list_weekly_plan_rows(conn, 1000):
        days = ensure_plan_day_ids(row["week_start"], json.loads(row["days_json"]))
        if any(day.get("session_id") == planned_session_id for day in days):
            return True
    return False


def link_activity_to_planned_session_data(
    conn: sqlite3.Connection,
    activity_id: str,
    planned_session_id: Optional[str],
) -> dict:
    activity_row = get_activity_row(conn, activity_id)
    if not activity_row:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_id}")

    if planned_session_id and not linked_planned_session_exists(conn, planned_session_id):
        raise HTTPException(status_code=404, detail=f"Planned session not found: {planned_session_id}")

    update_activity_linked_session_id(conn, activity_id, planned_session_id)
    reconcile_workout_template_rotation_state(conn)
    conn.commit()

    updated = get_activity_row(conn, activity_id)
    return dict(updated) if updated else {"status": "ok", "id": activity_id, "linked_planned_session_id": planned_session_id}


def update_activity_workout_intent_data(
    conn: sqlite3.Connection,
    activity_id: str,
    workout_intent: Optional[str],
) -> dict:
    activity_row = get_activity_row(conn, activity_id)
    if not activity_row:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_id}")

    normalized_intent = normalize_workout_intent(workout_intent, activity_row["type"])
    if workout_intent and not normalized_intent:
        raise HTTPException(status_code=400, detail=f"Invalid workout_intent for activity type {activity_row['type']}")

    update_activity_workout_intent(conn, activity_id, normalized_intent)
    conn.commit()

    updated = get_activity_row(conn, activity_id)
    if not updated:
        return {"status": "ok", "id": activity_id, "workout_intent": normalized_intent}

    response = dict(updated)
    response["workout_intent"] = normalized_intent
    response["workout_intent_label"] = format_workout_intent_label(normalized_intent)
    return response
