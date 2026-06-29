import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .dashboard import build_recent_context
from .plans import build_adjustment_diff_payload, format_workout_intent_label, normalize_plan_session_type

HARD_INTENTS = {"long", "tempo", "interval", "race_specific", "strength_general", "strength_lower", "strength_upper"}


def _parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


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

    if not active_goals:
        return {
            "status": "no_active_goals",
            "active_goal_count": 0,
            "most_urgent": [],
            "plan_supported_goals": 0,
            "key_observations": ["No active goals are shaping the current coaching read."],
        }

    urgency_counts = context.get("goal_planning_summary", {}).get("statuses", {})
    if urgency_counts.get("urgent"):
        status = "pressured"
    elif urgency_counts.get("pressured"):
        status = "watch"
    else:
        status = "steady"

    observations = []
    for goal in plan_goals[:3]:
        if goal.get("supported_sessions"):
            observations.append(
                f"{goal['title']} is supported by {goal['supported_sessions']} planned sessions this week."
            )
    if not observations:
        observations.append("Active goals are present, but plan support is still fairly lightweight.")

    return {
        "status": status,
        "active_goal_count": len(active_goals),
        "most_urgent": context.get("goal_planning_summary", {}).get("most_urgent", [])[:3],
        "plan_supported_goals": sum(1 for goal in plan_goals if goal.get("supported_sessions")),
        "key_observations": observations[:4],
    }


def build_recommended_next_sessions(active_plan: Optional[dict], recommendation_status: str) -> list[dict]:
    if not active_plan:
        return []

    today = datetime.now().date()
    upcoming_days = []
    for day in active_plan.get("days", []):
        day_date = _parse_date(day.get("date"))
        if not day_date or day_date < today:
            continue
        upcoming_days.append(day)

    upcoming_days.sort(key=lambda item: item["date"])
    recommendations = []
    for day in upcoming_days[:3]:
        hard = _is_hard_session(day)
        suggestion = "keep"
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
        })
    return recommendations


def build_focus_for_next_48h(recommendation_status: str, next_sessions: list[dict]) -> str:
    if not next_sessions:
        if recommendation_status == "push":
            return "You look ready for productive work, but there is no upcoming plan day to anchor it."
        return "No upcoming planned sessions are available for the next 48 hours."

    first = next_sessions[0]
    if recommendation_status == "recover":
        return f"Replace {first['title']} on {first['date']} with recovery work or rest."
    if recommendation_status == "reduce":
        return f"Keep {first['title']} on {first['date']}, but trim intensity and keep the effort controlled."
    if recommendation_status == "adjust":
        return f"Review the next sessions starting with {first['title']} on {first['date']} before forcing the original structure."
    if recommendation_status == "push":
        return f"The next key session is {first['title']} on {first['date']}; you are in a good position to lean into it."
    return f"Stay with the current structure starting with {first['title']} on {first['date']}."


def build_proposed_adjustment(active_plan: Optional[dict], recommendation_status: str, next_sessions: list[dict]) -> Optional[dict]:
    if recommendation_status not in {"reduce", "recover", "adjust"} or not active_plan or not next_sessions:
        return None

    updated_days = []
    for session in next_sessions[:2]:
        if session["suggestion"] not in {"swap_to_recovery", "lighten", "review"}:
            continue
        source_day = next(
            (day for day in active_plan.get("days", []) if day.get("date") == session["date"]),
            None,
        )
        if not source_day:
            continue
        adjusted = _build_adjusted_day(source_day, "recover" if session["suggestion"] == "swap_to_recovery" else recommendation_status)
        if adjusted:
            updated_days.append(adjusted)

    if not updated_days:
        return None

    adjustment = {
        "preview_only": True,
        "week_start": active_plan.get("week_start"),
        "effective_from": updated_days[0]["date"],
        "adaptation_reason": "Generated from one-shot coaching guidance.",
        "changed_dates": [day["date"] for day in updated_days],
        "days": updated_days,
    }
    adjustment["diff"] = build_adjustment_diff_payload(active_plan, adjustment)
    return adjustment


