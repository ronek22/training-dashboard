"""Winter arc: a few dated cycling blocks (base, sweet-spot build, VO2 touch, ...) instead of
planning each week on its own.

Each block sets weekly ride hours and a target ride mix (Z2, sweet spot and VO2 rides per week),
and every Nth week of a block can be lighter. The arc only shapes rides: lifts, anchors and
minimum weeks are never touched.

The weekly planner reads the current block from the coaching context. When a generated week is
saved, ``fit_week_to_arc`` converts easy rides into any key ride the block asks for but the week
is missing, and trims ride time in a lighter week. Days that are past, done, sick, in an illness
or mountain re-entry window, or tagged in life load never get a quality ride.

Weeks also build on each other: ``block_progress`` reads how the previous week went against its
target (key rides hit or missed, ride hours, plan follow-through) for the planner and a one-line
block note. A missed key ride may carry into the next week once, never into a lighter week or a
guarded day, and never out of a week lost to illness, a trip or busy days (``arc_adjust``): the
block is extended or the loss accepted instead of cramming.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException

from ..models.plans import WinterArc
from .cycling_workouts import get_cycling_workout, last_ridden_dates, render_cycling_workout, rotated_workout_id
from .ride_balance import INTENT_TYPES

SCHEMA = """
CREATE TABLE IF NOT EXISTS winter_arc_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    focus TEXT NOT NULL,
    label TEXT NOT NULL,
    weekly_hours REAL NOT NULL,
    ride_mix_json TEXT NOT NULL,
    lighter_every INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

FOCUSES = {"base": "Base", "sweet_spot": "Sweet-spot build", "vo2": "VO2 touch", "maintain": "Maintain"}
MIX_TYPES = (("z2", "Z2"), ("sweet_spot", "Sweet spot"), ("vo2", "VO2"))
MIX_LABELS = dict(MIX_TYPES)
QUALITY_TYPES = ("sweet_spot", "vo2")
LIGHTER_RATIO = 0.6
MIN_EASY_RIDE_MIN = 30
RIDE_TYPES = {"ride", "virtualride", "cycling", "bike"}
CATEGORY_TYPES = {
    "Recovery": "recovery", "Endurance": "z2", "Tempo": "sweet_spot", "Sweet spot": "sweet_spot",
    "Threshold": "sweet_spot", "VO2 max": "vo2",
}
# What an easy ride becomes when the block needs a key ride the week is missing.
KEY_RIDES = {
    "sweet_spot": {"workout_id": "sweet-spot-3x10", "intent": "tempo"},
    "vo2": {"workout_id": "vo2-5x3", "intent": "interval"},
}
REASON = "Winter arc"
CARRY_REASON = f"{REASON}: carried over"
MISSED_STATUSES = {"skipped", "replaced", "rest_day_changed"}


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    try:
        return conn.execute("SELECT * FROM winter_arc_blocks ORDER BY start_date").fetchall()
    except sqlite3.OperationalError:
        return []


def _block(row: sqlite3.Row) -> dict:
    start, end = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
    weeks = (end - start).days // 7 + 1
    lighter_every = int(row["lighter_every"] or 0)
    lighter_weeks = [n for n in range(1, weeks + 1) if lighter_every and n % lighter_every == 0]
    mix = json.loads(row["ride_mix_json"])
    return {
        "id": int(row["id"]),
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "weeks": weeks,
        "focus": row["focus"],
        "focus_label": FOCUSES.get(row["focus"], row["focus"]),
        "label": row["label"],
        "weekly_hours": float(row["weekly_hours"]),
        "ride_mix": {key: int(mix.get(key) or 0) for key, _ in MIX_TYPES},
        "key_types": _key_types(mix),
        "lighter_every": lighter_every,
        "lighter_weeks": [(start + timedelta(weeks=n - 1)).isoformat() for n in lighter_weeks],
    }


def _key_types(mix: dict) -> list[str]:
    """The rides that define the block: its quality rides, or Z2 for a pure base block."""
    quality = [key for key in QUALITY_TYPES if int(mix.get(key) or 0) > 0]
    return quality or (["z2"] if int(mix.get("z2") or 0) > 0 else [])


