"""A light protein habit on lift days: one yes/no tick, not calorie tracking.

Target is ~1.6 g per kg of body weight. A lift day is a logged strength
session (not recovery/mobility, not a sick day) or a strength session planned
for today. Protein is only known by evening, so yesterday stays answerable.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from .health_data import get_health_metric_history
from .sick_mode import sick_dates

PROTEIN_G_PER_KG = 1.6
PLANNED_STRENGTH_TYPES = {"strength", "weights", "weighttraining"}


def latest_body_weight(conn: sqlite3.Connection) -> Optional[dict]:
    """Most recent weigh-in from manual entries or Apple Health."""
    candidates = []
    row = conn.execute(
        "SELECT date, value FROM metrics WHERE metric = 'weight' AND value > 0 ORDER BY date DESC, id DESC LIMIT 1"
    ).fetchone()
    if row:
        candidates.append({"date": row["date"], "kg": float(row["value"])})
    try:
        health = get_health_metric_history(conn, "weight", 365)
    except sqlite3.OperationalError:
        health = []
    if health:
        candidates.append({"date": health[0]["date"], "kg": float(health[0]["value"])})
    return max(candidates, key=lambda item: item["date"]) if candidates else None


def protein_target_g(weight_kg: float) -> int:
    return int(round(weight_kg * PROTEIN_G_PER_KG / 5) * 5)


def _logged_lift_dates(conn: sqlite3.Connection, start: str, end: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT date FROM activities
        WHERE type = 'WeightTraining' AND date BETWEEN ? AND ?
          AND (workout_intent IS NULL OR workout_intent NOT IN ('recovery', 'mobility'))
        """,
        (start, end),
    ).fetchall()
    return {row["date"] for row in rows}


def _planned_lift(conn: sqlite3.Connection, day: date) -> bool:
    week_start = (day - timedelta(days=day.weekday())).isoformat()
    row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    if not row:
        return False
    return any(
        item.get("date") == day.isoformat()
        and str(item.get("session_type") or "").strip().lower() in PLANNED_STRENGTH_TYPES
        and item.get("workout_intent") != "mobility"
        for item in json.loads(row["days_json"] or "[]")
    )


def build_protein_status(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    window_start = min(week_start, today - timedelta(days=1))

    sick = sick_dates(conn)
    lift_dates = _logged_lift_dates(conn, window_start.isoformat(), today.isoformat()) - sick
    if today.isoformat() not in sick and _planned_lift(conn, today):
        lift_dates.add(today.isoformat())
    ticks = {
        row["date"]: bool(row["protein_hit"])
        for row in conn.execute(
            "SELECT date, protein_hit FROM daily_nutrition WHERE date BETWEEN ? AND ?",
            (window_start.isoformat(), today.isoformat()),
        ).fetchall()
    }

    weight = latest_body_weight(conn)
    target = protein_target_g(weight["kg"]) if weight else None
    # Logged food that reaches the target answers the tick; a manual tick still wins.
    auto_hits = set()
    if target:
        from .food_log import logged_protein_by_day

        for key, grams in logged_protein_by_day(conn, window_start.isoformat(), today.isoformat()).items():
            if key not in ticks and grams >= target:
                ticks[key] = True
                auto_hits.add(key)

    def day_status(day: date) -> dict:
        key = day.isoformat()
        return {"date": key, "is_lift_day": key in lift_dates, "hit": ticks.get(key), "from_food_log": key in auto_hits}

    week_lift_days = sorted(d for d in lift_dates if d >= week_start.isoformat())
    return {
        "target_g": target,
        "g_per_kg": PROTEIN_G_PER_KG,
        "weight": weight,
        "today": day_status(today),
        "yesterday": day_status(today - timedelta(days=1)),
        "week": {
            "lift_days": len(week_lift_days),
            "hits": sum(1 for d in week_lift_days if ticks.get(d)),
            "answered": sum(1 for d in week_lift_days if d in ticks),
        },
    }


def set_protein_tick(conn: sqlite3.Connection, day: str, hit: Optional[bool]) -> dict:
    try:
        parsed = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc
    today = datetime.now().date()
    if parsed > today or (today - parsed).days > 7:
        raise HTTPException(status_code=422, detail="Protein can be ticked for today or the past week only.")
    if hit is None:
        conn.execute("DELETE FROM daily_nutrition WHERE date = ?", (day,))
    else:
        conn.execute(
            """
            INSERT INTO daily_nutrition (date, protein_hit) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET protein_hit = excluded.protein_hit, updated_at = CURRENT_TIMESTAMP
            """,
            (day, 1 if hit else 0),
        )
    conn.commit()
    return build_protein_status(conn, today)
