"""Today's rehab routine as a guided follow-along session.

Built from the current routine of every active Recovery-page issue. The assistant writes doses as
free text ("5 x 30 sec, daily", "3 x 12/side, 4 days/week", "3 x 8-10, every other day"); they are
parsed into straight sets, and the frequency decides which exercises are due today. An exercise
ticked today is done and left out of the session.
"""
import math
import re
from datetime import date, datetime, timedelta
from typing import Optional

from .recovery import _ticked, rehab_routines

SESSION_KEY = "rehab"
CONTEXT = "rehab"
CONTEXT_LABEL = "Rehab"
SET_REST_SECONDS = 30
TRANSITION_SECONDS = 15
REP_SECONDS = 3

# Core Training syncs as a plain workout; Functional Strength would sync as WeightTraining and
# count toward the lift goal. A routine of stretches only is a Flexibility workout.
WATCH_WORKOUT = "Core Training"
STRETCH_WATCH_WORKOUT = "Flexibility"

_SETS = re.compile(
    r"(?P<sets>\d+)\s*[x×]\s*(?P<low>\d+)(?:\s*[-–]\s*(?P<high>\d+))?\s*(?P<unit>seconds?|secs?|s\b|minutes?|mins?|min\b)?",
    re.IGNORECASE,
)
_SINGLE = re.compile(r"(?P<low>\d+)(?:\s*[-–]\s*(?P<high>\d+))?\s*(?P<unit>seconds?|secs?|s\b|minutes?|mins?|min\b|reps?)", re.IGNORECASE)
_PER_SIDE = re.compile(r"/\s*side|per\s+(?:side|leg)|each\s+(?:side|leg)|/\s*leg", re.IGNORECASE)
_EVERY_OTHER = re.compile(r"every\s+other\s+day|alternate\s+days|co\s+drugi\s+dzie", re.IGNORECASE)
_PER_WEEK = re.compile(r"(\d)\s*(?:x|times|days?)\s*(?:/|a|per)\s*(?:week|wk)", re.IGNORECASE)


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def parse_dose(dose: str) -> dict:
    """Sets and a rep count or hold from the dose text, plus how often it is done.

    A range keeps its lower end as the target ("20-30 sec" holds 20 s) and the full range as a
    label, so the page can show "×8–10". Text with no numbers becomes one untimed step.
    """
    text = dose or ""
    match = _SETS.search(text)
    sets = int(match["sets"]) if match else 1
    if not match:
        match = _SINGLE.search(text)
    parsed = {"sets": max(1, min(sets, 10)), "per_side": bool(_PER_SIDE.search(text)), "frequency": parse_frequency(text)}
    if not match:
        return parsed
    low, high, unit = int(match["low"]), match["high"], (match["unit"] or "").lower()
    if unit.startswith("m"):
        parsed["seconds"] = low * 60
    elif unit.startswith("s"):
        parsed["seconds"] = low
    else:
        parsed["reps"] = low
    if high and int(high) > low:
        parsed["range"] = f"{low}–{high}" if "reps" in parsed else f"{low}–{high} s"
    return parsed


def parse_frequency(text: str) -> dict:
    if _EVERY_OTHER.search(text or ""):
        return {"kind": "every_other_day", "label": "every other day"}
    weekly = _PER_WEEK.search(text or "")
    if weekly:
        times = max(1, min(int(weekly[1]), 7))
        return {"kind": "per_week", "times": times, "label": f"{times} days/week"}
    return {"kind": "daily", "label": "daily"}


def _tick_days(conn, routine_id: int, index: int, since: date, until: date) -> set[str]:
    rows = conn.execute(
        "SELECT day FROM recovery_routine_ticks WHERE routine_id = ? AND exercise_index = ? AND day BETWEEN ? AND ?",
        (routine_id, index, since.isoformat(), until.isoformat()),
    )
    return {row[0] for row in rows}


def is_due(conn, routine_id: int, index: int, frequency: dict, today: date) -> bool:
    """Daily is always due; every other day rests after a ticked yesterday; n days/week is due
    until it has n ticks in the six days before today."""
    if frequency["kind"] == "every_other_day":
        yesterday = today - timedelta(days=1)
        return not _tick_days(conn, routine_id, index, yesterday, yesterday)
    if frequency["kind"] == "per_week":
        return len(_tick_days(conn, routine_id, index, today - timedelta(days=6), today - timedelta(days=1))) < frequency["times"]
    return True


