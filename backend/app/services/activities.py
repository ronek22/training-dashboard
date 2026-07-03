import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from fastapi import HTTPException

from ..repositories.activity_details import get_activity_detail_row, upsert_activity_detail_row
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
from .activity_feedback import attach_feedback_by_activity_id, get_activity_feedback_data
from .benchmarks import attach_benchmark_from_lookup, build_benchmark_session_lookup
from .plans import ensure_plan_day_ids, format_workout_intent_label, normalize_workout_intent
from .settings import get_workout_template_settings_for_conn, set_workout_template_settings_for_conn


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
        SELECT id, date, type, name, linked_planned_session_id
        FROM activities
        ORDER BY date ASC, created_at ASC, id ASC
        """
    ).fetchall()

    changed = False
    for row in rows:
        activity_id = row["id"]
        if activity_id in processed_lookup:
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
        payload.append(attach_benchmark_from_lookup(item, benchmark_lookup))
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
        return None
    return None


def _downsample_series(points: list[dict], limit: int = 180) -> list[dict]:
    if len(points) <= limit:
        return points
    step = max(len(points) / limit, 1)
    sampled = []
    index = 0.0
    while round(index) < len(points):
        sampled.append(points[int(index)])
        index += step
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def _build_stream_chart(
    key: str,
    label: str,
    unit: str,
    values: list[object],
    time_stream: list[object],
    transform: Callable[[float], float] = lambda value: value,
) -> Optional[dict]:
    if not values or not time_stream:
        return None
    points = []
    for index, raw_value in enumerate(values):
        if raw_value is None or index >= len(time_stream):
            continue
        try:
            time_value = float(time_stream[index]) / 60.0
            value = transform(float(raw_value))
        except (TypeError, ValueError):
            continue
        points.append({"x": round(time_value, 1), "y": round(value, 2)})
    if not points:
        return None
    y_values = [point["y"] for point in points]
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "points": _downsample_series(points),
        "min": round(min(y_values), 2),
        "max": round(max(y_values), 2),
        "latest": round(points[-1]["y"], 2),
    }


def _best_effort_targets_for_activity(activity_type: Optional[str]) -> list[tuple[str, float]]:
    if activity_type == "Run":
        return [
            ("400m", 400.0),
            ("1K", 1000.0),
            ("1 mile", 1609.34),
            ("5K", 5000.0),
            ("10K", 10000.0),
        ]
    if activity_type in {"Ride", "VirtualRide"}:
        return [
            ("1K", 1000.0),
            ("5K", 5000.0),
            ("10K", 10000.0),
            ("20K", 20000.0),
            ("50K", 50000.0),
        ]
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


def _interpolate_time_at_distance(left_distance: float, left_time: float, right_distance: float, right_time: float, target_distance: float) -> float:
    span = right_distance - left_distance
    if span <= 0:
        return right_time
    ratio = (target_distance - left_distance) / span
    return left_time + (right_time - left_time) * ratio


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
    if len(distance_points) < 2:
        return None

    best_effort = None
    end_index = 1
    total_points = len(distance_points)

    for start_index in range(total_points - 1):
        start_distance, start_time, start_stream_index = distance_points[start_index]
        target_end_distance = start_distance + target_distance_m

        while end_index < total_points and distance_points[end_index][0] < target_end_distance:
            end_index += 1
        if end_index >= total_points:
            break

        left_index = max(start_index, end_index - 1)
        left_distance, left_time, _ = distance_points[left_index]
        right_distance, right_time, end_stream_index = distance_points[end_index]
        end_time = _interpolate_time_at_distance(left_distance, left_time, right_distance, right_time, target_end_distance)
        duration_s = end_time - start_time
        if duration_s <= 0:
            continue

        hr_values = []
        if heartrate_stream:
            for sample_index in range(start_stream_index, min(end_stream_index + 1, len(heartrate_stream))):
                raw_value = heartrate_stream[sample_index]
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
            for sample_index in range(start_stream_index, min(end_stream_index + 1, len(altitude_stream))):
                raw_value = altitude_stream[sample_index]
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
            "end_time_s": round(end_time, 1),
            "start_stream_index": start_stream_index,
            "end_stream_index": end_stream_index,
            "metric_value": round(value_transform(duration_s), 2),
            "metric_unit": metric_unit,
            "metric_label": metric_label,
            "avg_hr": round(sum(hr_values) / len(hr_values)) if hr_values else None,
            "elevation_gain_m": elevation_gain,
        }
        if latlng_stream:
            segment_coordinates = []
            for sample_index in range(start_stream_index, min(end_stream_index + 1, len(latlng_stream))):
                raw_value = latlng_stream[sample_index]
                if not isinstance(raw_value, (list, tuple)) or len(raw_value) < 2:
                    continue
                try:
                    segment_coordinates.append([float(raw_value[0]), float(raw_value[1])])
                except (TypeError, ValueError):
                    continue
            if segment_coordinates:
                effort["route_segment"] = segment_coordinates
        if best_effort is None or effort["duration_s"] < best_effort["duration_s"]:
            best_effort = effort

    return best_effort


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
    charts = []
    if activity.get("type") == "Run":
        pace_chart = _build_stream_chart(
            "pace",
            "Pace",
            "min/km",
            (streams.get("velocity_smooth") or {}).get("data") or [],
            time_stream,
            transform=lambda value: 1000 / value / 60 if value > 0 else 0,
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
        )
        if chart:
            charts.append(chart)
    return charts


def _build_activity_detail_payload(
    conn: sqlite3.Connection,
    activity_row: sqlite3.Row,
    detail_row: Optional[sqlite3.Row],
    *,
    cache_status_override: Optional[str] = None,
) -> dict:
    activity = dict(activity_row)
    normalized_intent = normalize_workout_intent(activity.get("workout_intent"), activity.get("type"))
    activity["workout_intent"] = normalized_intent
    activity["workout_intent_label"] = format_workout_intent_label(normalized_intent)
    benchmark_lookup = build_benchmark_session_lookup(conn)
    activity = attach_benchmark_from_lookup(activity, benchmark_lookup)

    detail = _load_json_blob(detail_row["detail_json"]) if detail_row else None
    streams = _load_json_blob(detail_row["streams_json"]) if detail_row else None
    route_polyline = _extract_route_polyline(detail, streams, detail_row["route_polyline"] if detail_row else None)
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
    if activity.get("type") == "WeightTraining":
        strength_detail = get_fitbod_strength_detail_for_activity(conn, activity["id"]) or {"status": "not_linked"}

    return {
        "activity": activity,
        "stats": _build_activity_stats(activity, detail, stream_summary),
        "charts": _build_activity_charts(activity, detail, streams),
        "best_efforts": _build_best_efforts(activity, streams),
        "feedback": feedback,
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
    }


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
        return _build_activity_detail_payload(conn, activity_row, detail_row)

    if not _is_strava_backed_activity(activity_id):
        return _build_activity_detail_payload(conn, activity_row, None)

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
        return _build_activity_detail_payload(conn, activity_row, None)

    fetched_at = datetime.now().isoformat()
    source_status = "fetched"
    upsert_activity_detail_row(
        conn,
        activity_id=activity_id,
        fetched_at=fetched_at,
        source_status=source_status,
        detail_json=json.dumps(detail) if detail else None,
        streams_json=json.dumps(streams) if streams else None,
        route_polyline=_extract_route_polyline(detail, streams, None),
    )
    conn.commit()
    detail_row = get_activity_detail_row(conn, activity_id)
    return _build_activity_detail_payload(conn, activity_row, detail_row, cache_status_override="fetched")


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
