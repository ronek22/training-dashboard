"""Back from the mountains: a short re-entry window after a run of 3+ Mountains days.

A week of daily hikes leaves legs and sleep in debt, and the next week should not open with an
interval ride or a heavy leg day. When a run of 3 or more consecutive Mountains days ends, the
days after it are a re-entry window, like return from illness but shorter: about half the trip
length, 2 to 4 days. The first 1-2 days are easy rides only; the rest allows moderate work but
still no intervals. Leg lifts stay at their pre-trip loads with 2+ reps in reserve; upper-body
lifts go on as normal, and no lift session is ever dropped (the lift anchor).
"""
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .life_load import mountain_dates

MIN_TRIP_DAYS = 3
MIN_DAYS, MAX_DAYS = 2, 4
# Far enough back to find the end of a trip whose window could still be open.
LOOKBACK_DAYS = 45

PHASES = {
    "easy": {
        "label": "Easy only",
        "rpe_cap": 4,
        "guidance": "Easy rides only (RPE ≤4, conversational), no intervals or tempo. Leg lifts at pre-trip loads with 2+ reps in reserve; upper-body lifts as normal.",
    },
    "build": {
        "label": "Moderate",
        "rpe_cap": 6,
        "guidance": "Moderate work is fine (RPE ≤6), still no intervals or race efforts. Leg lifts at pre-trip loads with 2+ reps in reserve; upper-body lifts as normal.",
    },
}


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _short_date(value: date) -> str:
    return value.strftime("%b %-d")


def window_length(trip_days: int) -> int:
    """About half the trip, 2 to 4 days; 0 for runs too short to need one."""
    if trip_days < MIN_TRIP_DAYS:
        return 0
    return min(MAX_DAYS, max(MIN_DAYS, math.ceil(trip_days / 2)))


def easy_days(length: int) -> int:
    return 1 if length <= MIN_DAYS else 2


def build_mountain_reentry(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """The re-entry window open today, or None (no recent trip, still on it, or window over)."""
    day = _today(today)
    try:
        tagged = mountain_dates(conn, (day - timedelta(days=LOOKBACK_DAYS)).isoformat(), day.isoformat())
    except sqlite3.OperationalError:
        return None
    if not tagged or day.isoformat() in tagged:
        return None
    last = date.fromisoformat(max(tagged))
    first = last
    while (first - timedelta(days=1)).isoformat() in tagged:
        first -= timedelta(days=1)
    trip_days = (last - first).days + 1
    length = window_length(trip_days)
    day_number = (day - last).days
    if not length or day_number > length:
        return None

    phase = "easy" if day_number <= easy_days(length) else "build"
    ends_on = last + timedelta(days=length)
    headline = f"Day {day_number} of {length} back from the mountains"
    return {
        "active": True,
        "trip": {"start_date": first.isoformat(), "end_date": last.isoformat(), "days": trip_days},
        "day_number": day_number,
        "length_days": length,
        "ends_on": ends_on.isoformat(),
        "phase": phase,
        "phase_label": PHASES[phase]["label"],
        "rpe_cap": PHASES[phase]["rpe_cap"],
        "guidance": PHASES[phase]["guidance"],
        "headline": headline,
        "message": f"{headline} ({trip_days} hiking days to {_short_date(last)}). {PHASES[phase]['guidance']}",
    }


def mountain_reentry_dates(conn: sqlite3.Connection, today: Optional[date] = None) -> set[str]:
    """ISO dates from today to the end of the open window: no extra leg sets on them."""
    state = build_mountain_reentry(conn, today)
    if not state:
        return set()
    day, end = _today(today), date.fromisoformat(state["ends_on"])
    return {(day + timedelta(days=offset)).isoformat() for offset in range((end - day).days + 1)}


def mountain_reentry_readiness_factor(state: Optional[dict]) -> Optional[dict]:
    if not state:
        return None
    detail = f"day {state['day_number']} of {state['length_days']} after {state['trip']['days']} hiking days"
    return {"key": "mountain_reentry", "label": "Back from the mountains", "detail": detail, "tone": "caution", "points": 1}


def mountain_reentry_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Compact note for coaching prompts and the weekly planner."""
    state = build_mountain_reentry(conn, today)
    if not state:
        return None
    return {
        "trip_ended_on": state["trip"]["end_date"],
        "trip_days": state["trip"]["days"],
        "day_number": state["day_number"],
        "window_ends_on": state["ends_on"],
        "phase": state["phase_label"],
        "rpe_cap": state["rpe_cap"],
        "guidance": (
            f"The athlete is back from {state['trip']['days']} days of hiking until {state['ends_on']}. {state['guidance']} "
            "Do not plan intervals, tempo, quality rides or 90+ minute sessions before that date. Lifts stay on the "
            "plan (anchor goal): resume the A/B/C/D rotation, no extra leg sets, and the first lower-body lift "
            "repeats pre-trip loads."
        ),
    }


def past_reentry_dates(conn: sqlite3.Connection, start: date, end: date) -> set[str]:
    """ISO dates in [start, end] inside the re-entry window after any trip of 3+ Mountains days (look-backs)."""
    try:
        tagged = mountain_dates(conn, (start - timedelta(days=LOOKBACK_DAYS)).isoformat(), end.isoformat())
    except sqlite3.OperationalError:
        return set()
    dates = set()
    for value in tagged:
        last = date.fromisoformat(value)
        if (last + timedelta(days=1)).isoformat() in tagged:
            continue  # Not the last day of its trip.
        first = last
        while (first - timedelta(days=1)).isoformat() in tagged:
            first -= timedelta(days=1)
        for offset in range(1, window_length((last - first).days + 1) + 1):
            day = last + timedelta(days=offset)
            if start <= day <= end:
                dates.add(day.isoformat())
    return dates
