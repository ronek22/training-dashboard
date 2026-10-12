"""Stall blocks: a plateau suggestion actually applied, and what came of it.

When a lift stalls (see ``strength_plateaus``) the athlete can take the suggested
change as a block: usually 3 weeks of a different rep scheme, load, tempo or a
variation. Starting a block rewrites the lift in every saved workout that has it
(and in today's live session), remembers what it replaced, and records the stall
it answered. Finishing puts the original lift back, or keeps the new version, and
records the estimated 1RM before and after so later suggestions can learn from it.

Only one block runs at a time: change one lift at a time, so a result means something.
A micro-deload is a single session (``weeks`` 0) and is recorded the same way.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from fastapi import HTTPException

from .strength_plateaus import _lift_history, find_plateaus
from .strength_progression import _normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS strength_stall_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_name TEXT NOT NULL,
    applied_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    text TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_on TEXT NOT NULL,
    ends_on TEXT NOT NULL,
    session_id INTEGER,
    stall_json TEXT NOT NULL,
    templates_before_json TEXT NOT NULL DEFAULT '[]',
    session_before_json TEXT,
    ended_on TEXT,
    outcome_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
# scope: 'block' (saved workouts changed for ``weeks``) or 'today' (only the live session).
# status: 'active' while running, then 'reverted' (original lift back), 'kept' (new version stays)
# or 'undone' (taken back before it counted). A 'today' change ends as 'done' with the session.
OPEN = ("active",)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _serialize(row: sqlite3.Row, today: date) -> dict[str, Any]:
    started, ends = date.fromisoformat(row["started_on"]), date.fromisoformat(row["ends_on"])
    weeks = json.loads(row["plan_json"]).get("weeks") or 0
    return {
        "id": int(row["id"]),
        "exercise_name": row["exercise_name"],
        "applied_name": row["applied_name"],
        "kind": row["kind"],
        "label": row["label"],
        "text": row["text"],
        "plan": json.loads(row["plan_json"]),
        "scope": row["scope"],
        "status": row["status"],
        "started_on": row["started_on"],
        "ends_on": row["ends_on"],
        "week": min(weeks, (today - started).days // 7 + 1) if weeks else 0,
        "weeks": weeks,
        "due": row["status"] == "active" and row["scope"] == "block" and today >= ends,
        "session_id": row["session_id"],
        "stall": json.loads(row["stall_json"]),
        "ended_on": row["ended_on"],
        "outcome": json.loads(row["outcome_json"]) if row["outcome_json"] else None,
    }


def list_blocks(conn: sqlite3.Connection, today: Optional[date] = None, status: Optional[str] = None) -> list[dict]:
    today = today or date.today()
    try:
        rows = conn.execute(
            "SELECT * FROM strength_stall_blocks WHERE (? IS NULL OR status = ?) ORDER BY id DESC",
            (status, status),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize(row, today) for row in rows]


def active_blocks(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict]:
    return [block for block in list_blocks(conn, today, "active") if block["scope"] == "block"]


def block_starts(conn: sqlite3.Connection) -> dict[str, str]:
    """Lift name (normalized, as trained during the block) → block start, for running blocks.

    Progression ignores sessions before this date for the lift, so the block's targets
    are not overridden by the stalled numbers it is replacing."""
    return {_normalize(block["applied_name"]): block["started_on"] for block in active_blocks(conn)}


def one_off_dates(conn: Optional[sqlite3.Connection]) -> set[tuple[str, str]]:
    """(lift, date) pairs trained under a one-session change, which progression skips."""
    if conn is None:
        return set()
    try:
        rows = conn.execute("SELECT applied_name, started_on FROM strength_stall_blocks WHERE scope = 'today' AND status != 'undone'").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {(_normalize(row["applied_name"]), row["started_on"]) for row in rows}


def _block_for(blocks: Iterable[dict], name: str) -> Optional[dict]:
    key = _normalize(name)
    return next((block for block in blocks if key in {_normalize(block["exercise_name"]), _normalize(block["applied_name"])}), None)


def annotate_plateaus(conn: sqlite3.Connection, plateaus: list[dict], today: Optional[date] = None) -> list[dict]:
    """Drop lifts a running block already answers; mark the rest as queued behind it."""
    running = active_blocks(conn, today)
    queued_behind = running[0]["exercise_name"] if running else None
    result = []
    for plateau in plateaus:
        if _block_for(running, plateau["exercise_name"]):
            continue
        weeks = (plateau["suggestion"].get("plan") or {}).get("weeks") or 0
        result.append({**plateau, "queued_behind": queued_behind if weeks else None})
    return result


def blocks_for_names(conn: sqlite3.Connection, names: Iterable[str], session_id: Optional[int] = None,
                     today: Optional[date] = None) -> list[dict]:
    """Running blocks touching these lifts, plus any change made in this session."""
    keys = {_normalize(name) for name in names}
    result = []
    for block in list_blocks(conn, today):
        touches = keys & {_normalize(block["exercise_name"]), _normalize(block["applied_name"])}
        if (block["status"] == "active" and block["scope"] == "block" and touches) or (
            session_id is not None and block["session_id"] == session_id and block["status"] in {"active", "done"}
        ):
            result.append(block)
    return result


# --- applying to workouts -------------------------------------------------------------

def _template_rows(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    key = _normalize(name)
    rows = conn.execute("SELECT * FROM strength_template_exercises ORDER BY template_id, exercise_order").fetchall()
    return [row for row in rows if _normalize(row["exercise_name"]) == key]


def _block_note(plan: dict, ends_on: str) -> str:
    reps = f"{plan['reps']}–{plan['reps_max']} reps" if plan.get("reps") and plan.get("reps_max") else ""
    detail = "; ".join(item for item in (reps, plan.get("cue")) if item)
    return f"Stall block until {ends_on}" + (f": {detail}." if detail else ".")


def _apply_to_templates(conn: sqlite3.Connection, name: str, plan: dict, ends_on: str) -> list[dict]:
    before = []
    for row in _template_rows(conn, name):
        before.append(dict(row))
        conn.execute(
            """UPDATE strength_template_exercises SET exercise_name = ?, set_count = ?, target_reps = ?,
               target_weight_kg = ?, notes = ? WHERE id = ?""",
            (
                plan.get("swap_to") or row["exercise_name"],
                plan.get("sets") or row["set_count"],
                plan.get("reps") or row["target_reps"],
                plan["load_kg"] if plan.get("load_kg") is not None else row["target_weight_kg"],
                _block_note(plan, ends_on),
                row["id"],
            ),
        )
    return before


def _restore_templates(conn: sqlite3.Connection, before: list[dict], applied_name: str) -> None:
    """Put each saved workout's lift back, unless the athlete has since replaced it by hand."""
    key = _normalize(applied_name)
    for original in before:
        current = conn.execute("SELECT exercise_name FROM strength_template_exercises WHERE id = ?", (original["id"],)).fetchone()
        if not current or _normalize(current["exercise_name"]) != key:
            continue
        conn.execute(
            """UPDATE strength_template_exercises SET exercise_name = ?, set_count = ?, target_reps = ?,
               target_weight_kg = ?, notes = ? WHERE id = ?""",
            (original["exercise_name"], original["set_count"], original["target_reps"],
             original["target_weight_kg"], original["notes"], original["id"]),
        )


