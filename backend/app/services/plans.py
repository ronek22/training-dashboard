from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from .goals import serialize_goal
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment, WeeklyPlanDay, WeeklyPlanRevision
from ..repositories.plans import (
    count_weekly_plan_revision_rows,
    create_weekly_plan_revision_row,
    get_latest_weekly_plan_revision_row,
    get_weekly_plan_row,
    list_weekly_plan_rows,
    upsert_weekly_plan_row,
)

WORKOUT_INTENT_ALIASES = {
    "recovery": "recovery",
    "easy": "easy",
    "endurance": "easy",
    "long": "long",
    "tempo": "tempo",
    "steady": "tempo",
    "interval": "interval",
    "intervals": "interval",
    "race_specific": "race_specific",
    "race-specific": "race_specific",
    "strength_general": "strength_general",
    "general_strength": "strength_general",
    "strength_lower": "strength_lower",
    "lower_strength": "strength_lower",
    "strength_upper": "strength_upper",
    "upper_strength": "strength_upper",
    "mobility": "mobility",
}

SESSION_TYPE_INTENT_OPTIONS = {
    "Run": {"recovery", "easy", "long", "tempo", "interval", "race_specific"},
    "Ride": {"recovery", "easy", "long", "tempo", "interval", "race_specific"},
    "VirtualRide": {"recovery", "easy", "long", "tempo", "interval", "race_specific"},
    "WeightTraining": {"strength_general", "strength_lower", "strength_upper", "mobility"},
    "Walk": {"recovery", "easy", "mobility"},
    "Hike": {"easy", "long"},
    "Recovery": {"recovery", "mobility"},
    "Rest": set(),
}


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


def normalize_workout_intent(workout_intent: Optional[str], session_type: Optional[str] = None) -> Optional[str]:
    if not workout_intent:
        return None
    normalized = WORKOUT_INTENT_ALIASES.get(workout_intent.strip().lower())
    if not normalized:
        return None
    normalized_session_type = normalize_plan_session_type(session_type)
    allowed = SESSION_TYPE_INTENT_OPTIONS.get(normalized_session_type)
    if allowed is not None and allowed and normalized not in allowed:
        return None
    return normalized


def format_workout_intent_label(workout_intent: Optional[str]) -> Optional[str]:
    if not workout_intent:
        return None
    labels = {
        "recovery": "Recovery",
        "easy": "Easy",
        "long": "Long",
        "tempo": "Tempo",
        "interval": "Interval",
        "race_specific": "Race-specific",
        "strength_general": "General strength",
        "strength_lower": "Lower-body strength",
        "strength_upper": "Upper-body strength",
        "mobility": "Mobility",
    }
    return labels.get(workout_intent, workout_intent.replace("_", " ").title())


def is_past_or_today(day_value: Optional[str]) -> bool:
    if not day_value:
        return False
    try:
        day = datetime.strptime(day_value, "%Y-%m-%d").date()
    except ValueError:
        return False
    return day <= datetime.now().date()


def is_strictly_past(day_value: Optional[str]) -> bool:
    if not day_value:
        return False
    try:
        day = datetime.strptime(day_value, "%Y-%m-%d").date()
    except ValueError:
        return False
    return day < datetime.now().date()


def append_plan_note(existing_notes: Optional[str], adjustment_reason: Optional[str], effective_from: str) -> Optional[str]:
    adjustment_stamp = f"Adjusted from {effective_from}"
    if adjustment_reason:
        adjustment_stamp = f"{adjustment_stamp}: {adjustment_reason}"
    if existing_notes:
        return f"{existing_notes}\n{adjustment_stamp}"
    return adjustment_stamp


def serialize_plan_day(day: dict | WeeklyPlanDay) -> dict:
    if isinstance(day, WeeklyPlanDay):
        payload = day.model_dump()
    else:
        payload = dict(day)
    payload["workout_intent"] = normalize_workout_intent(payload.get("workout_intent"), payload.get("session_type"))
    payload["workout_intent_label"] = format_workout_intent_label(payload.get("workout_intent"))
    return payload


def build_day_change_details(before: Optional[dict], after: Optional[dict]) -> list[dict]:
    details = []
    fields = [
        ("title", "Title"),
        ("session_type", "Session type"),
        ("workout_intent_label", "Intent"),
        ("target_duration_min", "Duration"),
        ("target_distance_km", "Distance"),
        ("details", "Details"),
    ]
    for key, label in fields:
        before_value = before.get(key) if before else None
        after_value = after.get(key) if after else None
        if before_value == after_value:
            continue
        details.append({
            "field": key,
            "label": label,
            "before": before_value,
            "after": after_value,
        })
    return details