def build_weekly_recommendation(
    context: dict,
    execution: dict,
    recovery: dict,
    goals: dict,
    next_sessions: list[dict],
) -> dict:
    status = context.get("daily_recommendation", {}).get("status", "keep")
    recovery_score = int(recovery.get("caution_score") or 0)
    goal_status = goals.get("status")
    recent_feedback = context.get("recent_feedback", [])
    repeated_high_rpe = sum(1 for item in recent_feedback if int(item.get("rpe") or 0) >= 8)

    if recovery_score >= 4 and status != "recover":
        status = "recover"
    elif recovery_score >= 2 and status in {"keep", "push"}:
        status = "reduce"

    if execution["status"] == "off_track" and next_sessions:
        hard_upcoming = any(item["suggestion"] in {"swap_to_recovery", "lighten", "review"} for item in next_sessions)
        if hard_upcoming and status in {"keep", "push"}:
            status = "adjust"
    elif execution["missed_sessions"] >= 2 and status == "keep":
        status = "adjust"
    elif execution["modified_sessions"] >= 2 and status == "keep":
        status = "adjust"

    if execution["intent_alignment"]["different"] >= 2 and status == "keep":
        status = "adjust"

    if goal_status == "pressured" and status == "keep" and execution["fulfilled_sessions"] < max(1, execution["planned_sessions"] // 2):
        status = "adjust"
    elif goal_status == "watch" and status == "push":
        status = "keep"

    if repeated_high_rpe >= 2 and status == "push":
        status = "keep"

    if status == "push":
        headline = "You are in a good position to press the next quality session."
    elif status == "keep":
        headline = "Stay with the current weekly structure."
    elif status == "reduce":
        headline = "Keep the structure, but trim the next one or two sessions."
    elif status == "recover":
        headline = "Prioritize recovery before adding more load."
    else:
        headline = "Adjust the remainder of the week instead of forcing the original plan."

    rationale = []
    rationale.extend(recovery.get("key_reasons", []))
    rationale.extend(execution.get("key_observations", []))
    rationale.extend(goals.get("key_observations", []))
    if repeated_high_rpe >= 2:
        rationale.append("Recent feedback includes repeated high-RPE sessions.")
    if goal_status == "pressured" and goals.get("most_urgent"):
        rationale.append(f"Goal pressure is highest around {goals['most_urgent'][0]['title']}.")

    risks = []
    risks.extend(recovery.get("caution_flags", []))
    if execution["missed_sessions"]:
        risks.append(f"{execution['missed_sessions']} planned sessions were missed this week.")
    if execution["intent_alignment"]["different"]:
        risks.append(f"{execution['intent_alignment']['different']} sessions diverged from planned intent.")
    if goals.get("status") in {"pressured", "watch"} and goals.get("most_urgent"):
        risks.append(f"Active goals are under pressure, led by {goals['most_urgent'][0]['title']}.")

    return {
        "status": status,
        "headline": headline,
        "rationale": rationale[:5],
        "risks": risks[:5],
        "confidence": "high" if recovery_score >= 3 or execution["status"] == "off_track" else "moderate",
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
    active_plan = context.get("active_plan")
    execution = summarize_execution(active_plan)
    recovery = summarize_recovery(context)
    goals = summarize_goals(context, active_plan)
    next_sessions = build_recommended_next_sessions(active_plan, context.get("daily_recommendation", {}).get("status", "keep"))
    recommendation = build_weekly_recommendation(context, execution, recovery, goals, next_sessions)
    if recommendation["status"] != context.get("daily_recommendation", {}).get("status", "keep"):
        next_sessions = build_recommended_next_sessions(active_plan, recommendation["status"])
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
    elif execution["key_observations"]:
        summary_parts.append(execution["key_observations"][0])

    week_start = active_plan.get("week_start") if active_plan else None
    week_end = None
    if active_plan and active_plan.get("days"):
        week_end = max(day["date"] for day in active_plan["days"] if day.get("date"))

    return {
        "generated_at": datetime.now().isoformat(),
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
            "workout_intent_summary": context.get("workout_intent_summary"),
            "recent_feedback": context.get("recent_feedback", [])[:3],
            "recent_notes": context.get("recent_notes", [])[:3],
        },
    }
