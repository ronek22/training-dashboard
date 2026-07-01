import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .dashboard import build_recent_context
from .plans import (
    COACHING_ADAPTATION_REASON,
    build_adjustment_diff_payload,
    build_multi_week_execution_trend,
    format_workout_intent_label,
    normalize_plan_session_type,
)
from ..repositories.coaching import list_coaching_snapshot_rows, upsert_coaching_snapshot_row
from ..repositories.plans import count_weekly_plan_revision_rows
from .settings import _format_list, restriction_summary_text

HARD_INTENTS = {"long", "tempo", "interval", "race_specific", "strength_general", "strength_lower", "strength_upper"}


def _parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _goal_is_run_volume(goal: dict) -> bool:
    metric_type = goal.get("metric_type")
    if metric_type == "run_km":
        return True
    if metric_type == "activities_count":
        return normalize_plan_session_type(goal.get("activity_type")) == "Run"
    return False


def _should_deprioritize_run_goals(context: dict) -> bool:
    daily_status = context.get("daily_recommendation", {}).get("status")
    feedback = context.get("latest_subjective_state") or {}
    pain_level = int(feedback.get("pain_level") or 0)
    energy = int(feedback.get("energy") or 0)
    return daily_status in {"reduce", "recover"} or pain_level >= 2 or energy <= 2


def _append_unique(items: list[str], value: Optional[str]) -> None:
    if value and value not in items:
        items.append(value)


def _is_hard_session(day: dict) -> bool:
    session_type = normalize_plan_session_type(day.get("session_type"))
    intent = day.get("workout_intent")
    if session_type in {"Rest", "Recovery"}:
        return False
    if intent in HARD_INTENTS:
        return True
    if session_type == "WeightTraining" and intent != "mobility":
        return True
    return False


def _trimmed_duration(day: dict, ratio: float, floor_min: int = 20) -> Optional[int]:
    target = day.get("target_duration_min")
    if not target:
        return None
    return max(floor_min, int(round(float(target) * ratio)))


def _trimmed_distance(day: dict, ratio: float) -> Optional[float]:
    distance = day.get("target_distance_km")
    if not distance:
        return None
    return round(float(distance) * ratio, 1)


def _build_adjusted_day(day: dict, recommendation_status: str) -> Optional[dict]:
    session_type = normalize_plan_session_type(day.get("session_type"))
    if session_type in {"Rest", "Recovery"}:
        return None

    if recommendation_status == "recover":
        if session_type == "WeightTraining":
            return {
                "date": day["date"],
                "label": day["label"],
                "session_type": "Recovery",
                "workout_intent": "mobility",
                "title": "Mobility and recovery",
                "details": "Swap the planned session for gentle mobility, easy walking, or full rest if symptoms persist.",
                "target_duration_min": 20,
                "target_distance_km": None,
            }
        return {
            "date": day["date"],
            "label": day["label"],
            "session_type": "Recovery",
            "workout_intent": "recovery",
            "title": "Recovery session",
            "details": "Replace the planned session with easy movement, mobility, or full rest based on how you feel.",
            "target_duration_min": min(day.get("target_duration_min") or 30, 30),
            "target_distance_km": None,
        }

    if recommendation_status in {"reduce", "adjust"}:
        if session_type == "WeightTraining":
            return {
                "date": day["date"],
                "label": day["label"],
                "session_type": "WeightTraining",
                "workout_intent": "mobility",
                "title": f"Reduced {day['title']}",
                "details": "Keep it light and technical. Skip failure work and avoid adding lower-body fatigue.",
                "target_duration_min": _trimmed_duration(day, 0.65, floor_min=20) or 25,
                "target_distance_km": None,
            }
        return {
            "date": day["date"],
            "label": day["label"],
            "session_type": session_type,
            "workout_intent": "easy",
            "title": f"Reduced {day['title']}",
            "details": "Keep the structure, but remove intensity and keep the effort controlled.",
            "target_duration_min": _trimmed_duration(day, 0.65, floor_min=20),
            "target_distance_km": _trimmed_distance(day, 0.65),
        }

    return None


