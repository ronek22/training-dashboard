"""Week preview: a light, rule-built look at the next four weeks under the current plan.

Only the current week has day-by-day detail. The weeks after it are one row each, built by code
(no coach call), and a row says only what is different about that week. A normal week without a
winter arc is just "Normal week": repeating the weekly goals on every row tells you nothing.

What bends a week: a Mountains trip (hikes replace rides, lifts become short travel sessions, ride
targets shrink to the days off the trip), the re-entry window after a trip (easy days first, no
intervals until it ends, legs at pre-trip loads), an open illness return window, and other
life-load tags (no quality ride on them; 3+ tagged days make a busy week). Key rides, from the arc
or a weekly quality-ride goal, are placed on the days left open. With an arc, every row also shows
its block, week number, ride hours and key rides, so you can see where the winter is heading.
Goal end and review dates are shown as pills. Nothing here is saved; a preview week becomes a
real plan when it arrives.
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from ..repositories.goals import ACTIVE_GOAL_CONDITION
from .illness_return import build_illness_return
from .life_load import TAGS, get_life_load_days
from .minimum_week import anchor_session_counts
from .mountain_reentry import LOOKBACK_DAYS, easy_days, window_length
from .sick_mode import get_active_sick_period
from .winter_arc import MIX_LABELS, arc_week, build_winter_arc

PREVIEW_WEEKS = 4
BUSY_DAYS = 3  # tagged days that make a busy week, as in the volume-trend "life" label
GOAL_RIDE_METRICS = {"quality_sessions", "ride_km"}
QUALITY_TYPES = {"sweet_spot", "vo2", "quality"}


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _span(dates: list[str]) -> str:
    """'Oct 19', 'Oct 19–25' or 'Oct 30–Nov 2' for sorted ISO dates."""
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    if first == last:
        return first.strftime("%b %-d")
    tail = last.strftime("%-d") if first.month == last.month else last.strftime("%b %-d")
    return f"{first.strftime('%b %-d')}–{tail}"


def _weekdays(dates: list[str]) -> str:
    """'Wed', 'Mon–Tue' or 'Fri–Sun' for a run of days, 'Mon, Wed' otherwise."""
    days = [date.fromisoformat(value) for value in sorted(dates)]
    names = [day.strftime("%a") for day in days]
    if len(days) > 1 and (days[-1] - days[0]).days == len(days) - 1:
        return f"{names[0]}–{names[-1]}"
    return ", ".join(names)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _trip_windows(tagged: list[str]) -> list[dict]:
    """Each run of Mountains days with its re-entry window (the days right after it)."""
    runs: list[list[date]] = []
    for day in sorted(date.fromisoformat(value) for value in tagged):
        if runs and day - runs[-1][1] == timedelta(days=1):
            runs[-1][1] = day
        else:
            runs.append([day, day])
    windows = []
    for first, last in runs:
        trip_days = (last - first).days + 1
        length = window_length(trip_days)
        reentry = [(last + timedelta(days=offset)).isoformat() for offset in range(1, length + 1)]
        windows.append({"trip_days": trip_days, "reentry": reentry, "easy": reentry[: easy_days(length)] if length else []})
    return windows


def _weekly_ride_goals(conn: sqlite3.Connection, today: str) -> list[dict]:
    """Active weekly ride goals (quality rides, ride km) that stand in for the arc when there is none."""
    try:
        rows = conn.execute(
            f"""
            SELECT title, metric_type, target_value FROM goals
            WHERE {ACTIVE_GOAL_CONDITION} AND COALESCE(lifecycle_status, 'active') = 'active' AND period_type = 'week'
            ORDER BY id
            """,
            (today,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows if row["metric_type"] in GOAL_RIDE_METRICS and row["target_value"]]


def _goal_dates(conn: sqlite3.Connection, today: str, start: str, end: str) -> list[dict]:
    """Goal end dates (non-weekly goals) and review dates that fall in [start, end]."""
    try:
        rows = conn.execute(
            f"""
            SELECT title, period_type, end_date, review_on FROM goals
            WHERE {ACTIVE_GOAL_CONDITION} AND COALESCE(lifecycle_status, 'active') = 'active'
            ORDER BY id
            """,
            (today,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    found = []
    for row in rows:
        if row["period_type"] != "week" and row["end_date"] and start <= row["end_date"][:10] <= end:
            found.append({"date": row["end_date"][:10], "label": f"Goal ends: {row['title']}"})
        if row["review_on"] and start <= row["review_on"][:10] <= end:
            found.append({"date": row["review_on"][:10], "label": f"Goal review: {row['title']}"})
    return found


def _illness_window(conn: sqlite3.Connection, today: date) -> tuple[list[str], bool]:
    """Dates of the open illness return window from today, and whether sick mode is on now."""
    if get_active_sick_period(conn):
        return [], True
    state = build_illness_return(conn, today)
    if not state:
        return [], False
    end = date.fromisoformat(state["ends_on"])
    return [(today + timedelta(days=offset)).isoformat() for offset in range((end - today).days + 1)], False


def _key_rides(target: Optional[dict], goals: list[dict]) -> list[dict]:
    if target:
        return [
            {"type": key, "label": MIX_LABELS[key], "count": target["ride_mix"][key], "source": "arc"}
            for key in target["key_types"]
        ]
    return [
        {"type": "quality", "label": "Quality ride", "count": int(round(goal["target_value"])), "source": "goal"}
        for goal in goals if goal["metric_type"] == "quality_sessions"
    ]


def _rides_text(target: Optional[dict], ride_km: Optional[float], trip_days: int) -> Optional[str]:
    """Ride volume for the row: the arc's hours, shrunk to the days off a trip. Goal km only when bent."""
    if trip_days >= 7:
        return "Hikes instead of rides"
    share = (7 - trip_days) / 7
    if target:
        hours = round(target["ride_hours"] * share, 1)
        return f"{'~' if trip_days else ''}{hours:g} h rides"
    if ride_km and trip_days:
        return f"~{int(5 * round(ride_km * share / 5))} km rides"
    return None


