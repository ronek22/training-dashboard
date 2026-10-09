"""Weekly lift volume per muscle group for a planned week.

Counts hard sets per primary muscle group for the week: sets already logged
this week, plus the saved-workout sets of each lift day still ahead. Any main
group below ``TARGET_SETS_MIN`` gets accessory sets spread over the remaining
lift days, first as extra sets of a matching exercise already in that day's
workout, then as new accessory exercises. It only ever adds sets: lift days are
never removed, moved or shortened. Light days and minimum weeks are left alone.
"""
from __future__ import annotations

import math
import re
import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from .muscle_gain import MUSCLE_GROUPS, TARGET_SETS_MAX, TARGET_SETS_MIN, muscle_groups_for
from .illness_return import illness_return_dates
from .life_load import mountain_dates
from .settings import get_modality_restrictions_for_conn, protected_area_for_exercise
from .sick_mode import sick_dates
from .strength_progression import _max_dumbbell_kg, _normalize, _session_index, _working_sets, latest_next_steps, plan_next_step

MAX_ADDED_SETS_PER_DAY = 8
MAX_SETS_PER_EXERCISE = 5
MAX_SETS_PER_ACCESSORY = 4
DEFAULT_REPS = 10
DEFAULT_REST_SECONDS = 90

# Accessory choices per group, easiest to slot into any session first.
ACCESSORIES: dict[str, list[str]] = {
    "legs": ["Dumbbell Bulgarian Split Squat", "Standing Dumbbell Calf Raise", "Romanian Deadlift"],
    "back": ["Dumbbell Row", "Pull Up"],
    "chest": ["Dumbbell Bench Press", "Push Up"],
    "shoulders": ["Dumbbell Lateral Raise", "Dumbbell Rear Delt Raise"],
    "arms": ["Dumbbell Bicep Curl", "Dumbbell Skullcrusher"],
}
_LIGHT_DAY = re.compile(r"\b(?:light|easy|low energy|recovery|deload|mobility|travel kit)\b", re.IGNORECASE)
# Two or more hiking days in the week cover legs: no leg sets are added on top.
HIKING_DAYS_FOR_LEGS = 2


def _is_lift_day(day: dict) -> bool:
    return bool(re.search(r"strength|weight", str(day.get("session_type") or ""), re.IGNORECASE))


