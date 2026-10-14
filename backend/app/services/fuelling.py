"""Carbs and bottles to bring on a planned ride.

Bands follow common sports-nutrition guidance: 30–60 g/h keeps endurance
rides going, 60–90 g/h supports sweet spot and harder work. Short or recovery
rides need no plan beyond water.

It also names the key session on a day (a hard ride or a lower-body lift), so
Food can ask for a full, carb-leaning day before it, and compares how sessions
felt after fuelled and under-fuelled days for Weekly Review.
"""
import json
import math
import sqlite3
from datetime import date, timedelta
from typing import Optional

from .cycling_workouts import get_cycling_workout, render_cycling_workout

RIDE_TYPES = {"ride", "virtualride", "cycling", "bike"}
HARD_INTENTS = {"tempo", "interval", "race_specific"}
ENDURANCE_INTENTS = {"easy", "long"}

ENDURANCE_MIN_MINUTES = 90
HARD_MIN_MINUTES = 60
BOTTLE_ML = 600
FLUID_ML_PER_H = 500
HOT_FLUID_ML_PER_H = 750


def _target_g_per_h(intent: str, minutes: int) -> int:
    if intent in HARD_INTENTS:
        return 75 if minutes >= 90 else 60
    return 60 if minutes >= 180 else 50 if minutes >= 120 else 40


def _bottles(minutes: int, ml_per_h: int) -> int:
    # Round half up: 2.5 bottles means bring 3.
    return max(1, math.floor(minutes / 60 * ml_per_h / BOTTLE_ML + 0.5))


def build_fuel_plan(day: dict) -> Optional[dict]:
    """Return a fuel plan for a ride long or hard enough to need one, else None."""
    if str(day.get("session_type") or "").strip().lower() not in RIDE_TYPES:
        return None
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    intent = str(day.get("workout_intent") or (workout or {}).get("workout_intent") or "easy").lower()
    minutes = day.get("target_duration_min") or (render_cycling_workout(workout)["duration_min"] if workout else None)
    if not minutes or intent == "recovery":
        return None
    minutes = int(minutes)

    hard = intent in HARD_INTENTS
    if minutes < (HARD_MIN_MINUTES if hard else ENDURANCE_MIN_MINUTES):
        return None

    low, high = (60, 90) if hard else (30, 60)
    target = _target_g_per_h(intent, minutes)
    total = int(math.ceil(target * minutes / 60 / 10) * 10)
    bottles = _bottles(minutes, FLUID_ML_PER_H)
    hot_bottles = _bottles(minutes, HOT_FLUID_ML_PER_H)
    return {
        "intent": intent,
        "duration_min": minutes,
        "carbs_g_per_h": {"low": low, "high": high, "target": target},
        "total_carbs_g": total,
        "bottles": bottles,
        "hot_bottles": hot_bottles,
        "bottle_ml": BOTTLE_ML,
        "summary": f"~{target} g carbs/h · {total} g total · {bottles} bottle{'s' if bottles != 1 else ''}"
        + (f" ({hot_bottles} if hot)" if hot_bottles != bottles else ""),
        "tip": (
            "Start eating in the first 20 minutes and keep going every 20–30 minutes; drink mix counts toward carbs."
            if hard else
            "Eat little and often from the first half hour, before you feel hungry."
        ),
    }


def planned_key_session(conn: sqlite3.Connection, on: date) -> Optional[dict]:
    """The hard ride or lower-body lift planned on ``on``, or None."""
    from .lift_ride_clash import is_hard_ride, is_lower_lift, legs_check

    week_start = (on - timedelta(days=on.weekday())).isoformat()
    try:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    except sqlite3.OperationalError:
        return None
    days = [day for day in json.loads(row["days_json"]) if day.get("date") == on.isoformat()] if row else []
    trains_legs = legs_check(conn)
    for day in days:
        kind = "hard_ride" if is_hard_ride(day) else "leg_day" if is_lower_lift(day, trains_legs) else None
        if kind:
            return {"kind": kind, "date": on.isoformat(), "title": day.get("title") or ("Hard ride" if kind == "hard_ride" else "Leg day")}
    return None


COMPARISON_DAYS = 84
COMPARISON_MIN_DAYS = 4


def _side(rows: list[dict]) -> dict:
    return {
        "days": len({row["previous"] for row in rows}),
        "sessions": len(rows),
        "energy": round(sum(row["energy"] for row in rows) / len(rows), 1) if rows else None,
        "rpe": round(sum(row["rpe"] for row in rows) / len(rows), 1) if rows else None,
    }


def fuel_session_comparison(conn: sqlite3.Connection, through: date, today: Optional[date] = None) -> dict:
    """How sessions felt (post-session energy and RPE) after fuelled versus under-fuelled days.

    Only a session whose previous day was logged counts; an unlogged day is unknown and left out.
    Ready once each side has at least COMPARISON_MIN_DAYS logged days behind a rated session.
    """
    from .food_log import fuel_status_by_day

    start = through - timedelta(days=COMPARISON_DAYS - 1)
    status = fuel_status_by_day(conn, (start - timedelta(days=1)).isoformat(), (through - timedelta(days=1)).isoformat(), today)
    rows = []
    if status:
        try:
            found = conn.execute(
                """
                SELECT a.date, f.rpe, f.energy FROM activity_feedback f JOIN activities a ON a.id = f.activity_id
                WHERE a.date BETWEEN ? AND ? AND a.type != 'Walk'
                """,
                (start.isoformat(), through.isoformat()),
            ).fetchall()
        except sqlite3.OperationalError:
            found = []
        for row in found:
            previous = (date.fromisoformat(row["date"][:10]) - timedelta(days=1)).isoformat()
            if previous in status:
                rows.append({"previous": previous, "under": status[previous]["under"], "rpe": row["rpe"], "energy": row["energy"]})
    fuelled, under = _side([r for r in rows if not r["under"]]), _side([r for r in rows if r["under"]])
    ready = fuelled["days"] >= COMPARISON_MIN_DAYS and under["days"] >= COMPARISON_MIN_DAYS
    summary = None
    if ready:
        gap = round(fuelled["energy"] - under["energy"], 1)
        summary = (
            f"Sessions after fuelled days felt {abs(gap)} energy points {'better' if gap > 0 else 'worse'} on a 1–5 scale."
            if abs(gap) >= 0.3 else "Sessions felt about the same after fuelled and under-fuelled days."
        )
    return {
        "ready": ready,
        "window_days": COMPARISON_DAYS,
        "min_days": COMPARISON_MIN_DAYS,
        "fuelled": fuelled,
        "under": under,
        "summary": summary,
    }
