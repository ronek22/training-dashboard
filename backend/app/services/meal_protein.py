"""Protein per meal: muscle gain wants a decent dose at each main meal, not one big supper.

Each logged main meal (breakfast, obiad, kolacja) under ``MEAL_PROTEIN_MIN_G`` is light. A light
meal gets a quick top-up from the athlete's own saved foods, products and recipes (Polish staples
only when nothing of their own fits). Snacks are shown but never judged, and meals that were not
logged are unknown, so a day with nothing logged has no warnings.
"""
import sqlite3
from typing import Optional

MEAL_PROTEIN_MIN_G = 25
MEALS = ("breakfast", "lunch", "dinner", "snack")
JUDGED_MEALS = ("breakfast", "lunch", "dinner")
# Stored keys follow the Polish day: lunch is obiad (Dinner), dinner is kolacja (Supper).
MEAL_LABELS = {"breakfast": "Breakfast", "lunch": "Dinner", "dinner": "Supper", "snack": "Snack"}
TOP_UPS_PER_MEAL = 2
# A top-up should be protein-forward (share of kcal from protein) and quick, not a second meal.
MIN_PROTEIN_KCAL_SHARE = 0.25
MAX_TOP_UP_KCAL = 600


def _grams(entries: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for entry in entries:
        totals[entry["meal"]] = totals.get(entry["meal"], 0.0) + float(entry["totals"]["protein_g"] or 0)
    return totals


def _top_ups(candidates: list[dict], meal: str, shortfall: float) -> list[dict]:
    from .meal_ideas import _scaled, _totals

    ranked = []
    for candidate in candidates:
        best = None
        for factor in candidate["factors"]:
            items = _scaled(candidate["items"], factor)
            totals = _totals(items)
            if not totals["kcal"] or totals["kcal"] > MAX_TOP_UP_KCAL:
                continue
            if totals["protein_g"] * 4 / totals["kcal"] < MIN_PROTEIN_KCAL_SHARE:
                break
            best = {"key": candidate["key"], "title": candidate["title"], "source": candidate["source"],
                    "meal": meal, "portions": factor, "items": items, "totals": totals}
            if totals["protein_g"] >= shortfall:
                break
        if best:
            ranked.append(best)
    # Closes most of the gap first, then the lightest way to do it.
    ranked.sort(key=lambda idea: (-min(idea["totals"]["protein_g"], shortfall), idea["totals"]["kcal"]))
    return ranked[:TOP_UPS_PER_MEAL]


def build_meal_protein(conn: sqlite3.Connection, entries: list[dict], threshold: float = MEAL_PROTEIN_MIN_G) -> dict:
    """Per-meal protein for one day's entries, with light meals marked and topped up."""
    grams = _grams(entries)
    meals = [
        {
            "meal": meal,
            "label": MEAL_LABELS[meal],
            "protein_g": round(grams[meal], 1),
            "judged": meal in JUDGED_MEALS,
            "light": meal in JUDGED_MEALS and grams[meal] < threshold,
            "short_g": round(max(0.0, threshold - grams[meal])) if meal in JUDGED_MEALS else 0,
            "top_ups": [],
        }
        for meal in MEALS if meal in grams
    ]
    light = [item for item in meals if item["light"]]
    if light:
        from .meal_ideas import _candidates

        try:
            candidates = _candidates(conn)
        except sqlite3.OperationalError:
            candidates = []
        own = [candidate for candidate in candidates if candidate["source"] != "staple"]
        for item in light:
            suitable = [candidate for candidate in own if item["meal"] in candidate["meals"]]
            item["top_ups"] = _top_ups(suitable, item["meal"], item["short_g"]) or _top_ups(
                [candidate for candidate in candidates if candidate["source"] == "staple" and item["meal"] in candidate["meals"]],
                item["meal"], item["short_g"],
            )
    return {"threshold_g": threshold, "meals": meals, "light_count": len(light)}


def meal_protein_by_day(conn: sqlite3.Connection, start: str, end: str) -> dict[str, dict[str, float]]:
    """Logged protein per main meal per day; days with nothing logged are absent."""
    try:
        rows = conn.execute(
            """
            SELECT e.date, e.meal, COALESCE(SUM(i.protein_g), 0) AS protein
            FROM food_entries e LEFT JOIN food_items i ON i.entry_id = e.id
            WHERE e.date BETWEEN ? AND ? GROUP BY e.date, e.meal
            """,
            (start, end),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    days: dict[str, dict[str, float]] = {}
    for row in rows:
        days.setdefault(row["date"], {})
        if row["meal"] in JUDGED_MEALS:
            days[row["date"]][row["meal"]] = round(float(row["protein"]), 1)
    return days


def meal_spread(conn: sqlite3.Connection, days: list[str], threshold: float = MEAL_PROTEIN_MIN_G) -> Optional[dict]:
    """How evenly protein landed across main meals on the given days, from the food log."""
    if not days:
        return None
    by_day = meal_protein_by_day(conn, min(days), max(days))
    logged = [(day, by_day[day]) for day in days if by_day.get(day)]
    light_counts = {meal: 0 for meal in JUDGED_MEALS}
    detail = []
    for day, meals in logged:
        light = [meal for meal, grams in meals.items() if grams < threshold]
        for meal in light:
            light_counts[meal] += 1
        detail.append({"date": day, "meals": meals, "light": light})
    even = sum(1 for item in detail if not item["light"])
    worst = max(light_counts, key=lambda meal: light_counts[meal])
    return {
        "threshold_g": threshold,
        "logged_days": len(logged),
        "even_days": even,
        "share": round(even / len(logged), 2) if logged else None,
        "light_meals": light_counts,
        "most_often_light": {"meal": worst, "label": MEAL_LABELS[worst], "days": light_counts[worst]} if light_counts[worst] else None,
        "days": detail,
    }
