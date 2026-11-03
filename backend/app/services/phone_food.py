"""What the phone's Food tab puts on top: meals to log again, evening picks that close the gap, ride fuel.

- Again: yesterday's meal for this time of day, then meals logged at least twice in the last 30
  days, then saved foods. Logging one copies its items; nothing here writes.
- Gap: after 17:00, once something is logged and protein or kcal is still well short (counting a
  planned obiad), the two foods from the athlete's own log that close most of it (up to a
  dinner's worth) without overshooting. When kcal is
  nearly there only protein counts; after a ride of an hour or more the picks lean on carbs.
- Fuel: today's planned ride fuel plan (see fuelling.py) until a ride is recorded, with the work
  blocks and where to eat drawn to scale.
"""
import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from . import food_log, meal_ideas, products as product_book
from .cycling_workouts import _power_samples, get_cycling_workout
from .fuelling import build_fuel_plan

MACROS = food_log.MACROS
EVENING_HOUR = 17
GAP_PROTEIN_G = 15
GAP_KCAL = 300
FAVOURITE_DAYS = 30
FAVOURITE_MIN = 2
AGAIN_CARDS = 5
HISTORY_DAYS = 60
PICKS = 2
PICK_FACTORS = (0.5, 1, 1.5, 2)
# One pick is at most a dinner; a bigger gap gets a dinner-sized pick, not the whole day.
PICK_MAX_KCAL = 1000
# Protein-only picks may bring this many kcal per gram of protein still missing.
LEAN_KCAL_PER_G = 6
# ...and must get at least this share of their kcal from protein.
LEAN_MIN_PROTEIN_SHARE = 0.25
REFUEL_RIDE_MIN = 60
REFUEL_CARB_SHARE = 0.55
WORK_POWER = 0.84
FIRST_STOP_MIN = 15
STOP_EVERY_MIN = 20


def slot_for_hour(hour: int) -> str:
    return "breakfast" if hour < 11 else "lunch" if hour < 16 else "dinner" if hour < 21 else "snack"


def _item_key(name: str) -> str:
    # Word stems, so "frankfurterki z jagnięciny" and "... jagnięciną" count as one food.
    return " ".join(word[:6] for word in product_book._fold(name).split())


def signature(items: list[dict]) -> tuple:
    return tuple(sorted(_item_key(item["name"]) for item in items))


def _title(items: list[dict]) -> str:
    names = [item["name"] for item in items[:3]]
    text = ", ".join(names) + ("…" if len(items) > 3 else "")
    return text[:1].upper() + text[1:]


def _card(kind: str, entry: dict, count: int = 1) -> dict:
    return {
        "key": f"{kind}-{entry['id']}",
        "kind": kind,
        "meal": entry["meal"],
        "date": entry["date"],
        "count": count,
        "title": _title(entry["items"]),
        "items": entry["items"],
        "totals": entry["totals"],
    }


def _history(conn: sqlite3.Connection, day: str, days: int) -> list[dict]:
    end = date.fromisoformat(day) - timedelta(days=1)
    return food_log._entries(conn, (end - timedelta(days=days - 1)).isoformat(), end.isoformat())


def build_again(conn: sqlite3.Connection, day: str, hour: int, today_entries: list[dict]) -> list[dict]:
    slot = slot_for_hour(hour)
    eaten = {signature(entry["items"]) for entry in today_entries}
    history = _history(conn, day, FAVOURITE_DAYS)
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    cards, seen = [], set(eaten)

    last = [entry for entry in history if entry["date"] == yesterday and entry["meal"] == slot and entry["items"]]
    if last and signature(last[-1]["items"]) not in seen:
        cards.append(_card("yesterday", last[-1]))
        seen.add(signature(last[-1]["items"]))

    groups: dict[tuple, list[dict]] = {}
    for entry in history:
        if entry["items"]:
            groups.setdefault(signature(entry["items"]), []).append(entry)
    favourites = sorted(
        (entries for key, entries in groups.items() if len(entries) >= FAVOURITE_MIN and key not in seen),
        key=lambda entries: (len(entries), entries[-1]["date"]), reverse=True,
    )
    for entries in favourites:
        cards.append(_card("favourite", entries[-1], len(entries)))
        seen.add(signature(entries[-1]["items"]))

    for food in food_log.list_saved_foods(conn):
        item = meal_ideas._item(food["name"], food["grams"], *(food[key] for key in MACROS), "high")
        if signature([item]) in seen:
            continue
        seen.add(signature([item]))
        cards.append({
            "key": f"saved-{food['id']}", "kind": "saved", "meal": slot, "date": None, "count": food["use_count"],
            "title": food["name"], "items": [item], "totals": meal_ideas._totals([item]),
        })
    return cards[:AGAIN_CARDS]