def summarize_execution(active_plan: Optional[dict]) -> dict:
    if not active_plan:
        return {
            "status": "no_plan",
            "planned_sessions": 0,
            "completed_sessions": 0,
            "fulfilled_sessions": 0,
            "modified_sessions": 0,
            "missed_sessions": 0,
            "upcoming_sessions": 0,
            "adherence_pct": None,
            "status_counts": {},
            "intent_alignment": {"aligned": 0, "different": 0, "unknown": 0},
            "key_observations": ["No active weekly plan is available."],
        }

    today = datetime.now().date()
    days = active_plan.get("days", [])
    status_counts: dict[str, int] = {}
    intent_alignment = {"aligned": 0, "different": 0, "unknown": 0}
    fulfilled_statuses = {"linked", "matched", "moved"}
    modified_statuses = {"partially_matched", "replaced", "rest_day_changed"}

    eligible_past_days = 0
    fulfilled_sessions = 0
    modified_sessions = 0
    missed_sessions = 0
    upcoming_sessions = 0
    completed_sessions = 0

    for day in days:
        comparison = day.get("comparison", {})
        status = comparison.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        alignment = comparison.get("intent_alignment", "unknown")
        intent_alignment[alignment if alignment in intent_alignment else "unknown"] += 1

        day_date = _parse_date(day.get("date"))
        if day_date and day_date <= today:
            eligible_past_days += 1
            if status in fulfilled_statuses:
                fulfilled_sessions += 1
            elif status in modified_statuses:
                modified_sessions += 1
            elif status == "skipped":
                missed_sessions += 1
        elif status == "not_completed_yet":
            upcoming_sessions += 1

        if comparison.get("completed_activities"):
            completed_sessions += len(comparison["completed_activities"])

    adherence_base = fulfilled_sessions + modified_sessions + missed_sessions
    adherence_pct = round((fulfilled_sessions / adherence_base) * 100) if adherence_base else None

    if missed_sessions >= 2 or (missed_sessions + modified_sessions) >= 3:
        status = "off_track"
    elif missed_sessions >= 1 or modified_sessions >= 1:
        status = "mixed"
    else:
        status = "on_track"

    observations: list[str] = []
    if fulfilled_sessions:
        observations.append(f"{fulfilled_sessions} planned sessions were fulfilled cleanly.")
    if modified_sessions:
        observations.append(f"{modified_sessions} sessions were completed with a different type, volume, or intent.")
    if missed_sessions:
        observations.append(f"{missed_sessions} past planned sessions were skipped outright.")
    if status_counts.get("linked", 0):
        observations.append(f"{status_counts['linked']} sessions already use explicit planned-to-actual linking.")
    if intent_alignment["different"]:
        observations.append(f"{intent_alignment['different']} matched sessions had a different intent than planned.")
    if not observations:
        observations.append("No major execution deviations are visible in the current plan window.")

    return {
        "status": status,
        "planned_sessions": len(days),
        "completed_sessions": completed_sessions,
        "fulfilled_sessions": fulfilled_sessions,
        "modified_sessions": modified_sessions,
        "missed_sessions": missed_sessions,
        "upcoming_sessions": upcoming_sessions,
        "adherence_pct": adherence_pct,
        "status_counts": status_counts,
        "intent_alignment": intent_alignment,
        "key_observations": observations[:5],
    }


def summarize_recovery(context: dict) -> dict:
    daily = context.get("daily_recommendation", {})
    feedback = context.get("latest_subjective_state")
    training_load = context.get("training_load", {})
    current_load = training_load.get("current", {})
    caution_flags: list[str] = []

    if feedback:
        if int(feedback.get("pain_level") or 0) >= 4:
            caution_flags.append(f"Pain is elevated at {feedback['pain_level']}/10.")
        if int(feedback.get("energy") or 0) <= 2:
            caution_flags.append(f"Energy is low at {feedback['energy']}/5.")
        if int(feedback.get("muscle_soreness") or 0) >= 4:
            caution_flags.append(f"Soreness is elevated at {feedback['muscle_soreness']}/5.")

    form = float(current_load.get("form") or 0)
    if form <= -18:
        caution_flags.append(f"Training form is suppressed at {round(form)}.")

    recommendation_status = daily.get("status", "keep")
    restrictions = context.get("modality_restrictions", {})
    active_restrictions = restrictions.get("active", [])
    caution_score = 0
    if feedback:
        caution_score += 2 if int(feedback.get("pain_level") or 0) >= 4 else 0
        caution_score += 1 if int(feedback.get("energy") or 0) <= 2 else 0
        caution_score += 1 if int(feedback.get("muscle_soreness") or 0) >= 4 else 0
    caution_score += 1 if form <= -18 else 0

    if recommendation_status == "recover":
        status = "needs_recovery"
    elif recommendation_status == "reduce":
        status = "caution"
    elif recommendation_status == "push":
        status = "ready"
    else:
        status = "steady"

    return {
        "status": status,
        "daily_recommendation_status": recommendation_status,
        "action": daily.get("action"),
        "key_reasons": daily.get("reasons", [])[:4],
        "caution_flags": caution_flags[:4],
        "caution_score": caution_score,
        "active_restrictions": active_restrictions,
        "restriction_status": "restricted" if active_restrictions else "none",
        "latest_subjective_state": feedback,
        "training_load": {
            "fitness": current_load.get("fitness"),
            "fatigue": current_load.get("fatigue"),
            "form": current_load.get("form"),
            "ratio_status": training_load.get("ratio", {}).get("status"),
        },
    }


