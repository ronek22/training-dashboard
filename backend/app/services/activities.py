import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

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
from .activity_feedback import attach_feedback_by_activity_id
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