def _candidates(conn: sqlite3.Connection, day: str) -> list[dict]:
    """Whole meals and single foods the athlete has logged, newest first, plus saved foods and products."""
    found: dict[tuple, dict] = {}

    def add(key, title, source, items, last_date=None):
        sig = signature(items)
        if sig in found:
            found[sig]["count"] += 1
            return
        found[sig] = {"key": key, "title": title, "source": source, "items": items, "last_date": last_date, "count": 1,
                      "factors": PICK_FACTORS}

    for entry in reversed(_history(conn, day, HISTORY_DAYS)):
        if not entry["items"]:
            continue
        if len(entry["items"]) > 1:
            add(f"entry-{entry['id']}", _title(entry["items"]), "log", entry["items"], entry["date"])
        for item in entry["items"]:
            clean = {key: item.get(key) for key in ("name", "grams", "portions", "confidence", *MACROS)}
            add(f"item-{item['id']}", item["name"][:1].upper() + item["name"][1:], "log", [clean], entry["date"])
    for food in food_log.list_saved_foods(conn):
        add(f"saved-{food['id']}", food["name"], "saved",
            [meal_ideas._item(food["name"], food["grams"], *(food[key] for key in MACROS), "high")])
    try:
        for product in product_book.list_products(conn):
            grams = product["serving_g"] or 100
            values = [round(product["per_100g"][key] * grams / 100, 1) for key in MACROS]
            label = product["name"] + (f" ({product['brand']})" if product["brand"] else "")
            add(f"product-{product['id']}", label, "product", [meal_ideas._item(label, grams, *values, "high")])
    except sqlite3.OperationalError:
        pass
    return list(found.values())


def _lean_score(totals: dict, kcal_budget: float, protein_budget: float) -> Optional[float]:
    kcal = totals["kcal"]
    if kcal < meal_ideas.MIN_IDEA_KCAL or kcal > kcal_budget * meal_ideas.OVERSHOOT:
        return None
    if totals["protein_g"] * 4 < kcal * LEAN_MIN_PROTEIN_SHARE:
        return None
    return min(totals["protein_g"], protein_budget) / protein_budget - 0.25 * kcal / kcal_budget