def list_blocks(conn: sqlite3.Connection) -> list[dict]:
    return [_block(row) for row in _rows(conn)]


def week_target(block: dict, week_start: str) -> dict:
    """What the block asks of one week: ride hours and mix, scaled down in a lighter week."""
    number = (date.fromisoformat(week_start) - date.fromisoformat(block["start_date"])).days // 7 + 1
    lighter = week_start in block["lighter_weeks"]
    mix = dict(block["ride_mix"])
    if lighter:
        # Keep one of each key ride so the block's purpose survives; drop the rest of the volume.
        mix = {key: (min(count, 1) if key in QUALITY_TYPES else max(1, count - 1) if count else 0) for key, count in mix.items()}
    return {
        "block_id": block["id"],
        "label": block["label"],
        "focus": block["focus"],
        "focus_label": block["focus_label"],
        "week_start": week_start,
        "week_number": number,
        "weeks_in_block": block["weeks"],
        "weeks_left": block["weeks"] - number,
        "lighter": lighter,
        "ride_hours": round(block["weekly_hours"] * (LIGHTER_RATIO if lighter else 1), 1),
        "ride_mix": mix,
        "key_types": [key for key in block["key_types"] if mix.get(key)],
    }


def block_for_week(conn: sqlite3.Connection, week_start: str) -> Optional[dict]:
    for block in list_blocks(conn):
        if block["start_date"] <= week_start <= block["end_date"]:
            return block
    return None


def arc_week(conn: sqlite3.Connection, week_start: str) -> Optional[dict]:
    block = block_for_week(conn, week_start)
    return week_target(block, week_start) if block else None


