"""What to eat to close the day's gap: the athlete's own foods first, then a few Polish staples.

The gap is what the day burns minus what was eaten, less today's planned dinner (obiad) when it
is not logged yet. It is split across the meals still ahead (by the clock, for today) in
typical proportions, and each meal gets ideas sized to its share: closing as much of that
share as possible without overshooting, with extra weight on protein while the protein
target is still open. Picking an idea only prefills the log draft; nothing is saved here.
"""
import sqlite3
from typing import Optional

from . import food_log, products as product_book, recipes as recipe_book
from .dinner_plan import PLANNED_MEAL

MACROS = food_log.MACROS
# Below this the day is close enough; no ideas, just a nudge.
CLOSE_ENOUGH_KCAL = 120
# An idea may overshoot its meal's share by this much before it counts as too much.
OVERSHOOT = 1.15
MIN_IDEA_KCAL = 60
IDEAS_PER_MEAL = 4
# Typical share of a day's food per meal, and the hour after which a meal has passed.
MEAL_WEIGHTS = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.3, "snack": 0.1}
MEAL_ENDS = {"breakfast": 11, "lunch": 16, "dinner": 22, "snack": 24}
# Taken off an idea's score when its main food was already eaten today.
REPEAT_PENALTY = 0.2

# Typical portions with per-portion values, and the meals they suit.
STAPLES = [
    ("Skyr z bananem", ("breakfast", "snack"), [("skyr naturalny", 150, 96, 16.5, 6, 0.3), ("banan", 120, 107, 1.3, 27, 0.4)]),
    ("Serek wiejski", ("breakfast", "snack"), [("serek wiejski", 200, 194, 22, 4, 10)]),
    ("Twaróg z miodem", ("breakfast", "snack"), [("twaróg półtłusty", 150, 200, 28, 5.6, 7), ("miód", 15, 49, 0, 12, 0)]),
    ("Owsianka na mleku", ("breakfast",), [("płatki owsiane", 60, 222, 7.8, 36, 4.2), ("mleko 2%", 250, 128, 8.5, 12, 5)]),
    ("Kanapki z szynką", ("breakfast", "lunch", "snack"),
     [("chleb żytni", 80, 196, 5.4, 38, 1.4), ("szynka", 60, 75, 12, 0.8, 2.7), ("masło", 10, 72, 0.1, 0.1, 8.1)]),
    ("Jajecznica z 3 jaj", ("breakfast", "dinner"), [("jajka", 165, 236, 20.7, 1.8, 15.8), ("chleb żytni", 40, 98, 2.7, 19, 0.7)]),
    ("Shake białkowy na mleku", ("snack",), [("odżywka białkowa", 30, 120, 24, 2, 1.5), ("mleko 2%", 300, 153, 10.2, 14.4, 6)]),
    ("Kefir i garść orzechów", ("snack",), [("kefir", 400, 200, 13.6, 17.6, 8), ("orzechy włoskie", 30, 196, 4.6, 4.1, 19.6)]),
    ("Kanapka z masłem orzechowym", ("breakfast", "snack"), [("chleb żytni", 80, 196, 5.4, 38, 1.4), ("masło orzechowe", 32, 188, 8, 6, 16)]),
    ("Kurczak z ryżem", ("lunch", "dinner"),
     [("pierś z kurczaka grillowana", 150, 248, 46.5, 0, 5.4), ("ryż biały gotowany", 200, 260, 5.4, 56, 0.6), ("oliwa", 10, 88, 0, 0, 10)]),
    ("Makaron z tuńczykiem", ("lunch", "dinner"), [("makaron gotowany", 200, 316, 11.6, 62, 1.8), ("tuńczyk w sosie własnym", 120, 139, 31, 0, 1.2)]),
    ("Łosoś z ziemniakami", ("lunch", "dinner"), [("łosoś pieczony", 150, 309, 33, 0, 19.5), ("ziemniaki gotowane", 250, 193, 4.8, 43, 0.3)]),
]


