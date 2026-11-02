"""The recap shown when a TrainLog strength session ends.

Big numbers (time, volume, sets) against the last time this workout was done, new bests per lift
against every earlier session of it, and where each lift's target goes next: up, hold (and why,
from the progression guard) or a rep more. Next targets are planned from this session's own sets,
so they're right even before the session is linked to its Watch or Strava activity.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from .progression_guard import guard_steps
from .strength_progression import (
    _compare,
    _dumbbell_step_kg,
    _max_dumbbell_kg,
    _normalize,
    _session_index,
    _summary,
    _working_sets,
    plan_next_step,
)


def _done_working_sets(exercise: dict) -> list[dict]:
    return [
        item for item in exercise["sets"]
        if item["status"] == "completed" and item["set_type"] != "warmup"
    ]


def _volume(sets: list[dict]) -> float:
    return round(sum(float(item.get("actual_weight_kg") or 0) * int(item.get("actual_reps") or 0) for item in sets), 1)


def _history(conn: sqlite3.Connection, session_id: int, before: str) -> dict[str, dict[str, Any]]:
    """Per lift: the latest earlier session's summary and the best of every earlier one."""
    history: dict[str, dict[str, Any]] = {}
    for session in _session_index(conn):
        # The index lists TrainLog sessions under their negated id.
        if session["id"] == -session_id or session["workout_timestamp"] >= before:
            continue
        for exercise in session.get("exercises", []):
            sets = _working_sets(exercise)
            if not sets:
                continue
            summary = _summary(sets)
            entry = history.setdefault(_normalize(exercise["exercise_name"]), {"bests": {}})
            entry["last"] = {"date": session["workout_date"][:10], "summary": summary}
            bests = entry["bests"]
            for key in ("top_load_kg", "e1rm", "volume_kg"):
                if summary[key] is not None and summary[key] > (bests.get(key) or 0):
                    bests[key] = summary[key]
            if not summary["weighted"] and (summary["best_reps"] or 0) > (bests.get("bodyweight_reps") or 0):
                bests["bodyweight_reps"] = summary["best_reps"]
    return history


def _new_bests(summary: dict, bests: dict) -> list[str]:
    """Bests beaten today, most impressive first. A lift's first ever session has none."""
    if not bests:
        return []
    found = []
    if summary["weighted"]:
        if summary["top_load_kg"] and summary["top_load_kg"] > (bests.get("top_load_kg") or 0):
            found.append("heaviest")
        if summary["e1rm"] and summary["e1rm"] > (bests.get("e1rm") or 0):
            found.append("e1rm")
        if summary["volume_kg"] and summary["volume_kg"] > (bests.get("volume_kg") or 0):
            found.append("volume")
    elif summary["best_reps"] and summary["best_reps"] > (bests.get("bodyweight_reps") or 0):
        found.append("reps")
    return found


def _change(step: Optional[dict], summary: dict, reps_hit: int) -> Optional[str]:
    if not step:
        return None
    load, top = step.get("target_weight_kg"), summary["top_load_kg"]
    if load is not None and top is not None:
        if load > top:
            return "up"
        if load < top:
            return "down"
    if step.get("held"):
        return "hold"
    return "reps" if (step.get("target_reps") or 0) > reps_hit else "hold"


def _previous_template_session(conn: sqlite3.Connection, session: sqlite3.Row) -> Optional[dict]:
    if session["template_id"] is None:
        return None
    row = conn.execute(
        """
        SELECT id, started_at FROM strength_workout_sessions
        WHERE template_id = ? AND status = 'completed' AND id != ? AND started_at < ?
        ORDER BY started_at DESC LIMIT 1
        """,
        (session["template_id"], session["id"], session["started_at"]),
    ).fetchone()
    if not row:
        return None
    totals = conn.execute(
        """
        SELECT COALESCE(SUM(COALESCE(s.actual_weight_kg, 0) * COALESCE(s.actual_reps, 0)), 0) AS volume,
               COUNT(*) AS sets
        FROM strength_session_sets s
        JOIN strength_session_exercises e ON e.id = s.session_exercise_id
        WHERE e.session_id = ? AND s.status = 'completed' AND s.set_type != 'warmup'
        """,
        (row["id"],),
    ).fetchone()
    return {"date": row["started_at"][:10], "volume_kg": round(float(totals["volume"]), 1), "sets": int(totals["sets"])}