def summarize_goals(context: dict, active_plan: Optional[dict]) -> dict:
    active_goals = context.get("active_goals", [])
    plan_goals = (active_plan or {}).get("goal_context", {}).get("active_goals", [])
    plan_conflicts = (active_plan or {}).get("goal_context", {}).get("conflicts", [])

    if not active_goals:
        return {
            "status": "no_active_goals",
            "active_goal_count": 0,
            "most_urgent": [],
            "plan_supported_goals": 0,
            "unsupported_goal_count": 0,
            "conflict_count": 0,
            "key_observations": ["No active goals are shaping the current coaching read."],
        }

    run_restriction = ((context.get("modality_restrictions") or {}).get("modalities") or {}).get("run", {})
    deprioritize_run_goals = _should_deprioritize_run_goals(context) and run_restriction.get("status") == "allowed"
    constrained_goals = [goal for goal in active_goals if goal.get("is_constrained")]
    relevant_active_goals = [
        goal for goal in active_goals
        if not goal.get("is_constrained") and not (deprioritize_run_goals and _goal_is_run_volume(goal))
    ]
    relevant_plan_goals = [
        goal for goal in plan_goals
        if not goal.get("is_constrained") and not (deprioritize_run_goals and _goal_is_run_volume(goal))
    ]
    deferred_goals = [
        goal for goal in active_goals
        if deprioritize_run_goals and _goal_is_run_volume(goal)
    ]
    most_urgent = [
        goal for goal in context.get("goal_planning_summary", {}).get("most_urgent", [])[:3]
        if not (deprioritize_run_goals and _goal_is_run_volume(goal))
    ]
    risk_counts = {
        "at_risk": sum(1 for goal in relevant_active_goals if goal.get("risk_summary", {}).get("status") == "at_risk"),
        "under_pressure": sum(1 for goal in relevant_active_goals if goal.get("risk_summary", {}).get("status") == "under_pressure"),
        "watch": sum(1 for goal in relevant_active_goals if goal.get("risk_summary", {}).get("status") == "watch"),
        "on_track": sum(1 for goal in relevant_active_goals if goal.get("risk_summary", {}).get("status") == "on_track"),
        "completed": sum(1 for goal in relevant_active_goals if goal.get("risk_summary", {}).get("status") == "completed"),
    }
    unsupported_plan_goals = [goal for goal in relevant_plan_goals if goal.get("requirement_support_status") == "unsupported"]
    weak_plan_goals = [goal for goal in relevant_plan_goals if goal.get("requirement_support_status") == "weak"]
    if constrained_goals and not relevant_active_goals and not deferred_goals:
        status = "constrained"
    elif not relevant_active_goals and deferred_goals:
        status = "deferred"
    elif plan_conflicts or unsupported_plan_goals:
        status = "pressured"
    elif risk_counts.get("at_risk"):
        status = "pressured"
    elif risk_counts.get("under_pressure"):
        status = "pressured"
    elif risk_counts.get("watch"):
        status = "watch"
    else:
        status = "steady"

    observations = []
    for goal in constrained_goals[:2]:
        if (goal.get("constraint_summary") or {}).get("summary"):
            observations.append(goal["constraint_summary"]["summary"])
    for goal in relevant_plan_goals[:3]:
        if goal.get("supported_sessions"):
            family_label = (goal.get("family_label") or "Goal").lower()
            observations.append(f"{goal['title']} ({family_label}) is supported by {goal['supported_sessions']} planned sessions this week.")
        if goal.get("weekly_requirement_summary"):
            _append_unique(observations, goal["weekly_requirement_summary"])
        if goal.get("requirement_support_status") == "unsupported" and goal.get("unsupported_requirements"):
            _append_unique(
                observations,
                f"{goal['title']} is unsupported this week: {goal['unsupported_requirements'][0]['label']} is still missing.",
            )
        elif goal.get("requirement_support_status") == "weak" and goal.get("unsupported_requirements"):
            _append_unique(
                observations,
                f"{goal['title']} only has partial support: {goal['unsupported_requirements'][0]['label']} is still thin.",
            )
        if goal.get("risk_summary", {}).get("status") in {"at_risk", "under_pressure"}:
            observations.append(goal["risk_summary"]["summary"])
        elif goal.get("goal_family") in {"event_performance", "benchmark"} and goal.get("target_summary"):
            observations.append(goal["target_summary"])
    for goal in most_urgent[:2]:
        if goal.get("goal_family") in {"event_performance", "benchmark"} and goal.get("target_summary"):
            _append_unique(observations, goal["target_summary"])
    if deferred_goals:
        observations.append("Run-volume goals are temporarily backgrounded while recovery is the priority.")
    for conflict in plan_conflicts[:2]:
        _append_unique(observations, conflict.get("summary"))
    if not observations:
        observations.append("Active goals are present, but plan support is still fairly lightweight.")

    return {
        "status": status,
        "active_goal_count": len(active_goals),
        "most_urgent": most_urgent,
        "plan_supported_goals": sum(1 for goal in relevant_plan_goals if goal.get("supported_sessions")),
        "deferred_goal_count": len(deferred_goals),
        "constrained_goal_count": len(constrained_goals),
        "unsupported_goal_count": len(unsupported_plan_goals),
        "weakly_supported_goal_count": len(weak_plan_goals),
        "conflict_count": len(plan_conflicts),
        "conflicts": plan_conflicts,
        "key_observations": observations[:4],
    }