def _key_text(key_rides: list[dict], open_days: list[str], bent: bool, show_plain: bool) -> Optional[str]:
    """Key rides, and the days a quality ride fits on when other days are taken (Z2 fits anywhere)."""
    if not key_rides:
        return None
    rides = ", ".join(f"{ride['count']}× {ride['label'].lower()}" for ride in key_rides)
    if not any(ride["type"] in QUALITY_TYPES for ride in key_rides) or not (bent and len(open_days) < 7):
        return rides if show_plain else None
    if not open_days:
        return f"No day open for {'a quality ride' if sum(ride['count'] for ride in key_rides) == 1 else 'key rides'}"
    return f"{rides}, {_weekdays(open_days)}"


def _week_row(
    conn: sqlite3.Connection, index: int, start: date, *, today: date, tagged: dict, trips: list[dict],
    illness: list[str], sick_now: bool, ride_goals: list[dict],
) -> dict:
    end = start + timedelta(days=6)
    start_key, end_key = start.isoformat(), end.isoformat()
    days = [(start + timedelta(days=offset)).isoformat() for offset in range(7)]
    target = arc_week(conn, start_key)
    lifts, _, _ = anchor_session_counts(conn, start_key, end_key)
    events: list[dict] = []
    notes: list[str] = []
    guarded: set[str] = set()
    lift_text = None

    trip_days = [day for day in days if "mountains" in tagged.get(day, {}).get("tags", [])]
    if trip_days:
        guarded |= set(trip_days)
        events.append({"kind": "trip", "label": f"Mountains {_span(trip_days)}", "dates": trip_days})
        if len(trip_days) < 7:
            notes.append(f"Hikes {_weekdays(trip_days)}")
        if lifts:
            lift_text = f"{_plural(lifts, 'short travel lift')}" if len(trip_days) >= 7 else f"{_plural(lifts, 'lift')}, travel version on trip days"

    for trip in trips:
        window = [day for day in trip["reentry"] if day in days]
        if not window:
            continue
        guarded |= set(window)
        events.append({"kind": "reentry", "label": f"Re-entry {_span(window)}", "dates": window})
        easy = [day for day in trip["easy"] if day in days]
        if easy:
            notes.append(f"Easy only {_weekdays(easy)}")
        after = (date.fromisoformat(trip["reentry"][-1]) + timedelta(days=1)).isoformat()
        notes.append(f"no intervals until {date.fromisoformat(after).strftime('%a')}" if after <= end_key else "no intervals all week")
        if lifts and not lift_text:
            lift_text = f"{_plural(lifts, 'lift')}, legs at pre-trip loads"

    illness_days = [day for day in illness if day in days]
    if illness_days:
        guarded |= set(illness_days)
        events.append({"kind": "illness", "label": f"Illness return to {_span(illness_days[-1:])}", "dates": illness_days})
        notes.append(f"Effort capped {_weekdays(illness_days)}, no intervals")
    elif sick_now and index == 1:
        events.append({"kind": "sick", "label": "Sick mode on", "dates": []})
        notes.append("A capped return window follows when sick mode ends")

    life_days = {day: [tag for tag in tagged[day]["tags"] if tag != "mountains"] for day in days if day in tagged}
    life_days = {day: tags for day, tags in life_days.items() if tags}
    guarded |= set(life_days)
    for tag in TAGS:
        dates = [day for day, tags in life_days.items() if tag in tags]
        if dates:
            notes_for_tag = list(dict.fromkeys(tagged[day]["note"] for day in dates if tagged[day].get("note")))
            events.append({
                "kind": "life_load", "tag": tag, "label": f"{TAGS[tag]['label']} {_weekdays(dates)}",
                "detail": "; ".join(notes_for_tag) or None, "dates": dates,
            })
    busy = len(life_days) >= BUSY_DAYS

    for goal in _goal_dates(conn, today.isoformat(), start_key, end_key):
        events.append({"kind": "goal", "label": goal["label"], "dates": [goal["date"]]})

    lighter = bool(target and target["lighter"])
    bent = bool(guarded) or (sick_now and index == 1)
    key_rides = _key_rides(target, ride_goals)
    open_days = [day for day in days if day not in guarded]
    ride_km = next((goal["target_value"] for goal in ride_goals if goal["metric_type"] == "ride_km"), None)
    rides = _rides_text(target, ride_km, len(trip_days))
    key = None if len(trip_days) >= 7 else _key_text(key_rides, open_days, bent, show_plain=bool(target))
    summary = [text for text in (rides, key, lift_text) if text]

    return {
        "index": index,
        "week_start": start_key,
        "week_end": end_key,
        "plan_saved": bool(conn.execute("SELECT 1 FROM weekly_plans WHERE week_start = ?", (start_key,)).fetchone()),
        "block": {key: target[key] for key in ("label", "focus", "focus_label", "week_number", "weeks_in_block", "weeks_left")} if target else None,
        "new_block": bool(target and target["week_number"] == 1),
        "lighter": lighter,
        "normal": not bent and not lighter,
        "ride_hours": target["ride_hours"] if target else None,
        "key_rides": key_rides,
        "lift_days": lifts or None,
        "open_days": len(open_days),
        "busy": busy,
        "summary": summary,
        "notes": notes,
        "events": events,
    }


def build_week_preview(conn: sqlite3.Connection, today: Optional[date] = None, weeks: int = PREVIEW_WEEKS) -> dict:
    """The weeks after the current one, one compact row each; empty when nothing is known."""
    day = _today(today)
    first = _monday(day) + timedelta(weeks=1)
    last = first + timedelta(weeks=weeks, days=-1)
    tagged = get_life_load_days(conn, (day - timedelta(days=LOOKBACK_DAYS)).isoformat(), last.isoformat())
    trips = _trip_windows([key for key, item in tagged.items() if "mountains" in item["tags"]])
    illness, sick_now = _illness_window(conn, day)
    ride_goals = _weekly_ride_goals(conn, day.isoformat())
    rows = [
        _week_row(
            conn, index + 1, first + timedelta(weeks=index), today=day, tagged=tagged, trips=trips,
            illness=illness, sick_now=sick_now, ride_goals=ride_goals,
        )
        for index in range(weeks)
    ]
    has_content = any(row["block"] or not row["normal"] or row["events"] for row in rows)
    return {
        "today": day.isoformat(),
        "arc_status": build_winter_arc(conn, day)["status"],
        "weeks": rows if has_content else [],
    }