def _work_seconds(exercise: dict) -> int:
    work = exercise["seconds"] if "seconds" in exercise else exercise.get("reps", 10) * REP_SECONDS
    return work * (2 if exercise["per_side"] else 1)


def estimate_seconds(exercises: list[dict]) -> int:
    return sum(
        _work_seconds(item) * item["sets"] + SET_REST_SECONDS * (item["sets"] - 1) + TRANSITION_SECONDS
        for item in exercises
    )


def step_label(exercise: dict) -> str:
    if "seconds" in exercise:
        amount = exercise.get("range") or (f"{exercise['seconds'] // 60} min" if exercise["seconds"] % 60 == 0 else f"{exercise['seconds']} s")
    elif "reps" in exercise:
        amount = exercise.get("range") or str(exercise["reps"])
    else:
        return exercise["name"]
    sets = f"{exercise['sets']} × " if exercise["sets"] > 1 else ("×" if "reps" in exercise else "")
    return f"{exercise['name']} {sets}{amount}{'/side' if exercise['per_side'] else ''}"


def routine_exercises(conn, today: Optional[date] = None) -> list[dict]:
    """Every exercise of every current routine with its parsed dose, due and done flags."""
    day = _today(today)
    items = []
    for routine in rehab_routines(conn):
        ticked = set(_ticked(conn, routine["routine_id"], day.isoformat()))
        for index, exercise in enumerate(routine["exercises"]):
            parsed = parse_dose(exercise.get("dose") or "")
            done = index in ticked
            items.append({
                "issue_id": routine["issue_id"],
                "issue_title": routine["title"],
                "index": index,
                "name": exercise.get("name") or "Exercise",
                "dose": exercise.get("dose") or "",
                "cue": exercise.get("how") or "",
                **parsed,
                "done": done,
                "due": done or is_due(conn, routine["routine_id"], index, parsed["frequency"], day),
            })
    return items


def watch_workout_for(exercises: list[dict]) -> str:
    if exercises and all("stretch" in item["name"].lower() for item in exercises):
        return STRETCH_WATCH_WORKOUT
    return WATCH_WORKOUT


def _issue_titles(items: list[dict]) -> list[str]:
    return list(dict.fromkeys(item["issue_title"] for item in items))


def build_session(exercises: list[dict], issues: list[str]) -> dict:
    """A session in the guided-page shape; straight sets instead of rounds."""
    return {
        "key": SESSION_KEY,
        "title": "Rehab routine",
        "type": "Workout",
        "watch_workout": watch_workout_for(exercises),
        "context": CONTEXT,
        "context_label": CONTEXT_LABEL,
        "layout": "sets",
        "rounds": 1,
        "rest_seconds": SET_REST_SECONDS,
        "issues": issues,
        "exercises": exercises,
        "duration_min": max(1, math.ceil(estimate_seconds(exercises) / 60)),
        "steps": [step_label(item) for item in exercises],
    }


def todays_session(conn, today: Optional[date] = None) -> Optional[dict]:
    """The exercises still to do today, or None without an active routine."""
    items = routine_exercises(conn, today)
    if not items:
        return None
    pending = [item for item in items if item["due"] and not item["done"]]
    return build_session(pending, _issue_titles(items))


def done_session(conn, today: Optional[date] = None) -> Optional[dict]:
    """What was ticked today, kept with a finished session so the activity page can show it."""
    items = [item for item in routine_exercises(conn, today) if item["done"]]
    return build_session(items, _issue_titles(items)) if items else None


def build_rehab_today(conn, completed_today: list[dict], today: Optional[date] = None) -> dict:
    """Dashboard card state: what is due, what is done, and the session to start."""
    items = routine_exercises(conn, today)
    if not items:
        return {"active": False}
    due = [item for item in items if item["due"]]
    pending = [item for item in due if not item["done"]]
    session = build_session(pending, _issue_titles(items))
    return {
        "active": True,
        "issues": [{"id": issue_id, "title": title} for issue_id, title in dict.fromkeys((item["issue_id"], item["issue_title"]) for item in items)],
        "due_count": len(due),
        "done_count": len(due) - len(pending),
        "rest_count": len(items) - len(due),
        "pending_count": len(pending),
        "duration_min": session["duration_min"] if pending else 0,
        "watch_workout": session["watch_workout"],
        "steps": session["steps"],
        "completed_today": completed_today,
    }