def infer_preview_protected_dates(plan_days: list[dict], effective_from: str) -> list[str]:
    protected = []
    for day in plan_days:
        date_value = day.get("date")
        if not date_value:
            continue
        if date_value < effective_from or day.get("comparison", {}).get("completed_activities"):
            protected.append(date_value)
    return sorted(set(protected))


def build_adjustment_diff_payload(
    existing_plan: dict,
    adjustment_payload: dict,
    protected_dates: Optional[list[str]] = None,
) -> dict:
    existing_days = [serialize_plan_day(day) for day in existing_plan.get("days", [])]
    existing_by_date = {day["date"]: day for day in existing_days if day.get("date")}
    incoming_days = [serialize_plan_day(day) for day in adjustment_payload.get("days", [])]
    incoming_by_date = {day["date"]: day for day in incoming_days if day.get("date")}
    effective_from = adjustment_payload.get("effective_from") or existing_plan.get("week_start")
    protected_set = set(protected_dates or infer_preview_protected_dates(existing_days, effective_from))

    merged_days = []
    diff_days = []
    changed_dates = []
    all_dates = sorted({*existing_by_date.keys(), *incoming_by_date.keys()})
    for date_value in all_dates:
        before = existing_by_date.get(date_value)
        replacement = incoming_by_date.get(date_value)
        is_protected = date_value in protected_set

        if is_protected:
            after = before
            status = "protected"
        elif before and replacement:
            after = replacement
            status = "unchanged" if build_day_change_details(before, replacement) == [] else "edited"
        elif before and not replacement:
            after = before
            status = "unchanged"
        elif replacement and not before:
            after = replacement
            status = "added"
        else:
            continue

        if after:
            merged_days.append(after)

        changes = build_day_change_details(before, after)
        if status in {"edited", "added", "removed"}:
            changed_dates.append(date_value)

        diff_days.append({
            "date": date_value,
            "label": (after or before or {}).get("label"),
            "status": status,
            "is_protected": is_protected,
            "before": before,
            "after": after,
            "changes": changes,
        })

    summary = {
        "unchanged": sum(1 for item in diff_days if item["status"] == "unchanged"),
        "edited": sum(1 for item in diff_days if item["status"] == "edited"),
        "added": sum(1 for item in diff_days if item["status"] == "added"),
        "removed": sum(1 for item in diff_days if item["status"] == "removed"),
        "protected": sum(1 for item in diff_days if item["status"] == "protected"),
    }

    return {
        "week_start": existing_plan.get("week_start"),
        "effective_from": effective_from,
        "changed_dates": sorted(set(changed_dates)),
        "protected_dates": sorted(protected_set),
        "summary": summary,
        "days": diff_days,
        "before_plan": {
            "week_start": existing_plan.get("week_start"),
            "title": existing_plan.get("title"),
            "focus": existing_plan.get("focus"),
            "overview": existing_plan.get("overview"),
            "days": existing_days,
        },
        "after_plan": {
            "week_start": existing_plan.get("week_start"),
            "title": adjustment_payload.get("title", existing_plan.get("title")),
            "focus": adjustment_payload.get("focus", existing_plan.get("focus")),
            "overview": adjustment_payload.get("overview", existing_plan.get("overview")),
            "days": merged_days,
        },
    }


def build_activity_summary(row: sqlite3.Row) -> dict:
    normalized_intent = normalize_workout_intent(row["workout_intent"], row["type"])
    return {
        "id": row["id"],
        "date": row["date"],
        "type": row["type"],
        "workout_intent": normalized_intent,
        "workout_intent_label": format_workout_intent_label(normalized_intent),
        "name": row["name"],
        "distance_km": row["distance_km"],
        "duration_min": row["duration_min"],
        "avg_pace": row["avg_pace"],
        "avg_watts": row["avg_watts"],
        "linked_planned_session_id": row["linked_planned_session_id"],
    }


def build_planned_session_id(week_start: str, day: dict, index: int) -> str:
    date_part = day.get("date") or f"idx-{index}"
    return f"plan-{week_start}-{date_part}-{index + 1}"


