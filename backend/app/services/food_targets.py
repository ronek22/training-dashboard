"""Daily food targets that follow the planned training week.

Each day of the planned week gets a kind (key ride, long ride, lift, easy ride
or rest), an energy target and a carb target. Energy is the usual baseline
(resting × daily life, plus the gain surplus) plus the larger of logged and
planned training, so a plan can only raise a target, never lower it. Carbs
follow common g/kg bands by day kind, one step higher on ride days in a week
whose planned ride hours rise clearly above recent weeks. A lighter week just
loses that step; it never takes the baseline away.
"""
import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from .cycling_workouts import get_cycling_workout, render_cycling_workout
from .lift_ride_clash import LIFT_TYPES, RIDE_TYPES, is_hard_ride

LONG_RIDE_MINUTES = 120
DEFAULT_SESSION_MINUTES = 60
# Net METs (above rest) for a planned session, by what it is.
PLANNED_NET_METS = {"key_ride": 9.5, "long_ride": 6.5, "easy_ride": 6.0, "recovery_ride": 4.0, "lift": 3.5, "run": 8.8}
OTHER_NET_MET = 4.0
CARBS_G_PER_KG = {"key_ride": 6, "long_ride": 7, "easy_ride": 5, "lift": 4, "rest": 3}
BIG_WEEK_CARB_STEP = 1
# A week needs more food when planned ride hours beat recent weeks by both margins.
BIG_WEEK_MIN_EXTRA_H = 1.0
BIG_WEEK_MIN_SHARE = 0.15
KIND_ORDER = ("key_ride", "long_ride", "lift", "easy_ride", "rest")
KIND_LABELS = {"key_ride": "Key ride", "long_ride": "Long ride", "lift": "Lift", "easy_ride": "Easy ride", "rest": "Rest"}


def _type(day: dict) -> str:
    return str(day.get("session_type") or "").strip().lower()


def _minutes(day: dict) -> int:
    if day.get("target_duration_min"):
        return int(day["target_duration_min"])
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    return render_cycling_workout(workout)["duration_min"] if workout else DEFAULT_SESSION_MINUTES


def session_kind(day: dict) -> Optional[str]:
    """What one planned session asks of the day's food; None for rest or mobility."""
    kind = _type(day)
    if kind in RIDE_TYPES:
        if is_hard_ride(day):
            return "key_ride"
        if day.get("workout_intent") == "recovery":
            return "recovery_ride"
        return "long_ride" if day.get("workout_intent") == "long" or _minutes(day) >= LONG_RIDE_MINUTES else "easy_ride"
    if kind in LIFT_TYPES:
        return None if day.get("workout_intent") == "mobility" else "lift"
    if kind in ("run", "trailrun"):
        return "run"
    if kind in ("", "rest") or day.get("workout_intent") in ("mobility", "recovery"):
        return None
    return "other"


def _day_kind(kinds: list[str]) -> str:
    """The biggest food demand among a day's sessions; runs and other work count as an easy ride."""
    mapped = {"recovery_ride": "easy_ride", "run": "easy_ride", "other": "easy_ride"}
    present = {mapped.get(kind, kind) for kind in kinds}
    return next((kind for kind in KIND_ORDER if kind in present), "rest")


def planned_training_kcal(day: dict, weight_kg: float) -> int:
    kind = session_kind(day)
    if kind is None:
        return 0
    return round(PLANNED_NET_METS.get(kind, OTHER_NET_MET) * weight_kg * _minutes(day) / 60)


def _plan_days(conn: sqlite3.Connection, week_start: date) -> Optional[list[dict]]:
    try:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start.isoformat(),)).fetchone()
    except sqlite3.OperationalError:
        return None
    return json.loads(row["days_json"] or "[]") if row else None


def _planned_ride_hours(days: list[dict]) -> float:
    return round(sum(_minutes(day) for day in days if _type(day) in RIDE_TYPES) / 60, 1)


def _arc_ride_hours(conn: sqlite3.Connection, week_start: date) -> tuple[Optional[float], bool]:
    try:
        from .winter_arc import arc_week

        target = arc_week(conn, week_start.isoformat())
    except sqlite3.OperationalError:
        return None, False
    return (target["ride_hours"], bool(target["lighter"])) if target else (None, False)


def _recent_ride_hours(conn: sqlite3.Connection, week_start: date, weeks: int = 4) -> Optional[float]:
    """Average ride hours over the full weeks before ``week_start``; None without history."""
    try:
        row = conn.execute(
            """
            SELECT SUM(duration_min) FROM activities
            WHERE LOWER(type) IN ('ride', 'virtualride', 'mountainbikeride', 'gravelride') AND date >= ? AND date < ?
            """,
            ((week_start - timedelta(weeks=weeks)).isoformat(), week_start.isoformat()),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return round(float(row[0]) / 60 / weeks, 1) if row and row[0] else None


def is_big_week(planned_hours: Optional[float], recent_hours: Optional[float]) -> bool:
    if planned_hours is None or not recent_hours:
        return False
    extra = planned_hours - recent_hours
    return extra >= BIG_WEEK_MIN_EXTRA_H and extra >= recent_hours * BIG_WEEK_MIN_SHARE


def day_carbs_g(kind: str, weight_kg: Optional[float], big_week: bool) -> Optional[int]:
    if not weight_kg:
        return None
    per_kg = CARBS_G_PER_KG[kind] + (BIG_WEEK_CARB_STEP if big_week and kind not in ("rest", "lift") else 0)
    return int(round(per_kg * weight_kg / 10) * 10)


def planned_week(conn: sqlite3.Connection, on: date, weight_kg: Optional[float]) -> dict:
    """The planned Monday–Sunday week around ``on``: day kinds, planned training and the eat-more hint."""
    week_start = on - timedelta(days=on.weekday())
    days = _plan_days(conn, week_start)
    arc_hours, lighter = _arc_ride_hours(conn, week_start)
    planned_hours = _planned_ride_hours(days) if days else arc_hours
    recent_hours = _recent_ride_hours(conn, week_start)
    big_week = is_big_week(planned_hours, recent_hours)
    weight = weight_kg or 75

    out = []
    for offset in range(7):
        key = (week_start + timedelta(days=offset)).isoformat()
        sessions = [day for day in days or [] if day.get("date") == key]
        kind = _day_kind([k for k in (session_kind(day) for day in sessions) if k])
        out.append({
            "date": key,
            "kind": kind,
            "label": KIND_LABELS[kind],
            "sessions": [day.get("title") or day.get("label") for day in sessions if session_kind(day)],
            "planned_training_kcal": sum(planned_training_kcal(day, weight) for day in sessions),
            "carbs_g": day_carbs_g(kind, weight_kg, big_week),
        })

    hint = None
    if big_week:
        hint = (
            f"This week needs more food: about {planned_hours:g} h of riding planned against "
            f"{recent_hours:g} h a week lately. Eat to the targets on ride days, especially before key and long rides."
        )
    return {
        "week_start": week_start.isoformat(),
        "has_plan": days is not None,
        "planned_ride_hours": planned_hours,
        "recent_ride_hours": recent_hours,
        "arc_ride_hours": arc_hours,
        "lighter": lighter,
        "big_week": big_week,
        "hint": hint,
        "days": out,
    }