def _session_exercise(conn: sqlite3.Connection, session_id: Optional[int], name: str) -> Optional[sqlite3.Row]:
    if session_id is None:
        return None
    session = conn.execute("SELECT status FROM strength_workout_sessions WHERE id = ?", (session_id,)).fetchone()
    if not session or session["status"] != "active":
        return None
    key = _normalize(name)
    rows = conn.execute("SELECT * FROM strength_session_exercises WHERE session_id = ? ORDER BY exercise_order", (session_id,)).fetchall()
    return next((row for row in rows if _normalize(row["exercise_name"]) == key), None)


def _replace_pending_sets(conn: sqlite3.Connection, exercise_id: int, sets: list[dict]) -> None:
    """Swap the not-yet-logged working sets for ``sets``; logged sets and warm-ups stay as they are."""
    conn.execute("DELETE FROM strength_session_sets WHERE session_exercise_id = ? AND status = 'pending' AND set_type = 'working'",
                 (exercise_id,))
    top = conn.execute("SELECT COALESCE(MAX(set_order), 0) FROM strength_session_sets WHERE session_exercise_id = ?",
                       (exercise_id,)).fetchone()[0]
    for offset, item in enumerate(sets, start=1):
        conn.execute(
            "INSERT INTO strength_session_sets (session_exercise_id, set_order, target_reps, target_weight_kg, rest_seconds, set_type) VALUES (?, ?, ?, ?, ?, 'working')",
            (exercise_id, top + offset, item["target_reps"], item["target_weight_kg"], item["rest_seconds"]),
        )
    rows = conn.execute("SELECT id FROM strength_session_sets WHERE session_exercise_id = ? ORDER BY set_order", (exercise_id,)).fetchall()
    conn.execute("UPDATE strength_session_sets SET set_order = set_order + 1000 WHERE session_exercise_id = ?", (exercise_id,))
    for order, row in enumerate(rows, 1):
        conn.execute("UPDATE strength_session_sets SET set_order = ? WHERE id = ?", (order, row["id"]))


