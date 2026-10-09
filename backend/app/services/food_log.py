"""Food log for awareness: what was eaten against what the day burned.

The athlete tends to under-eat, so the signal is a shortfall, not a budget.
Burn = resting (Mifflin–St Jeor × a daily-life factor) + net exercise energy.
Only days with at least one logged meal are judged; an empty day is unknown.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from .protein import latest_body_weight, protein_target_g

PROFILE_KEY = "nutrition_profile"
MEALS = ("breakfast", "lunch", "dinner", "snack")
SOURCES = ("text", "photo", "saved", "manual")
LIFE_FACTORS = {"desk": 1.25, "mixed": 1.35, "on_feet": 1.5}
GAIN_SURPLUS_KCAL = 300
# A finished day below this share of the target counts as under-fuelled.
UNDER_SHARE = 0.85
# Net METs (above rest) when an activity has neither calories nor power.
NET_METS = {
    "run": 8.8, "trailrun": 9.0, "ride": 6.5, "virtualride": 6.0, "mountainbikeride": 7.0,
    "gravelride": 6.5, "weighttraining": 3.5, "walk": 2.5, "hike": 5.0, "swim": 6.0,
    "physicaltherapy": 1.5, "yoga": 1.5,
}
DEFAULT_NET_MET = 4.0
MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")


def _parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


def get_nutrition_profile(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (PROFILE_KEY,)).fetchone()
    stored = json.loads(row["value"]) if row else {}
    return {
        "sex": stored.get("sex"),
        "birth_year": stored.get("birth_year"),
        "height_cm": stored.get("height_cm"),
        "daily_life": stored.get("daily_life") or "mixed",
        "goal": stored.get("goal") or "maintain",
    }


def save_nutrition_profile(conn: sqlite3.Connection, payload: dict) -> dict:
    profile = {**get_nutrition_profile(conn), **{k: v for k, v in payload.items() if v is not None}}
    if profile["sex"] not in (None, "male", "female"):
        raise HTTPException(status_code=422, detail="sex must be male or female")
    if profile["daily_life"] not in LIFE_FACTORS:
        raise HTTPException(status_code=422, detail="daily_life must be desk, mixed or on_feet")
    if profile["goal"] not in ("maintain", "gain"):
        raise HTTPException(status_code=422, detail="goal must be maintain or gain")
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (PROFILE_KEY, json.dumps(profile)),
    )
    conn.commit()
    return profile


def resting_kcal(profile: dict, weight_kg: Optional[float], on: date) -> Optional[float]:
    """Mifflin–St Jeor BMR; None until sex, birth year and height are known."""
    if not (weight_kg and profile.get("sex") and profile.get("birth_year") and profile.get("height_cm")):
        return None
    age = on.year - int(profile["birth_year"])
    offset = 5 if profile["sex"] == "male" else -161
    return 10 * weight_kg + 6.25 * float(profile["height_cm"]) - 5 * age + offset


def _activity_net_kcal(row: sqlite3.Row, weight_kg: float, bmr_per_min: float) -> tuple[int, str]:
    minutes = float(row["duration_min"] or 0)
    resting_share = bmr_per_min * minutes
    gross = row["calories"] or row["detail_calories"]
    if gross and gross > 0:
        return max(0, round(gross - resting_share)), "recorded"
    if row["avg_watts"] and minutes:
        # Mechanical kJ ≈ kcal burned at ~24% gross efficiency.
        return max(0, round(row["avg_watts"] * minutes * 60 / 1000 - resting_share)), "power"
    met = NET_METS.get(str(row["type"] or "").lower(), DEFAULT_NET_MET)
    return round(met * weight_kg * minutes / 60), "estimate"


def exercise_by_day(conn: sqlite3.Connection, start: str, end: str, weight_kg: float, bmr: float) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name, a.duration_min, a.avg_watts, a.calories,
               json_extract(d.detail_json, '$.calories') AS detail_calories
        FROM activities a LEFT JOIN activity_details d ON d.activity_id = a.id
        WHERE a.date BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchall()
    days: dict[str, dict] = {}
    for row in rows:
        kcal, basis = _activity_net_kcal(row, weight_kg, bmr / 1440)
        day = days.setdefault(row["date"], {"kcal": 0, "activities": []})
        day["kcal"] += kcal
        day["activities"].append({"id": row["id"], "type": row["type"], "name": row["name"], "kcal": kcal, "basis": basis})
    return days


def _entries(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    entries = [
        dict(row) for row in conn.execute(
            "SELECT id, date, meal, source, raw_text, created_at FROM food_entries WHERE date BETWEEN ? AND ? ORDER BY date, id",
            (start, end),
        )
    ]
    by_id = {entry["id"]: {**entry, "items": []} for entry in entries}
    if by_id:
        marks = ",".join("?" * len(by_id))
        for item in conn.execute(
            f"SELECT id, entry_id, name, grams, kcal, protein_g, carbs_g, fat_g, confidence FROM food_items WHERE entry_id IN ({marks}) ORDER BY id",
            tuple(by_id),
        ):
            by_id[item["entry_id"]]["items"].append({k: item[k] for k in item.keys() if k != "entry_id"})
    for entry in by_id.values():
        entry["totals"] = _sum(entry["items"])
    return list(by_id.values())


def _sum(items: list[dict]) -> dict:
    return {key: round(sum(float(item.get(key) or 0) for item in items), 1) for key in MACROS}


def logged_protein_by_day(conn: sqlite3.Connection, start: str, end: str) -> dict[str, float]:
    try:
        rows = conn.execute(
            """
            SELECT e.date, SUM(i.protein_g) AS protein FROM food_entries e JOIN food_items i ON i.entry_id = e.id
            WHERE e.date BETWEEN ? AND ? GROUP BY e.date
            """,
            (start, end),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row["date"]: float(row["protein"] or 0) for row in rows}


def build_food_day(conn: sqlite3.Connection, day: str, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    selected = _parse_day(day)
    week_start = selected - timedelta(days=6)
    profile = get_nutrition_profile(conn)
    weight = latest_body_weight(conn)
    weight_kg = weight["kg"] if weight else None
    bmr = resting_kcal(profile, weight_kg, selected)

    entries = _entries(conn, week_start.isoformat(), selected.isoformat())
    exercise = exercise_by_day(conn, week_start.isoformat(), selected.isoformat(), weight_kg or 75, bmr or 1700)

    def target_for(key: str) -> Optional[dict]:
        if bmr is None:
            return None
        baseline = bmr * LIFE_FACTORS[profile["daily_life"]]
        training = exercise.get(key, {}).get("kcal", 0)
        surplus = GAIN_SURPLUS_KCAL if profile["goal"] == "gain" else 0
        return {
            "resting": round(bmr),
            "daily_life": round(baseline - bmr),
            "training": training,
            "surplus": surplus,
            "kcal": round(baseline + training + surplus),
        }

    week = []
    for offset in range(7):
        key = (week_start + timedelta(days=offset)).isoformat()
        day_entries = [entry for entry in entries if entry["date"] == key]
        eaten = _sum([item for entry in day_entries for item in entry["items"]])
        target = target_for(key)
        finished = key < today.isoformat()
        gap = round(eaten["kcal"] - target["kcal"]) if target and day_entries else None
        week.append({
            "date": key,
            "logged": bool(day_entries),
            "finished": finished,
            "training_kcal": exercise.get(key, {}).get("kcal", 0),
            "eaten": eaten,
            "target_kcal": target["kcal"] if target else None,
            "gap_kcal": gap,
            "under": bool(target and day_entries and finished and eaten["kcal"] < target["kcal"] * UNDER_SHARE),
        })

    judged = [item for item in week if item["logged"] and item["finished"] and item["gap_kcal"] is not None]
    selected_entries = [entry for entry in entries if entry["date"] == day]
    return {
        "date": day,
        "profile": profile,
        "profile_ready": bmr is not None,
        "weight": weight,
        "entries": selected_entries,
        "totals": _sum([item for entry in selected_entries for item in entry["items"]]),
        "target": target_for(day),
        "protein_target_g": protein_target_g(weight_kg) if weight_kg else None,
        "exercise": exercise.get(day, {"kcal": 0, "activities": []}),
        "week": week,
        "week_summary": {
            "logged_days": len(judged),
            "under_days": sum(1 for item in judged if item["under"]),
            "training_under_days": sum(1 for item in judged if item["under"] and item["training_kcal"] > 0),
            "avg_gap_kcal": round(sum(item["gap_kcal"] for item in judged) / len(judged)) if judged else None,
            "avg_protein_g": round(sum(item["eaten"]["protein_g"] for item in judged) / len(judged)) if judged else None,
        },
    }


def _clean_items(items: list) -> list[dict]:
    cleaned = []
    for item in items:
        name = str(item.get("name") or "").strip()[:120]
        if not name:
            continue
        cleaned.append({
            "name": name,
            "grams": max(0.0, float(item.get("grams") or 0)) or None,
            **{key: max(0.0, round(float(item.get(key) or 0), 1)) for key in MACROS},
            "confidence": item.get("confidence") if item.get("confidence") in ("high", "medium", "low") else None,
        })
    if not cleaned:
        raise HTTPException(status_code=422, detail="Add at least one food item.")
    return cleaned


def _write_entry(conn: sqlite3.Connection, entry_id: Optional[int], payload: dict) -> int:
    day = _parse_day(payload.get("date")).isoformat()
    meal = payload.get("meal") or "snack"
    source = payload.get("source") or "manual"
    if meal not in MEALS or source not in SOURCES:
        raise HTTPException(status_code=422, detail="Unknown meal or source.")
    items = _clean_items(payload.get("items") or [])
    raw_text = (payload.get("raw_text") or "").strip()[:2000] or None
    if entry_id is None:
        entry_id = conn.execute(
            "INSERT INTO food_entries (date, meal, source, raw_text) VALUES (?, ?, ?, ?)", (day, meal, source, raw_text)
        ).lastrowid
    else:
        updated = conn.execute(
            "UPDATE food_entries SET date = ?, meal = ?, source = ?, raw_text = ? WHERE id = ?",
            (day, meal, source, raw_text, entry_id),
        ).rowcount
        if not updated:
            raise HTTPException(status_code=404, detail="Food entry not found")
        conn.execute("DELETE FROM food_items WHERE entry_id = ?", (entry_id,))
    conn.executemany(
        "INSERT INTO food_items (entry_id, name, grams, kcal, protein_g, carbs_g, fat_g, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(entry_id, i["name"], i["grams"], i["kcal"], i["protein_g"], i["carbs_g"], i["fat_g"], i["confidence"]) for i in items],
    )
    conn.commit()
    return entry_id


def create_food_entry(conn: sqlite3.Connection, payload: dict) -> dict:
    _write_entry(conn, None, payload)
    return build_food_day(conn, payload["date"])


def update_food_entry(conn: sqlite3.Connection, entry_id: int, payload: dict) -> dict:
    _write_entry(conn, entry_id, payload)
    return build_food_day(conn, payload["date"])


def delete_food_entry(conn: sqlite3.Connection, entry_id: int) -> dict:
    row = conn.execute("SELECT date FROM food_entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Food entry not found")
    conn.execute("DELETE FROM food_items WHERE entry_id = ?", (entry_id,))
    conn.execute("DELETE FROM food_entries WHERE id = ?", (entry_id,))
    conn.commit()
    return build_food_day(conn, row["date"])


def list_saved_foods(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row) for row in conn.execute(
            "SELECT id, name, grams, kcal, protein_g, carbs_g, fat_g, use_count FROM saved_foods ORDER BY use_count DESC, name COLLATE NOCASE"
        )
    ]


def save_food(conn: sqlite3.Connection, payload: dict) -> list[dict]:
    item = _clean_items([payload])[0]
    conn.execute(
        """
        INSERT INTO saved_foods (name, grams, kcal, protein_g, carbs_g, fat_g) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET grams = excluded.grams, kcal = excluded.kcal, protein_g = excluded.protein_g,
            carbs_g = excluded.carbs_g, fat_g = excluded.fat_g
        """,
        (item["name"], item["grams"], item["kcal"], item["protein_g"], item["carbs_g"], item["fat_g"]),
    )
    conn.commit()
    return list_saved_foods(conn)


def use_saved_food(conn: sqlite3.Connection, food_id: int) -> None:
    conn.execute("UPDATE saved_foods SET use_count = use_count + 1 WHERE id = ?", (food_id,))
    conn.commit()


def delete_saved_food(conn: sqlite3.Connection, food_id: int) -> list[dict]:
    conn.execute("DELETE FROM saved_foods WHERE id = ?", (food_id,))
    conn.commit()
    return list_saved_foods(conn)


def build_nutrition_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """Compact last-7-days intake vs burn for the coach."""
    today = today or datetime.now().date()
    day = build_food_day(conn, today.isoformat(), today)
    return {
        "profile_ready": day["profile_ready"],
        "protein_target_g": day["protein_target_g"],
        "today": {"eaten": day["totals"], "target_kcal": (day["target"] or {}).get("kcal")},
        "days": [
            {k: item[k] for k in ("date", "logged", "training_kcal", "target_kcal", "gap_kcal", "under")}
            | {"kcal": item["eaten"]["kcal"], "protein_g": item["eaten"]["protein_g"]}
            for item in day["week"] if item["logged"]
        ],
        "summary": day["week_summary"],
        "note": "Estimates from text/photo logging (±20–30%). Unlogged days are unknown, not zero. The athlete tends to under-eat.",
    }


def nutrition_coaching_context(conn: sqlite3.Connection) -> Optional[dict]:
    """Week summary for get_recent_context; None when nothing was logged in 7 days."""
    try:
        context = build_nutrition_context(conn)
    except sqlite3.OperationalError:
        return None
    if not context["days"]:
        return None
    return {"summary": context["summary"], "today": context["today"], "detail_tool": "get_nutrition", "note": context["note"]}