def summarize_recent_patterns(conn: sqlite3.Connection, context: dict, active_plan: Optional[dict]) -> dict:
    execution_trend = build_multi_week_execution_trend(conn, weeks=6)
    recurring = execution_trend.get("recurring_patterns", {})
    streaks = execution_trend.get("streaks", {})
    totals = execution_trend.get("totals", {})
    recent_feedback = context.get("recent_feedback", [])
    latest_revision = (active_plan or {}).get("latest_revision")
    current_revision_count = int((active_plan or {}).get("revision_count") or 0)

    repeated_high_rpe = sum(1 for item in recent_feedback if int(item.get("rpe") or 0) >= 8)
    repeated_low_energy = sum(1 for item in recent_feedback if int(item.get("energy") or 0) <= 2)
    repeated_pain_flags = sum(1 for item in recent_feedback if int(item.get("pain_level") or 0) >= 4)

    observations: list[str] = []
    if recurring.get("weeks_with_skipped", 0) >= 2:
        _append_unique(observations, f"Skipped sessions appeared in {recurring['weeks_with_skipped']} recent planned weeks.")
    if recurring.get("weeks_with_moved", 0) >= 2:
        _append_unique(observations, f"Session movement repeated across {recurring['weeks_with_moved']} recent weeks.")
    if recurring.get("weeks_with_modified", 0) >= 2:
        _append_unique(observations, f"Execution changed materially in {recurring['weeks_with_modified']} recent weeks.")
    if recurring.get("weeks_with_intent_mismatch", 0) >= 2 or totals.get("intent_alignment", {}).get("different", 0) >= 2:
        _append_unique(observations, "Intent mismatches are repeating rather than looking like a one-off.")
    if current_revision_count >= 3:
        _append_unique(observations, f"This week has already been revised {current_revision_count} times.")
    elif current_revision_count >= 1 and latest_revision:
        _append_unique(observations, f"This week was already revised on {latest_revision['created_at'][:10]}.")
    if repeated_high_rpe >= 2:
        _append_unique(observations, f"Recent feedback includes {repeated_high_rpe} high-RPE sessions.")
    if repeated_low_energy >= 2:
        _append_unique(observations, f"Recent feedback includes {repeated_low_energy} low-energy check-ins.")
    if repeated_pain_flags >= 2:
        _append_unique(observations, f"Recent feedback includes {repeated_pain_flags} elevated-pain check-ins.")
    if not observations and execution_trend.get("observations"):
        observations.extend(execution_trend["observations"][:2])
    if not observations:
        observations.append("Recent pattern signals are fairly stable.")

    if (
        recurring.get("weeks_with_skipped", 0) >= 2
        or streaks.get("consecutive_weeks_with_skipped", 0) >= 2
        or current_revision_count >= 3
        or repeated_low_energy >= 2
        or repeated_pain_flags >= 2
    ):
        status = "concerning"
    elif (
        execution_trend.get("status") == "mixed"
        or recurring.get("weeks_with_modified", 0) >= 2
        or recurring.get("weeks_with_moved", 0) >= 2
        or totals.get("intent_alignment", {}).get("different", 0) >= 2
        or current_revision_count >= 1
        or repeated_high_rpe >= 2
    ):
        status = "watch"
    else:
        status = "stable"

    return {
        "status": status,
        "execution_trend": execution_trend,
        "current_week_revision_count": current_revision_count,
        "latest_revision": latest_revision,
        "recent_feedback_patterns": {
            "high_rpe_count": repeated_high_rpe,
            "low_energy_count": repeated_low_energy,
            "elevated_pain_count": repeated_pain_flags,
        },
        "key_observations": observations[:5],
    }


