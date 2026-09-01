import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .plans import normalize_workout_intent

HARD_INTENTS = {
    "tempo",
    "interval",
    "race_specific",
    "strength_lower",
}


def _append_unique(items: list[str], value: Optional[str]) -> None:
    if value and value not in items:
        items.append(value)


def _recent_feedback_rows(conn: sqlite3.Connection, days: int = 14) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            a.id AS activity_id,
            a.date AS activity_date,
            a.type AS activity_type,
            a.name AS activity_name,
            f.rpe,
            f.energy,
            f.muscle_soreness,
            f.pain_level,
            f.note,
            f.created_at
        FROM activity_feedback f
        JOIN activities a ON a.id = f.activity_id
        WHERE a.date >= date('now', ?)
        ORDER BY a.date DESC, f.updated_at DESC, f.created_at DESC
        """,
        (f"-{max(1, days)} days",),
    ).fetchall()


def _recent_activity_rows(conn: sqlite3.Connection, days: int = 14) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, date, type, workout_intent, duration_min, distance_km, avg_hr, zone2
        FROM activities
        WHERE date >= date('now', ?)
        ORDER BY date DESC, created_at DESC
        """,
        (f"-{max(1, days)} days",),
    ).fetchall()


def _is_hard_session(row: sqlite3.Row) -> bool:
    session_type = row["type"]
    intent = normalize_workout_intent(row["workout_intent"], session_type)
    # Readiness should only call a session hard when its purpose makes that
    # explicit. A long easy ride, ordinary strength session, or a missing/false
    # zone-2 flag is training volume, but is not reliable evidence of intensity.
    return intent in HARD_INTENTS


def _readiness_factor(key: str, label: str, value, tone: str) -> dict:
    return {
        "key": key,
        "label": label,
        "value": value,
        "tone": tone,
    }


