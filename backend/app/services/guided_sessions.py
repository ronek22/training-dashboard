"""Guided follow-along sessions: the catalog, time estimates, finished-session records and the
link from a finished session to the watch workout that synced for it.

Used by sick mode (gentle home movement while ill), the downshift (breathing and mobility on
high-stress days) and travel (no-equipment lifts on a mountain trip). Finished sessions live in sick_session_completions, a name kept from when
only sick mode used them.
"""
import json
import math
import sqlite3
from datetime import date, datetime
from typing import Optional


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _reps(name: str, reps: int, cue: str, per_side: bool = False) -> dict:
    return {"name": name, "reps": reps, "per_side": per_side, "cue": cue}


def _hold(name: str, seconds: int, cue: str, per_side: bool = False) -> dict:
    return {"name": name, "seconds": seconds, "per_side": per_side, "cue": cue}


# Exercises drive the guided follow-along page; rest_seconds sits between rounds.
# context: "sick" sessions are offered in sick mode (by severity) and name an Apple Watch workout
# that is matched to the synced activity; "stress" sessions are the downshift, done without a
# watch workout, and count toward the daily streak through their completion alone; "travel" sessions
# are real lifts away from home: the watch workout syncs as WeightTraining, so they count toward
# the lift goal, but they carry no template and never advance the A/B/C/D rotation.
SESSIONS = {
    "mobility_flow": {
        "title": "Mobility flow",
        "type": "Yoga",
        "watch_workout": "Flexibility",
        "context": "sick",
        "severities": ("above_neck",),
        "rounds": 2,
        "rest_seconds": 45,
        "exercises": [
            _reps("Cat-cow", 10, "On all fours. Inhale as you arch, exhale as you round. Slow."),
            _reps("World's greatest stretch", 5, "Lunge, hand inside the front foot, rotate the chest and reach up.", per_side=True),
            _reps("90/90 hip switches", 8, "Sit tall, both knees bent 90°, rotate the knees side to side."),
            _reps("Open book rotation", 8, "Lie on your side, knees stacked, open the top arm across to the floor.", per_side=True),
            _hold("Child's pose", 60, "Knees wide, arms long, breathe into your back."),
        ],
    },
    "easy_walk": {
        "title": "Easy walk",
        "type": "Walk",
        "watch_workout": "Outdoor or Indoor Walk",
        "context": "sick",
        "severities": ("above_neck",),
        "rounds": 1,
        "rest_seconds": 0,
        "exercises": [
            _hold("Easy walk", 1200, "Conversational pace, nasal breathing. Dress warm and stay close to home."),
        ],
    },
    "light_circuit": {
        "title": "Light bodyweight circuit",
        "type": "Workout",
        "watch_workout": "Core Training",
        "context": "sick",
        "severities": ("above_neck",),
        "rounds": 3,
        "rest_seconds": 60,
        "exercises": [
            _reps("Air squats", 10, "Easy tempo, RPE ≤ 4. Stop if you feel worse."),
            _reps("Incline push-ups", 8, "Hands on a desk or sofa. Smooth, no grinding."),
            _reps("Glute bridges", 12, "Squeeze at the top for a second."),
            _reps("Dead bug", 8, "Lower back pressed into the floor, slow opposite arm and leg.", per_side=True),
        ],
    },
    "gentle_stretch": {
        "title": "Gentle stretch",
        "type": "Yoga",
        "watch_workout": "Flexibility",
        "context": "sick",
        "severities": ("above_neck", "below_neck"),
        "rounds": 1,
        "rest_seconds": 0,
        "exercises": [
            _hold("Knee-to-chest", 60, "Lying on your back, hug one knee in, other leg long.", per_side=True),
            _hold("Supine twist", 60, "Knees drop to one side, shoulders stay down.", per_side=True),
            _hold("Figure-four stretch", 60, "Ankle over the opposite knee, pull the thigh gently in.", per_side=True),
            _hold("Legs up the wall", 120, "Scoot close to the wall, legs up, breathe slowly."),
        ],
    },
    "breathing_reset": {
        "title": "Breathing + neck & shoulders",
        "type": "Yoga",
        "watch_workout": "Mind & Body",
        "context": "sick",
        "severities": ("below_neck",),
        "rounds": 1,
        "rest_seconds": 0,
        "exercises": [
            _hold("Box breathing", 120, "In 4, hold 4, out 4, hold 4. Skip the holds if your chest is tight."),
            _reps("Neck rolls", 5, "Slow half circles, each direction."),
            _reps("Shoulder circles", 10, "Big and slow, forward then back."),
            _reps("Seated side bend", 5, "Reach one arm overhead and lean away.", per_side=True),
        ],
    },
    "two_minute_downshift": {
        "title": "Two-minute downshift",
        "type": "Breathwork",
        "watch_workout": None,
        "context": "stress",
        "rounds": 1,
        "rest_seconds": 0,
        "transition_seconds": 0,  # one breathing pattern flows into the next
        "exercises": [
            _hold("Physiological sigh", 60, "Two short inhales through the nose, one long slow exhale through the mouth. Repeat."),
            _hold("Box breathing", 60, "In 4, hold 4, out 4, hold 4. Shoulders down."),
        ],
    },
    "desk_mobility": {
        "title": "Desk mobility",
        "type": "Mobility",
        "watch_workout": None,
        "context": "stress",
        "rounds": 1,
        "rest_seconds": 0,
        "exercises": [
            _hold("Physiological sigh", 60, "Two short inhales through the nose, one long slow exhale. Let the jaw go."),
            _reps("Neck rolls", 5, "Slow half circles, each direction."),
            _reps("Shoulder circles", 10, "Big and slow, forward then back."),
            _reps("Seated thoracic twist", 6, "Sit tall, hands on the chest, rotate and breathe out.", per_side=True),
            _hold("Standing hip flexor stretch", 45, "Half-kneel or split stance, squeeze the back glute.", per_side=True),
            _reps("Chin tucks", 10, "Slide the head straight back, hold a second."),
            _hold("Forward fold", 45, "Soft knees, let the head hang, slow exhales."),
        ],
    },
    "travel_upper": {
        "title": "Travel kit · Upper body",
        "type": "WeightTraining",
        "watch_workout": "Traditional Strength Training",
        "context": "travel",
        "rounds": 4,
        "rest_seconds": 90,
        "exercises": [
            _reps("Push-ups", 12, "Feet raised on a bed or bench once 12 gets easy. Last rep should be hard, not ugly."),
            _reps("Pike push-ups", 8, "Hips high, lower the head between the hands. Shoulders, not chest."),
            _reps("Backpack rows", 12, "Fill the pack with water bottles, hinge forward, pull to the hip, pause.", per_side=True),
            _reps("Chair dips", 10, "Hands on a sturdy chair, elbows straight back, shoulders down."),
            _reps("Backpack curls", 12, "Hold the pack by the top handle or straps, slow on the way down."),
        ],
    },
    "travel_core": {
        "title": "Travel kit · Core",
        "type": "WeightTraining",
        "watch_workout": "Core Training",
        "context": "travel",
        "rounds": 3,
        "rest_seconds": 45,
        "exercises": [
            _hold("Plank", 45, "Squeeze glutes, ribs down, breathe."),
            _hold("Side plank", 30, "Hips high, top arm up.", per_side=True),
            _reps("Reverse crunch", 12, "Curl the hips off the floor, lower slowly."),
            _hold("Hollow hold", 30, "Lower back pressed down; bend the knees if it lifts."),
        ],
    },
}