def _item(name, grams, kcal, protein, carbs, fat, confidence="medium") -> dict:
    return {"name": name, "grams": grams, "kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "confidence": confidence}


def _totals(items: list[dict]) -> dict:
    return {key: round(sum(float(item.get(key) or 0) for item in items), 1) for key in MACROS}


def _scaled(items: list[dict], factor: float) -> list[dict]:
    if factor == 1:
        return items
    return [
        {**item, "grams": round(item["grams"] * factor) if item.get("grams") else None,
         **{key: round(float(item.get(key) or 0) * factor, 1) for key in MACROS}}
        for item in items
    ]


def _candidates(conn: sqlite3.Connection) -> list[dict]:
    """Everything that could be eaten, as one portion, with the portion sizes worth trying."""
    found = []
    for food in food_log.list_saved_foods(conn):
        found.append({"key": f"saved-{food['id']}", "title": food["name"], "source": "saved", "meals": tuple(MEAL_WEIGHTS),
                      "factors": (1, 2), "items": [_item(food["name"], food["grams"], *(food[key] for key in MACROS), "high")]})
    try:
        for product in product_book.list_products(conn):
            grams = product["serving_g"] or 100
            values = [round(product["per_100g"][key] * grams / 100, 1) for key in MACROS]
            label = product["name"] + (f" ({product['brand']})" if product["brand"] else "")
            found.append({"key": f"product-{product['id']}", "title": label, "source": "product", "meals": tuple(MEAL_WEIGHTS),
                          "factors": (1, 2, 3, 4), "items": [_item(label, grams, *values, "high")]})
    except sqlite3.OperationalError:
        pass
    try:
        for recipe in recipe_book.list_recipes(conn):
            if not recipe["per_serving"]["kcal"]:
                continue
            items = recipe_book.serving_items(recipe, 1) if recipe["ingredients"] else [
                _item(recipe["title"], None, *(recipe["per_serving"][key] for key in MACROS))
            ]
            found.append({"key": f"recipe-{recipe['id']}", "title": recipe["title"], "source": "recipe",
                          "meals": ("lunch", "dinner"), "factors": (1, 1.5, 2), "items": items})
    except sqlite3.OperationalError:
        pass
    for index, (title, meals, rows) in enumerate(STAPLES):
        found.append({"key": f"staple-{index}", "title": title, "source": "staple", "meals": meals,
                      "factors": (1, 1.5) if set(meals) & {"lunch", "dinner"} else (1,), "items": [_item(*row) for row in rows]})
    return found


def _score(totals: dict, kcal_budget: float, protein_budget: float) -> Optional[float]:
    kcal = totals["kcal"]
    if kcal < MIN_IDEA_KCAL or kcal > kcal_budget * OVERSHOOT:
        return None
    fill = min(kcal, kcal_budget) / kcal_budget
    if protein_budget <= 5:
        return fill
    return 0.55 * fill + 0.45 * min(totals["protein_g"], protein_budget) / protein_budget


def _best_portion(candidate: dict, kcal_budget: float, protein_budget: float) -> Optional[dict]:
    """The portion size that closes most of the meal's share without overshooting it."""
    best = None
    for factor in candidate["factors"]:
        items = _scaled(candidate["items"], factor)
        totals = _totals(items)
        score = _score(totals, kcal_budget, protein_budget)
        if score is not None and (best is None or score > best["score"]):
            best = {"key": candidate["key"], "title": candidate["title"], "source": candidate["source"],
                    "items": items, "totals": totals, "portions": factor, "score": score}
    return best


def _repeats(idea: dict, eaten_words: set[str]) -> bool:
    """The idea's lead word (e.g. "rosół", "skyr") already shows up in today's food."""
    words = product_book._fold(idea["title"]).split()
    return bool(words) and words[0] in eaten_words


def _planned_dinner(conn: sqlite3.Connection, day: str, entries: list[dict]) -> Optional[dict]:
    if any(entry["meal"] == PLANNED_MEAL for entry in entries):
        return None
    try:
        row = conn.execute("SELECT dish, kcal, protein_g FROM dinner_plans WHERE date = ?", (day,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or not row["kcal"]:
        return None
    return {"dish": row["dish"], "kcal": round(row["kcal"]), "protein_g": round(row["protein_g"] or 0)}


def meals_ahead(logged: set[str], hour: Optional[int]) -> list[str]:
    """Meals not logged yet that can still happen. Past days (hour None) keep every unlogged meal.

    A snack always stays open; once every main meal is logged or past, it carries the whole gap.
    """
    ahead = [meal for meal in MEAL_WEIGHTS if meal not in logged and (hour is None or hour < MEAL_ENDS[meal])]
    return ahead or ["snack"]


def build_meal_ideas(conn: sqlite3.Connection, day: str, hour: Optional[int] = None) -> dict:
    food_day = food_log.build_food_day(conn, day)
    target = food_day["target"]
    if not target:
        return {"date": day, "ready": False, "meals": []}
    eaten = food_day["totals"]
    dinner = _planned_dinner(conn, day, food_day["entries"])
    protein_target = food_day["protein_target_g"] or 0
    kcal_left = target["kcal"] - eaten["kcal"] - (dinner["kcal"] if dinner else 0)
    protein_left = max(0.0, protein_target - eaten["protein_g"] - (dinner["protein_g"] if dinner else 0))
    result = {
        "date": day,
        "ready": True,
        "planned_dinner": dinner,
        "left": {"kcal": round(kcal_left), "protein_g": round(protein_left)},
        "meals": [],
    }
    if kcal_left < CLOSE_ENOUGH_KCAL:
        return result

    logged = {entry["meal"] for entry in food_day["entries"]} | ({PLANNED_MEAL} if dinner else set())
    ahead = meals_ahead(logged, hour)
    weight = sum(MEAL_WEIGHTS[meal] for meal in ahead)
    candidates = _candidates(conn)
    eaten_words = {
        word for entry in food_day["entries"] for item in entry["items"] for word in product_book._fold(item["name"]).split()
    }
    for meal in ahead:
        share = MEAL_WEIGHTS[meal] / weight
        kcal_budget, protein_budget = kcal_left * share, protein_left * share
        ranked = [
            idea for idea in (_best_portion(c, kcal_budget, protein_budget) for c in candidates if meal in c["meals"]) if idea
        ]
        # Own foods win near-ties: they are what is actually in the kitchen. Today's repeats sink.
        for idea in ranked:
            idea["score"] += (0 if idea["source"] == "staple" else 0.08) - (REPEAT_PENALTY if _repeats(idea, eaten_words) else 0)
        ranked.sort(key=lambda idea: idea["score"], reverse=True)
        for idea in ranked:
            idea["covers"] = round(min(1, idea["totals"]["kcal"] / kcal_budget) * 100)
            del idea["score"]
        result["meals"].append({
            "meal": meal,
            "kcal": round(kcal_budget),
            "protein_g": round(protein_budget),
            "ideas": ranked[:IDEAS_PER_MEAL],
        })
    return result