def _templates_by_name(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    try:
        rows = conn.execute(
            """
            SELECT template.name, exercise.exercise_name, exercise.set_count, exercise.target_reps,
                   exercise.target_weight_kg, exercise.rest_seconds
            FROM strength_workout_templates template
            JOIN strength_template_exercises exercise ON exercise.template_id = template.id
            ORDER BY template.id, exercise.exercise_order
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    templates: dict[str, list[dict]] = {}
    for row in rows:
        templates.setdefault(row["name"], []).append(dict(row))
    return templates


def _day_exercises(day: dict, templates: dict[str, list[dict]]) -> list[dict]:
    """Saved-workout exercises for a plan day, matched the way the plan draft matches them."""
    for key in ("template_label", "title"):
        if day.get(key) in templates:
            return templates[day[key]]
    return []


def _empty_counts() -> dict[str, int]:
    return {group["key"]: 0 for group in MUSCLE_GROUPS}


def _accessory_target(name: str, templates: dict[str, list[dict]], history: dict, max_dumbbell_kg: Optional[float]) -> dict:
    saved = next(
        (exercise for exercises in templates.values() for exercise in exercises if _normalize(exercise["exercise_name"]) == _normalize(name)),
        None,
    )
    reps = saved["target_reps"] if saved else DEFAULT_REPS
    step = plan_next_step(history.get(_normalize(name)), name, reps, max_dumbbell_kg)
    return {
        "target_reps": step["target_reps"] if step else reps,
        "target_weight_kg": step["target_weight_kg"] if step else (saved["target_weight_kg"] if saved else None),
        "rest_seconds": saved["rest_seconds"] if saved else DEFAULT_REST_SECONDS,
    }


def _place_sets(
    group: str, count: int, exercises: list[dict], additions: list[dict], day_index: int, body_areas: list[dict], skipped: set[str]
) -> None:
    """Extra sets of a matching exercise already in the day first, then new accessories.

    Lifts that load a protected body area are never extended or added.
    """
    planned = {_normalize(item["exercise_name"]): item["set_count"] for item in exercises}
    for addition in additions:
        if addition["mode"] == "add":
            planned[_normalize(addition["exercise_name"])] = 0
        planned[_normalize(addition["exercise_name"])] = planned.get(_normalize(addition["exercise_name"]), 0) + addition["sets"]
    # The lift with the fewest planned sets takes the extra ones: usually the accessory, not the main lift.
    for exercise in sorted(exercises, key=lambda item: planned[_normalize(item["exercise_name"])]):
        if count <= 0:
            return
        if group not in muscle_groups_for(exercise["exercise_name"]):
            continue
        if protected_area_for_exercise(exercise["exercise_name"], body_areas):
            skipped.add(exercise["exercise_name"])
            continue
        room = MAX_SETS_PER_EXERCISE - planned[_normalize(exercise["exercise_name"])]
        extra = min(room, count)
        if extra > 0:
            additions.append({"exercise_name": exercise["exercise_name"], "group": group, "sets": extra, "mode": "extend"})
            planned[_normalize(exercise["exercise_name"])] += extra
            count -= extra
    options = []
    for name in ACCESSORIES[group]:
        if protected_area_for_exercise(name, body_areas):
            skipped.add(name)
        else:
            options.append(name)
    if not options:
        return
    rotated = options[day_index % len(options):] + options[: day_index % len(options)]
    fresh = [name for name in rotated if _normalize(name) not in planned]
    if not fresh or count <= 0:
        return
    pieces = min(len(fresh), math.ceil(count / MAX_SETS_PER_ACCESSORY))
    for index, name in enumerate(fresh[:pieces]):
        sets = count // pieces + (1 if index < count % pieces else 0)
        additions.append({"exercise_name": name, "group": group, "sets": sets, "mode": "add"})


def build_lift_volume(
    conn: sqlite3.Connection,
    days: list[dict],
    week_start: str,
    *,
    today: Optional[date] = None,
    minimum_week_active: bool = False,
) -> Optional[dict]:
    lift_days = [day for day in days if _is_lift_day(day) and day.get("date")]
    if not lift_days:
        return None
    today_iso = (today or date.today()).isoformat()
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    if week_end < today_iso:
        return None

    labels = {group["key"]: group["label"] for group in MUSCLE_GROUPS}
    templates = _templates_by_name(conn)
    # Sick days, the return-from-illness window and mountain-trip days (no gym) get no extra sets.
    sick = sick_dates(conn) | illness_return_dates(conn, today)
    mountains = mountain_dates(conn, week_start, week_end)
    hiking_covers_legs = len(mountains) >= HIKING_DAYS_FOR_LEGS
    try:
        body_areas = get_modality_restrictions_for_conn(conn).get("body_areas") or []
    except sqlite3.OperationalError:
        body_areas = []
    skipped: set[str] = set()

    done = _empty_counts()
    logged_dates: set[str] = set()
    for session in _session_index(conn):
        day = session["workout_date"][:10]
        if not week_start <= day <= week_end:
            continue
        logged_dates.add(day)
        for exercise in session.get("exercises", []):
            sets = len(_working_sets(exercise))
            for group in muscle_groups_for(exercise["exercise_name"]) if sets else ():
                done[group] += sets

    planned = _empty_counts()
    day_rows: list[dict[str, Any]] = []
    open_days: list[tuple[dict, list[dict]]] = []
    for day in sorted(lift_days, key=lambda item: item["date"]):
        exercises = _day_exercises(day, templates)
        if day["date"] in logged_dates:
            state = "done"
        elif day["date"] < today_iso:
            state = "missed"
        else:
            state = "planned"
            for exercise in exercises:
                for group in muscle_groups_for(exercise["exercise_name"]):
                    planned[group] += exercise["set_count"]
            light = bool(_LIGHT_DAY.search(str(day.get("title") or ""))) or day["date"] in sick or day["date"] in mountains
            if light:
                state = "light"
            elif not minimum_week_active:
                open_days.append((day, exercises))
        day_rows.append({"date": day["date"], "title": day.get("title") or day.get("template_label") or "Lift", "state": state, "additions": []})

    rows_by_date = {row["date"]: row for row in day_rows}
    deficits = {
        group["key"]: TARGET_SETS_MIN - done[group["key"]] - planned[group["key"]]
        for group in MUSCLE_GROUPS
        if group["targeted"] and not (hiking_covers_legs and group["key"] == "legs")
    }
    added = _empty_counts()
    for group in sorted((key for key, gap in deficits.items() if gap > 0), key=lambda key: (-deficits[key], key)):
        remaining = deficits[group]
        # Days that already train the group take the extra sets first, as more sets of a familiar lift.
        ordered = sorted(
            open_days,
            key=lambda item: (not any(group in muscle_groups_for(exercise["exercise_name"]) for exercise in item[1]), item[0]["date"]),
        )
        for index, (day, exercises) in enumerate(ordered):
            if remaining <= 0:
                break
            row = rows_by_date[day["date"]]
            capacity = MAX_ADDED_SETS_PER_DAY - sum(item["sets"] for item in row["additions"])
            share = min(capacity, math.ceil(remaining / (len(ordered) - index)))
            if share <= 0:
                continue
            before = sum(item["sets"] for item in row["additions"])
            _place_sets(group, share, exercises, row["additions"], open_days.index((day, exercises)), body_areas, skipped)
            placed = sum(item["sets"] for item in row["additions"]) - before
            added[group] += placed
            remaining -= placed

    if any(row["additions"] for row in day_rows):
        history = latest_next_steps(conn)
        max_dumbbell_kg = _max_dumbbell_kg(conn)
        for row in day_rows:
            for addition in row["additions"]:
                if addition["mode"] == "add":
                    addition.update(_accessory_target(addition["exercise_name"], templates, history, max_dumbbell_kg))
                addition["reason"] = f"Brings {labels[addition['group']].lower()} toward {TARGET_SETS_MIN} hard sets this week"

    groups = []
    for group in MUSCLE_GROUPS:
        key = group["key"]
        total = done[key] + planned[key] + added[key]
        if not group["targeted"]:
            status = "tracked"
        elif hiking_covers_legs and key == "legs" and total < TARGET_SETS_MIN:
            status = "hiking"
        elif total < TARGET_SETS_MIN:
            status = "low"
        elif total > TARGET_SETS_MAX:
            status = "high"
        else:
            status = "in_range"
        groups.append(
            {
                "key": key,
                "label": group["label"],
                "targeted": group["targeted"],
                "done_sets": done[key],
                "planned_sets": planned[key],
                "added_sets": added[key],
                "total_sets": total,
                "status": status,
                "shortfall": max(0, TARGET_SETS_MIN - total) if group["targeted"] and status != "hiking" else 0,
            }
        )

    added_total = sum(added.values())
    short = [item["label"].lower() for item in groups if item["shortfall"]]
    if minimum_week_active:
        summary = "Minimum week: no extra sets added."
    elif added_total:
        boosted = [item["label"].lower() for item in groups if item["added_sets"]]
        summary = f"Added {added_total} accessory set{'s' if added_total != 1 else ''} for {', '.join(boosted)}."
    elif not short:
        summary = f"Every main group reaches {TARGET_SETS_MIN} hard sets as planned."
    else:
        summary = "No lift days left to add sets to."
    if short and not minimum_week_active:
        summary += f" Still short: {', '.join(short)}."
    if hiking_covers_legs:
        summary += " Hiking covers legs this week."
    protected_labels = [item["summary_label"] for item in body_areas]
    if skipped and protected_labels:
        summary += f" Left out lifts that load your {', '.join(protected_labels)}."

    return {
        "target_min": TARGET_SETS_MIN,
        "target_max": TARGET_SETS_MAX,
        "groups": groups,
        "days": day_rows,
        "added_sets": added_total,
        "minimum_week_active": minimum_week_active,
        "hiking_covers_legs": hiking_covers_legs,
        "protected_areas": protected_labels,
        "skipped_for_protection": sorted(skipped),
        "summary": summary,
        "method": "Hard sets per primary muscle group: sets logged this week plus the saved-workout sets of lift days still ahead. Accessory sets go on remaining full lift days; sessions are never cut.",
    }


def apply_lift_volume(days: list[dict], volume: Optional[dict]) -> list[dict]:
    """Attach each day's accessory additions so the plan draft and today's card can use them."""
    by_date = {row["date"]: row["additions"] for row in (volume or {}).get("days", [])}
    return [{**day, "lift_volume_additions": by_date.get(day.get("date"), [])} if _is_lift_day(day) else day for day in days]