def ensure_plan_day_ids(week_start: str, days: list[dict]) -> list[dict]:
    normalized_days = []
    seen_ids: set[str] = set()
    for index, day in enumerate(days):
        normalized_day = dict(day)
        session_id = normalized_day.get("session_id")
        if not session_id or session_id in seen_ids:
            session_id = build_planned_session_id(week_start, normalized_day, index)
        normalized_day["session_id"] = session_id
        normalized_day["workout_intent"] = normalize_workout_intent(
            normalized_day.get("workout_intent"),
            normalized_day.get("session_type"),
        )
        seen_ids.add(session_id)
        normalized_days.append(normalized_day)
    return normalized_days


def infer_intent_alignment(planned_intent: Optional[str], completed_activities: list[dict]) -> str:
    if not planned_intent:
        return "unknown"
    completed_intents = {item.get("workout_intent") for item in completed_activities if item.get("workout_intent")}
    if not completed_intents:
        return "unknown"
    if planned_intent in completed_intents:
        return "aligned"
    return "different"


def infer_best_completed_intent(completed_activities: list[dict]) -> Optional[str]:
    for item in completed_activities:
        if item.get("workout_intent"):
            return item["workout_intent"]
    return None


def goal_applies_to_plan(goal: dict, week_start: str, week_end: str) -> bool:
    return bool(goal.get("is_active")) and goal["start_date"] <= week_end and goal["end_date"] >= week_start


def goal_supports_session(goal: dict, day: dict) -> Optional[str]:
    metric_type = goal.get("metric_type")
    session_type = normalize_plan_session_type(day.get("session_type"))
    if not session_type:
        return None

    if metric_type == "run_km" and session_type == "Run":
        return "Builds run volume"
    if metric_type == "ride_km" and session_type in {"Ride", "VirtualRide"}:
        return "Builds ride volume"
    if metric_type == "strength_sessions" and session_type == "WeightTraining":
        return "Counts toward strength target"
    if metric_type == "activities_count":
        activity_type = goal.get("activity_type")
        if not activity_type:
            return "Counts toward activity target"
        normalized_goal_type = normalize_plan_session_type(activity_type)
        if normalized_goal_type == session_type:
            return f"Counts toward {activity_type} target"
    return None


def build_plan_goal_context(conn: sqlite3.Connection, days: list[dict], week_start: str) -> dict:
    if not days:
        return {"active_goals": [], "goal_ids": []}

    week_end = max(day["date"] for day in days if day.get("date"))
    goal_rows = conn.execute(
        """
        SELECT *
        FROM goals
        WHERE is_active = 1
        ORDER BY created_at DESC
        LIMIT 12
        """
    ).fetchall()
    active_goals = [serialize_goal(row, conn) for row in goal_rows]
    relevant_goals = [goal for goal in active_goals if goal_applies_to_plan(goal, week_start, week_end)]

    enriched_goals = []
    for goal in relevant_goals:
        supported_days = []
        for day in days:
            support_reason = goal_supports_session(goal, day)
            if support_reason:
                supported_days.append({
                    "date": day["date"],
                    "label": day.get("label"),
                    "title": day.get("title"),
                    "support_reason": support_reason,
                })
        enriched_goals.append({
            **goal,
            "supported_sessions": len(supported_days),
            "supported_days": supported_days,
        })

    return {
        "active_goals": enriched_goals,
        "goal_ids": [goal["id"] for goal in enriched_goals],
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


def build_link_candidates(day: dict, candidate_rows: list[sqlite3.Row], max_candidates: int = 6) -> list[dict]:
    day_date = day.get("date")
    planned_type = normalize_plan_session_type(day.get("session_type"))
    planned_intent = normalize_workout_intent(day.get("workout_intent"), day.get("session_type"))
    ranked = []

    for row in candidate_rows:
        try:
            distance = abs((datetime.strptime(row["date"], "%Y-%m-%d") - datetime.strptime(day_date, "%Y-%m-%d")).days)
        except ValueError:
            distance = 999
        if distance > 2 and row["linked_planned_session_id"] != day.get("session_id"):
            continue
        type_match = normalize_plan_session_type(row["type"]) == planned_type if planned_type else True
        summary = build_activity_summary(row)
        intent_match = summary.get("workout_intent") == planned_intent if planned_intent and summary.get("workout_intent") else False
        ranked.append((0 if type_match else 1, 0 if intent_match else 1, distance, row["date"], summary))

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]["id"]))
    return [item[4] for item in ranked[:max_candidates]]