def build_readiness_summary(
    conn: sqlite3.Connection,
    *,
    training_load_summary: Optional[dict] = None,
    daily_recommendation: Optional[dict] = None,
) -> dict:
    training_load_summary = training_load_summary or {}
    daily_recommendation = daily_recommendation or {}
    activities = _recent_activity_rows(conn, days=14)
    feedback_rows = _recent_feedback_rows(conn, days=14)
    today = datetime.now().date()

    activity_count_14d = len(activities)
    total_duration_14d = round(sum(float(row["duration_min"] or 0) for row in activities), 1)
    recent_dates = sorted({row["date"] for row in activities}, reverse=True)
    most_recent_activity_date = recent_dates[0] if recent_dates else None
    latest_activity_age_days = None
    if most_recent_activity_date:
        latest_activity_age_days = (today - datetime.strptime(most_recent_activity_date, "%Y-%m-%d").date()).days

    sessions_7d = 0
    sessions_3d = 0
    hard_sessions_7d = 0
    active_days_7d: set[str] = set()
    modality_counts: dict[str, int] = {}
    seven_day_cutoff = today - timedelta(days=6)
    three_day_cutoff = today - timedelta(days=2)
    for row in activities:
        row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        modality_counts[row["type"]] = modality_counts.get(row["type"], 0) + 1
        if row_date >= seven_day_cutoff:
            sessions_7d += 1
            active_days_7d.add(row["date"])
            if _is_hard_session(row):
                hard_sessions_7d += 1
        if row_date >= three_day_cutoff:
            sessions_3d += 1

    feedback_count_14d = len(feedback_rows)
    recent_feedback_count_7d = sum(
        1
        for row in feedback_rows
        if datetime.strptime(row["activity_date"], "%Y-%m-%d").date() >= seven_day_cutoff
    )
    high_rpe_count = sum(1 for row in feedback_rows if int(row["rpe"] or 0) >= 8)
    low_energy_count = sum(1 for row in feedback_rows if int(row["energy"] or 0) <= 2)
    elevated_soreness_count = sum(1 for row in feedback_rows if int(row["muscle_soreness"] or 0) >= 4)
    elevated_pain_count = sum(1 for row in feedback_rows if int(row["pain_level"] or 0) >= 4)
    latest_feedback = dict(feedback_rows[0]) if feedback_rows else None

    current_load = training_load_summary.get("current", {})
    ratio = training_load_summary.get("ratio", {})
    model_coverage = (training_load_summary.get("model") or {}).get("coverage", {})
    form = float(current_load.get("form") or 0)
    ratio_status = ratio.get("status", "low")
    detailed_pct = int(model_coverage.get("detailed_pct") or 0)
    overall_detailed_pct = int(model_coverage.get("overall_pct") or 0)

    feedback_burden = (
        (2 if elevated_pain_count else 0)
        + (1 if low_energy_count else 0)
        + (1 if elevated_soreness_count else 0)
        + (1 if high_rpe_count >= 2 else 0)
    )

    limitation_items: list[str] = []
    if feedback_count_14d == 0:
        limitation_items.append("No recent subjective feedback is logged, so recovery burden is less certain.")
    elif recent_feedback_count_7d == 0:
        limitation_items.append("Recent feedback is older than a week, so the recovery read is slightly stale.")
    if detailed_pct < 50 and overall_detailed_pct < 50:
        limitation_items.append("Recent aerobic load is relying heavily on duration fallbacks rather than detailed HR or power data.")
    elif detailed_pct < 75:
        limitation_items.append("Load detail is only partial, so the strain read is intentionally conservative.")
    if len(modality_counts) >= 2:
        dominant_modality_sessions = max(modality_counts.values())
        if dominant_modality_sessions / activity_count_14d < 0.6:
            limitation_items.append("Recent work is split across modalities, so this shared readiness read stays coarse.")
    if latest_activity_age_days is not None and latest_activity_age_days >= 5:
        limitation_items.append("Training recency is fading, so the short-horizon readiness read is weak.")

    if (
        activity_count_14d < 2
        or total_duration_14d < 75
        or latest_activity_age_days is None
        or latest_activity_age_days >= 10
    ):
        state = "insufficient_data"
    elif (
        feedback_burden >= 4
        or (form <= -18 and (hard_sessions_7d >= 2 or feedback_burden >= 2))
        or (ratio_status == "high" and hard_sessions_7d >= 2)
        or elevated_pain_count >= 1
    ):
        state = "strained"
    elif (
        feedback_burden >= 2
        or (form <= -12 and (hard_sessions_7d >= 1 or sessions_3d >= 2 or feedback_burden >= 1))
        or (ratio_status == "high" and (hard_sessions_7d >= 1 or sessions_3d >= 2 or feedback_burden >= 1))
        or feedback_count_14d == 0
    ):
        state = "watch"
    else:
        latest_energy = int((latest_feedback or {}).get("energy") or 0)
        latest_soreness = int((latest_feedback or {}).get("muscle_soreness") or 0)
        latest_pain = int((latest_feedback or {}).get("pain_level") or 0)
        if (
            latest_feedback
            and latest_energy >= 3
            and latest_soreness <= 3
            and latest_pain <= 2
            and form >= -20
            and not (ratio_status == "high" and (hard_sessions_7d >= 1 or sessions_3d >= 2 or feedback_burden >= 1))
        ):
            state = "ready"
        else:
            state = "watch"

    limitation_score = 0
    limitation_score += 1 if feedback_count_14d == 0 else 0
    limitation_score += 1 if detailed_pct < 50 else 0
    limitation_score += 1 if len(limitation_items) >= 3 else 0
    limitation_score += 1 if activity_count_14d < 4 else 0
    if state == "insufficient_data":
        confidence = "low"
    elif limitation_score >= 2:
        confidence = "low"
    elif limitation_score == 1:
        confidence = "moderate"
    else:
        confidence = "high"

    reasons: list[str] = []
    if state == "ready":
        _append_unique(reasons, "Measured training load and the latest recovery check-in are aligned.")
        if latest_feedback:
            _append_unique(
                reasons,
                f"Latest check-in looks workable: energy {latest_feedback['energy']}/5, soreness {latest_feedback['muscle_soreness']}/5, pain {latest_feedback['pain_level']}/10.",
            )
        if form >= 0:
            _append_unique(reasons, f"Training form is positive at {round(form)}.")
        elif form > -12:
            _append_unique(reasons, f"Training form is only mildly suppressed at {round(form)}.")
    elif state == "watch":
        if hard_sessions_7d >= 2:
            _append_unique(reasons, f"Hard-session density is climbing with {hard_sessions_7d} demanding sessions in the last 7 days.")
        if sessions_3d >= 3:
            _append_unique(reasons, f"{sessions_3d} sessions have stacked into the last 3 days.")
        if feedback_count_14d == 0:
            _append_unique(reasons, "Recent training exists, but no fresh recovery check-in is logged.")
        if low_energy_count or elevated_soreness_count or high_rpe_count:
            _append_unique(
                reasons,
                f"Recent feedback shows some strain signals: {high_rpe_count} high-RPE, {low_energy_count} low-energy, and {elevated_soreness_count} high-soreness check-ins.",
            )
        if ratio_status == "high":
            _append_unique(reasons, "Short-term fatigue is running ahead of longer-term load.")
        elif form <= -12:
            _append_unique(reasons, f"Training form is suppressed at {round(form)}.")
    elif state == "strained":
        if elevated_pain_count:
            _append_unique(reasons, f"Recent feedback includes {elevated_pain_count} elevated-pain check-in{'s' if elevated_pain_count != 1 else ''}.")
        if low_energy_count or elevated_soreness_count:
            _append_unique(
                reasons,
                f"Recovery burden is elevated with {low_energy_count} low-energy and {elevated_soreness_count} high-soreness check-ins.",
            )
        if hard_sessions_7d >= 2:
            _append_unique(reasons, f"Demanding work is compressed into the short term with {hard_sessions_7d} hard sessions in 7 days.")
        if ratio_status == "high" or form <= -18:
            _append_unique(reasons, f"Load markers are strained: ratio is {ratio_status} and form is {round(form)}.")
    else:
        if activity_count_14d < 2:
            _append_unique(reasons, "Too few recent sessions are logged to estimate short-horizon readiness.")
        if total_duration_14d < 75:
            _append_unique(reasons, f"Only {round(total_duration_14d)} minutes of recent training are available in the last 14 days.")
        if latest_activity_age_days is None or latest_activity_age_days >= 10:
            _append_unique(reasons, "Recent activity is too stale to support a useful readiness read.")

    guidance_map = {
        "ready": "Load looks manageable. Stay with the plan and use how you feel during the session as the final guardrail.",
        "watch": "Watch short-term strain. Keep the next 48 hours controlled unless fresh feedback improves the picture.",
        "strained": "Short-term strain is building. The next 48 hours should bias toward recovery or a lighter substitute.",
        "insufficient_data": "Limited by missing recent evidence. Use a calm default and avoid forcing a harder session from this read alone.",
    }
    label_map = {
        "ready": "Balanced",
        "watch": "Watch",
        "strained": "Strained",
        "insufficient_data": "Insufficient data",
    }
    summary_map = {
        "ready": "Load and recovery are aligned.",
        "watch": "Watch short-term strain.",
        "strained": "Short-term strain is building.",
        "insufficient_data": "Limited by missing recovery or activity detail.",
    }

    top_modality = max(modality_counts.items(), key=lambda item: item[1])[0] if modality_counts else None

    supporting_factors = [
        _readiness_factor("sessions_7d", "Sessions in 7d", sessions_7d, "neutral"),
        _readiness_factor("hard_sessions_7d", "Hard sessions in 7d", hard_sessions_7d, "risk" if hard_sessions_7d >= 3 else "steady" if hard_sessions_7d <= 1 else "caution"),
        _readiness_factor("active_days_7d", "Active days in 7d", len(active_days_7d), "risk" if len(active_days_7d) >= 6 else "steady"),
        _readiness_factor("feedback_count_14d", "Feedback entries in 14d", feedback_count_14d, "steady" if feedback_count_14d else "quiet"),
        _readiness_factor("form", "Training form", round(form), "risk" if form <= -18 else "caution" if form <= -12 else "steady"),
        _readiness_factor("load_ratio", "Load ratio", ratio_status, "risk" if ratio_status == "high" else "steady"),
    ]

    return {
        "state": state,
        "available": state != "insufficient_data",
        "label": label_map[state],
        "summary": summary_map[state],
        "guidance_48h": guidance_map[state],
        "confidence": confidence,
        "confidence_label": confidence.title(),
        "reasons": reasons[:4],
        "limitations": limitation_items[:4],
        "supporting_factors": supporting_factors,
        "metrics": {
            "activity_count_14d": activity_count_14d,
            "total_duration_14d": round(total_duration_14d),
            "sessions_7d": sessions_7d,
            "sessions_3d": sessions_3d,
            "active_days_7d": len(active_days_7d),
            "hard_sessions_7d": hard_sessions_7d,
            "feedback_count_14d": feedback_count_14d,
            "high_rpe_count_14d": high_rpe_count,
            "low_energy_count_14d": low_energy_count,
            "elevated_soreness_count_14d": elevated_soreness_count,
            "elevated_pain_count_14d": elevated_pain_count,
            "latest_activity_age_days": latest_activity_age_days,
            "top_modality": top_modality,
        },
        "evidence": {
            "most_recent_activity_date": most_recent_activity_date,
            "feedback_in_last_7d": recent_feedback_count_7d,
            "detailed_load_coverage_pct": detailed_pct,
            "overall_detailed_load_pct": overall_detailed_pct,
            "ratio_status": ratio_status,
        },
        "latest_feedback": latest_feedback,
        "daily_recommendation_status": daily_recommendation.get("status"),
    }
