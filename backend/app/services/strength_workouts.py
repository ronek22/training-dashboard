import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Optional

from fastapi import HTTPException

from ..models.strength_workouts import (
    StrengthSessionExerciseAddRequest,
    StrengthTemplateInput,
    StrengthWarmupSetAddRequest,
)


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _template_or_404(conn: sqlite3.Connection, template_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM strength_workout_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strength workout template not found.")
    return row


def _session_or_404(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM strength_workout_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strength workout session not found.")
    return row


def _serialize_template(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    exercises = conn.execute(
        """
        SELECT id, exercise_order, exercise_name, set_count, target_reps,
               target_weight_kg, rest_seconds, notes
        FROM strength_template_exercises
        WHERE template_id = ?
        ORDER BY exercise_order
        """,
        (row["id"],),
    ).fetchall()
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "exercise_count": len(exercises),
        "set_count": sum(int(exercise["set_count"]) for exercise in exercises),
        "estimated_duration_minutes": round(
            sum(
                int(exercise["set_count"]) * 45
                + max(0, int(exercise["set_count"]) - 1) * int(exercise["rest_seconds"])
                for exercise in exercises
            )
            / 60
        ),
        "exercises": [dict(exercise) for exercise in exercises],
    }


def list_templates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM strength_workout_templates ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    return [_serialize_template(conn, row) for row in rows]


def get_template(conn: sqlite3.Connection, template_id: int) -> dict:
    return _serialize_template(conn, _template_or_404(conn, template_id))


def _suggestion_history_rows(conn: sqlite3.Connection) -> list[dict]:
    first_party_rows = conn.execute(
        """
        SELECT
            exercise.exercise_name,
            session.started_at AS performed_at,
            'TrainLog' AS source,
            'trainlog-' || session.id AS session_key,
            workout_set.set_order,
            workout_set.actual_reps AS reps,
            workout_set.actual_weight_kg AS weight_kg,
            CASE WHEN workout_set.set_type = 'warmup' THEN 1 ELSE 0 END AS is_warmup
        FROM strength_session_sets workout_set
        JOIN strength_session_exercises exercise
          ON exercise.id = workout_set.session_exercise_id
        JOIN strength_workout_sessions session
          ON session.id = exercise.session_id
        WHERE workout_set.status = 'completed'
        """
    ).fetchall()
    fitbod_rows = conn.execute(
        """
        SELECT
            exercise.exercise_name,
            session.workout_timestamp AS performed_at,
            'Fitbod' AS source,
            'fitbod-' || session.workout_timestamp AS session_key,
            workout_set.set_order,
            workout_set.reps,
            workout_set.weight_kg,
            workout_set.is_warmup
        FROM fitbod_workout_sets workout_set
        JOIN fitbod_workout_exercises exercise
          ON exercise.id = workout_set.exercise_id
        JOIN fitbod_workout_sessions session
          ON session.id = exercise.session_id
        """
    ).fetchall()
    return [dict(row) for row in [*first_party_rows, *fitbod_rows]]


def _mode(values: list[int]) -> Optional[int]:
    if not values:
        return None
    counts = Counter(values)
    highest_count = max(counts.values())
    return next(value for value in reversed(values) if counts[value] == highest_count)


def exercise_suggestions(
    conn: sqlite3.Connection,
    query: Optional[str] = None,
    limit: int = 12,
) -> list[dict]:
    normalized_query = "".join(character.lower() for character in (query or "") if character.isalnum())
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in _suggestion_history_rows(conn):
        normalized_name = "".join(
            character.lower() for character in (row["exercise_name"] or "") if character.isalnum()
        )
        if not normalized_name or (normalized_query and normalized_query not in normalized_name):
            continue
        grouped[normalized_name].append(row)

    suggestions = []
    for normalized_name, rows in grouped.items():
        rows.sort(key=lambda row: (row["performed_at"] or "", int(row["set_order"] or 0)))
        latest_row = rows[-1]
        latest_session_rows = [
            row
            for row in rows
            if row["session_key"] == latest_row["session_key"] and not bool(row["is_warmup"])
        ]
        if not latest_session_rows:
            latest_session_rows = [row for row in rows if row["session_key"] == latest_row["session_key"]]
        deduplicated_rows = []
        seen_sets = set()
        for row in latest_session_rows:
            signature = (row["set_order"], row["reps"], row["weight_kg"], row["is_warmup"])
            if signature in seen_sets:
                continue
            seen_sets.add(signature)
            deduplicated_rows.append(row)
        latest_session_rows = deduplicated_rows
        rep_values = [int(row["reps"]) for row in latest_session_rows if row["reps"] is not None]
        weight_values = [
            float(row["weight_kg"])
            for row in latest_session_rows
            if row["weight_kg"] is not None and float(row["weight_kg"]) > 0
        ]
        display_name = latest_row["exercise_name"]
        suggestions.append(
            {
                "exercise_name": display_name,
                "normalized_name": normalized_name,
                "last_performed_at": latest_row["performed_at"],
                "session_count": len({row["session_key"] for row in rows}),
                "sources": sorted({row["source"] for row in rows}),
                "suggested_set_count": len(latest_session_rows),
                "suggested_reps": _mode(rep_values),
                "suggested_weight_kg": round(float(median(weight_values)), 2) if weight_values else None,
                "basis": "Latest recorded work sets",
            }
        )

    suggestions.sort(key=lambda item: item["last_performed_at"] or "", reverse=True)
    suggestions.sort(key=lambda item: item["session_count"], reverse=True)
    if normalized_query:
        suggestions.sort(
            key=lambda item: 0 if item["normalized_name"].startswith(normalized_query) else 1
        )
    return suggestions[: max(1, min(limit, 50))]


def save_template(
    conn: sqlite3.Connection,
    payload: StrengthTemplateInput,
    template_id: Optional[int] = None,
) -> dict:
    now = _iso(_now())
    with conn:
        if template_id is None:
            cursor = conn.execute(
                "INSERT INTO strength_workout_templates (name, notes, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (payload.name, payload.notes, now, now),
            )
            template_id = int(cursor.lastrowid)
        else:
            _template_or_404(conn, template_id)
            conn.execute(
                "UPDATE strength_workout_templates SET name = ?, notes = ?, updated_at = ? WHERE id = ?",
                (payload.name, payload.notes, now, template_id),
            )
            conn.execute(
                "DELETE FROM strength_template_exercises WHERE template_id = ?",
                (template_id,),
            )

        for index, exercise in enumerate(payload.exercises, start=1):
            conn.execute(
                """
                INSERT INTO strength_template_exercises
                (template_id, exercise_order, exercise_name, set_count, target_reps,
                 target_weight_kg, rest_seconds, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template_id,
                    index,
                    exercise.exercise_name,
                    exercise.set_count,
                    exercise.target_reps,
                    exercise.target_weight_kg,
                    exercise.rest_seconds,
                    exercise.notes,
                ),
            )
    return get_template(conn, template_id)


def delete_template(conn: sqlite3.Connection, template_id: int) -> None:
    _template_or_404(conn, template_id)
    with conn:
        conn.execute(
            "UPDATE strength_workout_sessions SET template_id = NULL WHERE template_id = ?",
            (template_id,),
        )
        conn.execute(
            "DELETE FROM strength_template_exercises WHERE template_id = ?",
            (template_id,),
        )
        conn.execute("DELETE FROM strength_workout_templates WHERE id = ?", (template_id,))


def _serialize_session(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    exercise_rows = conn.execute(
        """
        SELECT * FROM strength_session_exercises
        WHERE session_id = ?
        ORDER BY exercise_order
        """,
        (row["id"],),
    ).fetchall()
    exercises = []
    total_sets = 0
    completed_sets = 0
    for exercise_row in exercise_rows:
        set_rows = conn.execute(
            """
            SELECT * FROM strength_session_sets
            WHERE session_exercise_id = ?
            ORDER BY set_order
            """,
            (exercise_row["id"],),
        ).fetchall()
        sets = [dict(set_row) for set_row in set_rows]
        working_sets = [item for item in sets if item["set_type"] != "warmup"]
        warmup_sets = [item for item in sets if item["set_type"] == "warmup"]
        total_sets += len(working_sets)
        completed_sets += sum(1 for item in working_sets if item["status"] == "completed")
        exercises.append(
            {
                "id": int(exercise_row["id"]),
                "exercise_order": int(exercise_row["exercise_order"]),
                "exercise_name": exercise_row["exercise_name"],
                "notes": exercise_row["notes"],
                "sets": sets,
                "completed_set_count": sum(
                    1 for item in working_sets if item["status"] == "completed"
                ),
                "warmup_set_count": len(warmup_sets),
                "completed_warmup_set_count": sum(
                    1 for item in warmup_sets if item["status"] == "completed"
                ),
            }
        )

    linked_activity = None
    if row["linked_activity_id"]:
        activity = conn.execute(
            """
            SELECT id, date, type, name, duration_min, avg_hr, max_hr, calories
            FROM activities WHERE id = ?
            """,
            (row["linked_activity_id"],),
        ).fetchone()
        linked_activity = dict(activity) if activity else None

    return {
        "id": int(row["id"]),
        "template_id": row["template_id"],
        "template_name": row["template_name"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "current_exercise_order": int(row["current_exercise_order"]),
        "current_set_order": int(row["current_set_order"]),
        "linked_activity": linked_activity,
        "progress": {
            "completed_sets": completed_sets,
            "total_sets": total_sets,
            "fraction": completed_sets / total_sets if total_sets else 0,
        },
        "exercises": exercises,
    }


def get_trainlog_strength_detail_for_activity(
    conn: sqlite3.Connection,
    activity_id: str,
) -> Optional[dict]:
    """Return a linked first-party workout in the Activity Detail strength contract."""
    session = conn.execute(
        """
        SELECT * FROM strength_workout_sessions
        WHERE linked_activity_id = ?
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (activity_id,),
    ).fetchone()
    if not session:
        return None

    exercise_rows = conn.execute(
        """
        SELECT * FROM strength_session_exercises
        WHERE session_id = ?
        ORDER BY exercise_order
        """,
        (session["id"],),
    ).fetchall()
    exercises = []
    for exercise in exercise_rows:
        completed_sets = conn.execute(
            """
            SELECT * FROM strength_session_sets
            WHERE session_exercise_id = ? AND status = 'completed'
            ORDER BY set_order
            """,
            (exercise["id"],),
        ).fetchall()
        if not completed_sets:
            continue

        sets = [
            {
                "id": f"trainlog-set-{workout_set['id']}",
                "set_order": int(workout_set["set_order"]),
                "reps": workout_set["actual_reps"],
                "weight_kg": workout_set["actual_weight_kg"],
                "duration_seconds": None,
                "distance_m": None,
                "incline": None,
                "resistance": None,
                "is_warmup": workout_set["set_type"] == "warmup",
                "note": None,
                "multiplier": None,
            }
            for workout_set in completed_sets
        ]
        working_sets = [
            workout_set for workout_set in completed_sets
            if workout_set["set_type"] != "warmup"
        ]
        warmup_sets = [
            workout_set for workout_set in completed_sets
            if workout_set["set_type"] == "warmup"
        ]
        rep_count = sum(int(workout_set["actual_reps"] or 0) for workout_set in working_sets)
        total_volume_kg = sum(
            int(workout_set["actual_reps"] or 0) * float(workout_set["actual_weight_kg"] or 0)
            for workout_set in working_sets
        )
        exercises.append(
            {
                "id": f"trainlog-exercise-{exercise['id']}",
                "exercise_order": int(exercise["exercise_order"]),
                "exercise_name": exercise["exercise_name"],
                "set_count": len(working_sets),
                "rep_count": rep_count,
                "total_volume_kg": round(total_volume_kg, 2),
                "work_set_count": len(working_sets),
                "warmup_set_count": len(warmup_sets),
                "sets": sets,
            }
        )

    started_at = session["started_at"]
    completed_at = session["completed_at"]
    duration_seconds = None
    if started_at and completed_at:
        try:
            duration_seconds = max(
                0,
                round((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds()),
            )
        except (TypeError, ValueError):
            duration_seconds = None

    return {
        "status": "enriched" if exercises else "linked_no_sets",
        "source": "trainlog",
        "session": {
            "id": f"trainlog-session-{session['id']}",
            "session_key": f"trainlog-{session['id']}",
            "workout_timestamp": started_at,
            "workout_date": str(started_at)[:10] if started_at else None,
            "title": session["template_name"],
            "exercise_count": len(exercises),
            "set_count": sum(exercise["set_count"] for exercise in exercises),
            "rep_count": sum(exercise["rep_count"] for exercise in exercises),
            "total_volume_kg": round(sum(exercise["total_volume_kg"] for exercise in exercises), 2),
            "total_duration_seconds": duration_seconds,
            "calories": None,
            "match_status": "matched",
            "match_provenance": "trainlog_link",
            "matched_activity_id": activity_id,
            "exercises": exercises,
        },
    }


def start_session(conn: sqlite3.Connection, template_id: int) -> dict:
    active = conn.execute(
        "SELECT id FROM strength_workout_sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if active:
        raise HTTPException(
            status_code=409,
            detail={"message": "A strength workout is already active.", "session_id": int(active["id"])},
        )

    template = _template_or_404(conn, template_id)
    template_exercises = conn.execute(
        "SELECT * FROM strength_template_exercises WHERE template_id = ? ORDER BY exercise_order",
        (template_id,),
    ).fetchall()
    if not template_exercises:
        raise HTTPException(status_code=400, detail="The template has no exercises.")

    now = _iso(_now())
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO strength_workout_sessions
            (template_id, template_name, status, started_at, current_exercise_order,
             current_set_order, created_at, updated_at)
            VALUES (?, ?, 'active', ?, 1, 1, ?, ?)
            """,
            (template_id, template["name"], now, now, now),
        )
        session_id = int(cursor.lastrowid)
        for exercise in template_exercises:
            exercise_cursor = conn.execute(
                """
                INSERT INTO strength_session_exercises
                (session_id, exercise_order, exercise_name, notes)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, exercise["exercise_order"], exercise["exercise_name"], exercise["notes"]),
            )
            session_exercise_id = int(exercise_cursor.lastrowid)
            for set_order in range(1, int(exercise["set_count"]) + 1):
                conn.execute(
                    """
                    INSERT INTO strength_session_sets
                    (session_exercise_id, set_order, target_reps, target_weight_kg, rest_seconds)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_exercise_id,
                        set_order,
                        exercise["target_reps"],
                        exercise["target_weight_kg"],
                        exercise["rest_seconds"],
                    ),
                )
    return get_session(conn, session_id)


def get_session(conn: sqlite3.Connection, session_id: int) -> dict:
    return _serialize_session(conn, _session_or_404(conn, session_id))


def get_active_session(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM strength_workout_sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return _serialize_session(conn, row) if row else None


def add_session_exercise(
    conn: sqlite3.Connection,
    session_id: int,
    payload: StrengthSessionExerciseAddRequest,
) -> dict:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    exercise_count = conn.execute(
        "SELECT COUNT(*) AS count FROM strength_session_exercises WHERE session_id = ?",
        (session_id,),
    ).fetchone()["count"]
    if int(exercise_count) >= 40:
        raise HTTPException(status_code=400, detail="A workout cannot contain more than 40 exercises.")
    next_order = int(
        conn.execute(
            "SELECT COALESCE(MAX(exercise_order), 0) + 1 AS next_order FROM strength_session_exercises WHERE session_id = ?",
            (session_id,),
        ).fetchone()["next_order"]
    )
    now = _iso(_now())
    with conn:
        exercise_cursor = conn.execute(
            """
            INSERT INTO strength_session_exercises
            (session_id, exercise_order, exercise_name, notes)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, next_order, payload.exercise_name, payload.notes),
        )
        exercise_id = int(exercise_cursor.lastrowid)
        for set_order in range(1, payload.set_count + 1):
            conn.execute(
                """
                INSERT INTO strength_session_sets
                (session_exercise_id, set_order, target_reps, target_weight_kg, rest_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    exercise_id,
                    set_order,
                    payload.target_reps,
                    payload.target_weight_kg,
                    payload.rest_seconds,
                ),
            )
        if payload.switch_to:
            conn.execute(
                """
                UPDATE strength_workout_sessions
                SET current_exercise_order = ?, current_set_order = 1, updated_at = ?
                WHERE id = ?
                """,
                (next_order, now, session_id),
            )
        else:
            conn.execute(
                "UPDATE strength_workout_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
    return get_session(conn, session_id)


def add_warmup_set(
    conn: sqlite3.Connection,
    session_id: int,
    exercise_id: int,
    payload: StrengthWarmupSetAddRequest,
) -> dict:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    exercise = conn.execute(
        """
        SELECT * FROM strength_session_exercises
        WHERE id = ? AND session_id = ?
        """,
        (exercise_id, session_id),
    ).fetchone()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found in this session.")

    warmup_count = int(
        conn.execute(
            """
            SELECT COUNT(*) AS count FROM strength_session_sets
            WHERE session_exercise_id = ? AND set_type = 'warmup'
            """,
            (exercise_id,),
        ).fetchone()["count"]
    )
    if warmup_count >= 10:
        raise HTTPException(status_code=400, detail="An exercise cannot contain more than 10 warm-up sets.")

    reference = conn.execute(
        """
        SELECT target_reps, target_weight_kg
        FROM strength_session_sets
        WHERE session_exercise_id = ? AND set_type = 'working'
        ORDER BY set_order LIMIT 1
        """,
        (exercise_id,),
    ).fetchone()
    target_reps = payload.target_reps or (int(reference["target_reps"]) if reference else 8)
    if payload.target_weight_kg is not None:
        target_weight_kg = payload.target_weight_kg
    elif reference and reference["target_weight_kg"] is not None:
        target_weight_kg = round(float(reference["target_weight_kg"]) * 0.5, 1)
    else:
        target_weight_kg = None

    now = _iso(_now())
    with conn:
        # Move every existing set safely to leave the first position for warm-up work.
        conn.execute(
            "UPDATE strength_session_sets SET set_order = set_order + 1000 WHERE session_exercise_id = ?",
            (exercise_id,),
        )
        conn.execute(
            "UPDATE strength_session_sets SET set_order = set_order - 999 WHERE session_exercise_id = ?",
            (exercise_id,),
        )
        conn.execute(
            """
            INSERT INTO strength_session_sets
            (session_exercise_id, set_order, target_reps, target_weight_kg,
             rest_seconds, set_type)
            VALUES (?, 1, ?, ?, ?, 'warmup')
            """,
            (exercise_id, target_reps, target_weight_kg, payload.rest_seconds),
        )
        if payload.switch_to:
            conn.execute(
                """
                UPDATE strength_workout_sessions
                SET current_exercise_order = ?, current_set_order = 1, updated_at = ?
                WHERE id = ?
                """,
                (exercise["exercise_order"], now, session_id),
            )
        elif int(session["current_exercise_order"]) == int(exercise["exercise_order"]):
            conn.execute(
                """
                UPDATE strength_workout_sessions
                SET current_set_order = current_set_order + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, session_id),
            )
    return get_session(conn, session_id)


