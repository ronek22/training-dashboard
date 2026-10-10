"""Weekly dinner planner: one planned dinner per day, Monday to Sunday.

A plan is a dish name with optional notes and a rough kcal/protein guess. It sits
next to the training plan so bigger sessions get a bigger dinner, and it turns into
a logged dinner only when the athlete confirms it on the Food page.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from . import recipes as recipe_book

# Sessions worth fuelling for: dinner the night before, and recovery the same evening.
HARD_INTENTS = {"long", "tempo", "threshold", "sweet_spot", "vo2", "vo2max", "intervals", "race"}
LONG_MINUTES = 90
SUGGESTION_LIMIT = 12


def _parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


def week_monday(value: str) -> date:
    day = _parse_day(value)
    return day - timedelta(days=day.weekday())


def _planned_sessions(conn: sqlite3.Connection, start: date, end: date) -> dict[str, list[dict]]:
    """Planned sessions by date across every weekly plan that touches the range."""
    sessions: dict[str, list[dict]] = {}
    monday = start - timedelta(days=start.weekday())
    while monday <= end:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (monday.isoformat(),)).fetchone()
        for item in json.loads(row["days_json"]) if row else []:
            if start.isoformat() <= item.get("date", "") <= end.isoformat() and item.get("session_type") != "rest":
                sessions.setdefault(item["date"], []).append(item)
        monday += timedelta(days=7)
    return sessions


def _is_big(session: dict) -> bool:
    intent = str(session.get("workout_intent") or "").lower()
    return intent in HARD_INTENTS or (session.get("target_duration_min") or 0) >= LONG_MINUTES


def _fuel_hint(today: list[dict], tomorrow: list[dict]) -> Optional[str]:
    big_tomorrow = next((s for s in tomorrow if _is_big(s)), None)
    if big_tomorrow:
        return f"Carb up: {big_tomorrow.get('title') or 'big session'} tomorrow"
    big_today = next((s for s in today if _is_big(s)), None)
    if big_today:
        return "Refuel: carbs and protein after today's session"
    return None


def _suggestions(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT dish, COUNT(*) AS uses, MAX(date) AS last FROM dinner_plans
        GROUP BY dish COLLATE NOCASE ORDER BY uses DESC, last DESC LIMIT ?
        """,
        (SUGGESTION_LIMIT,),
    ).fetchall()
    return [row["dish"] for row in rows]


def build_dinner_week(conn: sqlite3.Connection, week_start: str) -> dict:
    monday = week_monday(week_start)
    sunday = monday + timedelta(days=6)
    plans = {
        row["date"]: dict(row) for row in conn.execute(
            """
            SELECT p.date, p.dish, p.notes, p.kcal, p.protein_g, p.recipe_id, p.servings, r.minutes, r.source,
                   r.carbs_g * p.servings AS carbs_g, r.fat_g * p.servings AS fat_g,
                   r.ingredients_json, r.tags_json, r.source_url
            FROM dinner_plans p LEFT JOIN recipes r ON r.id = p.recipe_id WHERE p.date BETWEEN ? AND ?
            """,
            (monday.isoformat(), sunday.isoformat()),
        )
    }
    logged = {
        row["date"] for row in conn.execute(
            "SELECT DISTINCT date FROM food_entries WHERE meal = 'dinner' AND date BETWEEN ? AND ?",
            (monday.isoformat(), sunday.isoformat()),
        )
    }
    # One day past Sunday so Sunday's dinner knows about Monday's session.
    sessions = _planned_sessions(conn, monday, sunday + timedelta(days=1))
    days = []
    for offset in range(7):
        key = (monday + timedelta(days=offset)).isoformat()
        plan = plans.get(key) or {}
        today_sessions = sessions.get(key, [])
        days.append({
            "date": key,
            "dish": plan.get("dish"),
            "notes": plan.get("notes"),
            "kcal": plan.get("kcal"),
            "protein_g": plan.get("protein_g"),
            "recipe": {
                "id": plan["recipe_id"], "servings": plan["servings"], "minutes": plan["minutes"], "source": plan["source"],
                "carbs_g": plan["carbs_g"], "fat_g": plan["fat_g"], "source_url": plan["source_url"],
                "tags": json.loads(plan["tags_json"] or "[]"),
                # Main ingredients, biggest first, as a one-line description on the board.
                "ingredients": [
                    item["name"] for item in sorted(json.loads(plan["ingredients_json"] or "[]"), key=lambda item: -(item.get("kcal") or 0))
                ][:6],
            } if plan.get("recipe_id") else None,
            "logged": key in logged,
            "training": [
                {"title": s.get("title"), "session_type": s.get("session_type"), "duration_min": s.get("target_duration_min")}
                for s in today_sessions
            ],
            "fuel_hint": _fuel_hint(today_sessions, sessions.get((monday + timedelta(days=offset + 1)).isoformat(), [])),
        })
    return {
        "week_start": monday.isoformat(),
        "days": days,
        "planned": sum(1 for day in days if day["dish"]),
        "suggestions": _suggestions(conn),
    }


