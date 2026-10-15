"""Strength phases: an optional dated label that gives lifting a light longer rhythm.

Off by default: with no phase saved, progression and stall blocks behave exactly as before.
A phase never adds a progression rule, it only nudges the existing ones:

- ``volume``: a label for normal building; nothing changes.
- ``hold``: no load jumps. The progression guard holds every lift at last time's load.
- ``deload``: a lighter week. Same lifts, fewer sets (``DELOAD_SET_SHARE``, at least one),
  and no load jumps. The workouts and how often you lift stay the same, so the weekly lift
  count toward the 3x anchor is untouched.

Suggestions line a deload week up with each upcoming winter-arc lighter week. They are
only saved once confirmed.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException

SCHEMA = """
CREATE TABLE IF NOT EXISTS strength_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
KINDS = {"volume": "Volume", "hold": "Hold", "deload": "Deload week"}
# Phases that pause load jumps.
HOLDING = {"hold", "deload"}
DELOAD_SET_SHARE = 0.6


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "kind": row["kind"],
        "kind_label": KINDS.get(row["kind"], row["kind"]),
        "label": row["label"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "source": row["source"],
    }


def list_phases(conn: Optional[sqlite3.Connection]) -> list[dict]:
    if conn is None:
        return []
    try:
        rows = conn.execute("SELECT * FROM strength_phases ORDER BY start_date, id").fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize(row) for row in rows]


def current_phase(conn: Optional[sqlite3.Connection], today: Optional[date] = None) -> Optional[dict]:
    """The phase covering today, with a one-line headline for briefs."""
    day = (today or date.today()).isoformat()
    phase = next((item for item in list_phases(conn) if item["start_date"] <= day <= item["end_date"]), None)
    return {**phase, "headline": headline(phase)} if phase else None


def headline(phase: dict) -> str:
    until = date.fromisoformat(phase["end_date"]).strftime("%-d %b")
    if phase["kind"] == "deload":
        return f"{phase['label']} until {until}: same lifts, fewer sets, no load jumps"
    if phase["kind"] == "hold":
        return f"{phase['label']} until {until}: match last time's loads, no jumps"
    return f"{phase['label']} until {until}"


def deload_sets(set_count: int) -> int:
    """Working sets in a deload week: about 60%, never fewer than one."""
    return max(1, round(int(set_count) * DELOAD_SET_SHARE))


def session_set_count(conn: Optional[sqlite3.Connection], set_count: int, today: Optional[date] = None) -> int:
    phase = current_phase(conn, today)
    return deload_sets(set_count) if phase and phase["kind"] == "deload" else int(set_count)


def suggestions(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict]:
    """A deload week for each winter-arc lighter week from this week on that no phase covers yet."""
    from .winter_arc import list_blocks

    monday = (today or date.today()) - timedelta(days=(today or date.today()).weekday())
    phases = list_phases(conn)
    result = []
    for block in list_blocks(conn):
        for week_start in block["lighter_weeks"]:
            if week_start < monday.isoformat():
                continue
            week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
            if any(item["start_date"] <= week_end and week_start <= item["end_date"] for item in phases):
                continue
            result.append({
                "kind": "deload",
                "label": KINDS["deload"],
                "start_date": week_start,
                "end_date": week_end,
                "source": "arc_lighter_week",
                "reason": f"{block['label']} has a lighter ride week here: lift lighter the same week.",
            })
    return result


def build_strength_phases(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    day = (today or date.today()).isoformat()
    phases = list_phases(conn)
    return {
        "current": current_phase(conn, today),
        "phases": [item for item in phases if item["end_date"] >= day],
        "suggestions": suggestions(conn, today),
        "kinds": [{"key": key, "label": label} for key, label in KINDS.items()],
        "deload_set_share": DELOAD_SET_SHARE,
    }


def save_phase(conn: sqlite3.Connection, kind: str, start: date, end: date, label: Optional[str] = None,
               source: str = "manual") -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown phase: {kind}")
    if end < start:
        raise HTTPException(status_code=422, detail="A phase cannot end before it starts")
    if kind == "deload" and (end - start).days > 13:
        raise HTTPException(status_code=422, detail="A deload is a week, two at most")
    for item in list_phases(conn):
        if item["start_date"] <= end.isoformat() and start.isoformat() <= item["end_date"]:
            raise HTTPException(status_code=409, detail=f"Overlaps the {item['label']} phase ({item['start_date']} to {item['end_date']})")
    ensure_table(conn)
    with conn:
        cursor = conn.execute(
            "INSERT INTO strength_phases (kind, label, start_date, end_date, source) VALUES (?, ?, ?, ?, ?)",
            (kind, (label or "").strip() or KINDS[kind], start.isoformat(), end.isoformat(), source),
        )
    row = conn.execute("SELECT * FROM strength_phases WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row)


def delete_phase(conn: sqlite3.Connection, phase_id: int) -> None:
    ensure_table(conn)
    with conn:
        deleted = conn.execute("DELETE FROM strength_phases WHERE id = ?", (phase_id,)).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="Strength phase not found.")