def _recent_ride_hours(conn: sqlite3.Connection, today: date, weeks: int = 6) -> Optional[float]:
    end = _monday(today)
    start = end - timedelta(weeks=weeks)
    try:
        row = conn.execute(
            "SELECT SUM(duration_min) FROM activities WHERE type IN ('Ride', 'VirtualRide') AND date >= ? AND date < ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return round(float(row[0]) / 60 / weeks, 1) if row and row[0] else None


def build_winter_arc(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """The whole arc for the strip: blocks, where today sits, and the current week's target."""
    today = today or date.today()
    blocks = list_blocks(conn)
    this_week = _monday(today).isoformat()
    current = next((block for block in blocks if block["start_date"] <= this_week <= block["end_date"]), None)
    upcoming = next((block for block in blocks if block["start_date"] > this_week), None)
    return {
        "today": today.isoformat(),
        "blocks": blocks,
        "start_date": blocks[0]["start_date"] if blocks else None,
        "end_date": blocks[-1]["end_date"] if blocks else None,
        "current": week_target(current, this_week) if current else None,
        "upcoming": upcoming,
        "status": "none" if not blocks else "active" if current else "upcoming" if upcoming and this_week < blocks[0]["start_date"] else "gap" if upcoming else "finished",
        "recent_ride_hours": _recent_ride_hours(conn, today),
        "focuses": [{"key": key, "label": label} for key, label in FOCUSES.items()],
    }


def save_winter_arc(conn: sqlite3.Connection, arc: WinterArc, today: Optional[date] = None) -> dict:
    """Replace the arc with these blocks (create and edit are the same call)."""
    blocks = sorted(arc.blocks, key=lambda block: block.start_date)
    for index, block in enumerate(blocks):
        if block.focus not in FOCUSES:
            raise HTTPException(status_code=422, detail=f"Unknown focus: {block.focus}")
        if block.start_date.weekday() != 0 or block.end_date.weekday() != 6:
            raise HTTPException(status_code=422, detail="Blocks run Monday to Sunday")
        if block.end_date < block.start_date:
            raise HTTPException(status_code=422, detail="A block cannot end before it starts")
        if index and block.start_date <= blocks[index - 1].end_date:
            raise HTTPException(status_code=422, detail="Blocks cannot overlap")
        if not any(block.ride_mix.model_dump().values()):
            raise HTTPException(status_code=422, detail="Each block needs at least one ride a week")
    ensure_table(conn)
    conn.execute("DELETE FROM winter_arc_blocks")
    for block in blocks:
        conn.execute(
            "INSERT INTO winter_arc_blocks (start_date, end_date, focus, label, weekly_hours, ride_mix_json, lighter_every) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                block.start_date.isoformat(), block.end_date.isoformat(), block.focus,
                (block.label or "").strip() or FOCUSES[block.focus], round(block.weekly_hours, 1),
                json.dumps(block.ride_mix.model_dump()), block.lighter_every,
            ),
        )
    conn.commit()
    return build_winter_arc(conn, today)


def clear_winter_arc(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    from .arc_adjust import clear_adjustments
    from .block_recap import clear_decisions

    ensure_table(conn)
    conn.execute("DELETE FROM winter_arc_blocks")
    clear_adjustments(conn)
    clear_decisions(conn)
    conn.commit()
    return build_winter_arc(conn, today)


# --- Reading and shaping a week's rides -------------------------------------------------------

def _is_ride(day: dict) -> bool:
    return str(day.get("session_type") or "").strip().lower() in RIDE_TYPES


def ride_type(day: dict) -> Optional[str]:
    """z2, sweet_spot, vo2 or recovery for a planned ride; None for anything else."""
    if not _is_ride(day):
        return None
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    if workout:
        return CATEGORY_TYPES.get(workout["category"], "z2")
    return INTENT_TYPES.get(day.get("workout_intent") or "", "z2")


def _ride_minutes(day: dict) -> int:
    if day.get("target_duration_min"):
        return int(day["target_duration_min"])
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    return render_cycling_workout(workout)["duration_min"] if workout else 0


def planned_mix(days: list[dict]) -> dict:
    mix = {key: 0 for key, _ in MIX_TYPES}
    for day in days:
        kind = ride_type(day)
        if kind in mix:
            mix[kind] += 1
    return mix


def _planned_ride_hours(days: list[dict]) -> float:
    return round(sum(_ride_minutes(day) for day in days if _is_ride(day)) / 60, 1)


def _missing(target: dict, mix: dict) -> list[dict]:
    return [
        {"type": key, "label": MIX_LABELS[key], "count": target["ride_mix"][key] - mix.get(key, 0)}
        for key in target["key_types"]
        if mix.get(key, 0) < target["ride_mix"][key]
    ]


def arc_week_status(
    conn: Optional[sqlite3.Connection], days: list[dict], week_start: str, with_progress: bool = False,
) -> Optional[dict]:
    """How a saved week lines up with its arc block (None outside the arc).

    ``with_progress`` adds how last week went and the one-line block note (current and upcoming weeks).
    """
    if conn is None:
        return None
    target = arc_week(conn, week_start)
    if not target:
        return None
    mix = planned_mix(days)
    status = {
        **target,
        "planned_mix": mix,
        "planned_ride_hours": _planned_ride_hours(days),
        "missing": _missing(target, mix),
    }
    if with_progress:
        progress = block_progress(conn, week_start, days)
        status["last_week"] = progress["last_week"]
        status["note"] = progress["note"]
    return status


# --- How last week went, and what carries into this one ---------------------------------------

def _is_carried(day: dict) -> bool:
    return str(day.get("planning_rule_reason") or "").startswith(CARRY_REASON)


def _done_ride_hours(conn: sqlite3.Connection, week_start: str) -> Optional[float]:
    end = (date.fromisoformat(week_start) + timedelta(weeks=1)).isoformat()
    try:
        row = conn.execute(
            "SELECT SUM(duration_min) FROM activities WHERE type IN ('Ride', 'VirtualRide') AND date >= ? AND date < ?",
            (week_start, end),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return round(float(row[0] or 0) / 60, 1)


def last_week_review(conn: sqlite3.Connection, week_start: str) -> dict:
    """The week before ``week_start`` against its arc target: key rides, ride hours, follow-through."""
    # Lazy: plans and plan_follow_through import this module.
    from ..repositories.plans import get_weekly_plan_row
    from .plan_follow_through import OUTCOMES, classify_planned_day
    from .plans import serialize_weekly_plan

    previous = (date.fromisoformat(week_start) - timedelta(weeks=1)).isoformat()
    target = arc_week(conn, previous)
    review = {
        "week_start": previous,
        "label": target["label"] if target else None,
        "week_number": target["week_number"] if target else None,
        "lighter": target["lighter"] if target else False,
        "ride_hours_target": target["ride_hours"] if target else None,
        "ride_hours_done": _done_ride_hours(conn, previous),
        "key_rides": None,
        "follow_through": None,
        "lost": None,
    }
    if target:
        from .arc_adjust import week_disruption

        review["lost"] = week_disruption(conn, previous, review["ride_hours_target"], review["ride_hours_done"])
    row = get_weekly_plan_row(conn, previous)
    if not row:
        return review
    days = serialize_weekly_plan(row, conn)["days"]
    counts = {"planned": 0, "done": 0, "changed": 0, "missed": 0}
    hit, missed = [], []
    for day in days:
        status = (day.get("comparison") or {}).get("status")
        outcome = OUTCOMES.get(status)
        if outcome and classify_planned_day(day):
            counts["planned"] += 1
            counts["done" if outcome == "done" else "changed" if outcome == "changed" else "missed"] += 1
        kind = ride_type(day)
        if kind in QUALITY_TYPES and outcome:
            entry = {"date": day["date"], "type": kind, "label": MIX_LABELS[kind], "carried": _is_carried(day)}
            (missed if status in MISSED_STATUSES else hit).append(entry)
    review["key_rides"] = {"planned": len(hit) + len(missed), "hit": len(hit), "missed": missed}
    review["follow_through"] = counts if counts["planned"] else None
    return review


def _carry_candidate(target: dict, last: dict) -> tuple[Optional[dict], Optional[str]]:
    """The one missed key ride that may move into this week, or why none can."""
    missed = (last.get("key_rides") or {}).get("missed") or []
    if not missed:
        return None, None
    in_block = [ride for ride in missed if ride["type"] in target["key_types"]]
    fresh = [ride for ride in in_block if not ride["carried"]]
    if target["lighter"]:
        return None, "lighter week"
    if last.get("lost"):
        return None, "that week was lost"
    if not in_block:
        return None, "not this block's ride"
    if not fresh:
        return None, "already moved once"
    return fresh[0], None


def _ride_name(kind: str) -> str:
    return "SS" if kind == "sweet_spot" else MIX_LABELS[kind]


def block_progress(conn: sqlite3.Connection, week_start: str, days: Optional[list[dict]] = None) -> Optional[dict]:
    """Where a week sits in its block and how last week went. ``days``: the saved week, if any."""
    target = arc_week(conn, week_start)
    if not target:
        return None
    last = last_week_review(conn, week_start)
    carry, blocked = _carry_candidate(target, last)
    next_start = (date.fromisoformat(week_start) + timedelta(weeks=1)).isoformat()
    following = arc_week(conn, next_start)

    parts = [f"Week {target['week_number']} of {target['weeks_in_block']} in {target['label']}" + (" (lighter)" if target["lighter"] else "")]
    carried = [day for day in days or [] if _is_carried(day)]
    missed = (last.get("key_rides") or {}).get("missed") or []
    if carried:
        parts.append(f"last week's {_ride_name(ride_type(carried[0]) or 'sweet_spot')} ride moved here")
    elif carry:
        parts.append(f"last week's {_ride_name(carry['type'])} ride missed" + (", no safe day to move it" if days is not None else ", may move here once"))
    elif missed:
        parts.append(f"last week's {_ride_name(missed[0]['type'])} ride missed, not carried ({blocked})")
    if last["ride_hours_target"] is not None and last["ride_hours_done"] is not None:
        parts.append(f"last week {last['ride_hours_done']:g} of {last['ride_hours_target']:g} h riding")
    if following and following["block_id"] != target["block_id"]:
        parts.append(f"{following['label']} starts next")
    elif following and following["lighter"]:
        parts.append("lighter week next")
    elif not following:
        parts.append("last week of the arc" if target["weeks_left"] == 0 else "block ends next")

    return {
        "week_start": week_start,
        "last_week": last,
        "carry_over": carry,
        "carry_blocked": blocked,
        "next_week_lighter": bool(following and following["lighter"]),
        "note": ", ".join(parts),
    }


def _guarded_dates(conn: sqlite3.Connection, days: list[dict], today: Optional[date]) -> set[str]:
    """Days that must not get a quality ride: done, past, sick, return windows, tagged life load."""
    from .illness_return import illness_return_dates
    from .life_load import get_life_load_days
    from .lift_ride_clash import locked_dates
    from .mountain_reentry import mountain_reentry_dates
    from .sick_mode import sick_dates

    dates = sorted(day["date"] for day in days)
    guarded = locked_dates(conn, days, today) | sick_dates(conn)
    for read in (illness_return_dates, mountain_reentry_dates):
        try:
            guarded |= read(conn, today)
        except sqlite3.OperationalError:
            pass
    try:
        guarded |= set(get_life_load_days(conn, dates[0], dates[-1]))
    except sqlite3.OperationalError:
        pass
    return guarded


def _adjacent_to_hard(days: list[dict], value: str) -> bool:
    current = date.fromisoformat(value)
    near = {(current + timedelta(days=offset)).isoformat() for offset in (-1, 1)}
    return any(day["date"] in near and ride_type(day) in QUALITY_TYPES for day in days)


def _key_ride(day: dict, kind: str, target: dict, last_ridden: dict[str, str]) -> dict:
    """The block's key ride on ``day``, swapped for an equivalent workout when it was ridden lately."""
    spec = KEY_RIDES[kind]
    workout_id = rotated_workout_id(spec["workout_id"], last_ridden, date.fromisoformat(target["week_start"]))
    workout = render_cycling_workout(get_cycling_workout(workout_id))
    return {
        **day,
        "workout_intent": spec["intent"],
        "cycling_workout_id": workout_id,
        "title": workout["name"],
        "details": f"{target['label']} key ride: {workout['description']}",
        "target_duration_min": workout["duration_min"],
        "target_distance_km": None,
        "planning_rule_reason": f"{REASON}: {target['label']} needs a {MIX_LABELS[kind].lower()} ride this week",
    }


def fit_week_to_arc(
    conn: Optional[sqlite3.Connection], days: list[dict], week_start: str, today: Optional[date] = None,
) -> tuple[list[dict], list[dict]]:
    """Make a generated week carry its block's key rides and respect a lighter week. Rides only."""
    if conn is None:
        return days, []
    target = arc_week(conn, week_start)
    if not target:
        return days, []
    days = [dict(day) for day in days]
    guarded = _guarded_dates(conn, days, today)
    last_ridden = last_ridden_dates(conn)
    changes: list[dict] = []

    for kind in QUALITY_TYPES:
        if kind not in target["key_types"]:
            continue
        for _ in range(max(0, target["ride_mix"][kind] - planned_mix(days)[kind])):
            candidates = [
                day for day in days
                if day["date"] not in guarded and ride_type(day) == "z2" and day.get("workout_intent") != "long"
            ]
            if not candidates:
                break
            # A weekday ride away from other quality rides; the earliest such day wins ties.
            pick = min(candidates, key=lambda day: (
                _adjacent_to_hard(days, day["date"]), date.fromisoformat(day["date"]).weekday() >= 5, day["date"],
            ))
            index = days.index(pick)
            days[index] = _key_ride(pick, kind, target, last_ridden)
            changes.append({"date": pick["date"], "kind": "key_ride", "type": kind, "from": pick.get("title"), "to": days[index]["title"]})

    changes += _carry_over(conn, days, target, guarded, last_ridden)

    if target["lighter"]:
        cap = target["ride_hours"] * 60
        open_easy = [day for day in days if day["date"] not in guarded and ride_type(day) in ("z2", "recovery") and _ride_minutes(day)]
        fixed = sum(_ride_minutes(day) for day in days if _is_ride(day) and day not in open_easy)
        easy_total = sum(_ride_minutes(day) for day in open_easy)
        if easy_total and fixed + easy_total > cap:
            ratio = max(0.0, cap - fixed) / easy_total
            for day in open_easy:
                before = _ride_minutes(day)
                after = max(MIN_EASY_RIDE_MIN, int(5 * round(before * ratio / 5)))
                if after < before:
                    index = days.index(day)
                    days[index] = {
                        **day, "target_duration_min": after, "target_distance_km": None, "cycling_workout_id": None,
                        "planning_rule_reason": f"{REASON}: lighter week, rides trimmed to about {target['ride_hours']:g} h",
                    }
                    changes.append({"date": day["date"], "kind": "lighter", "from_min": before, "to_min": after})
    return days, changes


def _carry_over(
    conn: sqlite3.Connection, days: list[dict], target: dict, guarded: set[str], last_ridden: dict[str, str],
) -> list[dict]:
    """Move last week's missed key ride into this week once, on a free easy weekday. Edits ``days``."""
    carry, _ = _carry_candidate(target, last_week_review(conn, target["week_start"]))
    if not carry or any(_is_carried(day) for day in days):
        return []
    kind = carry["type"]
    reason = f"{CARRY_REASON} last week's missed {MIX_LABELS[kind].lower()} ride (moves once)"
    open_days = [day for day in days if day["date"] not in guarded]
    if planned_mix(days)[kind] > target["ride_mix"][kind]:
        # The planner already added it: mark it so it cannot carry again.
        extra = [day for day in open_days if ride_type(day) == kind and not day.get("planning_rule_reason")]
        if extra:
            days[days.index(extra[-1])] = {**extra[-1], "planning_rule_reason": reason}
            return [{"date": extra[-1]["date"], "kind": "carry_over", "type": kind, "from": carry["date"], "to": extra[-1].get("title")}]
        return []
    candidates = [
        day for day in open_days
        if ride_type(day) == "z2" and day.get("workout_intent") != "long" and not _adjacent_to_hard(days, day["date"])
    ]
    if not candidates:
        return []
    pick = min(candidates, key=lambda day: (date.fromisoformat(day["date"]).weekday() >= 5, day["date"]))
    index = days.index(pick)
    days[index] = {**_key_ride(pick, kind, target, last_ridden), "planning_rule_reason": reason}
    return [{"date": pick["date"], "kind": "carry_over", "type": kind, "from": carry["date"], "to": days[index]["title"]}]


def winter_arc_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Compact note for coaching prompts and the weekly planner."""
    arc = build_winter_arc(conn, today)
    if arc["status"] in ("none", "finished"):
        return None
    this_week = _monday(date.fromisoformat(arc["today"]))
    next_week = (this_week + timedelta(weeks=1)).isoformat()

    def brief(target: Optional[dict]) -> Optional[dict]:
        if not target:
            return None
        progress = block_progress(conn, target["week_start"])
        last = progress["last_week"]
        return {
            **{key: target[key] for key in ("week_start", "label", "focus", "week_number", "weeks_in_block", "weeks_left", "lighter", "ride_hours", "ride_mix", "key_types")},
            "note": progress["note"],
            "last_week": {
                "ride_hours": [last["ride_hours_done"], last["ride_hours_target"]],
                "key_rides": last["key_rides"] and {**last["key_rides"], "missed": [ride["type"] for ride in last["key_rides"]["missed"]]},
                "follow_through": last["follow_through"],
            },
            "carry_over": progress["carry_over"] and progress["carry_over"]["type"],
            "next_week_lighter": progress["next_week_lighter"],
        }

    return {
        "arc": f"{arc['start_date']} to {arc['end_date']}",
        "blocks": [{key: block[key] for key in ("label", "focus", "start_date", "end_date", "weekly_hours", "ride_mix")} for block in arc["blocks"]],
        "this_week": brief(arc["current"]),
        "next_week": brief(arc_week(conn, next_week)),
        "guidance": (
            "Plan rides to the block for the week you are planning: include its key ride types (ride_mix counts are rides "
            "per week; use get_cycling_workout_library), keep total ride time near ride_hours, and in a lighter week "
            "shorten rides rather than dropping lifts. Each week's note and last_week say how the previous week went "
            "(ride_hours is [done, target]); carry_over names a missed key ride that may move into that week once, which "
            "the dashboard places on save on a free easy weekday, never in a lighter week. The arc only shapes rides: lift days, anchor goals, minimum weeks, "
            "illness or mountain re-entry windows and life-load days still win."
        ),
    }
