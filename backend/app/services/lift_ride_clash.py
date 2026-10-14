"""Lift and hard-ride clash rule: keep a lower-body lift off the days next to a hard ride.

A hard ride is sweet spot, threshold or VO2 work (tempo, interval or race-specific intent,
or a sweet-spot/threshold/VO2 workout from the library). A lower-body lift is a lift that
trains legs; upper-body lifts, mobility and easy or Z2 rides never clash.
"""

import sqlite3
from datetime import date, timedelta
from typing import Callable, Iterable, Optional

from .cycling_workouts import get_cycling_workout

HARD_RIDE_INTENTS = {"tempo", "interval", "race_specific"}
HARD_RIDE_CATEGORIES = {"Tempo", "Sweet spot", "Threshold", "VO2 max"}
RIDE_TYPES = {"ride", "virtualride", "cycling", "bike"}
LIFT_TYPES = {"weighttraining", "strength", "weights"}
REASON = "Moved to keep the leg lift off the day next to a hard ride"

LegsCheck = Callable[[dict], bool]


def _type(day: dict) -> str:
    return str(day.get("session_type") or "").strip().lower()


def is_hard_ride(day: dict) -> bool:
    if _type(day) not in RIDE_TYPES:
        return False
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    if workout:
        return workout["category"] in HARD_RIDE_CATEGORIES
    return day.get("workout_intent") in HARD_RIDE_INTENTS


def intent_trains_legs(day: dict) -> bool:
    """Lower-body by intent alone; used when there is no database to read saved workouts from."""
    return day.get("workout_intent") == "strength_lower"


def legs_check(conn: Optional[sqlite3.Connection]) -> LegsCheck:
    """Lower-body or whole-body lift: by intent, or by legs in its saved workout."""
    if conn is None:
        return intent_trains_legs
    from .session_brief import _trains_legs

    def check(day: dict) -> bool:
        try:
            return _trains_legs(day, conn)
        except sqlite3.OperationalError:
            return intent_trains_legs(day)

    return check


def is_lower_lift(day: dict, trains_legs: LegsCheck = intent_trains_legs) -> bool:
    if _type(day) not in LIFT_TYPES or day.get("workout_intent") in ("strength_upper", "mobility"):
        return False
    return trains_legs(day)


def _shift(value: str, days: int) -> str:
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat()


def find_clashes(days: Iterable[dict], trains_legs: LegsCheck = intent_trains_legs) -> list[dict]:
    """Each lower-body lift on the day before or after a hard ride."""
    by_date = {day["date"]: day for day in days}
    clashes = []
    for lift in sorted(by_date.values(), key=lambda item: item["date"]):
        if not is_lower_lift(lift, trains_legs):
            continue
        for offset in (-1, 1):
            ride = by_date.get(_shift(lift["date"], offset))
            if ride and is_hard_ride(ride):
                clashes.append({
                    "lift_date": lift["date"],
                    "lift_title": lift.get("title"),
                    "ride_date": ride["date"],
                    "ride_title": ride.get("title"),
                    "order": "lift_first" if offset == 1 else "ride_first",
                })
    return clashes


def _swapped(days: list[dict], first: str, second: str) -> list[dict]:
    """The week with the sessions of two dates exchanged; an empty date counts as rest."""
    by_date = {day["date"]: day for day in days}
    result = [day for day in days if day["date"] not in (first, second)]
    for source, target in ((first, second), (second, first)):
        if source in by_date:
            result.append({**by_date[source], "date": target, "label": date.fromisoformat(target).strftime("%a")})
    return sorted(result, key=lambda day: day["date"])


def _week_dates(days: list[dict]) -> list[str]:
    start = date.fromisoformat(min(day["date"] for day in days))
    start -= timedelta(days=start.weekday())
    return [(start + timedelta(days=offset)).isoformat() for offset in range(7)]


def best_swap(
    days: list[dict],
    clash: dict,
    trains_legs: LegsCheck = intent_trains_legs,
    locked: Iterable[str] = (),
    pinned: Iterable[str] = (),
) -> Optional[dict]:
    """One within-week swap that clears this clash and leaves fewer clashes overall.

    Moves the lift first, then the ride; ``locked`` dates (past or done) never move and
    ``pinned`` dates (a session the athlete just placed) are only moved as a last resort.
    """
    if not days:
        return None
    locked = set(locked)
    pinned = set(pinned)
    before = len(find_clashes(days, trains_legs))
    options = []
    for rank, mover in enumerate((clash["lift_date"], clash["ride_date"])):
        if mover in locked:
            continue
        for target in _week_dates(days):
            if target == mover or target in locked:
                continue
            trial = _swapped(days, mover, target)
            after = find_clashes(trial, trains_legs)
            moved_keys = {(item["lift_date"], item["ride_date"]) for item in after}
            new_lift = target if mover == clash["lift_date"] else clash["lift_date"]
            new_ride = target if mover == clash["ride_date"] else clash["ride_date"]
            if (new_lift, new_ride) in moved_keys or len(after) >= before:
                continue
            touches_pinned = int(bool(pinned & {mover, target}))
            distance = abs((date.fromisoformat(target) - date.fromisoformat(mover)).days)
            options.append((touches_pinned, len(after), rank, distance, target, mover))
    if not options:
        return None
    *_, target, mover = min(options)
    return {"from_date": mover, "to_date": target}


def resolve_clashes(
    days: list[dict],
    trains_legs: LegsCheck = intent_trains_legs,
    locked: Iterable[str] = (),
    max_swaps: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Swap days until no lift sits next to a hard ride, or no swap helps. Returns (days, swaps)."""
    swaps: list[dict] = []
    current = sorted(days, key=lambda day: day["date"])
    for _ in range(max_swaps):
        clashes = find_clashes(current, trains_legs)
        swap = next((found for found in (best_swap(current, clash, trains_legs, locked) for clash in clashes) if found), None)
        if not swap:
            break
        current = _swapped(current, swap["from_date"], swap["to_date"])
        for moved in (swap["from_date"], swap["to_date"]):
            current = [
                {**day, "planning_rule_reason": REASON} if day["date"] == moved and is_lower_lift(day, trains_legs) else day
                for day in current
            ]
        swaps.append(swap)
    return current, swaps


def plan_clashes(
    days: list[dict],
    trains_legs: LegsCheck = intent_trains_legs,
    locked: Iterable[str] = (),
    pinned: Iterable[str] = (),
) -> list[dict]:
    """Clashes that can still be changed (at least one session is open), each with a suggested swap."""
    locked = set(locked)
    result = []
    for clash in find_clashes(days, trains_legs):
        if clash["lift_date"] in locked and clash["ride_date"] in locked:
            continue
        result.append({**clash, "suggested_swap": best_swap(days, clash, trains_legs, locked, pinned)})
    return result


def locked_dates(conn: Optional[sqlite3.Connection], days: list[dict], today: Optional[date] = None) -> set[str]:
    """Past days and days that already have a recorded activity."""
    if not days:
        return set()
    today_key = (today or date.today()).isoformat()
    dates = sorted(day["date"] for day in days)
    busy: set[str] = set()
    if conn is not None:
        try:
            busy = {row[0] for row in conn.execute(
                "SELECT DISTINCT date FROM activities WHERE date BETWEEN ? AND ?", (dates[0], dates[-1])
            )}
        except sqlite3.OperationalError:
            busy = set()
    return {value for value in _week_dates(days) if value < today_key} | busy