def build_recommended_next_sessions(active_plan: Optional[dict], recommendation_status: str, restrictions: Optional[dict] = None) -> list[dict]:
    if not active_plan:
        return []

    today = datetime.now().date()
    fulfilled_statuses = {"linked", "matched", "moved"}
    modified_statuses = {"partially_matched", "replaced", "rest_day_changed"}
    upcoming_days = []
    for day in active_plan.get("days", []):
        day_date = _parse_date(day.get("date"))
        if not day_date or day_date < today:
            continue
        comparison = day.get("comparison", {})
        status = comparison.get("status")
        if status in fulfilled_statuses or status in modified_statuses:
            continue
        if comparison.get("completed_activities"):
            continue
        upcoming_days.append(day)

    upcoming_days.sort(key=lambda item: item["date"])
    recommendations = []
    for day in upcoming_days[:3]:
        hard = _is_hard_session(day)
        suggestion = "keep"
        modality_restriction = day.get("modality_restriction") or {}
        restriction_status = modality_restriction.get("status", "allowed")
        if restriction_status == "blocked":
            suggestion = "substitute" if day.get("session_type") in {"Run", "Ride", "VirtualRide"} else "avoid"
        elif restriction_status == "limited":
            suggestion = "limit"
        if recommendation_status == "recover" and hard:
            suggestion = "swap_to_recovery"
        elif recommendation_status in {"reduce", "adjust"} and hard:
            suggestion = "lighten"
        elif recommendation_status == "adjust":
            suggestion = "review"

        recommendations.append({
            "date": day["date"],
            "label": day.get("label"),
            "title": day.get("title"),
            "session_type": day.get("session_type"),
            "workout_intent": day.get("workout_intent"),
            "workout_intent_label": day.get("workout_intent_label") or format_workout_intent_label(day.get("workout_intent")),
            "target_duration_min": day.get("target_duration_min"),
            "target_distance_km": day.get("target_distance_km"),
            "comparison_status": day.get("comparison", {}).get("status"),
            "suggestion": suggestion,
            "modality": day.get("modality"),
            "modality_restriction": modality_restriction,
            "restriction_summary": restriction_summary_text(modality_restriction) if restriction_status in {"limited", "blocked"} else None,
        })
    return recommendations


def build_focus_for_next_48h(recommendation_status: str, next_sessions: list[dict]) -> str:
    if not next_sessions:
        if recommendation_status == "push":
            return "You look ready for productive work, but there is no upcoming plan day to anchor it."
        return "No upcoming planned sessions are available for the next 48 hours."

    first = next_sessions[0]
    if first.get("suggestion") == "substitute":
        return f"Replace {first['title']} on {first['date']} with work in an allowed modality."
    if first.get("suggestion") == "avoid":
        return f"Avoid {first['title']} on {first['date']} while {first.get('modality_restriction', {}).get('label', 'that modality')} is blocked."
    if first.get("suggestion") == "limit":
        return f"Keep {first['title']} on {first['date']} only if it stays easy and symptom-aware."
    if recommendation_status == "recover":
        return f"Replace {first['title']} on {first['date']} with recovery work or rest."
    if recommendation_status == "reduce":
        return f"Keep {first['title']} on {first['date']}, but trim intensity and keep the effort controlled."
    if recommendation_status == "adjust":
        return f"Review the next sessions starting with {first['title']} on {first['date']} before forcing the original structure."
    if recommendation_status == "push":
        return f"The next key session is {first['title']} on {first['date']}; you are in a good position to lean into it."
    return f"Stay with the current structure starting with {first['title']} on {first['date']}."


def _build_restriction_adjusted_day(day: dict, suggestion: str, restriction: dict) -> Optional[dict]:
    session_type = normalize_plan_session_type(day.get("session_type"))
    modality = day.get("modality")
    if suggestion == "limit":
        return _build_adjusted_day(day, "reduce")
    if suggestion == "substitute" and modality == "run":
        return {
            "date": day["date"],
            "label": day["label"],
            "session_type": "Ride",
            "workout_intent": "easy",
            "title": f"Alternative to {day['title']}",
            "details": "Running is blocked right now. Replace the session with an easy aerobic ride or trainer spin.",
            "target_duration_min": day.get("target_duration_min") or 40,
            "target_distance_km": None,
        }
    if suggestion in {"substitute", "avoid"}:
        return {
            "date": day["date"],
            "label": day["label"],
            "session_type": "Recovery",
            "workout_intent": "mobility",
            "title": f"Protected {restriction.get('label', 'modality')} day",
            "details": f"{restriction.get('label', 'This modality')} is currently {restriction.get('status')}. Swap this session for mobility, walking, or full rest.",
            "target_duration_min": 20,
            "target_distance_km": None,
        }
    return None


