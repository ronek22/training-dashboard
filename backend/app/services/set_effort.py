"""Carry between-set effort taps into the next session's brief.

Only the latest TrainLog session of each lift counts: that is the one the
next session builds on, and older taps say little about today's load.
"""

import sqlite3
from collections import defaultdict
from typing import Iterable


def _normalize(name: str) -> str:
    return "".join(character.lower() for character in (name or "") if character.isalnum())


def _kg(value: float) -> str:
    return f"{value:g} kg"


def _note(rated: list[dict]) -> tuple[str, str] | None:
    counts = defaultdict(int)
    for item in rated:
        counts[item["effort"]] += 1
    top = max(float(item["weight_kg"] or 0) for item in rated)
    load = _kg(top) if top else "bodyweight"
    total = len(rated)
    if counts["form"]:
        sets = f"{counts['form']} set{'s' if counts['form'] > 1 else ''}"
        return "form", f"Form broke on {sets} at {load} last time. Own every rep at {load} before adding load."
    if counts["grinding"] * 2 >= total:
        return "grinding", f"Grinding on {counts['grinding']} of {total} rated sets at {load} last time. Repeat {load} and match the reps before adding."
    if counts["easy"] * 2 >= total and not counts["grinding"]:
        return "easy", f"Felt easy at {load} last time. Add one step today."
    return None


def effort_carryover(conn: sqlite3.Connection, exercise_names: Iterable[str]) -> list[dict]:
    wanted = {_normalize(name): name for name in exercise_names if name}
    if not wanted:
        return []
    rows = conn.execute(
        """
        SELECT exercise.exercise_name, session.id AS session_id, session.started_at,
               workout_set.actual_reps AS reps, workout_set.actual_weight_kg AS weight_kg, workout_set.effort
        FROM strength_session_sets workout_set
        JOIN strength_session_exercises exercise ON exercise.id = workout_set.session_exercise_id
        JOIN strength_workout_sessions session ON session.id = exercise.session_id
        WHERE workout_set.status = 'completed' AND workout_set.set_type != 'warmup'
          AND session.status = 'completed'
        ORDER BY session.started_at DESC, workout_set.set_order
        """
    ).fetchall()
    latest: dict[str, int] = {}
    sets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _normalize(row["exercise_name"])
        if key not in wanted:
            continue
        latest.setdefault(key, row["session_id"])
        if row["session_id"] == latest[key]:
            sets[key].append(dict(row))
    notes = []
    for key, items in sets.items():
        rated = [item for item in items if item["effort"]]
        result = _note(rated) if rated else None
        if result:
            notes.append({
                "exercise_name": wanted[key],
                "effort": result[0],
                "text": result[1],
                "performed_at": items[0]["started_at"],
            })
    order = {"form": 0, "grinding": 1, "easy": 2}
    return sorted(notes, key=lambda item: order[item["effort"]])