CONTEXT_LABELS = {"sick": "Sick mode", "stress": "Downshift", "travel": "Travel kit"}


# Pace for the time estimate: an easy rep plus a short setup before each exercise.
REP_SECONDS = 3
TRANSITION_SECONDS = 15


def estimate_seconds(session: dict) -> int:
    exercises = session["exercises"]
    transition = session.get("transition_seconds", TRANSITION_SECONDS) if len(exercises) > 1 else 0
    per_round = sum(
        (item["reps"] * REP_SECONDS if "reps" in item else item["seconds"]) * (2 if item["per_side"] else 1) + transition
        for item in exercises
    )
    return per_round * session["rounds"] + session["rest_seconds"] * (session["rounds"] - 1)


def _step_label(exercise: dict) -> str:
    dose = f"×{exercise['reps']}" if "reps" in exercise else (
        f"{exercise['seconds'] // 60} min" if exercise["seconds"] % 60 == 0 else f"{exercise['seconds']} s"
    )
    return f"{exercise['name']} {dose}{'/side' if exercise['per_side'] else ''}"


def session_steps(session: dict) -> list[str]:
    steps = [_step_label(exercise) for exercise in session["exercises"]]
    # Travel lifts are real work; only the sick and stress sessions are "easy".
    pace = "" if session["context"] == "travel" else "easy "
    return ([f"{session['rounds']} {pace}rounds"] if session["rounds"] > 1 else []) + steps


def public_session(key: str) -> Optional[dict]:
    session = SESSIONS.get(key)
    if not session:
        return None
    return {
        "key": key,
        **{field: value for field, value in session.items() if field != "severities"},
        "context_label": CONTEXT_LABELS[session["context"]],
        "duration_min": math.ceil(estimate_seconds(session) / 60),
        "steps": session_steps(session),
    }