def _repair_position(conn: sqlite3.Connection, session_id: int, exercise_id: int) -> None:
    from .strength_workouts import _active_set_id, _repair_position as repair, _session_or_404

    session = _session_or_404(conn, session_id)
    repair(conn, session_id, _active_set_id(conn, session), exercise_id)


def _apply_to_session(conn: sqlite3.Connection, exercise: sqlite3.Row, plan: dict, note: str) -> dict:
    sets = conn.execute("SELECT * FROM strength_session_sets WHERE session_exercise_id = ? AND set_type = 'working' ORDER BY set_order",
                        (exercise["id"],)).fetchall()
    pending = [row for row in sets if row["status"] == "pending"]
    logged = len(sets) - len(pending)
    before = {
        "exercise_id": int(exercise["id"]),
        "exercise_name": exercise["exercise_name"],
        "notes": exercise["notes"],
        "pending": [{key: row[key] for key in ("target_reps", "target_weight_kg", "rest_seconds")} for row in pending],
    }
    count = max((plan.get("sets") or len(sets)) - logged, 0) if plan.get("sets") else len(pending)
    reference = pending[0] if pending else (sets[-1] if sets else None)
    rest = reference["rest_seconds"] if reference else 90
    new_sets = [
        {
            "target_reps": plan.get("reps") or (reference["target_reps"] if reference else 8),
            "target_weight_kg": plan["load_kg"] if plan.get("load_kg") is not None else (reference["target_weight_kg"] if reference else None),
            "rest_seconds": rest,
        }
        for _ in range(count)
    ]
    conn.execute("UPDATE strength_session_exercises SET exercise_name = ?, notes = ? WHERE id = ?",
                 (plan.get("swap_to") or exercise["exercise_name"], note, exercise["id"]))
    _replace_pending_sets(conn, exercise["id"], new_sets)
    _repair_position(conn, exercise["session_id"], exercise["id"])
    return before


def _restore_session(conn: sqlite3.Connection, session_id: Optional[int], before: Optional[dict]) -> None:
    if not before or session_id is None:
        return
    session = conn.execute("SELECT status FROM strength_workout_sessions WHERE id = ?", (session_id,)).fetchone()
    exercise = conn.execute("SELECT * FROM strength_session_exercises WHERE id = ? AND session_id = ?",
                            (before["exercise_id"], session_id)).fetchone()
    if not session or session["status"] != "active" or not exercise:
        return
    conn.execute("UPDATE strength_session_exercises SET exercise_name = ?, notes = ? WHERE id = ?",
                 (before["exercise_name"], before["notes"], exercise["id"]))
    _replace_pending_sets(conn, exercise["id"], before["pending"])
    _repair_position(conn, session_id, exercise["id"])


# --- lifecycle ------------------------------------------------------------------------

