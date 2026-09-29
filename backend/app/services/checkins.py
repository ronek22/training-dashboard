import sqlite3
from datetime import datetime
from typing import Optional

CHECKIN_COLUMNS = "date, energy, muscle_soreness, stress, sleep_quality, pain_level, note, updated_at"


def get_daily_checkin(conn: sqlite3.Connection, date: Optional[str] = None) -> Optional[dict]:
    day = date or datetime.now().date().isoformat()
    row = conn.execute(f"SELECT {CHECKIN_COLUMNS} FROM daily_checkins WHERE date = ?", (day,)).fetchone()
    return dict(row) if row else None


def latest_daily_checkin(conn: sqlite3.Connection) -> Optional[dict]:
    try:
        row = conn.execute(f"SELECT {CHECKIN_COLUMNS} FROM daily_checkins ORDER BY date DESC LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def upsert_daily_checkin(conn: sqlite3.Connection, payload: dict) -> dict:
    day = payload.get("date") or datetime.now().date().isoformat()
    conn.execute(
        """
        INSERT INTO daily_checkins (date, energy, muscle_soreness, stress, sleep_quality, pain_level, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            energy = excluded.energy,
            muscle_soreness = excluded.muscle_soreness,
            stress = excluded.stress,
            sleep_quality = excluded.sleep_quality,
            pain_level = excluded.pain_level,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            day,
            payload["energy"],
            payload["muscle_soreness"],
            payload["stress"],
            payload["sleep_quality"],
            payload.get("pain_level", 0),
            (payload.get("note") or None),
        ),
    )
    conn.commit()
    return get_daily_checkin(conn, day)
