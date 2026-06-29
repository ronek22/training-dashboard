import json
import sqlite3
from datetime import datetime, timedelta
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
from .plans import ensure_plan_day_ids, format_workout_intent_label, normalize_workout_intent


def create_activity_data(conn: sqlite3.Connection, activity: dict) -> dict:
    upsert_activity_row(conn, activity)
    conn.commit()
    return {"status": "ok", "id": activity["id"]}


def list_activities_data(
    conn: sqlite3.Connection,
    limit: int = 50,
    activity_type: Optional[str] = None,
    days: Optional[int] = None,
) -> list[dict]:
    rows = list_activity_rows(conn, limit=limit, activity_type=activity_type, days=days)
    payload = []
    for row in rows:
        item = dict(row)
        normalized_intent = normalize_workout_intent(item.get("workout_intent"), item.get("type"))
        item["workout_intent"] = normalized_intent
        item["workout_intent_label"] = format_workout_intent_label(normalized_intent)
        payload.append(item)
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

    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    output = []
    for week_index in range(weeks):
        week_start = latest_week_start - timedelta(weeks=week_index)
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
            day_key = day.isoformat()
            activities = by_date.get(day_key, [])
            day_distance = round(sum((activity["distance_km"] or 0) for activity in activities), 1)
            day_duration = round(sum((activity["duration_min"] or 0) for activity in activities), 1)
            day_elevation = round(sum((activity["elevation_m"] or 0) for activity in activities))
            type_counts: dict[str, int] = {}

            for activity in activities:
                activity_type = activity["type"]
                type_counts[activity_type] = type_counts.get(activity_type, 0) + 1
                if activity_type == "Run":
                    run_km += activity["distance_km"] or 0
                if activity_type in {"Ride", "VirtualRide"}:
                    ride_km += activity["distance_km"] or 0
                if activity_type == "WeightTraining":
                    strength_sessions += 1

            total_duration += day_duration
            total_distance += day_distance
            total_elevation += day_elevation
            total_sessions += len(activities)

            days.append(
                {
                    "date": day_key,
                    "weekday": day.strftime("%a"),
                    "total_distance_km": day_distance,
                    "total_duration_min": day_duration,
                    "total_elevation_m": day_elevation,
                    "sessions": len(activities),
                    "type_counts": type_counts,
                    "activities": [
                        {
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
                        }
                        for activity in activities
                    ],
                }
            )

        output.append(
            {
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
        )

    for week in output:
        for day in week["days"]:
            attach_feedback_by_activity_id(conn, day["activities"])

    return output


def get_calendar_weeks_data(conn: sqlite3.Connection, weeks: int = 8) -> list[dict]:
    safe_weeks = max(1, min(weeks, 16))
    return build_calendar_weeks_data(conn, safe_weeks)


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
