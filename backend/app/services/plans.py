import json
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment, WeeklyPlanDay, WeeklyPlanRevision
from ..repositories.plans import (
    count_weekly_plan_revision_rows,
    create_weekly_plan_revision_row,
    get_latest_weekly_plan_revision_row,
    get_weekly_plan_row,
    list_weekly_plan_rows,
    upsert_weekly_plan_row,
)


def parse_plan_date(value: str):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}. Use YYYY-MM-DD.") from exc


def normalize_plan_session_type(session_type: Optional[str]) -> Optional[str]:
    if not session_type:
        return None
    normalized = session_type.strip().lower()
    mapping = {
        "run": "Run",
        "ride": "Ride",
        "cycling": "Ride",
        "bike": "Ride",
        "strength": "WeightTraining",
        "weights": "WeightTraining",
        "recovery": "Recovery",
        "rest": "Rest",
        "walk": "Walk",
        "hike": "Hike",
    }
    return mapping.get(normalized, session_type)


def is_past_or_today(day_value: Optional[str]) -> bool:
    if not day_value:
        return False
    try:
        day = datetime.strptime(day_value, "%Y-%m-%d").date()
    except ValueError:
        return False
    return day <= datetime.now().date()


def append_plan_note(existing_notes: Optional[str], adjustment_reason: Optional[str], effective_from: str) -> Optional[str]:
    adjustment_stamp = f"Adjusted from {effective_from}"
    if adjustment_reason:
        adjustment_stamp = f"{adjustment_stamp}: {adjustment_reason}"
    if existing_notes:
        return f"{existing_notes}\n{adjustment_stamp}"
    return adjustment_stamp


def build_activity_summary(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "type": row["type"],
        "name": row["name"],
        "distance_km": row["distance_km"],
        "duration_min": row["duration_min"],
        "avg_pace": row["avg_pace"],
        "avg_watts": row["avg_watts"],
    }


def find_moved_session(day: dict, by_date: dict[str, list[sqlite3.Row]], week_days_by_date: dict[str, dict]) -> Optional[dict]:
    planned_type = normalize_plan_session_type(day.get("session_type"))
    if not planned_type or not is_past_or_today(day.get("date")):
        return None

    day_date = datetime.strptime(day["date"], "%Y-%m-%d").date()
    for offset in (-2, -1, 1, 2):
        nearby_date = day_date.fromordinal(day_date.toordinal() + offset).isoformat()
        nearby_day = week_days_by_date.get(nearby_date)
        if not nearby_day:
            continue
        nearby_planned_type = normalize_plan_session_type(nearby_day.get("session_type"))
        if nearby_planned_type == planned_type:
            continue

        matches = [
            build_activity_summary(row)
            for row in by_date.get(nearby_date, [])
            if normalize_plan_session_type(row["type"]) == planned_type
        ]
        if matches:
            return {"date": nearby_date, "activities": matches}

    return None


def build_plan_day_comparison(day: dict, activities: list[sqlite3.Row], by_date: dict[str, list[sqlite3.Row]], week_days_by_date: dict[str, dict]) -> dict:
    planned_type = normalize_plan_session_type(day.get("session_type"))
    completed = [build_activity_summary(row) for row in activities]

    if not completed:
        moved_session = find_moved_session(day, by_date, week_days_by_date)
        if moved_session:
            return {
                "status": "moved",
                "label": f"Moved to {moved_session['date']}",
                "planned_type": planned_type,
                "completed_activities": moved_session["activities"],
                "moved_to_date": moved_session["date"],
            }

        if is_past_or_today(day.get("date")):
            return {
                "status": "skipped",
                "label": "Skipped",
                "planned_type": planned_type,
                "completed_activities": [],
            }
        return {
            "status": "not_completed_yet",
            "label": "Not completed yet",
            "planned_type": planned_type,
            "completed_activities": [],
        }

    completed_types = {item["type"] for item in completed}
    total_duration = sum((item["duration_min"] or 0) for item in completed)
    target_duration = day.get("target_duration_min")

    if planned_type in {"Rest", "Recovery"}:
        label = "Recovery changed" if planned_type == "Recovery" else "Rest day changed"
        return {
            "status": "rest_day_changed",
            "label": label,
            "planned_type": planned_type,
            "completed_activities": completed,
        }

    if planned_type in completed_types:
        if target_duration and total_duration < (target_duration * 0.6):
            status = "partially_matched"
            label = "Partially matched"
        else:
            status = "matched"
            label = "Matched"
    else:
        status = "replaced"
        label = "Replaced"

    return {
        "status": status,
        "label": label,
        "planned_type": planned_type,
        "completed_activities": completed,
    }


def serialize_weekly_plan_revision_row(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": row["id"],
        "week_start": row["week_start"],
        "effective_from": row["effective_from"],
        "adaptation_reason": row["adaptation_reason"],
        "changed_dates": json.loads(row["changed_dates_json"]),
        "preserved_dates": json.loads(row["preserved_dates_json"]),
        "created_at": row["created_at"],
    }