def _optional_amount(value) -> Optional[float]:
    if value in (None, ""):
        return None
    amount = round(float(value), 1)
    if amount < 0:
        raise HTTPException(status_code=422, detail="kcal and protein can't be negative")
    return amount


def set_dinner(conn: sqlite3.Connection, day: str, payload: dict) -> dict:
    key = _parse_day(day).isoformat()
    recipe_id = payload.get("recipe_id")
    servings = _optional_amount(payload.get("servings")) or 1
    if recipe_id:
        # A recipe sets the dish and numbers; the plan keeps its own notes.
        recipe = recipe_book.get_recipe(conn, int(recipe_id))
        payload = {
            **payload, "dish": recipe["title"],
            "kcal": round(recipe["per_serving"]["kcal"] * servings, 1),
            "protein_g": round(recipe["per_serving"]["protein_g"] * servings, 1),
        }
    dish = (payload.get("dish") or "").strip()[:160]
    if not dish:
        conn.execute("DELETE FROM dinner_plans WHERE date = ?", (key,))
    else:
        conn.execute(
            """
            INSERT INTO dinner_plans (date, dish, notes, kcal, protein_g, recipe_id, servings, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(date) DO UPDATE SET dish = excluded.dish, notes = excluded.notes, kcal = excluded.kcal,
                protein_g = excluded.protein_g, recipe_id = excluded.recipe_id, servings = excluded.servings,
                updated_at = excluded.updated_at
            """,
            (key, dish, (payload.get("notes") or "").strip()[:500] or None,
             _optional_amount(payload.get("kcal")), _optional_amount(payload.get("protein_g")),
             int(recipe_id) if recipe_id else None, servings),
        )
    conn.commit()
    return build_dinner_week(conn, key)


def dinner_log_items(conn: sqlite3.Connection, day: str) -> dict:
    """What "log as eaten" should prefill: recipe ingredients for the portions planned, or just the dish."""
    key = _parse_day(day).isoformat()
    row = conn.execute("SELECT dish, kcal, protein_g, recipe_id, servings FROM dinner_plans WHERE date = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No dinner planned that day")
    if row["recipe_id"]:
        recipe = recipe_book.get_recipe(conn, row["recipe_id"])
        return {"dish": row["dish"], "items": recipe_book.serving_items(recipe, row["servings"] or 1)}
    items = [{"name": row["dish"], "kcal": row["kcal"] or 0, "protein_g": row["protein_g"] or 0}] if row["kcal"] else []
    return {"dish": row["dish"], "items": items}


def copy_previous_week(conn: sqlite3.Connection, week_start: str) -> dict:
    """Fill this week's empty days with last week's dinners, same weekday."""
    monday = week_monday(week_start)
    previous = monday - timedelta(days=7)
    conn.execute(
        """
        INSERT OR IGNORE INTO dinner_plans (date, dish, notes, kcal, protein_g, recipe_id, servings)
        SELECT date(date, '+7 days'), dish, notes, kcal, protein_g, recipe_id, servings FROM dinner_plans WHERE date BETWEEN ? AND ?
        """,
        (previous.isoformat(), (previous + timedelta(days=6)).isoformat()),
    )
    conn.commit()
    return build_dinner_week(conn, monday.isoformat())
