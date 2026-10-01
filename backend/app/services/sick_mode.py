"""Sick mode: a short illness period that swaps the day's plan for gentle home movement.

Uses the "neck check": head-cold symptoms (runny nose, sore throat) allow easy movement;
fever, chest congestion, body aches or stomach bugs mean the bare minimum. Each session
names the Apple Watch workout to start, so it syncs through Strava like any activity; the
manual log is a fallback for days without the watch. Strength types are avoided on purpose so
a light circuit is never matched to a planned lift and does not advance the A/B rotation.
"""
import json
import math
import sqlite3
from datetime import date, datetime
from typing import Optional

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

def _reps(name: str, reps: int, cue: str, per_side: bool = False) -> dict:
    return {"name": name, "reps": reps, "per_side": per_side, "cue": cue}


def _hold(name: str, seconds: int, cue: str, per_side: bool = False) -> dict:
    return {"name": name, "seconds": seconds, "per_side": per_side, "cue": cue}


# Exercises drive the guided follow-along page; rest_seconds sits between rounds.
SESSIONS = {
    "mobility_flow": {
        "title": "Mobility flow",
        "type": "Yoga",
        "watch_workout": "Flexibility",
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
}


# Pace for the time estimate: an easy rep plus a short setup before each exercise.
REP_SECONDS = 3
TRANSITION_SECONDS = 15


def estimate_seconds(session: dict) -> int:
    exercises = session["exercises"]
    transition = TRANSITION_SECONDS if len(exercises) > 1 else 0
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
    return ([f"{session['rounds']} easy rounds"] if session["rounds"] > 1 else []) + steps


def public_session(key: str) -> Optional[dict]:
    session = SESSIONS.get(key)
    if not session:
        return None
    return {
        "key": key,
        **{field: value for field, value in session.items() if field != "severities"},
        "duration_min": math.ceil(estimate_seconds(session) / 60),
        "steps": session_steps(session),
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
    if not session:
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


def save_sick_session_completion(conn: sqlite3.Connection, payload: dict, today: Optional[date] = None) -> dict:
    """Record a finished guided session; re-finishing (after an extra round) updates the same row."""
    if payload["session_key"] not in SESSIONS:
        raise ValueError(f"Unknown sick mode session: {payload['session_key']}")
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
    reconcile_sick_session_activities(conn)
    return build_sick_mode(conn, today)


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
    return f"Sick mode: {session['title']}{added} (guided in TrainLog)."


def reconcile_sick_session_activities(conn: sqlite3.Connection) -> None:
    """Match each guided session to the watch workout that synced for it and mark it as mobility.

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
        if completion["session_key"] not in SESSIONS:
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


def _completions_on(conn: sqlite3.Connection, day: str) -> list[dict]:
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
    ]


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
    completions = _completions_on(conn, day.isoformat())
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
            if severity in session["severities"]
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
