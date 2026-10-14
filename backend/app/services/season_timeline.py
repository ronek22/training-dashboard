"""Season timeline: the coming months on one read-only strip.

Arc blocks are bands with their lighter weeks marked, Mountains trips and goal dates are pins,
the running stall block is a thin bar, and the current week is "you are here". Everything is
read from data other pages already keep (winter arc, life-load tags, goals, stall blocks); any
of it may be missing, and the strip still shows the weeks around today.

The window starts two weeks back (or at an arc that started up to six weeks back), runs at least
twenty weeks and stretches to the arc's end, up to twenty-six weeks. Dates past the window are
listed as "later" so a far target is not lost.
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from ..repositories.goals import ACTIVE_GOAL_CONDITION
from .life_load import get_life_load_days
from .mountain_trips import list_trips
from .stall_blocks import current_block
from .winter_arc import list_blocks

BACK_WEEKS = 2
ARC_BACK_WEEKS = 6
MIN_WEEKS = 20
MAX_WEEKS = 26
PREVIEW_MAX_WEEKS = MAX_WEEKS  # How far the Plan page's week preview can be asked to reach.


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _window(this_week: date, blocks: list[dict]) -> tuple[date, date]:
    start = this_week - timedelta(weeks=BACK_WEEKS)
    live = [block for block in blocks if date.fromisoformat(block["end_date"]) >= this_week]
    if live:
        arc_start = date.fromisoformat(live[0]["start_date"])
        start = max(min(start, arc_start), this_week - timedelta(weeks=ARC_BACK_WEEKS))
    end = start + timedelta(weeks=MIN_WEEKS, days=-1)
    if live:
        end = max(end, date.fromisoformat(live[-1]["end_date"]))
    return start, min(end, start + timedelta(weeks=MAX_WEEKS, days=-1))


def _clip(first: str, last: str, start: str, end: str) -> Optional[tuple[str, str]]:
    if last < start or first > end:
        return None
    return max(first, start), min(last, end)


def _trips(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Every run of Mountains days, with its recap link once a hike is logged."""
    recaps = {trip["start_date"]: trip["url"] for trip in list_trips(conn, today)["trips"]}
    days = sorted(key for key, item in get_life_load_days(conn).items() if "mountains" in item["tags"])
    runs: list[list[str]] = []
    for value in days:
        if runs and date.fromisoformat(value) - date.fromisoformat(runs[-1][1]) == timedelta(days=1):
            runs[-1][1] = value
        else:
            runs.append([value, value])
    return [
        {"kind": "trip", "date": first, "end_date": last, "label": "Mountains", "url": recaps.get(first)}
        for first, last in runs
    ]


def _goal_dates(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Target dates of non-weekly goals and review dates of any active goal."""
    try:
        rows = conn.execute(
            f"""
            SELECT id, title, period_type, end_date, review_on FROM goals
            WHERE {ACTIVE_GOAL_CONDITION} AND COALESCE(lifecycle_status, 'active') = 'active'
            ORDER BY id
            """,
            (today.isoformat(),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    found = []
    for row in rows:
        if row["period_type"] != "week" and row["end_date"]:
            found.append({"kind": "goal", "date": row["end_date"][:10], "label": row["title"], "goal_id": row["id"]})
        if row["review_on"]:
            found.append({"kind": "review", "date": row["review_on"][:10], "label": f"Review: {row['title']}", "goal_id": row["id"]})
    return found


def _saved_weeks(conn: sqlite3.Connection, start: str, end: str) -> set[str]:
    try:
        rows = conn.execute("SELECT week_start FROM weekly_plans WHERE week_start BETWEEN ? AND ?", (start, end)).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {row[0] for row in rows}


def build_season_timeline(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    day = today or datetime.now().date()
    this_week = _monday(day)
    blocks = list_blocks(conn)
    start, end = _window(this_week, blocks)
    start_key, end_key = start.isoformat(), end.isoformat()
    this_key = this_week.isoformat()
    saved = _saved_weeks(conn, start_key, end_key)

    lighter = {week for block in blocks for week in block["lighter_weeks"]}
    weeks = []
    for index in range((end - start).days // 7 + 1):
        week_start = (start + timedelta(weeks=index)).isoformat()
        block = next((block for block in blocks if block["start_date"] <= week_start <= block["end_date"]), None)
        weeks_ahead = index - (this_week - start).days // 7
        weeks.append({
            "week_start": week_start,
            "block_id": block["id"] if block else None,
            "lighter": week_start in lighter,
            "current": week_start == this_key,
            "past": week_start < this_key,
            "plan_saved": week_start in saved,
            # Where a click goes: the saved plan, or the rule-built preview for a future week.
            "link": "plan" if week_start == this_key or (week_start in saved) else "preview" if weeks_ahead > 0 else None,
        })

    bands = []
    for block in blocks:
        span = _clip(block["start_date"], block["end_date"], start_key, end_key)
        if span:
            bands.append({
                **{key: block[key] for key in ("id", "label", "focus", "focus_label", "weeks", "weekly_hours", "ride_mix", "lighter_every")},
                "start_date": block["start_date"], "end_date": block["end_date"],
                "visible_start": span[0], "visible_end": span[1],
            })

    stall = None
    running = current_block(conn, day)
    if running:
        span = _clip(running["started_on"], running["ends_on"], start_key, end_key)
        if span:
            stall = {
                **{key: running[key] for key in ("id", "exercise_name", "label", "started_on", "ends_on", "week", "weeks", "headline")},
                "visible_start": span[0], "visible_end": span[1],
            }

    pins, later = [], []
    for pin in sorted(_trips(conn, day) + _goal_dates(conn, day), key=lambda item: item["date"]):
        last = pin.get("end_date") or pin["date"]
        if last < start_key:
            continue
        if pin["date"] > end_key:
            later.append(pin)
        else:
            pins.append(pin)

    return {
        "today": day.isoformat(),
        "start_date": start_key,
        "end_date": end_key,
        "weeks": weeks,
        "blocks": bands,
        "stall_block": stall,
        "pins": pins,
        "later": later,
        "has_content": bool(bands or stall or pins or later),
    }