def build_plan_day_comparison(
    day: dict,
    activities: list[sqlite3.Row],
    by_date: dict[str, list[sqlite3.Row]],
    week_days_by_date: dict[str, dict],
    linked_activities: list[sqlite3.Row],
) -> dict:
    planned_type = normalize_plan_session_type(day.get("session_type"))
    planned_intent = normalize_workout_intent(day.get("workout_intent"), day.get("session_type"))
    explicitly_linked = [build_activity_summary(row) for row in linked_activities]

    if explicitly_linked:
        return {
            "status": "linked",
            "label": "Linked",
            "planned_type": planned_type,
            "completed_activities": explicitly_linked,
            "matching_strategy": "explicit",
            "linked_session_id": day.get("session_id"),
            "planned_intent": planned_intent,
            "planned_intent_label": format_workout_intent_label(planned_intent),
            "intent_alignment": infer_intent_alignment(planned_intent, explicitly_linked),
        }

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
                "matching_strategy": "inferred",
                "planned_intent": planned_intent,
                "planned_intent_label": format_workout_intent_label(planned_intent),
                "intent_alignment": infer_intent_alignment(planned_intent, moved_session["activities"]),
            }

        if is_strictly_past(day.get("date")):
            return {
                "status": "skipped",
                "label": "Skipped",
                "planned_type": planned_type,
                "completed_activities": [],
                "matching_strategy": "unmatched",
                "planned_intent": planned_intent,
                "planned_intent_label": format_workout_intent_label(planned_intent),
                "intent_alignment": "unknown",
            }
        return {
            "status": "not_completed_yet",
            "label": "Not completed yet",
            "planned_type": planned_type,
            "completed_activities": [],
            "matching_strategy": "unmatched",
            "planned_intent": planned_intent,
            "planned_intent_label": format_workout_intent_label(planned_intent),
            "intent_alignment": "unknown",
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
            "matching_strategy": "inferred",
            "planned_intent": planned_intent,
            "planned_intent_label": format_workout_intent_label(planned_intent),
            "intent_alignment": infer_intent_alignment(planned_intent, completed),
        }

    if planned_type in completed_types:
        intent_alignment = infer_intent_alignment(planned_intent, completed)
        if target_duration and total_duration < (target_duration * 0.6):
            status = "partially_matched"
            label = "Partially matched"
        elif planned_intent and intent_alignment == "different":
            status = "partially_matched"
            completed_intent = infer_best_completed_intent(completed)
            if completed_intent:
                label = f"Different intent than planned {format_workout_intent_label(planned_intent).lower()}"
            else:
                label = "Intent unclear"
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
        "matching_strategy": "inferred",
        "planned_intent": planned_intent,
        "planned_intent_label": format_workout_intent_label(planned_intent),
        "intent_alignment": infer_intent_alignment(planned_intent, completed),
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
    days = ensure_plan_day_ids(row["week_start"], json.loads(row["days_json"]))
    latest_revision = None
    revision_count = 0
    goal_context = {"active_goals": [], "goal_ids": []}
    if conn:
        week_days_by_date = {day["date"]: day for day in days if day.get("date")}
        dates = [day["date"] for day in days if day.get("date")]
        session_ids = [day["session_id"] for day in days if day.get("session_id")]
        by_date: dict[str, list[sqlite3.Row]] = {}
        by_linked_session_id: dict[str, list[sqlite3.Row]] = {}
        activity_rows: list[sqlite3.Row] = []
        if dates:
            week_start_date = min(dates)
            week_end_date = max(dates)
            linked_placeholders = ",".join("?" for _ in session_ids) if session_ids else "''"
            activity_rows = conn.execute(
                f"""
                SELECT id, date, type, workout_intent, name, distance_km, duration_min, avg_pace, avg_watts, linked_planned_session_id
                FROM activities
                WHERE (
                    date >= date(?, '-2 days')
                    AND date <= date(?, '+2 days')
                )
                OR linked_planned_session_id IN ({linked_placeholders})
                ORDER BY date ASC, created_at DESC
                """,
                [week_start_date, week_end_date, *session_ids],
            ).fetchall()
            for activity in activity_rows:
                by_date.setdefault(activity["date"], []).append(activity)
                if activity["linked_planned_session_id"]:
                    by_linked_session_id.setdefault(activity["linked_planned_session_id"], []).append(activity)

        enriched_days = []
        for day in days:
            comparison = build_plan_day_comparison(
                day,
                by_date.get(day.get("date"), []),
                by_date,
                week_days_by_date,
                by_linked_session_id.get(day.get("session_id"), []),
            )
            enriched_day = dict(day)
            enriched_day["workout_intent_label"] = format_workout_intent_label(enriched_day.get("workout_intent"))
            enriched_day["comparison"] = comparison
            enriched_day["link_candidates"] = build_link_candidates(day, activity_rows)
            enriched_day["goal_links"] = []
            enriched_days.append(enriched_day)
        days = enriched_days
        goal_context = build_plan_goal_context(conn, days, row["week_start"])
        goals_by_id = {goal["id"]: goal for goal in goal_context["active_goals"]}
        for day in days:
            day["goal_links"] = [
                {
                    "goal_id": goal["id"],
                    "goal_title": goal["title"],
                    "metric_type": goal["metric_type"],
                    "period_label": goal["period_label"],
                    "support_reason": goal_supports_session(goal, day),
                    "status": goal["status"],
                }
                for goal in goals_by_id.values()
                if goal_supports_session(goal, day)
            ]
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
        "goal_context": goal_context,
    }


