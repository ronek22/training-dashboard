from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from .goals import build_requirement_summary, serialize_goal
from .settings import get_modality_restrictions_for_conn, modality_for_session_type
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment, WeeklyPlanDay, WeeklyPlanRevision
from ..repositories.plans import (
    count_weekly_plan_revision_rows,
    create_weekly_plan_revision_row,
    get_latest_weekly_plan_revision_row,
    get_weekly_plan_row,
    list_weekly_plan_revision_rows,
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

COACHING_ADAPTATION_REASON = "Generated from one-shot coaching guidance."


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


def _requirement_support_for_day(requirement: dict, day: dict) -> Optional[dict]:
    session_type = normalize_plan_session_type(day.get("session_type"))
    workout_intent = normalize_workout_intent(day.get("workout_intent"), session_type)
    if not session_type:
        return None

    allowed_session_types = set(requirement.get("session_types") or [])
    if allowed_session_types and session_type not in allowed_session_types:
        return None
    preferred_intents = set(requirement.get("preferred_intents") or [])
    fallback_intents = set(requirement.get("fallback_intents") or [])

    if not preferred_intents:
        return {
            "requirement_type": requirement.get("type"),
            "requirement_label": requirement.get("label"),
            "support_level": "strong",
            "support_reason": requirement.get("label"),
        }

    if workout_intent in preferred_intents:
        support_level = "strong"
    elif not workout_intent and requirement.get("type") in {"aerobic_volume", "session_frequency"}:
        support_level = "strong"
    elif workout_intent in fallback_intents or requirement.get("type") in {"aerobic_volume", "session_frequency"}:
        support_level = "weak"
    elif requirement.get("type") == "aerobic_endurance" and session_type in {"Run", "Ride", "VirtualRide"}:
        support_level = "weak"
    else:
        return None

    reason = requirement.get("label")
    if support_level == "weak":
        reason = f"Weak {reason.lower()} support"
    return {
        "requirement_type": requirement.get("type"),
        "requirement_label": requirement.get("label"),
        "support_level": support_level,
        "support_reason": reason,
    }


def goal_supports_session(goal: dict, day: dict) -> Optional[str]:
    matches = goal_requirement_matches(goal, day)
    if not matches:
        return None
    strongest = next((item for item in matches if item["support_level"] == "strong"), matches[0])
    return strongest["support_reason"]


def goal_requirement_matches(goal: dict, day: dict) -> list[dict]:
    matches = []
    for requirement in goal.get("weekly_requirements") or []:
        match = _requirement_support_for_day(requirement, day)
        if match:
            matches.append(match)
    return matches


def _build_requirement_status(requirement: dict, supporting_days: list[dict]) -> dict:
    strong_count = sum(1 for item in supporting_days if item.get("support_level") == "strong")
    weak_count = sum(1 for item in supporting_days if item.get("support_level") == "weak")
    minimum_sessions = int(requirement.get("minimum_sessions") or 1)
    if strong_count >= minimum_sessions:
        status = "supported"
    elif strong_count + weak_count >= minimum_sessions and (strong_count > 0 or weak_count > 0):
        status = "weakly_supported"
    else:
        status = "unsupported"
    return {
        **requirement,
        "strong_support_count": strong_count,
        "weak_support_count": weak_count,
        "status": status,
        "supporting_days": supporting_days,
    }


def _build_goal_conflicts(enriched_goals: list[dict]) -> list[dict]:
    if len(enriched_goals) < 2:
        return []

    conflicts: list[dict] = []
    unmet_goals = [goal for goal in enriched_goals if goal.get("requirement_support_status") in {"unsupported", "weak"}]
    primary_modalities = {
        goal.get("modality")
        for goal in enriched_goals
        if goal.get("modality") and any(item.get("priority") == "primary" for item in goal.get("requirement_statuses", []))
    }
    if len(primary_modalities) >= 2:
        conflicts.append({
            "type": "modality_pull",
            "label": "Competing modality demands",
            "summary": "Active goals are asking for key work across multiple modalities this week.",
            "goal_titles": [goal["title"] for goal in enriched_goals[:3]],
        })

    strength_goals = [
        goal for goal in enriched_goals
        if any(item.get("type") == "strength_frequency" for item in goal.get("requirement_statuses", []))
    ]
    quality_goals = [
        goal for goal in enriched_goals
        if any(item.get("type") in {"event_specific_quality", "benchmark_specific_quality"} for item in goal.get("requirement_statuses", []))
    ]
    if strength_goals and quality_goals:
        conflicts.append({
            "type": "lower_body_load",
            "label": "Quality vs strength tension",
            "summary": "Strength frequency and quality goals are both competing for the harder slots in the week.",
            "goal_titles": [strength_goals[0]["title"], quality_goals[0]["title"]],
        })

    supported_goals = [goal for goal in enriched_goals if goal.get("requirement_support_status") == "supported"]
    if unmet_goals and supported_goals:
        conflicts.append({
            "type": "deprioritized",
            "label": "Deprioritized goals",
            "summary": f"{unmet_goals[0]['title']} has weaker support while other goals are taking the clearer sessions this week.",
            "goal_titles": [goal["title"] for goal in unmet_goals[:2]],
        })

    return conflicts[:3]


def build_plan_goal_context(conn: sqlite3.Connection, days: list[dict], week_start: str) -> dict:
    if not days:
        return {"active_goals": [], "goal_ids": [], "conflicts": [], "unsupported_goal_count": 0}

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
    restrictions = get_modality_restrictions_for_conn(conn)
    active_goals = [serialize_goal(row, conn, restrictions) for row in goal_rows]
    relevant_goals = [goal for goal in active_goals if goal_applies_to_plan(goal, week_start, week_end)]

    priority_order = {"constrained": 0, "at_risk": 1, "under_pressure": 2, "watch": 3, "on_track": 4, "completed": 5}
    enriched_goals = []
    for goal in relevant_goals:
        supported_days = []
        requirement_statuses = []
        unique_supported_dates: set[str] = set()
        for requirement in goal.get("weekly_requirements") or []:
            requirement_days = []
            for day in days:
                for match in goal_requirement_matches({**goal, "weekly_requirements": [requirement]}, day):
                    requirement_days.append({
                        "date": day["date"],
                        "label": day.get("label"),
                        "title": day.get("title"),
                        "support_reason": match["support_reason"],
                        "support_level": match["support_level"],
                        "requirement_type": match["requirement_type"],
                        "requirement_label": match["requirement_label"],
                    })
            requirement_status = _build_requirement_status(requirement, requirement_days)
            requirement_statuses.append(requirement_status)
            for item in requirement_days:
                unique_supported_dates.add(item["date"])
                supported_days.append({
                    **item,
                    "priority": goal.get("risk_summary", {}).get("status", "on_track"),
                    "restriction_status": (goal.get("constraint_summary") or {}).get("status"),
                })
        if any(item["status"] == "unsupported" and item.get("priority") == "primary" for item in requirement_statuses):
            requirement_support_status = "unsupported"
        elif any(item["status"] == "unsupported" for item in requirement_statuses) or any(item["status"] == "weakly_supported" for item in requirement_statuses):
            requirement_support_status = "weak"
        else:
            requirement_support_status = "supported"
        unsupported_requirements = [item for item in requirement_statuses if item["status"] == "unsupported"]
        enriched_goals.append({
            **goal,
            "supported_sessions": len(unique_supported_dates),
            "supported_days": supported_days,
            "requirement_statuses": requirement_statuses,
            "requirement_support_status": requirement_support_status,
            "unsupported_requirements": unsupported_requirements,
            "weekly_requirement_summary": build_requirement_summary(goal.get("weekly_requirements") or []),
        })
    enriched_goals.sort(
        key=lambda goal: (
            priority_order.get(goal.get("risk_summary", {}).get("status", "on_track"), 99),
            goal.get("days_remaining", 9999),
            goal.get("title", ""),
        )
    )

    return {
        "active_goals": enriched_goals,
        "goal_ids": [goal["id"] for goal in enriched_goals],
        "constrained_goal_count": sum(1 for goal in enriched_goals if goal.get("is_constrained")),
        "unsupported_goal_count": sum(1 for goal in enriched_goals if goal.get("requirement_support_status") == "unsupported"),
        "conflicts": _build_goal_conflicts(enriched_goals),
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
    changed_dates = json.loads(row["changed_dates_json"])
    preserved_dates = json.loads(row["preserved_dates_json"])
    source = "coaching" if row["adaptation_reason"] == COACHING_ADAPTATION_REASON else "manual"
    return {
        "id": row["id"],
        "week_start": row["week_start"],
        "effective_from": row["effective_from"],
        "adaptation_reason": row["adaptation_reason"],
        "changed_dates": changed_dates,
        "preserved_dates": preserved_dates,
        "change_count": len(changed_dates),
        "preserved_count": len(preserved_dates),
        "source": source,
        "created_at": row["created_at"],
    }


def serialize_weekly_plan(row: sqlite3.Row, conn: Optional[sqlite3.Connection] = None) -> dict:
    days = ensure_plan_day_ids(row["week_start"], json.loads(row["days_json"]))
    latest_revision = None
    revisions = []
    revision_count = 0
    goal_context = {"active_goals": [], "goal_ids": [], "conflicts": [], "unsupported_goal_count": 0}
    if conn:
        restrictions = get_modality_restrictions_for_conn(conn)
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
            day_modality = modality_for_session_type(enriched_day.get("session_type"))
            enriched_day["modality"] = day_modality
            enriched_day["modality_restriction"] = restrictions.get("modalities", {}).get(day_modality) if day_modality else None
            enriched_day["comparison"] = comparison
            enriched_day["link_candidates"] = build_link_candidates(day, activity_rows)
            enriched_day["goal_links"] = []
            enriched_days.append(enriched_day)
        days = enriched_days
        goal_context = build_plan_goal_context(conn, days, row["week_start"])
        goals_by_id = {goal["id"]: goal for goal in goal_context["active_goals"]}
        for day in days:
            goal_links = []
            for goal in goals_by_id.values():
                for match in goal_requirement_matches(goal, day):
                    goal_links.append({
                        "goal_id": goal["id"],
                        "goal_title": goal["title"],
                        "metric_type": goal["metric_type"],
                        "period_label": goal["period_label"],
                        "support_reason": match["support_reason"],
                        "support_level": match["support_level"],
                        "requirement_type": match["requirement_type"],
                        "requirement_label": match["requirement_label"],
                        "status": goal["status"],
                        "risk_status": goal.get("risk_summary", {}).get("status"),
                        "risk_label": goal.get("risk_summary", {}).get("label"),
                        "is_constrained": goal.get("is_constrained", False),
                        "constraint_summary": goal.get("constraint_summary"),
                    })
            day["goal_links"] = goal_links
        latest_revision = serialize_weekly_plan_revision_row(get_latest_weekly_plan_revision_row(conn, row["week_start"]))
        revisions = [
            serialize_weekly_plan_revision_row(item)
            for item in list_weekly_plan_revision_rows(conn, row["week_start"], limit=12)
        ]
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
        "revisions": revisions,
        "goal_context": goal_context,
    }


def list_weekly_plans_data(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = list_weekly_plan_rows(conn, limit)
    return [serialize_weekly_plan(row, conn) for row in rows]


def build_multi_week_execution_trend(conn: sqlite3.Connection, weeks: int = 6) -> dict:
    safe_weeks = max(2, min(weeks, 12))
    plan_rows = list_weekly_plan_rows(conn, safe_weeks)
    plans = [serialize_weekly_plan(row, conn) for row in plan_rows]
    plans.reverse()

    tracked_statuses = [
        "linked",
        "matched",
        "moved",
        "partially_matched",
        "replaced",
        "rest_day_changed",
        "skipped",
    ]
    fulfilled_statuses = {"linked", "matched", "moved"}
    modified_statuses = {"partially_matched", "replaced", "rest_day_changed"}
    totals = {status: 0 for status in tracked_statuses}
    intent_totals = {"aligned": 0, "different": 0, "unknown": 0}
    weeks_output = []
    weeks_with_any_evaluable_day = 0
    skipped_weeks = 0
    moved_weeks = 0
    modified_weeks = 0
    intent_mismatch_weeks = 0

    for plan in plans:
        status_counts = {status: 0 for status in tracked_statuses}
        intent_counts = {"aligned": 0, "different": 0, "unknown": 0}
        evaluable_days = 0
        fulfilled_sessions = 0
        modified_sessions = 0
        missed_sessions = 0

        for day in plan.get("days", []):
            comparison = day.get("comparison") or {}
            status = comparison.get("status")
            if status == "not_completed_yet" or not status:
                continue
            if status not in status_counts:
                continue

            evaluable_days += 1
            status_counts[status] += 1
            totals[status] += 1

            alignment = comparison.get("intent_alignment", "unknown")
            if alignment not in intent_counts:
                alignment = "unknown"
            intent_counts[alignment] += 1
            intent_totals[alignment] += 1

            if status in fulfilled_statuses:
                fulfilled_sessions += 1
            elif status in modified_statuses:
                modified_sessions += 1
            elif status == "skipped":
                missed_sessions += 1

        if evaluable_days:
            weeks_with_any_evaluable_day += 1
        if status_counts["skipped"]:
            skipped_weeks += 1
        if status_counts["moved"]:
            moved_weeks += 1
        if modified_sessions:
            modified_weeks += 1
        if intent_counts["different"]:
            intent_mismatch_weeks += 1

        adherence_base = fulfilled_sessions + modified_sessions + missed_sessions
        adherence_pct = round((fulfilled_sessions / adherence_base) * 100) if adherence_base else None
        if missed_sessions >= 2 or (missed_sessions + modified_sessions) >= 3:
            week_status = "off_track"
        elif missed_sessions >= 1 or modified_sessions >= 1:
            week_status = "mixed"
        elif fulfilled_sessions:
            week_status = "on_track"
        else:
            week_status = "quiet"

        weeks_output.append({
            "week_start": plan["week_start"],
            "label": plan["week_start"],
            "title": plan.get("title"),
            "planned_sessions": len(plan.get("days", [])),
            "evaluable_sessions": evaluable_days,
            "fulfilled_sessions": fulfilled_sessions,
            "modified_sessions": modified_sessions,
            "missed_sessions": missed_sessions,
            "adherence_pct": adherence_pct,
            "status": week_status,
            "status_counts": status_counts,
            "intent_alignment": intent_counts,
        })

    observations = []
    if skipped_weeks >= 2:
        observations.append(f"Skipped sessions appeared in {skipped_weeks} of the last {len(weeks_output)} planned weeks.")
    if moved_weeks >= 2:
        observations.append(f"Session movement repeated across {moved_weeks} recent weeks.")
    if modified_weeks >= 2:
        observations.append(f"Execution changed materially in {modified_weeks} recent weeks.")
    if intent_mismatch_weeks >= 2:
        observations.append(f"Intent mismatches showed up in {intent_mismatch_weeks} recent weeks.")
    if totals["linked"] >= 3:
        observations.append(f"Explicit linking already covers {totals['linked']} sessions in the recent window.")
    if not observations:
        observations.append("Recent execution looks stable enough that no strong recurring pattern stands out yet.")

    consecutive_skipped_weeks = 0
    consecutive_moved_weeks = 0
    consecutive_modified_weeks = 0
    for week in reversed(weeks_output):
        if week["status_counts"]["skipped"] > 0:
            consecutive_skipped_weeks += 1
        else:
            break
    for week in reversed(weeks_output):
        if week["status_counts"]["moved"] > 0:
            consecutive_moved_weeks += 1
        else:
            break
    for week in reversed(weeks_output):
        if week["modified_sessions"] > 0:
            consecutive_modified_weeks += 1
        else:
            break

    evaluable_total = sum(week["evaluable_sessions"] for week in weeks_output)
    fulfilled_total = sum(week["fulfilled_sessions"] for week in weeks_output)
    modified_total = sum(week["modified_sessions"] for week in weeks_output)
    missed_total = sum(week["missed_sessions"] for week in weeks_output)

    if missed_total >= 3 or skipped_weeks >= 2:
        summary_status = "off_track"
    elif modified_total >= 3 or moved_weeks >= 2 or intent_totals["different"] >= 2:
        summary_status = "mixed"
    elif fulfilled_total > 0:
        summary_status = "on_track"
    else:
        summary_status = "quiet"

    return {
        "weeks_requested": safe_weeks,
        "weeks_considered": len(weeks_output),
        "weeks_with_data": weeks_with_any_evaluable_day,
        "status": summary_status,
        "totals": {
            "planned_sessions": sum(week["planned_sessions"] for week in weeks_output),
            "evaluable_sessions": evaluable_total,
            "fulfilled_sessions": fulfilled_total,
            "modified_sessions": modified_total,
            "missed_sessions": missed_total,
            "status_counts": totals,
            "intent_alignment": intent_totals,
        },
        "recurring_patterns": {
            "weeks_with_skipped": skipped_weeks,
            "weeks_with_moved": moved_weeks,
            "weeks_with_modified": modified_weeks,
            "weeks_with_intent_mismatch": intent_mismatch_weeks,
        },
        "streaks": {
            "consecutive_weeks_with_skipped": consecutive_skipped_weeks,
            "consecutive_weeks_with_moved": consecutive_moved_weeks,
            "consecutive_weeks_with_modified": consecutive_modified_weeks,
        },
        "observations": observations[:5],
        "weeks": weeks_output,
    }


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