def build_proposed_adjustment(active_plan: Optional[dict], recommendation_status: str, next_sessions: list[dict]) -> Optional[dict]:
    if recommendation_status not in {"reduce", "recover", "adjust", "keep"} or not active_plan or not next_sessions:
        return None

    updated_days = []
    for session in next_sessions[:2]:
        if session["suggestion"] not in {"swap_to_recovery", "lighten", "review", "substitute", "avoid", "limit"}:
            continue
        source_day = next(
            (day for day in active_plan.get("days", []) if day.get("date") == session["date"]),
            None,
        )
        if not source_day:
            continue
        if session["suggestion"] in {"substitute", "avoid", "limit"}:
            adjusted = _build_restriction_adjusted_day(source_day, session["suggestion"], session.get("modality_restriction") or {})
        else:
            adjusted = _build_adjusted_day(source_day, "recover" if session["suggestion"] == "swap_to_recovery" else recommendation_status)
        if adjusted:
            updated_days.append(adjusted)

    if not updated_days:
        return None

    adjustment = {
        "preview_only": True,
        "week_start": active_plan.get("week_start"),
        "effective_from": updated_days[0]["date"],
        "adaptation_reason": COACHING_ADAPTATION_REASON,
        "changed_dates": [day["date"] for day in updated_days],
        "days": updated_days,
    }
    adjustment["diff"] = build_adjustment_diff_payload(active_plan, adjustment)
    return adjustment


def serialize_coaching_snapshot_row(row: sqlite3.Row) -> dict:
    return {
        "week_start": row["week_start"],
        "week_end": row["week_end"],
        "summary_status": row["summary_status"],
        "headline": row["headline"],
        "rationale_summary": row["rationale_summary"],
        "recommendation_status": row["recommendation_status"],
        "recommendation_action": row["recommendation_action"],
        "focus_for_next_48h": row["focus_for_next_48h"],
        "proposed_changed_dates": json.loads(row["proposed_changed_dates_json"]),
        "revision_count": int(row["revision_count"] or 0),
        "generated_at": row["generated_at"],
        "updated_at": row["updated_at"],
    }


def list_coaching_history_data(conn: sqlite3.Connection, limit: int = 6) -> list[dict]:
    rows = list_coaching_snapshot_rows(conn, limit)
    return [serialize_coaching_snapshot_row(row) for row in rows]