def save_guided_completion(conn: sqlite3.Connection, payload: dict, today: Optional[date] = None) -> dict:
    """Record a finished guided session; re-finishing (after an extra round) updates the same row."""
    if payload["session_key"] not in SESSIONS:
        raise ValueError(f"Unknown guided session: {payload['session_key']}")
    conn.execute(
        """
        INSERT INTO sick_session_completions (date, session_key, started_at, elapsed_seconds, completed_steps, extras_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_key, started_at) DO UPDATE SET
            elapsed_seconds = excluded.elapsed_seconds,
            completed_steps = excluded.completed_steps,
            extras_json = excluded.extras_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            _today(today).isoformat(),
            payload["session_key"],
            payload["started_at"],
            int(payload["elapsed_seconds"]),
            int(payload.get("completed_steps") or 0),
            json.dumps(payload.get("extras") or []),
        ),
    )
    conn.commit()
    reconcile_guided_session_activities(conn)
    return {"completed_today": completions_on(conn, _today(today).isoformat(), SESSIONS[payload["session_key"]]["context"])}


def _parse_instant(value: Optional[str]) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _completion_note(completion: dict) -> str:
    session = SESSIONS[completion["session_key"]]
    extras = json.loads(completion["extras_json"] or "[]")
    added = f" + {', '.join(extras)}" if extras else ""
    return f"{CONTEXT_LABELS[session['context']]}: {session['title']}{added} (guided in TrainLog)."


def reconcile_guided_session_activities(conn: sqlite3.Connection) -> None:
    """Match each sick-mode session to the watch workout that synced for it and mark it as mobility.

    Downshift sessions are skipped: they have no watch workout, and on a normal training day the
    nearest activity is a real session that must not be relabelled.

    Mobility is the intent every synced type accepts (WeightTraining rejects "recovery").

    Picks the same-day activity whose recorded start is closest to the guided start (within
    3 hours); without a recorded start, the only unmatched activity that day.
    """
    try:
        completions = conn.execute(
            "SELECT id, date, session_key, started_at, extras_json FROM sick_session_completions WHERE activity_id IS NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        return
    changed = False
    for completion in completions:
        if SESSIONS.get(completion["session_key"], {}).get("context") != "sick":
            continue
        candidates = conn.execute(
            """
            SELECT activity.id, activity.notes,
                   (SELECT MIN(ref.started_at) FROM activity_source_refs ref WHERE ref.activity_id = activity.id) AS started_at
            FROM activities activity
            WHERE activity.date = ? AND activity.id NOT LIKE 'sick-%'
              AND activity.id NOT IN (SELECT activity_id FROM sick_session_completions WHERE activity_id IS NOT NULL)
            """,
            (completion["date"],),
        ).fetchall()
        guided_start = _parse_instant(completion["started_at"])
        timed = [
            (abs((_parse_instant(row["started_at"]) - guided_start).total_seconds()), row)
            for row in candidates
            if guided_start and _parse_instant(row["started_at"])
        ]
        timed = [item for item in timed if item[0] <= 3 * 3600]
        if timed:
            match = min(timed, key=lambda item: item[0])[1]
        elif len(candidates) == 1 and not candidates[0]["started_at"]:
            match = candidates[0]
        else:
            continue
        note = _completion_note(dict(completion))
        conn.execute("UPDATE sick_session_completions SET activity_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (match["id"], completion["id"]))
        conn.execute(
            "UPDATE activities SET workout_intent = 'mobility', notes = CASE WHEN notes IS NULL OR notes = '' THEN ? ELSE notes || char(10) || ? END WHERE id = ?",
            (note, note, match["id"]),
        )
        changed = True
    if changed:
        conn.commit()


def completions_on(conn: sqlite3.Connection, day: str, context: Optional[str] = None) -> list[dict]:
    try:
        rows = conn.execute(
            """
            SELECT completion.session_key, completion.elapsed_seconds, completion.extras_json, completion.activity_id,
                   activity.name AS activity_name, activity.duration_min AS activity_duration_min
            FROM sick_session_completions completion
            LEFT JOIN activities activity ON activity.id = completion.activity_id
            WHERE completion.date = ?
            ORDER BY completion.started_at
            """,
            (day,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "session_key": row["session_key"],
            "title": SESSIONS.get(row["session_key"], {}).get("title", row["session_key"]),
            "elapsed_min": round(row["elapsed_seconds"] / 60, 1),
            "extras": json.loads(row["extras_json"] or "[]"),
            "activity_id": row["activity_id"],
            "activity_name": row["activity_name"],
            "activity_duration_min": row["activity_duration_min"],
        }
        for row in rows
        if context is None or SESSIONS.get(row["session_key"], {}).get("context") == context
    ]


def guided_completion_dates(conn: sqlite3.Connection) -> set[str]:
    """Days with a finished guided session: they keep the daily streak even without an activity."""
    try:
        return {row[0] for row in conn.execute("SELECT DISTINCT date FROM sick_session_completions")}
    except sqlite3.OperationalError:
        return set()


def guided_session_for_activity(conn: sqlite3.Connection, activity_id: str) -> Optional[dict]:
    """The guided session behind an activity: a linked watch workout or a manual sick-mode log."""
    try:
        row = conn.execute(
            "SELECT session_key, elapsed_seconds, extras_json FROM sick_session_completions WHERE activity_id = ? ORDER BY started_at DESC LIMIT 1",
            (activity_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row:
        key, guided_min, extras = row["session_key"], round(row["elapsed_seconds"] / 60, 1), json.loads(row["extras_json"] or "[]")
    else:
        key = next((key for key in SESSIONS if str(activity_id).startswith("sick-") and str(activity_id).endswith(f"-{key}")), None)
        guided_min, extras = None, []
    session = public_session(key) if key else None
    if not session:
        return None
    return {**session, "guided_min": guided_min, "extras": extras, "logged_manually": row is None}
