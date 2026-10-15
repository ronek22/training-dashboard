"""The winter arc adapts when life gets in the way.

The arc has fixed dates, so an illness, a mountain trip or a busy fortnight can quietly eat a
block. Each finished week of the block that holds last week is checked for lost days: sick days,
illness return and mountain re-entry windows, Mountains days and other life-load tags. A week is
lost when 4+ of its 7 days were disrupted, or 2+ were and less than half of its ride hours got
ridden. A block with lost weeks gets a suggestion: extend it by the lost weeks (up to 2) and shift
every later block by the same amount, or accept the loss and move on.

Nothing changes until one is confirmed. Each decision is stored with the arc before and after, so
the latest one can be undone (an extension only while the arc is still as it left it). Missed key
rides are never crammed into the remaining weeks: a lost week's missed ride does not carry over.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from . import winter_arc

SCHEMA = """
CREATE TABLE IF NOT EXISTS winter_arc_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_start TEXT NOT NULL,
    block_label TEXT NOT NULL,
    action TEXT NOT NULL,
    weeks INTEGER NOT NULL DEFAULT 0,
    lost_weeks_json TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    undone_at TEXT
);
"""

LOST_DAYS = 4  # disrupted days that make a week lost on their own
LOW_HOURS_DAYS = 2  # fewer disrupted days still count when the riding also fell short
LOW_HOURS_RATIO = 0.5
MAX_EXTEND_WEEKS = 2
UNDO_DAYS = 14  # how long the last decision stays on the card with Undo
ACTIONS = ("extend", "accept")
BLOCK_COLUMNS = ("start_date", "end_date", "focus", "label", "weekly_hours", "ride_mix_json", "lighter_every")
REASONS = (
    ("sick", "sick day", "sick days"),
    ("illness_return", "illness return day", "illness return days"),
    ("mountains", "Mountains day", "Mountains days"),
    ("reentry", "mountain re-entry day", "mountain re-entry days"),
    ("life_load", "busy day", "busy days"),
)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _short(value: str) -> str:
    return date.fromisoformat(value).strftime("%-d %b")


# --- Which days and weeks were lost ------------------------------------------------------------

def disrupted_days(conn: sqlite3.Connection, start: date, end: date) -> dict[str, str]:
    """ISO date -> the main reason it was disrupted, for days in [start, end]."""
    from .illness_return import past_return_dates
    from .life_load import get_life_load_days
    from .mountain_reentry import past_reentry_dates
    from .sick_mode import sick_dates

    days: dict[str, str] = {}
    tagged = get_life_load_days(conn, start.isoformat(), end.isoformat())
    sources = (
        ("sick", {value for value in sick_dates(conn) if start.isoformat() <= value <= end.isoformat()}),
        ("illness_return", past_return_dates(conn, start, end)),
        ("mountains", {value for value, item in tagged.items() if "mountains" in item["tags"]}),
        ("reentry", past_reentry_dates(conn, start, end)),
        ("life_load", set(tagged)),
    )
    for reason, dates in sources:  # First reason wins: sick beats a tag on the same day.
        for value in dates:
            days.setdefault(value, reason)
    return days


def week_disruption(conn: sqlite3.Connection, week_start: str, ride_hours_target: Optional[float], ride_hours_done: Optional[float]) -> Optional[dict]:
    """Why a finished week counts as lost, or None when it does not."""
    start = date.fromisoformat(week_start)
    days = disrupted_days(conn, start, start + timedelta(days=6))
    low = bool(ride_hours_target) and (ride_hours_done or 0) < ride_hours_target * LOW_HOURS_RATIO
    if len(days) < LOST_DAYS and not (low and len(days) >= LOW_HOURS_DAYS):
        return None
    counts = {reason: sum(1 for value in days.values() if value == reason) for reason, _, _ in REASONS}
    reasons = [f"{count} {one if count == 1 else many}" for (reason, one, many) in REASONS if (count := counts[reason])]
    return {
        "week_start": week_start,
        "disrupted_days": len(days),
        "reasons": reasons,
        "kinds": [reason for reason, *_ in REASONS if counts[reason]],
        "low_ride_hours": low,
    }


def lost_weeks(conn: sqlite3.Connection, block: dict, today: date) -> list[dict]:
    """The block's finished weeks that were lost, oldest first."""
    weeks = []
    week = date.fromisoformat(block["start_date"])
    while week.isoformat() <= block["end_date"] and week + timedelta(days=6) < today:
        target = winter_arc.week_target(block, week.isoformat())
        done = winter_arc._done_ride_hours(conn, week.isoformat())
        lost = week_disruption(conn, week.isoformat(), target["ride_hours"], done)
        if lost:
            weeks.append({**lost, "week_number": target["week_number"], "lighter": target["lighter"], "ride_hours_target": target["ride_hours"], "ride_hours_done": done})
        week += timedelta(weeks=1)
    return weeks


