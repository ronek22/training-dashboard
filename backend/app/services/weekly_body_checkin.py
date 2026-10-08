"""Weekly body check-in: one Monday prompt for a weigh-in and last week's protein.

Daily protein ticks and weigh-ins are easy to skip, which leaves the muscle-gain
check without a protein share or a body-weight trend. This asks once a week
instead. The check-in reviews the previous Monday–Sunday week and stays open
Monday to Wednesday until answered or skipped.

The weigh-in is stored as a normal manual ``weight`` metric on the check-in
day, so the protein target and the weight trend pick it up unchanged. The
protein answer ("most days?") fills lift days of that week that have no daily
tick; daily ticks always win.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from .protein import latest_body_weight

OPEN_WEEKDAYS = 3  # Monday, Tuesday, Wednesday
MIN_WEIGHT_KG = 30
MAX_WEIGHT_KG = 250
WEIGHT_NOTE = "Weekly check-in"


def reviewed_week_start(today: date) -> date:
    return today - timedelta(days=today.weekday() + 7)


def weekly_protein_answers(conn: sqlite3.Connection, start: str, end: str) -> dict[str, bool]:
    """Answered weeks overlapping ``start``–``end``, keyed by week start (Monday)."""
    floor = (date.fromisoformat(start) - timedelta(days=6)).isoformat()
    try:
        rows = conn.execute(
            "SELECT week_start, protein_most_days FROM weekly_body_checkins WHERE week_start BETWEEN ? AND ? AND protein_most_days IS NOT NULL",
            (floor, end),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row["week_start"]: bool(row["protein_most_days"]) for row in rows}


def build_weekly_body_checkin(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    week_start = reviewed_week_start(today)
    row = conn.execute(
        "SELECT protein_most_days, weight_kg, skipped FROM weekly_body_checkins WHERE week_start = ?",
        (week_start.isoformat(),),
    ).fetchone()
    answered = row is not None
    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "due": not answered and today.weekday() < OPEN_WEEKDAYS,
        "answered": answered,
        "skipped": bool(row["skipped"]) if row else False,
        "protein_most_days": None if not row or row["protein_most_days"] is None else bool(row["protein_most_days"]),
        "weight_kg": row["weight_kg"] if row else None,
        "last_weight": latest_body_weight(conn),
    }


def save_weekly_body_checkin(
    conn: sqlite3.Connection,
    protein_most_days: Optional[bool],
    weight_kg: Optional[float],
    skipped: bool,
    today: Optional[date] = None,
) -> dict:
    today = today or datetime.now().date()
    if skipped:
        protein_most_days, weight_kg = None, None
    elif protein_most_days is None and weight_kg is None:
        raise HTTPException(status_code=422, detail="Answer protein, add a weight, or skip this week.")
    if weight_kg is not None and not MIN_WEIGHT_KG <= weight_kg <= MAX_WEIGHT_KG:
        raise HTTPException(status_code=422, detail=f"Weight must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg.")
    week_start = reviewed_week_start(today).isoformat()
    conn.execute(
        """
        INSERT INTO weekly_body_checkins (week_start, protein_most_days, weight_kg, skipped) VALUES (?, ?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            protein_most_days = excluded.protein_most_days, weight_kg = excluded.weight_kg,
            skipped = excluded.skipped, updated_at = CURRENT_TIMESTAMP
        """,
        (week_start, None if protein_most_days is None else int(protein_most_days), weight_kg, int(skipped)),
    )
    if weight_kg is not None:
        # One check-in weigh-in per day: re-saving corrects it instead of adding a second point.
        existing = conn.execute(
            "SELECT id FROM metrics WHERE metric = 'weight' AND date = ? AND notes = ?",
            (today.isoformat(), WEIGHT_NOTE),
        ).fetchone()
        if existing:
            conn.execute("UPDATE metrics SET value = ? WHERE id = ?", (weight_kg, existing["id"]))
        else:
            conn.execute(
                "INSERT INTO metrics (date, metric, value, unit, notes) VALUES (?, 'weight', ?, 'kg', ?)",
                (today.isoformat(), weight_kg, WEIGHT_NOTE),
            )
    conn.commit()
    return build_weekly_body_checkin(conn, today)
