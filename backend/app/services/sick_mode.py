"""Sick mode: a short illness period that swaps the day's plan for gentle home movement.

Uses the "neck check": head-cold symptoms (runny nose, sore throat) allow easy movement;
fever, chest congestion, body aches or stomach bugs mean the bare minimum. Each session
names the Apple Watch workout to start, so it syncs through Strava like any activity; the
manual log is a fallback for days without the watch. Strength types are avoided on purpose so
a light circuit is never matched to a planned lift and does not advance the A/B rotation.
"""
import math
import sqlite3
from datetime import date, datetime
from typing import Optional

from .guided_sessions import SESSIONS, completions_on, estimate_seconds, public_session, session_steps

SEVERITIES = {
    "above_neck": {
        "label": "Head cold",
        "advice": "Above-the-neck symptoms: easy movement is fine. Keep it conversational, stay home if you can, stop if you feel worse.",
    },
    "below_neck": {
        "label": "Fever or chest",
        "advice": "Fever, chest or body aches: rest is the training. A few minutes of gentle stretching keeps the habit without slowing recovery.",
    },
}

PERIOD_COLUMNS = "id, start_date, end_date, severity, note, created_at, updated_at"


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def get_active_sick_period(conn: sqlite3.Connection) -> Optional[dict]:
    try:
        row = conn.execute(f"SELECT {PERIOD_COLUMNS} FROM sick_periods WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def sick_days_between(conn: sqlite3.Connection, start: date, end: date) -> int:
    """Days in [start, end] covered by a sick period (open periods run to today)."""
    try:
        rows = conn.execute(
            "SELECT start_date, COALESCE(end_date, date('now', 'localtime')) AS end_date FROM sick_periods WHERE start_date <= ? AND (end_date IS NULL OR end_date >= ?)",
            (end.isoformat(), start.isoformat()),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0
    days = set()
    for row in rows:
        first = max(start, date.fromisoformat(row["start_date"]))
        last = min(end, date.fromisoformat(row["end_date"]))
        days.update(first.toordinal() + offset for offset in range((last - first).days + 1))
    return len(days)


def sick_dates(conn: sqlite3.Connection) -> set[str]:
    """Every ISO date covered by a sick period (open periods run to today)."""
    try:
        rows = conn.execute("SELECT start_date, COALESCE(end_date, date('now', 'localtime')) AS end_date FROM sick_periods").fetchall()
    except sqlite3.OperationalError:
        return set()
    dates = set()
    for row in rows:
        first, last = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
        dates.update(date.fromordinal(first.toordinal() + offset).isoformat() for offset in range((last - first).days + 1))
    return dates


def start_sick_mode(conn: sqlite3.Connection, severity: str, note: Optional[str] = None, today: Optional[date] = None) -> dict:
    active = get_active_sick_period(conn)
    if active:
        conn.execute(
            "UPDATE sick_periods SET severity = ?, note = COALESCE(?, note), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (severity, note or None, active["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO sick_periods (start_date, severity, note) VALUES (?, ?, ?)",
            (_today(today).isoformat(), severity, note or None),
        )
    conn.commit()
    return build_sick_mode(conn, today)


def end_sick_mode(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    active = get_active_sick_period(conn)
    if active:
        conn.execute(
            "UPDATE sick_periods SET end_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (max(_today(today).isoformat(), active["start_date"]), active["id"]),
        )
        conn.commit()
    return build_sick_mode(conn, today)


def log_sick_session(conn: sqlite3.Connection, session_key: str, today: Optional[date] = None) -> dict:
    from ..models.activities import Activity
    from .activities import create_activity_data

    session = SESSIONS.get(session_key)
    if not session or session["context"] != "sick":
        raise ValueError(f"Unknown sick mode session: {session_key}")
    active = get_active_sick_period(conn)
    severity_label = SEVERITIES.get((active or {}).get("severity"), {}).get("label", "sick")
    day = _today(today).isoformat()
    create_activity_data(conn, Activity(**{
        "id": f"sick-{day}-{session_key}",
        "date": day,
        "type": session["type"],
        "name": session["title"],
        "duration_min": math.ceil(estimate_seconds(session) / 60),
        "workout_intent": "mobility",
        "notes": f"Sick mode ({severity_label.lower()}): {'; '.join(session_steps(session))}",
    }).model_dump())
    return build_sick_mode(conn, today)


def build_sick_mode(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    active = get_active_sick_period(conn)
    if not active:
        return {"active": False}
    day = _today(today)
    severity = active["severity"] if active["severity"] in SEVERITIES else "above_neck"
    moved_today = [
        {"id": row["id"], "name": row["name"] or row["type"], "type": row["type"], "duration_min": row["duration_min"]}
        for row in conn.execute("SELECT id, name, type, duration_min FROM activities WHERE date = ? ORDER BY created_at", (day.isoformat(),))
    ]
    completions = completions_on(conn, day.isoformat(), "sick")
    completed_keys = {item["session_key"] for item in completions} | {
        str(item["id"]).removeprefix(f"sick-{day.isoformat()}-") for item in moved_today if str(item["id"]).startswith("sick-")
    }
    return {
        "active": True,
        "period": active,
        "day_number": (day - date.fromisoformat(active["start_date"])).days + 1,
        "severity": severity,
        "severity_label": SEVERITIES[severity]["label"],
        "advice": SEVERITIES[severity]["advice"],
        "severities": [{"key": key, "label": value["label"]} for key, value in SEVERITIES.items()],
        "sessions": [
            {**public_session(key), "completed_today": key in completed_keys}
            for key, session in SESSIONS.items()
            if severity in session.get("severities", ())
        ],
        "completed_today": completions,
        "moved_today": moved_today,
        # A watch workout already synced today: a manual log would only duplicate it.
        "synced_today": any(not str(item["id"]).startswith("sick-") for item in moved_today),
    }


def sick_mode_coaching_context(conn: sqlite3.Connection) -> Optional[dict]:
    """Compact note for coaching prompts: the athlete is ill, keep everything gentle."""
    state = build_sick_mode(conn)
    if not state["active"]:
        return None
    return {
        "since": state["period"]["start_date"],
        "day_number": state["day_number"],
        "severity": state["severity_label"],
        "guidance": "Athlete is sick. Do not prescribe structured or hard training; only gentle home movement to keep the daily streak. Do not count missed sessions or volume drop against them.",
    }