def _get(conn: sqlite3.Connection, block_id: int) -> sqlite3.Row:
    ensure_table(conn)
    row = conn.execute("SELECT * FROM strength_stall_blocks WHERE id = ?", (block_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Stall block not found.")
    return row


def start_block(conn: sqlite3.Connection, exercise_name: str, session_id: Optional[int] = None,
                scope: str = "block", today: Optional[date] = None) -> dict:
    today = today or date.today()
    ensure_table(conn)
    plateau = next(iter(find_plateaus(conn, today, [exercise_name])), None)
    if not plateau or not plateau["suggestion"].get("plan"):
        raise HTTPException(status_code=400, detail=f"{exercise_name} is not stalled right now.")
    suggestion = plateau["suggestion"]
    plan = suggestion["plan"]
    if not plan["weeks"]:
        scope = "today"  # A micro-deload is one session by design.
    running = active_blocks(conn, today)
    if _block_for(running, exercise_name):
        raise HTTPException(status_code=409, detail=f"{exercise_name} already has a block running.")
    if scope == "block" and running:
        raise HTTPException(status_code=409, detail=f"One lift at a time: finish the {running[0]['exercise_name']} block first.")
    exercise = _session_exercise(conn, session_id, exercise_name)
    if scope == "today" and not exercise:
        raise HTTPException(status_code=400, detail=f"{exercise_name} is not in a workout in progress.")

    ends_on = (today + timedelta(weeks=plan["weeks"])).isoformat() if scope == "block" else today.isoformat()
    note = _block_note(plan, ends_on) if scope == "block" else f"Trying today: {suggestion['label'].lower()}" + (f", {plan['cue']}." if plan.get("cue") else ".")
    with conn:
        templates_before = _apply_to_templates(conn, exercise_name, plan, ends_on) if scope == "block" else []
        session_before = _apply_to_session(conn, exercise, plan, note) if exercise else None
        cursor = conn.execute(
            """INSERT INTO strength_stall_blocks (exercise_name, applied_name, kind, label, text, plan_json, scope, status,
               started_on, ends_on, session_id, stall_json, templates_before_json, session_before_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)""",
            (
                plateau["exercise_name"], plan.get("swap_to") or plateau["exercise_name"], suggestion["kind"],
                suggestion["label"], suggestion["text"], json.dumps(plan), scope, today.isoformat(), ends_on,
                session_id if exercise else None,
                json.dumps({key: plateau[key] for key in ("e1rm", "since", "weeks", "sessions", "last")}),
                json.dumps(templates_before), json.dumps(session_before) if session_before else None,
            ),
        )
    return _serialize(_get(conn, int(cursor.lastrowid)), today)


def undo_block(conn: sqlite3.Connection, block_id: int, today: Optional[date] = None) -> dict:
    """Take a block back as if it never started (only before any of it has been logged)."""
    today = today or date.today()
    row = _get(conn, block_id)
    if row["status"] != "active":
        raise HTTPException(status_code=400, detail="Only a running block can be undone.")
    with conn:
        _restore_templates(conn, json.loads(row["templates_before_json"]), row["applied_name"])
        _restore_session(conn, row["session_id"], json.loads(row["session_before_json"]) if row["session_before_json"] else None)
        conn.execute("UPDATE strength_stall_blocks SET status = 'undone', ended_on = ? WHERE id = ?", (today.isoformat(), block_id))
    return _serialize(_get(conn, block_id), today)


def _best_since(conn: sqlite3.Connection, name: str, since: date, today: date) -> Optional[dict]:
    lift = _lift_history(conn, since, today + timedelta(days=1)).get(_normalize(name))
    if not lift:
        return None
    best = max(lift["points"], key=lambda point: point["e1rm"])
    return {"e1rm": best["e1rm"], "top_load_kg": best["top_load_kg"], "reps": best["reps"],
            "date": best["date"].isoformat(), "sessions": len(lift["points"])}


def finish_block(conn: sqlite3.Connection, block_id: int, keep: bool = False, today: Optional[date] = None) -> dict:
    """End a block: put the original lift back (or keep the new version) and record the result."""
    today = today or date.today()
    row = _get(conn, block_id)
    if row["status"] != "active":
        raise HTTPException(status_code=400, detail="This block has already ended.")
    started = date.fromisoformat(row["started_on"])
    stall = json.loads(row["stall_json"])
    during = _best_since(conn, row["applied_name"], started, today)
    outcome = {
        "e1rm_before": stall.get("e1rm"),
        "during": during,
        # Same lift trained in the block: did its estimated 1RM finally move past the stall?
        "beat_stall": bool(during and row["applied_name"] == row["exercise_name"] and stall.get("e1rm")
                           and during["e1rm"] > stall["e1rm"]),
    }
    status = "kept" if keep else ("done" if row["scope"] == "today" else "reverted")
    with conn:
        if not keep:
            _restore_templates(conn, json.loads(row["templates_before_json"]), row["applied_name"])
        conn.execute("UPDATE strength_stall_blocks SET status = ?, ended_on = ?, outcome_json = ? WHERE id = ?",
                     (status, today.isoformat(), json.dumps(outcome), block_id))
    return _serialize(_get(conn, block_id), today)


def close_session_changes(conn: sqlite3.Connection, session_id: int, abandoned: bool = False,
                          today: Optional[date] = None) -> None:
    """A one-session change ends with its session; a discarded session takes it back."""
    try:
        rows = conn.execute("SELECT id FROM strength_stall_blocks WHERE session_id = ? AND scope = 'today' AND status = 'active'",
                            (session_id,)).fetchall()
    except sqlite3.OperationalError:
        return
    for row in rows:
        if abandoned:
            with conn:
                conn.execute("UPDATE strength_stall_blocks SET status = 'undone', ended_on = ? WHERE id = ?",
                             ((today or date.today()).isoformat(), row["id"]))
        else:
            finish_block(conn, int(row["id"]), today=today)
