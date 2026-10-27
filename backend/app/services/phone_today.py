"""The iOS app's Today screen: the widget brief plus the numbers the phone shows."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .checkins import get_daily_checkin
from .dashboard import compute_activity_streak
from .health_data import get_health_metric_history, get_sleep_history
from .plans import serialize_weekly_plan
from .strength_workouts import list_templates
from .widget_brief import _day_status, _plan_row_for, build_widget_brief

RIDE_TYPES = {"ride", "virtualride", "ebikeride", "gravelride", "mountainbikeride"}
RUN_TYPES = {"run", "trailrun", "virtualrun"}
STRENGTH_TYPES = {"weighttraining", "strength", "crossfit"}
MOBILITY_TYPES = {"yoga", "pilates", "mobility", "recovery", "rehab", "stretching"}


def sport_of(kind: Optional[str], intent: Optional[str] = None) -> str:
    """Collapse activity types and planned session types to the app's sport colours."""
    key = str(kind or "").replace(" ", "").lower()
    if key in RIDE_TYPES:
        return "ride"
    if key in RUN_TYPES:
        return "run"
    if key in STRENGTH_TYPES:
        return "strength"
    if key in MOBILITY_TYPES or str(intent or "").lower() in {"mobility", "recovery", "rehab"}:
        return "mobility"
    if key == "workout":
        return "strength"
    if key == "walk":
        return "walk"
    if key == "hike":
        return "hike"
    if key == "rest":
        return "rest"
    return "other"


def _latest(history: list[dict]) -> Optional[float]:
    return history[0]["value"] if history else None


def _exercises_for(conn: sqlite3.Connection, day: Optional[dict]) -> tuple[Optional[dict], Optional[str]]:
    if not day or sport_of(day.get("session_type")) != "strength":
        return None, None
    names = {day.get("template_label"), day.get("title")} - {None}
    template = next((item for item in list_templates(conn) if item["name"] in names), None)
    if not template:
        return None, None
    last = conn.execute(
        """
        SELECT MAX(day) FROM (
            SELECT substr(completed_at, 1, 10) AS day FROM strength_workout_sessions
            WHERE template_id = ? AND status = 'completed'
            UNION ALL
            SELECT date AS day FROM activities WHERE name = ?
        ) WHERE day < ?
        """,
        (template["id"], template["name"], day.get("date")),
    ).fetchone()[0]
    exercises = []
    for exercise in template["exercises"]:
        step = exercise.get("next") or {}
        exercises.append({
            "name": exercise["exercise_name"],
            "sets": exercise["set_count"],
            "reps": step.get("target_reps") or exercise.get("target_reps"),
            "weight_kg": step.get("target_weight_kg") if step else exercise.get("target_weight_kg"),
        })
    return {"template_id": template["id"], "exercises": exercises, "last_done": last}, template["name"]


def build_phone_today(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    brief = build_widget_brief(conn, today)

    row = _plan_row_for(conn, today)
    plan = serialize_weekly_plan(row, conn) if row else None
    days = (plan or {}).get("days") or []
    by_date = {day.get("date"): day for day in days}

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    activities = conn.execute(
        "SELECT date, type, workout_intent, duration_min FROM activities WHERE date >= ? AND date <= ? ORDER BY date, created_at",
        (week_start.isoformat(), week_end.isoformat()),
    ).fetchall()
    done_by_date: dict[str, list[str]] = {}
    minutes_by_sport: dict[str, float] = {}
    for activity in activities:
        sport = sport_of(activity["type"], activity["workout_intent"])
        sports = done_by_date.setdefault(activity["date"], [])
        if sport not in sports:
            sports.append(sport)
        minutes_by_sport[sport] = minutes_by_sport.get(sport, 0) + (activity["duration_min"] or 0)

    week = []
    for offset in range(7):
        day_date = (week_start + timedelta(days=offset)).isoformat()
        day = by_date.get(day_date) or {}
        week.append({
            "date": day_date,
            "label": day.get("label") or (week_start + timedelta(days=offset)).strftime("%a"),
            "title": day.get("title"),
            "sport": sport_of(day.get("session_type"), day.get("workout_intent")) if day else "rest",
            "status": _day_status(day, today) if day else ("today" if day_date == today.isoformat() else "rest"),
            "done_sports": done_by_date.get(day_date, []),
        })

    today_day = by_date.get(today.isoformat())
    strength, _ = _exercises_for(conn, today_day)
    session = brief["today"]
    if session is not None:
        session = {**session, "sport": sport_of(today_day.get("session_type"), today_day.get("workout_intent")), "fallback": today_day.get("fallback"), "strength": strength}

    checkin = get_daily_checkin(conn, today.isoformat()) or {}
    return {
        "date": brief["date"],
        "generated_at": brief["generated_at"],
        "streak_days": compute_activity_streak(conn).get("value") or 0,
        "readiness": brief["readiness"],
        "vitals": {
            "resting_hr": _latest(get_health_metric_history(conn, "resting_hr", 7)),
            "sleep_h": _latest(get_sleep_history(conn, 7)),
            "pain": checkin.get("pain_level"),
        },
        "checkin_done": brief["checkin_done"],
        "sick": brief["sick"],
        "today": session,
        "tomorrow": brief["tomorrow"],
        "week": week,
        "week_minutes": {
            "done": round(sum(minutes_by_sport.values())),
            "planned": round(sum(day.get("target_duration_min") or 0 for day in days)),
            "by_sport": [
                {"sport": sport, "minutes": round(minutes)}
                for sport, minutes in sorted(minutes_by_sport.items(), key=lambda item: -item[1])
                if minutes > 0
            ],
        },
    }