def list_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM strength_workout_sessions ORDER BY started_at DESC LIMIT ?",
        (max(1, min(limit, 100)),),
    ).fetchall()
    return [_serialize_session(conn, row) for row in rows]


def _assert_active(session: sqlite3.Row) -> None:
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="This workout is no longer active.")


def complete_set(
    conn: sqlite3.Connection,
    session_id: int,
    set_id: int,
    actual_reps: int,
    actual_weight_kg: Optional[float],
) -> dict:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    set_row = conn.execute(
        """
        SELECT workout_set.*, exercise.session_id, exercise.exercise_order
        FROM strength_session_sets workout_set
        JOIN strength_session_exercises exercise ON exercise.id = workout_set.session_exercise_id
        WHERE workout_set.id = ? AND exercise.session_id = ?
        """,
        (set_id, session_id),
    ).fetchone()
    if not set_row:
        raise HTTPException(status_code=404, detail="Workout set not found in this session.")

    now = _now()
    rest_ends_at = now + timedelta(seconds=int(set_row["rest_seconds"]))
    with conn:
        conn.execute(
            """
            UPDATE strength_session_sets
            SET actual_reps = ?, actual_weight_kg = ?, status = 'completed',
                completed_at = ?, rest_ends_at = ?
            WHERE id = ?
            """,
            (actual_reps, actual_weight_kg, _iso(now), _iso(rest_ends_at), set_id),
        )
        next_set = conn.execute(
            """
            SELECT exercise.exercise_order, workout_set.set_order
            FROM strength_session_sets workout_set
            JOIN strength_session_exercises exercise ON exercise.id = workout_set.session_exercise_id
            WHERE exercise.session_id = ? AND workout_set.status = 'pending'
            ORDER BY CASE WHEN exercise.exercise_order = ? THEN 0 ELSE 1 END,
                     exercise.exercise_order, workout_set.set_order
            LIMIT 1
            """,
            (session_id, set_row["exercise_order"]),
        ).fetchone()
        if next_set:
            conn.execute(
                """
                UPDATE strength_workout_sessions
                SET current_exercise_order = ?, current_set_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_set["exercise_order"], next_set["set_order"], _iso(now), session_id),
            )
    return get_session(conn, session_id)


def set_session_position(
    conn: sqlite3.Connection,
    session_id: int,
    exercise_order: int,
    set_order: Optional[int],
) -> dict:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    exercise = conn.execute(
        """
        SELECT id FROM strength_session_exercises
        WHERE session_id = ? AND exercise_order = ?
        """,
        (session_id, exercise_order),
    ).fetchone()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found in this session.")
    if set_order is None:
        pending = conn.execute(
            """
            SELECT set_order FROM strength_session_sets
            WHERE session_exercise_id = ? AND status = 'pending'
            ORDER BY set_order LIMIT 1
            """,
            (exercise["id"],),
        ).fetchone()
        set_order = int(pending["set_order"]) if pending else 1
    elif not conn.execute(
        "SELECT 1 FROM strength_session_sets WHERE session_exercise_id = ? AND set_order = ?",
        (exercise["id"], set_order),
    ).fetchone():
        raise HTTPException(status_code=404, detail="Set not found for this exercise.")
    with conn:
        conn.execute(
            """
            UPDATE strength_workout_sessions
            SET current_exercise_order = ?, current_set_order = ?, updated_at = ?
            WHERE id = ?
            """,
            (exercise_order, set_order, _iso(_now()), session_id),
        )
    return get_session(conn, session_id)


def finish_session(
    conn: sqlite3.Connection,
    session_id: int,
    linked_activity_id: Optional[str] = None,
) -> dict:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    if linked_activity_id:
        _validate_activity(conn, linked_activity_id)
        _assert_activity_available(conn, linked_activity_id, session_id)
    now = _iso(_now())
    with conn:
        conn.execute(
            """
            UPDATE strength_workout_sessions
            SET status = 'completed', completed_at = ?, linked_activity_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, linked_activity_id, now, session_id),
        )
    return get_session(conn, session_id)


