import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .activity_feedback import list_recent_feedback_data
from .plans import normalize_plan_session_type
from .settings import get_modality_restrictions_for_conn, modality_for_session_type


def latest_feedback_entry(conn: sqlite3.Connection) -> dict | None:
    items = list_recent_feedback_data(conn, limit=1)
    return items[0] if items else None


def latest_subjective_state(conn: sqlite3.Connection) -> dict | None:
    feedback = latest_feedback_entry(conn)
    if not feedback:
        return None
    return {
        "activity_id": feedback["activity_id"],
        "date": feedback["activity_date"],
        "activity_type": feedback["activity_type"],
        "activity_name": feedback["activity_name"],
        "energy": feedback["energy"],
        "muscle_soreness": feedback["muscle_soreness"],
        "pain_level": feedback["pain_level"],
        "rpe": feedback["rpe"],
        "note": feedback["note"],
    }


def get_today_plan(weekly_plan: Optional[dict]) -> dict | None:
    if not weekly_plan or not weekly_plan.get("days"):
        return None
    today = datetime.now().date().isoformat()
    for day in weekly_plan["days"]:
        if day.get("date") == today:
            return day
    return None


def recent_hard_session(conn: sqlite3.Connection) -> dict | None:
    cutoff = (datetime.now().date() - timedelta(days=2)).isoformat()
    row = conn.execute(
        """
        SELECT
            a.id,
            a.date,
            a.type,
            a.name,
            a.duration_min,
            a.avg_hr,
            a.avg_watts,
            f.rpe
        FROM activities a
        LEFT JOIN activity_feedback f ON f.activity_id = a.id
        WHERE a.date >= ?
        ORDER BY a.date DESC, a.created_at DESC
        LIMIT 8
        """,
        (cutoff,),
    ).fetchall()

    for item in row:
        rpe = int(item["rpe"] or 0)
        avg_hr = int(item["avg_hr"] or 0)
        avg_watts = float(item["avg_watts"] or 0)
        duration_min = float(item["duration_min"] or 0)
        is_hard = (
            rpe >= 8
            or avg_hr >= 168
            or avg_watts >= 220
            or duration_min >= 100
        )
        if is_hard:
            return {
                "activity_id": item["id"],
                "date": item["date"],
                "type": item["type"],
                "name": item["name"],
                "rpe": item["rpe"],
            }
    return None


def build_daily_recommendation(
    conn: sqlite3.Connection,
    training_load_summary: Optional[dict] = None,
    weekly_plan: Optional[dict] = None,
) -> dict:
    feedback = latest_subjective_state(conn)
    training_load = training_load_summary or {
        "current": {"fitness": 0, "fatigue": 0, "form": 0, "daily_load": 0},
        "ratio": {"value": 0.0, "status": "low"},
    }
    today_plan = get_today_plan(weekly_plan)
    plan_type = normalize_plan_session_type(today_plan.get("session_type")) if today_plan else None
    hard_session = recent_hard_session(conn)
    restrictions = get_modality_restrictions_for_conn(conn)
    streak_row = conn.execute("SELECT COUNT(DISTINCT date) AS days FROM activities WHERE date >= date('now', '-6 days')").fetchone()
    recent_streak_days = int(streak_row["days"] or 0) if streak_row else 0

    status = "keep"
    reasons: list[str] = []
    action = "Stay with the planned session."

    pain_level = int(feedback["pain_level"]) if feedback else None
    energy = int(feedback["energy"]) if feedback else None
    soreness = int(feedback["muscle_soreness"]) if feedback else None
    rpe = int(feedback["rpe"]) if feedback else None
    form = float(training_load.get("current", {}).get("form", 0) or 0)
    ratio_status = training_load.get("ratio", {}).get("status", "low")

    if pain_level is not None and pain_level >= 7:
        status = "recover"
        reasons.append(f"Pain signal is high at {pain_level}/10.")
        action = "Recover today and avoid impact."
    elif pain_level is not None and pain_level >= 4:
        status = "reduce"
        reasons.append(f"Pain signal is elevated at {pain_level}/10.")
        action = "Reduce impact and trim intensity today."
    elif energy is not None and soreness is not None and energy <= 2 and soreness >= 4:
        status = "recover"
        reasons.append(f"Energy is low ({energy}/5) and soreness is high ({soreness}/5).")
        action = "Recover today rather than forcing the planned work."
    elif energy is not None and energy <= 2:
        status = "reduce"
        reasons.append(f"Energy is low at {energy}/5.")
        action = "Keep moving, but reduce intensity."
    elif soreness is not None and soreness >= 4:
        status = "reduce"
        reasons.append(f"Muscle soreness is elevated at {soreness}/5.")
        action = "Keep the session easier than planned."

    if status not in {"recover"} and form <= -18:
        status = "reduce"
        reasons.append(f"Training form is suppressed at {round(form)}.")
        action = "Reduce the load today to absorb recent training."
    elif status == "keep" and form >= 8 and ratio_status in {"recovery", "low"} and energy is not None and energy >= 4 and (pain_level or 0) <= 2:
        status = "push"
        reasons.append(f"Form is fresh at {round(form)} with good energy ({energy}/5).")
        action = "You can push a bit if the session calls for quality."

    if status in {"keep", "reduce"} and hard_session:
        reasons.append(f"Recent hard session: {hard_session['type']} on {hard_session['date']}.")
        if status == "keep" and rpe is not None and rpe >= 8:
            status = "reduce"
            action = "Back off a step after the recent hard effort."

    if status == "keep" and recent_streak_days >= 5:
        reasons.append(f"You have trained on {recent_streak_days} of the last 7 days.")

    if today_plan:
        plan_modality = modality_for_session_type(today_plan.get("session_type"))
        plan_restriction = restrictions.get("modalities", {}).get(plan_modality) if plan_modality else None
        if plan_restriction and plan_restriction.get("status") == "blocked":
            status = "adjust"
            reasons.insert(0, f"{plan_restriction['label']} is currently blocked.")
            action = f"Swap {today_plan['title']} out. {plan_restriction['label']} is currently blocked."
        elif plan_restriction and plan_restriction.get("status") == "limited" and status in {"keep", "push"}:
            status = "reduce"
            reasons.insert(0, f"{plan_restriction['label']} is currently limited.")
            action = f"Keep {today_plan['title']} only if it stays easy and symptom-aware."
        if plan_type in {"Rest", "Recovery"}:
            action = "Keep today light and let the recovery day do its job."
        elif status == "recover":
            action = f"Swap {today_plan['title']} for recovery work or rest."
        elif status == "reduce":
            action = f"Keep {today_plan['title']}, but cut volume or intensity."
        elif status == "push":
            action = f"{today_plan['title']} is a good session to lean into today."
        else:
            action = f"Keep the planned {today_plan['title']}."
    elif status == "push":
        action = "You look ready for a productive session if you want one."

    if not reasons:
        reasons.append("No strong recovery warning signals are present.")

    return {
        "status": status,
        "action": action,
        "reasons": reasons[:3],
        "today_plan": today_plan,
        "signals": {
            "latest_feedback": feedback,
            "modality_restrictions": restrictions,
            "training_load": {
                "form": round(form, 1),
                "fatigue": training_load.get("current", {}).get("fatigue"),
                "fitness": training_load.get("current", {}).get("fitness"),
                "ratio_status": ratio_status,
            },
            "recent_hard_session": hard_session,
            "recent_streak_days": recent_streak_days,
        },
    }
