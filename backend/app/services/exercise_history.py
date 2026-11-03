"""Recent sessions of one lift, for the phone's mid-workout history.

Built on the same full session index as progression (TrainLog and Fitbod, linked
to an activity). TrainLog sets also carry how they felt and hold times, read from
the first-party set rows by id.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from .strength_progression import _normalize, _session_index


def _set_details(conn: Optional[sqlite3.Connection], set_ids: list[int]) -> dict[int, dict]:
    """Effort and seconds for TrainLog sets; the index gives them negative ids."""
    own = [-set_id for set_id in set_ids if set_id < 0]
    if conn is None or not own:
        return {}
    placeholders = ",".join("?" for _ in own)
    try:
        rows = conn.execute(
            f"SELECT id, effort, actual_seconds FROM strength_session_sets WHERE id IN ({placeholders})",
            own,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {-int(row["id"]): {"effort": row["effort"], "seconds": row["actual_seconds"]} for row in rows}


def _best(sessions: list[dict]) -> Optional[dict]:
    """Heaviest set ever (more reps breaks a tie); most reps, then longest hold, when nothing is loaded."""
    candidates = [(session["date"], item) for session in sessions for item in session["sets"]]
    loaded = [(day, item) for day, item in candidates if (item["weight_kg"] or 0) > 0]
    if loaded:
        day, item = max(loaded, key=lambda pair: (pair[1]["weight_kg"], pair[1]["reps"] or 0, pair[0]))
    else:
        timed = [(day, item) for day, item in candidates if item["seconds"]]
        pool = timed or [(day, item) for day, item in candidates if item["reps"]]
        if not pool:
            return None
        field = "seconds" if timed else "reps"
        day, item = max(pool, key=lambda pair: (pair[1][field], pair[0]))
    return {"date": day, "weight_kg": item["weight_kg"], "reps": item["reps"], "seconds": item["seconds"]}


def exercise_history(conn: Optional[sqlite3.Connection], name: str, limit: int = 4) -> dict[str, Any]:
    key = _normalize(name)
    found: list[tuple[dict, list[dict]]] = []
    for session in _session_index(conn):
        for exercise in session.get("exercises", []):
            if _normalize(exercise.get("exercise_name", "")) == key:
                found.append((session, [item for item in exercise.get("sets", []) if not item.get("is_warmup")]))

    details = _set_details(conn, [int(item["id"]) for _, sets in found for item in sets if "id" in item])
    sessions: list[dict] = []
    for session, sets in sorted(found, key=lambda pair: pair[0]["workout_timestamp"]):
        rows = []
        for item in sets:
            extra = details.get(int(item["id"]), {}) if "id" in item else {}
            reps, seconds = item.get("reps"), extra.get("seconds")
            if not (reps or seconds):
                continue
            rows.append({
                "reps": reps,
                "weight_kg": item.get("weight_kg"),
                "seconds": seconds,
                "effort": extra.get("effort"),
            })
        if rows:
            sessions.append({"date": session["workout_date"], "sets": rows})

    best = _best(sessions)
    recent = sessions[-max(1, limit):]
    for session in recent:
        loads = [item["weight_kg"] for item in session["sets"] if (item["weight_kg"] or 0) > 0]
        session["top_load_kg"] = max(loads) if loads else None
        session["best_reps"] = max((item["reps"] or 0 for item in session["sets"]), default=0) or None
        session["best_seconds"] = max((item["seconds"] or 0 for item in session["sets"]), default=0) or None
    return {
        "exercise_name": name,
        "session_count": len(sessions),
        "sessions": list(reversed(recent)),
        "best": best,
    }