def abandon_session(conn: sqlite3.Connection, session_id: int) -> None:
    session = _session_or_404(conn, session_id)
    _assert_active(session)
    delete_session(conn, session_id)


def delete_session(conn: sqlite3.Connection, session_id: int) -> None:
    _session_or_404(conn, session_id)
    with conn:
        conn.execute(
            """
            DELETE FROM strength_session_sets
            WHERE session_exercise_id IN (
                SELECT id FROM strength_session_exercises WHERE session_id = ?
            )
            """,
            (session_id,),
        )
        conn.execute(
            "DELETE FROM strength_session_exercises WHERE session_id = ?",
            (session_id,),
        )
        conn.execute(
            "DELETE FROM strength_workout_sessions WHERE id = ?",
            (session_id,),
        )


def _validate_activity(conn: sqlite3.Connection, activity_id: str) -> sqlite3.Row:
    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found.")
    if activity["type"] not in {"WeightTraining", "Workout"}:
        raise HTTPException(status_code=400, detail="Only strength or workout activities can be linked.")
    return activity


def _assert_activity_available(
    conn: sqlite3.Connection,
    activity_id: str,
    session_id: int,
) -> None:
    linked = conn.execute(
        """
        SELECT id FROM strength_workout_sessions
        WHERE linked_activity_id = ? AND id != ?
        LIMIT 1
        """,
        (activity_id, session_id),
    ).fetchone()
    if linked:
        raise HTTPException(
            status_code=409,
            detail="This activity is already attached to another strength session.",
        )


def link_activity(
    conn: sqlite3.Connection,
    session_id: int,
    activity_id: Optional[str],
) -> dict:
    _session_or_404(conn, session_id)
    if activity_id:
        _validate_activity(conn, activity_id)
        _assert_activity_available(conn, activity_id, session_id)
    with conn:
        conn.execute(
            "UPDATE strength_workout_sessions SET linked_activity_id = ?, updated_at = ? WHERE id = ?",
            (activity_id, _iso(_now()), session_id),
        )
    return get_session(conn, session_id)


def activity_candidates(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    session = _session_or_404(conn, session_id)
    session_date = str(session["started_at"])[:10]
    rows = conn.execute(
        """
        SELECT id, date, type, name, duration_min, avg_hr, max_hr, calories
        FROM activities
        WHERE type IN ('WeightTraining', 'Workout')
          AND date BETWEEN date(?, '-2 days') AND date(?, '+2 days')
        ORDER BY ABS(julianday(date) - julianday(?)), date DESC
        LIMIT 12
        """,
        (session_date, session_date, session_date),
    ).fetchall()
    return [dict(row) for row in rows]