def build_weekly_recommendation(
    context: dict,
    execution: dict,
    recovery: dict,
    goals: dict,
    next_sessions: list[dict],
    recent_patterns: dict,
) -> dict:
    status = context.get("daily_recommendation", {}).get("status", "keep")
    athlete_brief = context.get("athlete_brief") or {}
    recovery_score = int(recovery.get("caution_score") or 0)
    goal_status = goals.get("status")
    pattern_status = recent_patterns.get("status")
    trend = recent_patterns.get("execution_trend", {})
    recurring = trend.get("recurring_patterns", {})
    streaks = trend.get("streaks", {})
    feedback_patterns = recent_patterns.get("recent_feedback_patterns", {})
    repeated_high_rpe = int(feedback_patterns.get("high_rpe_count") or 0)
    repeated_low_energy = int(feedback_patterns.get("low_energy_count") or 0)
    repeated_pain_flags = int(feedback_patterns.get("elevated_pain_count") or 0)
    current_revision_count = int(recent_patterns.get("current_week_revision_count") or 0)
    hard_upcoming = any(item["suggestion"] in {"swap_to_recovery", "lighten", "review"} for item in next_sessions)
    blocked_upcoming = any(item["suggestion"] in {"substitute", "avoid"} for item in next_sessions)
    goal_support_is_thin = execution["fulfilled_sessions"] < max(1, execution["planned_sessions"] // 2)

    if recovery_score >= 4 or (repeated_pain_flags >= 2 and recovery_score >= 2):
        status = "recover"
    elif recovery_score >= 3 and repeated_low_energy >= 2 and status != "recover":
        status = "recover"
    elif recovery_score >= 2 and status in {"keep", "push"}:
        status = "reduce"

    if status not in {"recover", "reduce"}:
        if blocked_upcoming:
            status = "adjust"
        if execution["status"] == "off_track" and next_sessions and hard_upcoming:
            status = "adjust"
        elif execution["missed_sessions"] >= 2 and status == "keep":
            status = "adjust"
        elif execution["modified_sessions"] >= 2 and status == "keep":
            status = "adjust"
        elif execution["intent_alignment"]["different"] >= 2 and status == "keep":
            status = "adjust"
        elif recurring.get("weeks_with_skipped", 0) >= 2 and status == "keep":
            status = "adjust"
        elif recurring.get("weeks_with_modified", 0) >= 2 and current_revision_count >= 1 and status == "keep":
            status = "adjust"
        elif current_revision_count >= 3 and status == "keep":
            status = "adjust"
        elif streaks.get("consecutive_weeks_with_skipped", 0) >= 2 and status == "keep":
            status = "adjust"

    if status == "push" and (pattern_status != "stable" or repeated_high_rpe >= 2 or execution["status"] != "on_track"):
        status = "keep"
    elif goal_status == "watch" and status == "push":
        status = "keep"

    if goal_status == "pressured" and status == "keep" and goal_support_is_thin:
        status = "adjust"
    elif (
        goal_status == "pressured"
        and status == "keep"
        and recovery_score <= 1
        and pattern_status == "stable"
        and execution["status"] == "on_track"
        and repeated_high_rpe == 0
        and execution["fulfilled_sessions"] >= max(1, execution["planned_sessions"] // 2)
    ):
        status = "push"

    if status == "push":
        headline = "You are in a good position to press the next quality session."
        action = "Lean into the next key session without adding extra complexity."
    elif status == "keep":
        headline = "Stay with the current weekly structure."
        action = "Keep the planned structure and avoid unnecessary changes."
    elif status == "reduce":
        headline = "Keep the structure, but trim the next one or two sessions."
        action = "Hold onto the week shape, but reduce intensity or volume in the next sessions."
    elif status == "recover":
        headline = "Prioritize recovery before adding more load."
        action = "Swap the next demanding session for recovery work or rest."
    else:
        headline = "Adjust the remainder of the week instead of forcing the original plan."
        action = "Review and rewrite the next one or two sessions to match current execution reality."

    rationale: list[str] = []
    for text in recovery.get("key_reasons", []):
        _append_unique(rationale, text)
    for item in recovery.get("active_restrictions", [])[:2]:
        _append_unique(rationale, item.get("summary"))
    for text in recent_patterns.get("key_observations", []):
        _append_unique(rationale, text)
    for text in execution.get("key_observations", []):
        _append_unique(rationale, text)
    for text in goals.get("key_observations", []):
        _append_unique(rationale, text)
    if athlete_brief.get("headline"):
        _append_unique(rationale, athlete_brief["headline"])
    if athlete_brief.get("current_block"):
        _append_unique(rationale, f"Current emphasis block: {athlete_brief['current_block']}.")
    if athlete_brief.get("preferred_long_session_day_labels"):
        _append_unique(
            rationale,
            f"Long-session preference is {_format_list(athlete_brief['preferred_long_session_day_labels'])}.",
        )
    if athlete_brief.get("planning_notes"):
        _append_unique(rationale, f"Planning note: {athlete_brief['planning_notes']}.")
    if repeated_high_rpe >= 2:
        _append_unique(rationale, "Recent feedback includes repeated high-RPE sessions.")
    if goal_status == "pressured" and goals.get("most_urgent"):
        _append_unique(rationale, f"Goal pressure is highest around {goals['most_urgent'][0]['title']}.")
    if goals.get("constrained_goal_count"):
        _append_unique(rationale, f"{goals['constrained_goal_count']} active goals are constrained by current modality limits.")
    if goals.get("conflict_count"):
        _append_unique(rationale, f"{goals['conflict_count']} goal tradeoff{'s are' if goals['conflict_count'] != 1 else ' is'} visible in the current week.")
    if goals.get("unsupported_goal_count"):
        _append_unique(rationale, f"{goals['unsupported_goal_count']} active goal{'s are' if goals['unsupported_goal_count'] != 1 else ' is'} not meaningfully supported this week.")

    risks: list[str] = []
    for text in recovery.get("caution_flags", []):
        _append_unique(risks, text)
    for item in recovery.get("active_restrictions", [])[:2]:
        _append_unique(risks, item.get("summary"))
    if execution["missed_sessions"]:
        _append_unique(risks, f"{execution['missed_sessions']} planned sessions were missed this week.")
    if execution["intent_alignment"]["different"]:
        _append_unique(risks, f"{execution['intent_alignment']['different']} sessions diverged from planned intent.")
    if recurring.get("weeks_with_skipped", 0) >= 2:
        _append_unique(risks, f"Skipped sessions have recurred in {recurring['weeks_with_skipped']} recent weeks.")
    if current_revision_count >= 2:
        _append_unique(risks, f"The current week has already needed {current_revision_count} revisions.")
    if goals.get("status") in {"pressured", "watch"} and goals.get("most_urgent"):
        _append_unique(risks, f"Active goals are under pressure, led by {goals['most_urgent'][0]['title']}.")
    if goals.get("unsupported_goal_count"):
        _append_unique(risks, f"{goals['unsupported_goal_count']} active goal{'s lack' if goals['unsupported_goal_count'] != 1 else ' lacks'} enough weekly support.")

    return {
        "status": status,
        "headline": headline,
        "action": action,
        "rationale": rationale[:5],
        "risks": risks[:5],
        "confidence": "high" if recovery_score >= 3 or execution["status"] == "off_track" or pattern_status == "concerning" else "moderate",
        "focus_for_next_48h": build_focus_for_next_48h(status, next_sessions),
    }


def build_weekly_coaching(
    conn: sqlite3.Connection,
    lookback_days: int = 14,
    context_days: int = 30,
    recent_activity_limit: int = 12,
    recent_note_limit: int = 5,
    include_proposed_adjustment: bool = True,
) -> dict:
    context = build_recent_context(
        conn,
        lookback_days=lookback_days,
        context_days=context_days,
        recent_activity_limit=recent_activity_limit,
        recent_note_limit=recent_note_limit,
    )
    athlete_brief = context.get("athlete_brief")
    active_plan = context.get("active_plan")
    execution = summarize_execution(active_plan)
    recovery = summarize_recovery(context)
    goals = summarize_goals(context, active_plan)
    recent_patterns = summarize_recent_patterns(conn, context, active_plan)
    next_sessions = build_recommended_next_sessions(active_plan, context.get("daily_recommendation", {}).get("status", "keep"), context.get("modality_restrictions"))
    recommendation = build_weekly_recommendation(context, execution, recovery, goals, next_sessions, recent_patterns)
    if recommendation["status"] != context.get("daily_recommendation", {}).get("status", "keep"):
        next_sessions = build_recommended_next_sessions(active_plan, recommendation["status"], context.get("modality_restrictions"))
        recommendation["focus_for_next_48h"] = build_focus_for_next_48h(recommendation["status"], next_sessions)
    proposed_adjustment = build_proposed_adjustment(active_plan, recommendation["status"], next_sessions) if include_proposed_adjustment else None

    if recommendation["status"] in {"recover", "reduce", "adjust"}:
        summary_status = "caution"
    elif recommendation["status"] == "push":
        summary_status = "opportunity"
    else:
        summary_status = "steady"

    summary_parts = []
    summary_parts.append(recommendation["headline"])
    if execution["missed_sessions"]:
        summary_parts.append(f"{execution['missed_sessions']} planned sessions were missed.")
    if recovery.get("caution_flags"):
        summary_parts.append(recovery["caution_flags"][0])
    elif recent_patterns.get("key_observations"):
        summary_parts.append(recent_patterns["key_observations"][0])
    elif execution["key_observations"]:
        summary_parts.append(execution["key_observations"][0])

    week_start = active_plan.get("week_start") if active_plan else None
    week_end = None
    if active_plan and active_plan.get("days"):
        week_end = max(day["date"] for day in active_plan["days"] if day.get("date"))

    generated_at = datetime.now().isoformat()
    payload = {
        "generated_at": generated_at,
        "week_start": week_start,
        "week_end": week_end,
        "summary": {
            "status": summary_status,
            "headline": recommendation["headline"],
            "text": " ".join(part for part in summary_parts if part),
        },
        "execution_assessment": execution,
        "recovery_assessment": recovery,
        "goal_assessment": goals,
        "recommendation": recommendation,
        "recommended_next_sessions": next_sessions,
        "proposed_adjustment": proposed_adjustment,
        "reasoning_signals": {
            "daily_recommendation": context.get("daily_recommendation"),
            "latest_subjective_state": context.get("latest_subjective_state"),
            "training_load": context.get("training_load"),
            "goal_planning_summary": context.get("goal_planning_summary"),
            "athlete_brief": athlete_brief,
            "athlete_profile": context.get("athlete_profile"),
            "modality_restrictions": context.get("modality_restrictions"),
            "workout_intent_summary": context.get("workout_intent_summary"),
            "recent_pattern_summary": recent_patterns,
            "recent_feedback": context.get("recent_feedback", [])[:3],
            "recent_notes": context.get("recent_notes", [])[:3],
        },
    }

    if week_start:
        upsert_coaching_snapshot_row(
            conn,
            week_start=week_start,
            week_end=week_end,
            summary_status=summary_status,
            headline=recommendation["headline"],
            rationale_summary=payload["summary"]["text"],
            recommendation_status=recommendation["status"],
            recommendation_action=recommendation.get("action"),
            focus_for_next_48h=recommendation.get("focus_for_next_48h"),
            proposed_changed_dates=[day["date"] for day in (proposed_adjustment or {}).get("days", []) if day.get("date")],
            revision_count=count_weekly_plan_revision_rows(conn, week_start),
            generated_at=generated_at,
        )
        conn.commit()

    return payload