def _rode_today(conn: sqlite3.Connection, day: str, min_minutes: float = 0) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM activities WHERE substr(date, 1, 10) = ? AND LOWER(type) LIKE '%ride%' AND COALESCE(duration_min, 0) >= ? LIMIT 1",
            (day, min_minutes),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def build_gap(conn: sqlite3.Connection, day: str, hour: int, food_day: dict) -> Optional[dict]:
    target = food_day["target"]
    # Nothing logged yet means unknown, not hungry.
    if hour < EVENING_HOUR or not target or not food_day["entries"]:
        return None
    eaten = food_day["totals"]
    dinner = meal_ideas._planned_dinner(conn, day, food_day["entries"])
    kcal_left = target["kcal"] - eaten["kcal"] - (dinner["kcal"] if dinner else 0)
    protein_left = max(0.0, (food_day["protein_target_g"] or 0) - eaten["protein_g"] - (dinner["protein_g"] if dinner else 0))
    if kcal_left < GAP_KCAL and protein_left < GAP_PROTEIN_G:
        return None

    refuel = kcal_left >= GAP_KCAL and _rode_today(conn, day, REFUEL_RIDE_MIN)
    focus = "protein" if kcal_left < GAP_KCAL else "refuel" if refuel else "both"
    kcal_budget = min(kcal_left, PICK_MAX_KCAL)
    protein_budget = protein_left * kcal_budget / kcal_left if focus != "protein" and kcal_left > 0 else protein_left
    carbs_budget = kcal_budget * REFUEL_CARB_SHARE / 4 if refuel else 0
    lean_budget = max(kcal_left, 0) + protein_left * LEAN_KCAL_PER_G
    eaten_words = {
        word for entry in food_day["entries"] for item in entry["items"] for word in product_book._fold(item["name"]).split()
    }

    ranked = []
    for candidate in _candidates(conn, day):
        best = None
        for factor in candidate["factors"]:
            items = meal_ideas._scaled(candidate["items"], factor)
            totals = meal_ideas._totals(items)
            score = (_lean_score(totals, lean_budget, protein_left) if focus == "protein"
                     else meal_ideas._score(totals, kcal_budget, protein_budget, carbs_budget))
            if score is not None and (best is None or score > best["score"]):
                best = {"items": items, "totals": totals, "portions": factor, "score": score}
        if best:
            idea = {k: candidate[k] for k in ("key", "title", "source", "last_date", "count")} | best
            if meal_ideas._repeats(idea, eaten_words):
                idea["score"] -= meal_ideas.REPEAT_PENALTY
            ranked.append(idea)
    ranked.sort(key=lambda idea: idea["score"], reverse=True)

    picks, leads = [], set()
    for idea in ranked:
        lead = _item_key(idea["title"]).split()[:1]
        if tuple(lead) in leads:
            continue
        leads.add(tuple(lead))
        del idea["score"]
        picks.append(idea)
        if len(picks) == PICKS:
            break
    return {
        "focus": focus,
        "meal": slot_for_hour(hour),
        "left": {"kcal": round(kcal_left), "protein_g": round(protein_left)},
        "planned_dinner": dinner,
        "picks": picks,
    }


def _work_blocks(workout: Optional[dict]) -> list[list[int]]:
    if not workout:
        return []
    blocks, at, start = [], 0, None
    for seconds, power in _power_samples(workout["steps"]):
        if power >= WORK_POWER and start is None:
            start = at
        elif power < WORK_POWER and start is not None:
            blocks.append([round(start / 60), round(at / 60)])
            start = None
        at += seconds
    if start is not None:
        blocks.append([round(start / 60), round(at / 60)])
    return blocks


def build_fuel(conn: sqlite3.Connection, day: str) -> Optional[dict]:
    on = date.fromisoformat(day)
    week_start = (on - timedelta(days=on.weekday())).isoformat()
    try:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or _rode_today(conn, day):
        return None
    for plan_day in json.loads(row["days_json"] or "[]"):
        if plan_day.get("date") != day:
            continue
        plan = build_fuel_plan(plan_day)
        if not plan:
            continue
        minutes = plan["duration_min"]
        stops = list(range(FIRST_STOP_MIN, minutes - 5, STOP_EVERY_MIN)) or [FIRST_STOP_MIN]
        grams = max(5, round(plan["total_carbs_g"] / len(stops) / 5) * 5)
        return {
            **plan,
            "title": plan_day.get("title") or "Ride",
            "blocks": _work_blocks(get_cycling_workout(plan_day.get("cycling_workout_id"))),
            "stops": [{"min": stop, "carbs_g": grams} for stop in stops],
        }
    return None


def build_food_quick(conn: sqlite3.Connection, day: str, hour: int) -> dict:
    food_day = food_log.build_food_day(conn, day)
    return {
        "date": day,
        "slot": slot_for_hour(hour),
        "again": build_again(conn, day, hour, food_day["entries"]),
        "gap": build_gap(conn, day, hour, food_day),
        "fuel": build_fuel(conn, day),
    }