def serialize_weekly_plan(row: sqlite3.Row, conn: Optional[sqlite3.Connection] = None) -> dict:
    days = json.loads(row["days_json"])
    latest_revision = None
    revision_count = 0
    if conn:
        week_days_by_date = {day["date"]: day for day in days if day.get("date")}
        dates = [day["date"] for day in days if day.get("date")]
        by_date: dict[str, list[sqlite3.Row]] = {}
        if dates:
            placeholders = ",".join("?" for _ in dates)
            activity_rows = conn.execute(
                f"""
                SELECT id, date, type, name, distance_km, duration_min, avg_pace, avg_watts
                FROM activities
                WHERE date IN ({placeholders})
                ORDER BY date ASC, created_at DESC
                """,
                dates,
            ).fetchall()
            for activity in activity_rows:
                by_date.setdefault(activity["date"], []).append(activity)

        enriched_days = []
        for day in days:
            comparison = build_plan_day_comparison(day, by_date.get(day.get("date"), []), by_date, week_days_by_date)
            enriched_day = dict(day)
            enriched_day["comparison"] = comparison
            enriched_days.append(enriched_day)
        days = enriched_days
        latest_revision = serialize_weekly_plan_revision_row(get_latest_weekly_plan_revision_row(conn, row["week_start"]))
        revision_count = count_weekly_plan_revision_rows(conn, row["week_start"])

    return {
        "week_start": row["week_start"],
        "title": row["title"],
        "focus": row["focus"],
        "overview": row["overview"],
        "days": days,
        "notes": row["notes"],
        "created_at": row["created_at"],
        "revision_count": revision_count,
        "latest_revision": latest_revision,
    }


def list_weekly_plans_data(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = list_weekly_plan_rows(conn, limit)
    return [serialize_weekly_plan(row, conn) for row in rows]


def adjust_weekly_plan_data(conn: sqlite3.Connection, adjustment: WeeklyPlanAdjustment) -> dict:
    plan_row = get_weekly_plan_row(conn, adjustment.week_start)
    if not plan_row:
        raise HTTPException(status_code=404, detail=f"Weekly plan not found for {adjustment.week_start}")

    existing_plan = WeeklyPlan(
        week_start=plan_row["week_start"],
        title=plan_row["title"],
        focus=plan_row["focus"],
        overview=plan_row["overview"],
        days=[WeeklyPlanDay(**day) for day in json.loads(plan_row["days_json"])],
        notes=plan_row["notes"],
    )
    if not existing_plan.days:
        raise HTTPException(status_code=400, detail="Weekly plan has no days to adjust")

    week_dates = {day.date for day in existing_plan.days}
    effective_from = adjustment.effective_from or datetime.now().date().isoformat()
    parse_plan_date(effective_from)

    if effective_from not in week_dates:
        raise HTTPException(
            status_code=400,
            detail=f"effective_from {effective_from} is outside plan week {adjustment.week_start}",
        )

    incoming_by_date: dict[str, WeeklyPlanDay] = {}
    for day in adjustment.days:
        parse_plan_date(day.date)
        if day.date not in week_dates:
            raise HTTPException(
                status_code=400,
                detail=f"Adjusted day {day.date} is outside plan week {adjustment.week_start}",
            )
        if day.date < effective_from:
            raise HTTPException(
                status_code=400,
                detail=f"Adjusted day {day.date} is before effective_from {effective_from}",
            )
        if day.date in incoming_by_date:
            raise HTTPException(status_code=400, detail=f"Duplicate adjusted day {day.date}")
        incoming_by_date[day.date] = day

    week_end = max(week_dates)
    activity_rows = conn.execute(
        """
        SELECT DISTINCT date
        FROM activities
        WHERE date >= ? AND date <= ?
        """,
        (adjustment.week_start, week_end),
    ).fetchall()
    completed_dates = {row["date"] for row in activity_rows}

    protected_dates = {
        day.date
        for day in existing_plan.days
        if day.date < effective_from or day.date in completed_dates
    }
    conflicting_dates = sorted(protected_dates.intersection(incoming_by_date.keys()))
    if conflicting_dates:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot adjust protected days with completed or past sessions: {', '.join(conflicting_dates)}",
        )

    merged_days: list[WeeklyPlanDay] = []
    changed_dates: list[str] = []
    for day in sorted(existing_plan.days, key=lambda item: item.date):
        replacement = incoming_by_date.get(day.date)
        final_day = day if day.date in protected_dates or replacement is None else replacement
        merged_days.append(final_day)
        if final_day.model_dump() != day.model_dump():
            changed_dates.append(day.date)

    updated_plan = WeeklyPlan(
        week_start=existing_plan.week_start,
        title=adjustment.title if adjustment.title is not None else existing_plan.title,
        focus=adjustment.focus if adjustment.focus is not None else existing_plan.focus,
        overview=adjustment.overview if adjustment.overview is not None else existing_plan.overview,
        days=merged_days,
        notes=adjustment.notes if adjustment.notes is not None else append_plan_note(existing_plan.notes, adjustment.adaptation_reason, effective_from),
    )

    create_weekly_plan_revision_row(
        conn,
        WeeklyPlanRevision(
            week_start=existing_plan.week_start,
            effective_from=effective_from,
            adaptation_reason=adjustment.adaptation_reason,
            changed_dates=changed_dates,
            preserved_dates=sorted(protected_dates),
            previous_plan=existing_plan,
            updated_plan=updated_plan,
        ),
    )
    upsert_weekly_plan_row(conn, updated_plan)
    conn.commit()

    updated_row = get_weekly_plan_row(conn, adjustment.week_start)
    return {
        "status": "ok",
        "week_start": adjustment.week_start,
        "effective_from": effective_from,
        "changed_dates": changed_dates,
        "preserved_dates": sorted(protected_dates),
        "latest_revision": serialize_weekly_plan_revision_row(get_latest_weekly_plan_revision_row(conn, adjustment.week_start)),
        "plan": serialize_weekly_plan(updated_row, conn) if updated_row else None,
    }