def _minutes(started_at: str, completed_at: Optional[str]) -> Optional[int]:
    if not completed_at:
        return None
    try:
        delta = datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)
    except ValueError:
        return None
    return max(0, round(delta.total_seconds() / 60))


def build_session_summary(conn: sqlite3.Connection, session_id: int) -> dict:
    from .strength_workouts import get_session

    row = conn.execute("SELECT * FROM strength_workout_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strength workout session not found.")
    session = get_session(conn, session_id)
    day = row["started_at"][:10]
    history = _history(conn, session_id, row["started_at"])

    exercises, names, lifts, steps, reps_hit = [], [], [], [], []
    for exercise in session["exercises"]:
        done = _done_working_sets(exercise)
        if not done:
            continue
        name = exercise["exercise_name"]
        sets = [{"reps": int(item["actual_reps"] or 0), "weight_kg": item.get("actual_weight_kg")} for item in done]
        lifted = [item for item in sets if item["reps"] > 0]
        summary = _summary(lifted) if lifted else None
        past = history.get(_normalize(name), {})
        last = past.get("last")
        timed = any(item.get("target_seconds") for item in exercise["sets"])
        target_reps = max((int(item["target_reps"] or 0) for item in done), default=0) or None
        lift = None
        if summary and not timed:
            compared = _compare(summary, last["summary"]) if last else None
            lift = {
                "exercise_name": name,
                "date": day,
                "sets": lifted,
                "summary": summary,
                "previous": {"metric_value": compared["value"], "direction": compared["direction"]} if compared else None,
            }
        names.append(name)
        lifts.append(lift)
        steps.append(plan_next_step(lift, name, target_reps, _max_dumbbell_kg(conn), _dumbbell_step_kg(conn)) if lift else None)
        top_set = max(done, key=lambda item: (float(item.get("actual_weight_kg") or 0), int(item.get("actual_reps") or 0), int(item.get("actual_seconds") or 0)))
        reps_hit.append(min((item["reps"] for item in lifted if item["weight_kg"] == (summary or {}).get("top_load_kg")), default=0))
        exercises.append({
            "exercise_name": name,
            "set_count": len(done),
            "reps": sum(item["reps"] for item in lifted) if not timed else None,
            "volume_kg": _volume(done),
            "top_set": {
                "weight_kg": top_set.get("actual_weight_kg"),
                "reps": top_set.get("actual_reps"),
                "seconds": top_set.get("actual_seconds"),
            },
            "seconds": sum(int(item.get("actual_seconds") or 0) for item in done) if timed else None,
            "last": {
                "date": last["date"],
                "volume_kg": last["summary"]["volume_kg"],
                "top_weight_kg": last["summary"]["top_load_kg"],
                "best_reps": last["summary"]["best_reps"],
            } if last and not timed else None,
            "bests": _new_bests(summary, past.get("bests", {})) if summary and not timed else [],
            "first_time": not past,
        })

    # Next session's targets, with the same caution the pre-workout brief applies, judged for
    # the day after (the guard writes "today", so a busy-day hold names that day instead).
    next_day = date.fromisoformat(day) + timedelta(days=1)
    guarded = guard_steps(conn, names, lifts, steps, today=next_day) if names else []
    for exercise, lift, step, hit in zip(exercises, lifts, guarded, reps_hit):
        hint = step and step.get("hint")
        if hint and step.get("held") == "life_load":
            hint = hint.replace(" today:", f" {next_day.strftime('%A')}:", 1)
        exercise["next"] = step and {
            "target_weight_kg": step.get("target_weight_kg"),
            "target_reps": step.get("target_reps"),
            "hint": hint,
            "held": step.get("held"),
            "change": _change(step, lift["summary"], hit),
        }

    all_done = [item for exercise in session["exercises"] for item in _done_working_sets(exercise)]
    changes = [exercise["next"]["change"] for exercise in exercises if exercise.get("next")]
    return {
        "session_id": session_id,
        "template_id": session["template_id"],
        "name": session["template_name"],
        "status": session["status"],
        "date": day,
        "duration_minutes": _minutes(row["started_at"], row["completed_at"]),
        "volume_kg": _volume(all_done),
        "set_count": len(all_done),
        "rep_count": sum(int(item.get("actual_reps") or 0) for item in all_done if not item.get("actual_seconds")),
        "previous": _previous_template_session(conn, row),
        "best_count": sum(1 for exercise in exercises if exercise["bests"]),
        "going_up": changes.count("up"),
        "holding": sum(1 for change in changes if change in ("hold", "down")),
        "exercises": exercises,
    }