# --- Decisions --------------------------------------------------------------------------------

def _decisions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    try:
        return conn.execute("SELECT * FROM winter_arc_adjustments ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return []


def _snapshot(conn: sqlite3.Connection) -> list[dict]:
    return [{key: row[key] for key in BLOCK_COLUMNS} for row in winter_arc._rows(conn)]


def _shifted(rows: list[dict], block_start: str, weeks: int) -> list[dict]:
    """The arc with the block starting ``block_start`` ``weeks`` longer and every later block moved."""
    shift = timedelta(weeks=weeks)
    result = []
    for row in rows:
        row = dict(row)
        if row["start_date"] == block_start:
            row["end_date"] = (date.fromisoformat(row["end_date"]) + shift).isoformat()
        elif row["start_date"] > block_start:
            row["start_date"] = (date.fromisoformat(row["start_date"]) + shift).isoformat()
            row["end_date"] = (date.fromisoformat(row["end_date"]) + shift).isoformat()
        result.append(row)
    return result


def _preview(rows: list[dict]) -> list[dict]:
    """Snapshot rows as the strip's blocks: dates, weeks and lighter weeks."""
    return [
        {key: block[key] for key in ("label", "focus", "start_date", "end_date", "weeks", "lighter_weeks")}
        for block in (winter_arc._block({**row, "id": index}) for index, row in enumerate(rows))
    ]


def _write(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.execute("DELETE FROM winter_arc_blocks")
    for row in rows:
        conn.execute(
            f"INSERT INTO winter_arc_blocks ({', '.join(BLOCK_COLUMNS)}) VALUES ({', '.join('?' for _ in BLOCK_COLUMNS)})",
            [row[key] for key in BLOCK_COLUMNS],
        )


def build_suggestion(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Extend-or-accept for the block that holds last week, when it lost weeks nobody decided on yet."""
    day = _today(today)
    last_week = (winter_arc._monday(day) - timedelta(weeks=1)).isoformat()
    block = winter_arc.block_for_week(conn, last_week)
    if not block:
        return None
    decided = set()
    for row in _decisions(conn):
        if row["block_start"] == block["start_date"] and not row["undone_at"]:
            decided.update(json.loads(row["lost_weeks_json"]))
    lost = [week for week in lost_weeks(conn, block, day) if week["week_start"] not in decided]
    if not lost:
        return None
    weeks = min(len(lost), MAX_EXTEND_WEEKS)
    rows = _snapshot(conn)
    after = _shifted(rows, block["start_date"], weeks)
    kinds = {kind for week in lost for kind in week["kinds"]}
    cause = (
        "illness" if kinds & {"sick", "illness_return"} else
        "a mountain trip" if kinds & {"mountains", "reentry"} else
        "busy days"
    )
    lost_text = f"{len(lost)} week{'s' if len(lost) > 1 else ''} ({', '.join(_short(week['week_start']) for week in lost)})"
    later = sum(1 for row in rows if row["start_date"] > block["start_date"])
    return {
        "block": {key: block[key] for key in ("id", "label", "focus", "start_date", "end_date", "weeks")},
        "lost_weeks": lost,
        "extend_weeks": weeks,
        "later_blocks": later,
        "message": (
            f"{block['label']} lost {lost_text} to {cause}. Extend it by {weeks} week{'s' if weeks > 1 else ''}"
            + (f" and move the {later} later block{'s' if later > 1 else ''} back" if later else "")
            + ", or accept it and move on. Missed key rides are not crammed into the weeks that are left."
        ),
        "before": _preview(rows),
        "after": _preview(after),
    }


def _last_decision(conn: sqlite3.Connection, today: date) -> Optional[dict]:
    rows = [row for row in _decisions(conn) if not row["undone_at"]]
    if not rows:
        return None
    row = rows[-1]
    if row["created_at"][:10] < (today - timedelta(days=UNDO_DAYS)).isoformat():
        return None
    can_undo = row["action"] == "accept" or json.loads(row["after_json"]) == _snapshot(conn)
    weeks = row["weeks"]
    return {
        "id": row["id"],
        "action": row["action"],
        "weeks": weeks,
        "block_label": row["block_label"],
        "created_at": row["created_at"],
        "can_undo": can_undo,
        "summary": (
            f"{row['block_label']} extended by {weeks} week{'s' if weeks > 1 else ''}; later blocks moved back."
            if row["action"] == "extend" else f"Accepted the lost time in {row['block_label']}; dates unchanged."
        ),
    }


def build_arc_adjustment(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    day = _today(today)
    return {"suggestion": build_suggestion(conn, day), "last": _last_decision(conn, day)}


def winter_arc_payload(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """The arc for Plan, with any extend-or-accept suggestion and the last decision."""
    return {**winter_arc.build_winter_arc(conn, today), "adjustment": build_arc_adjustment(conn, today)}


def apply_arc_adjustment(conn: sqlite3.Connection, action: str, block_start: str, weeks: int = 0, today: Optional[date] = None) -> dict:
    """Confirm the current suggestion. It must still match, so a stale card cannot move the arc."""
    if action not in ACTIONS:
        raise HTTPException(status_code=422, detail=f"Unknown action: {action}")
    day = _today(today)
    suggestion = build_suggestion(conn, day)
    if not suggestion or suggestion["block"]["start_date"] != block_start or (action == "extend" and weeks != suggestion["extend_weeks"]):
        raise HTTPException(status_code=409, detail="The arc changed since this suggestion; reload Plan.")
    ensure_table(conn)
    before = _snapshot(conn)
    after = _shifted(before, block_start, weeks) if action == "extend" else before
    if action == "extend":
        _write(conn, after)
    conn.execute(
        "INSERT INTO winter_arc_adjustments (block_start, block_label, action, weeks, lost_weeks_json, before_json, after_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            block_start, suggestion["block"]["label"], action, weeks if action == "extend" else 0,
            json.dumps([week["week_start"] for week in suggestion["lost_weeks"]]), json.dumps(before), json.dumps(after),
            datetime.combine(day, datetime.now().time()).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    return winter_arc_payload(conn, day)


def undo_arc_adjustment(conn: sqlite3.Connection, adjustment_id: int, today: Optional[date] = None) -> dict:
    """Undo the last decision: put the arc back as it was and bring the suggestion back."""
    day = _today(today)
    last = _last_decision(conn, day)
    if not last or last["id"] != adjustment_id:
        raise HTTPException(status_code=409, detail="Only the last decision can be undone.")
    if not last["can_undo"]:
        raise HTTPException(status_code=409, detail="The arc was edited since; edit it directly instead.")
    row = conn.execute("SELECT before_json FROM winter_arc_adjustments WHERE id = ?", (adjustment_id,)).fetchone()
    if last["action"] == "extend":
        _write(conn, json.loads(row["before_json"]))
    conn.execute("UPDATE winter_arc_adjustments SET undone_at = ? WHERE id = ?", (datetime.now().isoformat(timespec="seconds"), adjustment_id))
    conn.commit()
    return winter_arc_payload(conn, day)


def clear_adjustments(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("DELETE FROM winter_arc_adjustments")
    except sqlite3.OperationalError:
        pass
