"""Keep planned load increases honest: how the sets felt, how big the jump is, how many at once.

Double progression alone adds load as soon as every target rep is hit. That ignores the
between-set effort taps and can stack several jumps into one session. This guard runs over a
workout's progressed targets and holds load when:

1. Last time was grinding on most rated sets, or form broke: repeat the load (or go back to the
   lighter load the athlete finished on) and own every rep first.
2. The jump is big (over ``BIG_JUMP_SHARE`` of the load, e.g. 14 → 16 kg dumbbells) and the
   sets were not rated easy: wait until they are.
3. More than ``MAX_LOAD_STEPS`` lifts would go up in one session: the rest hold, lifts rated
   easy go first. One or two changes at a time keep a hard day from turning into a slog.
4. The day is tagged in life load (deadline, poor sleep, travel, ...): no lift goes up.
5. Back from a mountain trip: leg lifts last done before the trip stay at their pre-trip loads.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from .life_load import get_life_load_days
from .mountain_reentry import build_mountain_reentry
from .muscle_gain import muscle_groups_for
from .set_effort import latest_ratings
from .strength_progression import _fmt, _normalize

BIG_JUMP_SHARE = 0.10
MAX_LOAD_STEPS = 2


def _top(lift: Optional[dict]) -> Optional[float]:
    loads = [float(item["weight_kg"]) for item in (lift or {}).get("sets", []) if item.get("weight_kg")]
    return max(loads) if loads else None


def _rises(step: Optional[dict], top: Optional[float]) -> bool:
    return bool(step and top and step.get("target_weight_kg") and step["target_weight_kg"] > top)


def _held(step: dict, load: float, hint: str, reason: str) -> dict:
    return {**step, "target_weight_kg": load, "hint": hint, "held": reason}


def _by_feel(name: str, step: dict, top: float, rating: dict) -> dict:
    counts, total = rating["counts"], rating["total"]
    if counts["form"] or counts["grinding"] * 2 >= total:
        finish = rating.get("finish_load")
        load = min(top, float(finish)) if finish else top
        what = "Form broke" if counts["form"] else "Grinding"
        move = f"back to {_fmt(load)} kg" if load < top else f"stay at {_fmt(top)} kg"
        return _held(step, load, f"{what} at {_fmt(top)} kg last time: {move} and own every rep before adding.", "effort")
    if _rises(step, top) and counts["easy"] * 2 < total:
        jump = (step["target_weight_kg"] - top) / top
        if jump > BIG_JUMP_SHARE:
            return _held(step, top, f"{_fmt(step['target_weight_kg'])} kg is a {round(jump * 100)}% jump. "
                                    f"Stay at {_fmt(top)} kg until the sets feel easy.", "big_jump")
    return step


def guard_steps(conn: sqlite3.Connection, names: list[str], lifts: list[Optional[dict]],
                steps: list[Optional[dict]], today: Optional[date] = None) -> list[Optional[dict]]:
    """``steps`` with load increases held per the rules above; same order as ``names``."""
    today = today or date.today()
    ratings = latest_ratings(conn)
    result: list[Optional[dict]] = []
    for name, lift, step in zip(names, lifts, steps):
        top = _top(lift)
        rating = ratings.get(_normalize(name))
        if step and top and rating and lift and rating["date"] == lift["date"]:
            step = _by_feel(name, step, top, rating)
        result.append(step)

    reentry = build_mountain_reentry(conn, today)
    if reentry:
        trip_end = reentry["trip"]["end_date"]
        for index, (name, lift, step) in enumerate(zip(names, lifts, result)):
            if "legs" in muscle_groups_for(name) and lift and lift["date"] <= trip_end and _rises(step, _top(lift)):
                top = _top(lift)
                result[index] = _held(step, top, f"Back from the mountains: {_fmt(top)} kg like before the trip, 2+ reps in reserve.", "mountain_reentry")

    tagged = get_life_load_days(conn, today.isoformat(), today.isoformat()).get(today.isoformat())
    busy = tagged and [label for tag, label in zip(tagged["tags"], tagged["labels"]) if tag != "mountains"]
    limit = 0 if busy else MAX_LOAD_STEPS
    rising = [index for index, (lift, step) in enumerate(zip(lifts, result)) if _rises(step, _top(lift))]
    # Lifts that felt easy go up first, then workout order.
    easy = lambda index: -(ratings.get(_normalize(names[index])) or {"counts": {}})["counts"].get("easy", 0)
    for index in sorted(rising, key=lambda index: (easy(index), index))[limit:]:
        top = _top(lifts[index])
        hint = (f"{busy[0]} today: holding {_fmt(top)} kg on every lift. Match last time." if busy else
                f"Holding {_fmt(top)} kg today: {MAX_LOAD_STEPS} other lifts already go up. One or two jumps per session.")
        result[index] = _held(result[index], top, hint, "life_load" if busy else "one_change")
    return result
