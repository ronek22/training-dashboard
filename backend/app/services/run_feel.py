"""How a run felt (easy / ok / hard), tapped on the phone after it syncs.

Two hard runs in a row ease the easy band by ``EASE_S`` per km until a run feels easy or OK again.
A tap never makes the band faster; only VDOT does.
"""

import sqlite3
from typing import Any

FEELS = ("easy", "ok", "hard")
EASE_S = 10
RECENT_RUNS = 8


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_feel (
            activity_id TEXT PRIMARY KEY,
            felt TEXT NOT NULL CHECK (felt IN ('easy', 'ok', 'hard')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        )
        """
    )


def save_run_feel(conn: sqlite3.Connection, activity_id: str, felt: str) -> dict[str, Any]:
    if felt not in FEELS:
        raise ValueError(f"felt must be one of {', '.join(FEELS)}")
    _ensure_table(conn)
    row = conn.execute("SELECT type FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not row:
        raise LookupError("Activity not found")
    if row["type"] != "Run":
        raise ValueError("Felt is for runs")
    conn.execute(
        """
        INSERT INTO run_feel (activity_id, felt) VALUES (?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET felt = excluded.felt, updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, felt),
    )
    conn.commit()
    return {"activity_id": activity_id, "felt": felt}


def feel_by_run(conn: sqlite3.Connection) -> dict[str, str]:
    _ensure_table(conn)
    return {row["activity_id"]: row["felt"] for row in conn.execute("SELECT activity_id, felt FROM run_feel")}


def eased_seconds(felts: list[str]) -> int:
    """``felts`` oldest first, answered runs only: the last two both hard ease the band."""
    return EASE_S if len(felts) >= 2 and felts[-1] == felts[-2] == "hard" else 0


def recent_feel(conn: sqlite3.Connection, runs: list[dict]) -> dict[str, Any]:
    """The last runs with their answer (None when not tapped), oldest first, and the easing."""
    felt = feel_by_run(conn)
    recent = []
    for run in runs[-RECENT_RUNS:]:
        pace = run["duration_min"] * 60 / run["distance_km"] if run["distance_km"] else None
        recent.append({
            "activity_id": run["id"],
            "date": run["date"],
            "name": run["name"],
            "distance_km": round(run["distance_km"], 2),
            "duration_min": round(run["duration_min"], 1),
            "pace_s": round(pace) if pace else None,
            "avg_hr": run["avg_hr"],
            "felt": felt.get(run["id"]),
        })
    answered = [felt[run["id"]] for run in runs if run["id"] in felt]
    return {"recent": recent, "eased_s": eased_seconds(answered)}