def list_weekly_plans_data(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = list_weekly_plan_rows(conn, limit)
    return [serialize_weekly_plan(row, conn) for row in rows]


def prepare_weekly_plan_for_storage(plan: WeeklyPlan) -> WeeklyPlan:
    normalized_days = ensure_plan_day_ids(
        plan.week_start,
        [day.model_dump() for day in plan.days],
    )
    return WeeklyPlan(
        week_start=plan.week_start,
        title=plan.title,
        focus=plan.focus,
        overview=plan.overview,
        days=[WeeklyPlanDay(**day) for day in normalized_days],
        notes=plan.notes,
    )


def upsert_weekly_plan_data(conn: sqlite3.Connection, plan: WeeklyPlan) -> dict:
    prepared_plan = prepare_weekly_plan_for_storage(plan)
    upsert_weekly_plan_row(conn, prepared_plan)
    conn.commit()
    return {"status": "ok", "week_start": prepared_plan.week_start}


def preview_weekly_plan_adjustment_data(conn: sqlite3.Connection, adjustment: WeeklyPlanAdjustment) -> dict:
    plan_row = get_weekly_plan_row(conn, adjustment.week_start)
    if not plan_row:
        raise HTTPException(status_code=404, detail=f"Weekly plan not found for {adjustment.week_start}")

    existing_plan = serialize_weekly_plan(plan_row, conn)
    effective_from = adjustment.effective_from or datetime.now().date().isoformat()
    week_dates = {day["date"] for day in existing_plan.get("days", [])}
    if effective_from not in week_dates:
        raise HTTPException(
            status_code=400,
            detail=f"effective_from {effective_from} is outside plan week {adjustment.week_start}",
        )

    diff = build_adjustment_diff_payload(
        existing_plan,
        {
            "week_start": adjustment.week_start,
            "effective_from": effective_from,
            "title": adjustment.title,
            "focus": adjustment.focus,
            "overview": adjustment.overview,
            "days": [day.model_dump() for day in adjustment.days],
        },
    )
    return {
        "status": "ok",
        "week_start": adjustment.week_start,
        "preview_only": True,
        "diff": diff,
    }


def adjust_weekly_plan_data(conn: sqlite3.Connection, adjustment: WeeklyPlanAdjustment) -> dict:
    plan_row = get_weekly_plan_row(conn, adjustment.week_start)
    if not plan_row:
        raise HTTPException(status_code=404, detail=f"Weekly plan not found for {adjustment.week_start}")

    existing_plan = prepare_weekly_plan_for_storage(WeeklyPlan(
        week_start=plan_row["week_start"],
        title=plan_row["title"],
        focus=plan_row["focus"],
        overview=plan_row["overview"],
        days=[WeeklyPlanDay(**day) for day in json.loads(plan_row["days_json"])],
        notes=plan_row["notes"],
    ))
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

    diff = build_adjustment_diff_payload(
        serialize_weekly_plan(plan_row, conn),
        {
            "week_start": adjustment.week_start,
            "effective_from": effective_from,
            "title": adjustment.title,
            "focus": adjustment.focus,
            "overview": adjustment.overview,
            "days": [day.model_dump() for day in adjustment.days],
        },
        protected_dates=sorted(protected_dates),
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
        "diff": diff,
        "latest_revision": serialize_weekly_plan_revision_row(get_latest_weekly_plan_revision_row(conn, adjustment.week_start)),
        "plan": serialize_weekly_plan(updated_row, conn) if updated_row else None,
    }
