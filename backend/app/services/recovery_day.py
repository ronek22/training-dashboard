"""Recovery days: light days that keep the daily streak and still count as rest.

A day is a recovery day when it has at least one activity and every activity on it fits the cap:

- a walk of at most 60 minutes,
- a mobility block (yoga, stretching, physical therapy, or a session tagged mobility) of at most 30 minutes,
- an easy spin (Ride or VirtualRide) of at most 45 minutes with average heart rate below the
  start of riding zone 2 (Athlete page); without heart rate, only a ride tagged recovery fits.

All activities together stay at or under 60 minutes, and none may carry a hard intent.

Any activity keeps the daily streak, so going over the cap never breaks it; the day simply
counts as a training day in readiness and the plan shows which limit was crossed.
"""
import sqlite3
from typing import Iterable, Optional

from .heart_rate_zones import hr_zone_starts

WALK_MAX_MIN = 60
MOBILITY_MAX_MIN = 30
SPIN_MAX_MIN = 45
DAY_MAX_MIN = 60

WALK_TYPES = {"Walk"}
MOBILITY_TYPES = {"Yoga", "Pilates", "Stretching", "PhysicalTherapy", "Mobility", "Recovery"}
SPIN_TYPES = {"Ride", "VirtualRide"}
HARD_INTENTS = {"tempo", "interval", "race_specific", "long", "strength_lower", "strength_upper", "strength_general"}


def _get(activity, key: str):
    try:
        return activity[key]
    except (KeyError, IndexError):
        return None


def spin_hr_limit(conn: sqlite3.Connection) -> int:
    """Average heart rate must stay below riding zone 2."""
    return hr_zone_starts(conn)["ride"][0]


def recovery_cap(conn: sqlite3.Connection) -> dict:
    hr_limit = spin_hr_limit(conn)
    return {
        "walk_max_min": WALK_MAX_MIN,
        "mobility_max_min": MOBILITY_MAX_MIN,
        "spin_max_min": SPIN_MAX_MIN,
        "spin_hr_below": hr_limit,
        "day_max_min": DAY_MAX_MIN,
        "summary": (
            f"Walk ≤{WALK_MAX_MIN} min, mobility ≤{MOBILITY_MAX_MIN} min or easy spin ≤{SPIN_MAX_MIN} min "
            f"under {hr_limit} bpm · ≤{DAY_MAX_MIN} min in total"
        ),
    }


def _activity_overage(activity, hr_limit: int) -> Optional[str]:
    """None when the activity fits the cap, otherwise a short reason."""
    activity_type = _get(activity, "type") or ""
    intent = _get(activity, "workout_intent")
    minutes = float(_get(activity, "duration_min") or 0)
    if intent in HARD_INTENTS:
        return f"{activity_type} tagged {intent.replace('_', ' ')}"
    if intent == "mobility" or activity_type in MOBILITY_TYPES:
        return None if minutes <= MOBILITY_MAX_MIN else f"mobility {round(minutes)} min > {MOBILITY_MAX_MIN}"
    if activity_type in WALK_TYPES:
        return None if minutes <= WALK_MAX_MIN else f"walk {round(minutes)} min > {WALK_MAX_MIN}"
    if activity_type in SPIN_TYPES:
        if minutes > SPIN_MAX_MIN:
            return f"ride {round(minutes)} min > {SPIN_MAX_MIN}"
        avg_hr = _get(activity, "avg_hr")
        if avg_hr:
            return None if float(avg_hr) < hr_limit else f"ride avg HR {round(float(avg_hr))} ≥ {hr_limit} bpm"
        return None if intent == "recovery" else "ride without heart rate"
    return f"{activity_type or 'activity'} is not a recovery activity"


def check_recovery_day(activities: Iterable, hr_limit: int) -> Optional[dict]:
    """Whether one day's activities stay under the cap; None when there were no activities."""
    items = list(activities)
    if not items:
        return None
    over = [reason for reason in (_activity_overage(item, hr_limit) for item in items) if reason]
    total = round(sum(float(_get(item, "duration_min") or 0) for item in items))
    if total > DAY_MAX_MIN:
        over.append(f"{total} min in total > {DAY_MAX_MIN}")
    return {"within_cap": not over, "total_min": total, "over": over}


def recovery_dates(conn: sqlite3.Connection, rows: Iterable) -> set[str]:
    """Dates whose activities (rows with date, type, workout_intent, duration_min, avg_hr) all fit the cap."""
    hr_limit = spin_hr_limit(conn)
    by_date: dict[str, list] = {}
    for row in rows:
        by_date.setdefault(str(row["date"])[:10], []).append(row)
    return {day for day, items in by_date.items() if check_recovery_day(items, hr_limit)["within_cap"]}
