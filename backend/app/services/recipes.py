"""Recipe library: dinners worth keeping, with ingredients, steps and per-serving macros.

Recipes come from a description or a URL (drafted by Claude through the coach helper)
or are typed in. Ingredient macros are for the whole recipe; per-serving values are
derived from them, so editing an ingredient keeps the serving numbers honest.
"""
import json
import sqlite3
from typing import Optional

from fastapi import HTTPException

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")
SOURCES = ("manual", "generated", "url")
MAX_INGREDIENTS = 60
MAX_STEPS = 40


def _number(value, upper: float = 100000) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        amount = round(float(value), 1)
    except (TypeError, ValueError):
        return None
    return min(max(0.0, amount), upper)


def _clean_ingredients(items) -> list[dict]:
    cleaned = []
    for item in (items or [])[:MAX_INGREDIENTS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:120]
        if not name:
            continue
        cleaned.append({
            "name": name,
            "amount": str(item.get("amount") or "").strip()[:60] or None,
            "grams": _number(item.get("grams")),
            **{key: _number(item.get(key)) or 0.0 for key in MACROS},
            **_product_link(item),
        })
    return cleaned


def _product_link(item: dict) -> dict:
    per_100g = item.get("per_100g")
    if not item.get("product_id") or not isinstance(per_100g, dict):
        return {}
    return {"product_id": int(item["product_id"]), "per_100g": {key: _number(per_100g.get(key)) or 0.0 for key in MACROS}}


def _clean_steps(steps) -> list[str]:
    if isinstance(steps, str):
        steps = steps.splitlines()
    return [str(step).strip()[:800] for step in (steps or []) if str(step).strip()][:MAX_STEPS]


def per_serving(ingredients: list[dict], servings: float) -> dict:
    servings = servings or 1
    return {key: round(sum(item[key] for item in ingredients) / servings, 1) for key in MACROS}


def _row_to_recipe(row: sqlite3.Row) -> dict:
    recipe = dict(row)
    recipe["ingredients"] = json.loads(recipe.pop("ingredients_json") or "[]")
    recipe["steps"] = json.loads(recipe.pop("steps_json") or "[]")
    recipe["tags"] = json.loads(recipe.pop("tags_json") or "[]")
    recipe["per_serving"] = {key: recipe.pop(key) for key in MACROS}
    return recipe


SELECT = """
    SELECT r.id, r.title, r.servings, r.minutes, r.source, r.source_url, r.ingredients_json, r.steps_json,
           r.tags_json, r.notes, r.kcal, r.protein_g, r.carbs_g, r.fat_g, r.created_at, r.updated_at,
           (SELECT COUNT(*) FROM dinner_plans p WHERE p.recipe_id = r.id) AS planned_count,
           (SELECT MAX(p.date) FROM dinner_plans p WHERE p.recipe_id = r.id) AS last_planned
    FROM recipes r
"""


def list_recipes(conn: sqlite3.Connection, query: str = "") -> list[dict]:
    rows = conn.execute(
        SELECT + " WHERE r.title LIKE ? ORDER BY planned_count DESC, r.updated_at DESC",
        (f"%{query.strip()}%",),
    ).fetchall()
    return [_row_to_recipe(row) for row in rows]


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> dict:
    row = conn.execute(SELECT + " WHERE r.id = ?", (recipe_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _row_to_recipe(row)


def _values(payload: dict) -> tuple:
    title = str(payload.get("title") or "").strip()[:160]
    if not title:
        raise HTTPException(status_code=422, detail="A recipe needs a title.")
    source = payload.get("source") or "manual"
    if source not in SOURCES:
        raise HTTPException(status_code=422, detail="Unknown recipe source.")
    servings = _number(payload.get("servings"), 50) or 1
    ingredients = _clean_ingredients(payload.get("ingredients"))
    macros = per_serving(ingredients, servings) if any(item["kcal"] for item in ingredients) else {
        key: _number((payload.get("per_serving") or {}).get(key)) or 0.0 for key in MACROS
    }
    minutes = _number(payload.get("minutes"), 1440)
    tags = [str(tag).strip()[:30] for tag in (payload.get("tags") or []) if str(tag).strip()][:10]
    url = str(payload.get("source_url") or "").strip()[:500] or None
    return (
        title, servings, int(minutes) if minutes else None, source, url,
        json.dumps(ingredients, ensure_ascii=False), json.dumps(_clean_steps(payload.get("steps")), ensure_ascii=False),
        json.dumps(tags, ensure_ascii=False), str(payload.get("notes") or "").strip()[:2000] or None,
        *(macros[key] for key in MACROS),
    )


COLUMNS = "title, servings, minutes, source, source_url, ingredients_json, steps_json, tags_json, notes, kcal, protein_g, carbs_g, fat_g"


def create_recipe(conn: sqlite3.Connection, payload: dict) -> dict:
    recipe_id = conn.execute(
        f"INSERT INTO recipes ({COLUMNS}) VALUES ({', '.join('?' * 13)})", _values(payload)
    ).lastrowid
    conn.commit()
    return get_recipe(conn, recipe_id)


def update_recipe(conn: sqlite3.Connection, recipe_id: int, payload: dict) -> dict:
    assignments = ", ".join(f"{column.strip()} = ?" for column in COLUMNS.split(","))
    updated = conn.execute(
        f"UPDATE recipes SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (*_values(payload), recipe_id)
    ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe = get_recipe(conn, recipe_id)
    # Planned dinners show the recipe's current name and numbers.
    conn.execute(
        "UPDATE dinner_plans SET dish = ?, kcal = ? * servings, protein_g = ? * servings WHERE recipe_id = ?",
        (recipe["title"], recipe["per_serving"]["kcal"], recipe["per_serving"]["protein_g"], recipe_id),
    )
    conn.commit()
    return recipe


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> dict:
    """Planned dinners keep their dish name; only the link to the recipe goes."""
    conn.execute("UPDATE dinner_plans SET recipe_id = NULL WHERE recipe_id = ?", (recipe_id,))
    deleted = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,)).rowcount
    conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"ok": True}


def serving_items(recipe: dict, servings: float = 1) -> list[dict]:
    """Food-log items for the portions eaten: the dish as one row counted in portions.

    No grams: a recipe's raw weight (water that boils off, bones, strained vegetables)
    says nothing about what lands in the bowl, so portions are the honest unit.
    """
    servings = servings or 1
    return [{
        "name": recipe["title"],
        "grams": None,
        "portions": servings,
        "recipe_id": recipe["id"],
        **{key: round(recipe["per_serving"][key] * servings, 1) for key in MACROS},
        "confidence": "medium",
    }]
