"""Spot lifts whose estimated 1RM has stopped moving, and suggest one change.

A lift has stalled when its best estimated 1RM of the last ``LOOKBACK_DAYS``
was first reached ``STALL_DAYS`` or more ago and at least ``MIN_SESSIONS_SINCE``
later sessions have not beaten it. Gaps in training are not plateaus: the lift
must still be trained (last session within ``ACTIVE_DAYS``).

The estimate uses Epley on every weighted working set without the usual rep cap,
so extra reps on a maxed-out dumbbell still count as movement. Bodyweight lifts
are skipped. Exactly one change is suggested per lift, picked in this order:

1. Sliding back (last session 5%+ under the best): a micro-deload for that lift.
2. Heaviest dumbbell already in use: slow tempo, the only lever left.
3. Stuck 6+ weeks, or the rep scheme already changed: a variation.
4. Otherwise: a different rep scheme (higher reps for single-joint lifts).
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from .personal_records import BODYWEIGHT_TOKENS, epley_1rm
from .strength_progression import (
    RAMP_UP_SHARE,
    _fmt,
    _increment,
    _is_dumbbell,
    _max_dumbbell_kg,
    _normalize,
    _session_index,
    _working_sets,
)

LOOKBACK_DAYS = 70
STALL_DAYS = 21
LONG_STALL_DAYS = 42
MIN_SESSIONS_SINCE = 2
ACTIVE_DAYS = 21
DECLINE_SHARE = 0.95
DELOAD_SHARE = 0.9
# Ignore e1RM wobble smaller than this when deciding whether a lift moved.
MOVE_KG = 0.5

# Single-joint lifts: heavy low-rep sets are a poor fit, so they get higher reps instead.
ISOLATION_TOKENS = ("curl", "raise", "extension", "skullcrusher", "fly", "kickback", "uprightrow", "shrug")

# Variations that keep the movement pattern but change the stimulus.
VARIATIONS: dict[str, str] = {
    "backsquat": "paused back squats (2 s in the hole)",
    "frontsquat": "paused front squats (2 s in the hole)",
    "barbellinclinebenchpress": "paused incline bench (1 s on the chest)",
    "barbellbenchpress": "close-grip bench press",
    "benchpress": "paused bench press (1 s on the chest)",
    "dumbbellbenchpress": "incline dumbbell press",
    "inclinedumbbellpress": "flat dumbbell bench press",
    "dumbbellinclinebenchpress": "flat dumbbell bench press",
    "romaniandeadlift": "paused Romanian deadlifts (1 s just below the knee)",
    "deadlift": "paused deadlifts (1 s just off the floor)",
    "bentoverbarbellrow": "Pendlay rows (dead stop on the floor each rep)",
    "barbellrow": "Pendlay rows (dead stop on the floor each rep)",
    "dumbbellrow": "chest-supported dumbbell rows",
    "barbellshoulderpress": "seated dumbbell shoulder press",
    "standingdumbbellshoulderpress": "Arnold presses",
    "seateddumbbellshoulderpress": "Arnold presses",
    "dumbbellbicepcurl": "incline dumbbell curls",
    "inclinedumbbellcurl": "hammer curls",
    "hammercurls": "cross-body hammer curls",
    "dumbbellskullcrusher": "overhead dumbbell triceps extensions",
    "dumbbellbulgariansplitsquat": "front-foot-elevated split squats",
}


def _is_bodyweight(name: str) -> bool:
    normalized = _normalize(name)
    return any(token in normalized for token in BODYWEIGHT_TOKENS)


def _session_point(day: date, sets: list[dict]) -> Optional[dict[str, Any]]:
    weighted = [item for item in sets if (item.get("weight_kg") or 0) > 0]
    if not weighted:
        return None
    top = max(float(item["weight_kg"]) for item in weighted)
    working = [item for item in weighted if float(item["weight_kg"]) >= top * RAMP_UP_SHARE]
    top_reps = [int(item["reps"]) for item in working if float(item["weight_kg"]) == top]
    return {
        "date": day,
        "e1rm": round(max(epley_1rm(float(item["weight_kg"]), int(item["reps"])) for item in working), 1),
        "top_load_kg": top,
        "reps": max(top_reps),
        "sets": len(working),
    }


def _lift_history(conn: sqlite3.Connection, since: date, until: date) -> dict[str, dict[str, Any]]:
    lifts: dict[str, dict[str, Any]] = {}
    for session in _session_index(conn):
        day = date.fromisoformat(session["workout_date"][:10])
        if not since <= day < until:
            continue
        for exercise in session.get("exercises", []):
            name = exercise["exercise_name"]
            if _is_bodyweight(name):
                continue
            point = _session_point(day, _working_sets(exercise))
            if point:
                lift = lifts.setdefault(_normalize(name), {"exercise_name": name, "points": []})
                lift["points"].append(point)
    return lifts


def _is_isolation(name: str) -> bool:
    normalized = _normalize(name)
    return any(token in normalized for token in ISOLATION_TOKENS)


def _round_to(value: float, step: float) -> float:
    return round(value / step) * step


def _suggest(name: str, points: list[dict], peak: dict, stalled_days: int, max_dumbbell_kg: Optional[float]) -> dict[str, str]:
    key = _normalize(name)
    last = points[-1]
    top, reps = last["top_load_kg"], last["reps"]
    step = _increment(name, top)
    capped = bool(max_dumbbell_kg and _is_dumbbell(name) and top >= max_dumbbell_kg)

    if last["e1rm"] < peak["e1rm"] * DECLINE_SHARE:
        load = _round_to(top * DELOAD_SHARE, step)
        return {
            "kind": "micro_deload",
            "label": "Micro-deload",
            "text": f"{_fmt(load)} kg × {reps} for all sets today (about 90%), crisp reps only. Back to {_fmt(top)} kg next time.",
        }
    if capped:
        return {
            "kind": "variation",
            "label": "Tempo",
            "text": f"Keep {_fmt(top)} kg but lower every rep over 3 s with a 1 s pause at the stretch, for 3 weeks.",
        }
    reps_since_peak = [point["reps"] for point in points if point["date"] >= peak["date"]]
    rep_scheme_changed = max(reps_since_peak) - min(reps_since_peak) >= 3
    if stalled_days >= LONG_STALL_DAYS or rep_scheme_changed:
        variation = VARIATIONS.get(key)
        if variation:
            return {"kind": "variation", "label": "Variation", "text": f"Swap to {variation} for 3 weeks, then come back to {name.lower()}."}
        return {
            "kind": "variation",
            "label": "Tempo",
            "text": f"Lower every rep over 3 s with a 1 s pause at the stretch for 3 weeks; start {step:g} kg lighter.",
        }
    if _is_isolation(name):
        if reps < 12:
            return {
                "kind": "rep_scheme",
                "label": "Rep scheme",
                "text": f"Switch to 3 × 12–15 at {_fmt(max(top - step, step))} kg for 3 weeks, last set close to failure.",
            }
        return {
            "kind": "rep_scheme",
            "label": "Rep scheme",
            "text": f"Keep {_fmt(top)} kg and finish the last set with a rest-pause: 15 s rest, then 3–5 more reps.",
        }
    if reps <= 7:
        load = _round_to(top * 0.85, step)
        return {
            "kind": "rep_scheme",
            "label": "Rep scheme",
            "text": f"Switch to 3 × 8–10 at {_fmt(load)} kg for 3 weeks, adding reps before load, then return to heavy sets.",
        }
    if max_dumbbell_kg and _is_dumbbell(name) and top + step > max_dumbbell_kg:
        return {
            "kind": "rep_scheme",
            "label": "Rep scheme",
            "text": f"Add a 4th set at {_fmt(top)} kg and take the last set to 1 rep in reserve.",
        }
    return {
        "kind": "rep_scheme",
        "label": "Rep scheme",
        "text": f"Switch to 4 × 5–6 at {_fmt(top + 2 * step)} kg for 3 weeks, then return to {reps}s at a heavier load.",
    }


def find_plateaus(
    conn: sqlite3.Connection,
    today: Optional[date] = None,
    exercise_names: Optional[Iterable[str]] = None,
) -> list[dict[str, Any]]:
    """Stalled lifts, longest stall first. ``exercise_names`` limits the check to those lifts."""
    today = today or date.today()
    wanted = {_normalize(name) for name in exercise_names} if exercise_names is not None else None
    max_dumbbell_kg = _max_dumbbell_kg(conn)
    plateaus = []
    for key, lift in _lift_history(conn, today - timedelta(days=LOOKBACK_DAYS), today).items():
        if wanted is not None and key not in wanted:
            continue
        points = lift["points"]
        best = max(point["e1rm"] for point in points)
        peak = next(point for point in points if point["e1rm"] >= best - MOVE_KG)
        after = [point for point in points if point["date"] > peak["date"]]
        stalled_days = (today - peak["date"]).days
        if stalled_days < STALL_DAYS or len(after) < MIN_SESSIONS_SINCE:
            continue
        if (today - points[-1]["date"]).days > ACTIVE_DAYS:
            continue
        plateaus.append(
            {
                "exercise_name": lift["exercise_name"],
                "e1rm": peak["e1rm"],
                "since": peak["date"].isoformat(),
                "weeks": stalled_days // 7,
                "sessions": len(after) + 1,
                "last": {"date": points[-1]["date"].isoformat(), "e1rm": points[-1]["e1rm"],
                         "top_load_kg": points[-1]["top_load_kg"], "reps": points[-1]["reps"]},
                "suggestion": _suggest(lift["exercise_name"], points, peak, stalled_days, max_dumbbell_kg),
            }
        )
    plateaus.sort(key=lambda item: item["since"])
    return plateaus
