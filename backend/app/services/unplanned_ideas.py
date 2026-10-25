"""Ideas for a day with nothing planned: a lift, an easy ride and a streak saver.

After a trip, or a week that never got planned, the Today card would otherwise only say "No
workout planned". Instead it offers two or three ready sessions, shaped by what is open now:
the mountain re-entry and illness-return windows cap the ride's effort and keep the lift upper
body, a lift is offered while the week is short of three (the anchor goal), and a blocked
modality is never suggested. The last idea is always a few minutes of guided mobility, which
keeps the daily streak on its own.
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .guided_sessions import SESSIONS, estimate_seconds
from .settings import get_modality_restrictions_for_conn

LIFTS_PER_WEEK = 3
STREAK_SESSION = "desk_mobility"
# Effort caps (RPE) where an open window allows only easy or moderate work.
EASY_RPE = 4
RIDE_MINUTES = {"easy": 40, "moderate": 60, "endurance": 75}


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _count(conn: sqlite3.Connection, where: str, params: tuple) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM activities WHERE {where}", params).fetchone()[0] or 0)


def _last_date(conn: sqlite3.Connection, where: str) -> Optional[date]:
    row = conn.execute(f"SELECT MAX(substr(date, 1, 10)) FROM activities WHERE {where}").fetchone()
    return date.fromisoformat(row[0]) if row and row[0] else None


def _days_ago(day: date, last: Optional[date]) -> str:
    if not last:
        return ""
    gap = (day - last).days
    return "yesterday" if gap == 1 else f"{gap} days ago"


def _rpe_cap(*windows: Optional[dict]) -> Optional[int]:
    caps = [window["rpe_cap"] for window in windows if window and window.get("rpe_cap")]
    return min(caps) if caps else None


def _blocked(restrictions: dict, modality: str) -> bool:
    return (restrictions.get("modalities", {}).get(modality) or {}).get("status") == "blocked"


def _lift_idea(conn: sqlite3.Connection, day: date, mountains: Optional[dict], illness: Optional[dict]) -> Optional[dict]:
    monday = day - timedelta(days=day.weekday())
    done = _count(conn, "type = 'WeightTraining' AND substr(date, 1, 10) BETWEEN ? AND ?", (monday.isoformat(), day.isoformat()))
    if done >= LIFTS_PER_WEEK:
        return None
    last = _days_ago(day, _last_date(conn, "type = 'WeightTraining'"))
    week = f"Lift {done + 1} of {LIFTS_PER_WEEK} this week"
    summary = "Next workout from your rotation in Workout Studio, at last time's loads."
    if mountains:
        title, minutes = "Upper-body lift", 40
        summary = "An upper-body workout from Workout Studio. Any leg work at pre-trip loads, 2+ reps in reserve."
        why = f"{week}. Legs are still recovering from the mountains."
    elif illness:
        title, minutes = "Light full-body lift", 35
        why = f"{week}. Back from illness: 3+ reps in reserve and about two thirds of the usual sets."
    else:
        title, minutes = "Strength session", 50
        why = f"{week}{f'; last lift {last}' if last else ''}."
    return {
        "key": "lift",
        "kind": "strength",
        "session_type": "WeightTraining",
        "title": title,
        "minutes": minutes,
        "summary": summary,
        "why": why,
        "action": {"label": "Open Workout Studio", "to": "/strength/workouts"},
    }


def _ride_idea(conn: sqlite3.Connection, day: date, cap: Optional[int], status: str) -> dict:
    last = _days_ago(day, _last_date(conn, "type IN ('Ride', 'VirtualRide')"))
    since = f" Last ride {last}." if last else ""
    if cap is not None and cap <= EASY_RPE or status == "recover":
        title, minutes = "Easy spin", RIDE_MINUTES["easy"]
        summary = f"{minutes} min conversational, RPE ≤{cap or EASY_RPE}. No intervals; flush the legs out."
    elif cap is not None or status == "reduce":
        title, minutes = "Steady ride", RIDE_MINUTES["moderate"]
        summary = f"{minutes} min mostly Zone 2, RPE ≤{cap or 6}. Still no intervals."
    else:
        title, minutes = "Endurance ride", RIDE_MINUTES["endurance"]
        summary = f"{minutes} min in Zone 2, indoors or out. Banks aerobic time without a plan."
    return {
        "key": "ride",
        "kind": "ride",
        "session_type": "Ride",
        "title": title,
        "minutes": minutes,
        "summary": summary,
        "why": ("Easy pedalling helps the legs recover faster than sitting still." if title == "Easy spin" else "Aerobic base keeps building on unplanned days too.") + since,
        "action": None,
    }


def _streak_idea() -> dict:
    session = SESSIONS[STREAK_SESSION]
    minutes = max(1, round(estimate_seconds(session) / 60))
    return {
        "key": "streak",
        "kind": "mobility",
        "session_type": session["type"],
        "title": f"{minutes}-min mobility",
        "minutes": minutes,
        "summary": "Guided follow-along, no kit. Finishing it keeps the streak on its own.",
        "why": "The smallest thing that still counts.",
        "action": {"label": "Start guided session", "to": f"/guided/{STREAK_SESSION}"},
    }


def build_unplanned_ideas(
    conn: sqlite3.Connection,
    *,
    weekly_plan: Optional[dict] = None,
    daily_recommendation: Optional[dict] = None,
    mountain_reentry: Optional[dict] = None,
    illness_return: Optional[dict] = None,
    today: Optional[date] = None,
) -> Optional[dict]:
    """Ideas for today, or None when today has a planned day or already has a session."""
    day = _today(today)
    key = day.isoformat()
    if any(item.get("date") == key for item in (weekly_plan or {}).get("days") or []):
        return None
    if _count(conn, "substr(date, 1, 10) = ?", (key,)):
        return None

    status = (daily_recommendation or {}).get("status") or "keep"
    restrictions = get_modality_restrictions_for_conn(conn)
    ideas: list[dict] = []
    lift = None if _blocked(restrictions, "strength") else _lift_idea(conn, day, mountain_reentry, illness_return)
    ride = None if _blocked(restrictions, "ride") else _ride_idea(conn, day, _rpe_cap(mountain_reentry, illness_return), status)
    # On a recover day the gentlest option leads; otherwise the anchor lift does.
    if status == "recover":
        ideas = [_streak_idea(), *(item for item in (ride, lift) if item)]
    else:
        ideas = [*(item for item in (lift, ride) if item), _streak_idea()]

    if mountain_reentry:
        message = f"{mountain_reentry['headline']}. Nothing is planned, so pick one of these; any of them keeps the streak."
    elif illness_return:
        message = f"{illness_return['headline']}. Nothing is planned, so keep it gentle; any of these keeps the streak."
    else:
        message = "Nothing is planned today. Pick one; any of them keeps the streak."
    return {"date": key, "message": message, "ideas": ideas}
