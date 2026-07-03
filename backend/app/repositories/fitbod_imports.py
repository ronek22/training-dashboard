import sqlite3
from typing import Optional


def get_fitbod_import_batch_by_hash(conn: sqlite3.Connection, file_hash: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_import_batches
        WHERE file_hash = ?
        """,
        (file_hash,),
    ).fetchone()


def get_latest_fitbod_import_batch(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_import_batches
        ORDER BY imported_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def create_fitbod_import_batch(
    conn: sqlite3.Connection,
    *,
    file_name: Optional[str],
    file_hash: str,
    parser_version: str,
    grouping_version: str,
    imported_at: str,
    raw_row_count: int,
    strength_row_count: int,
    ignored_row_count: int,
    rejected_row_count: int,
    session_count: int,
    matched_count: int,
    ambiguous_count: int,
    unmatched_count: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO fitbod_import_batches
        (
            file_name, file_hash, parser_version, grouping_version, imported_at,
            raw_row_count, strength_row_count, ignored_row_count, rejected_row_count,
            session_count, matched_count, ambiguous_count, unmatched_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_name,
            file_hash,
            parser_version,
            grouping_version,
            imported_at,
            raw_row_count,
            strength_row_count,
            ignored_row_count,
            rejected_row_count,
            session_count,
            matched_count,
            ambiguous_count,
            unmatched_count,
        ),
    )
    return int(cursor.lastrowid)


def create_fitbod_import_row(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    row_index: int,
    row_kind: str,
    workout_timestamp: Optional[str],
    exercise_name: Optional[str],
    ignore_reason: Optional[str],
    raw_json: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fitbod_import_rows
        (batch_id, row_index, row_kind, workout_timestamp, exercise_name, ignore_reason, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (batch_id, row_index, row_kind, workout_timestamp, exercise_name, ignore_reason, raw_json),
    )


def create_fitbod_workout_session(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    session_key: str,
    workout_timestamp: str,
    workout_date: str,
    title: Optional[str],
    exercise_count: int,
    set_count: int,
    rep_count: int,
    total_volume_kg: Optional[float],
    total_duration_seconds: Optional[float],
    total_distance_m: Optional[float],
    calories: Optional[int],
    match_status: str,
    matched_activity_id: Optional[str],
    match_confidence: Optional[float],
    match_provenance: Optional[str],
    match_reason: Optional[str],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO fitbod_workout_sessions
        (
            batch_id, session_key, workout_timestamp, workout_date, title,
            exercise_count, set_count, rep_count, total_volume_kg, total_duration_seconds,
            total_distance_m, calories, match_status, matched_activity_id,
            match_confidence, match_provenance, match_reason, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            batch_id,
            session_key,
            workout_timestamp,
            workout_date,
            title,
            exercise_count,
            set_count,
            rep_count,
            total_volume_kg,
            total_duration_seconds,
            total_distance_m,
            calories,
            match_status,
            matched_activity_id,
            match_confidence,
            match_provenance,
            match_reason,
        ),
    )
    return int(cursor.lastrowid)


def create_fitbod_workout_exercise(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    exercise_order: int,
    exercise_name: str,
    set_count: int,
    rep_count: int,
    total_volume_kg: Optional[float],
    work_set_count: int,
    warmup_set_count: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO fitbod_workout_exercises
        (
            session_id, exercise_order, exercise_name, set_count, rep_count,
            total_volume_kg, work_set_count, warmup_set_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            exercise_order,
            exercise_name,
            set_count,
            rep_count,
            total_volume_kg,
            work_set_count,
            warmup_set_count,
        ),
    )
    return int(cursor.lastrowid)


def create_fitbod_workout_set(
    conn: sqlite3.Connection,
    *,
    exercise_id: int,
    set_order: int,
    reps: Optional[int],
    weight_kg: Optional[float],
    duration_seconds: Optional[float],
    distance_m: Optional[float],
    incline: Optional[float],
    resistance: Optional[float],
    is_warmup: bool,
    note: Optional[str],
    multiplier: Optional[float],
) -> None:
    conn.execute(
        """
        INSERT INTO fitbod_workout_sets
        (
            exercise_id, set_order, reps, weight_kg, duration_seconds, distance_m,
            incline, resistance, is_warmup, note, multiplier
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exercise_id,
            set_order,
            reps,
            weight_kg,
            duration_seconds,
            distance_m,
            incline,
            resistance,
            1 if is_warmup else 0,
            note,
            multiplier,
        ),
    )


def list_fitbod_workout_sessions_by_batch(conn: sqlite3.Connection, batch_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.*, a.name AS matched_activity_name, a.duration_min AS matched_activity_duration_min
        FROM fitbod_workout_sessions s
        LEFT JOIN activities a ON a.id = s.matched_activity_id
        WHERE s.batch_id = ?
        ORDER BY s.workout_timestamp DESC, s.id DESC
        """,
        (batch_id,),
    ).fetchall()


def list_fitbod_workout_exercises_by_session(conn: sqlite3.Connection, session_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_workout_exercises
        WHERE session_id = ?
        ORDER BY exercise_order ASC, id ASC
        """,
        (session_id,),
    ).fetchall()


def list_fitbod_workout_sets_by_exercise(conn: sqlite3.Connection, exercise_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_workout_sets
        WHERE exercise_id = ?
        ORDER BY set_order ASC, id ASC
        """,
        (exercise_id,),
    ).fetchall()


def count_fitbod_import_rows_by_kind(conn: sqlite3.Connection, batch_id: int, row_kind: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM fitbod_import_rows
        WHERE batch_id = ? AND row_kind = ?
        """,
        (batch_id, row_kind),
    ).fetchone()
    return int(row["count"]) if row else 0


def get_fitbod_workout_session(conn: sqlite3.Connection, session_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_workout_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()


def get_fitbod_workout_session_by_timestamp(conn: sqlite3.Connection, workout_timestamp: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_workout_sessions
        WHERE workout_timestamp = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (workout_timestamp,),
    ).fetchone()


def get_fitbod_session_by_activity_id(conn: sqlite3.Connection, activity_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_workout_sessions
        WHERE matched_activity_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (activity_id,),
    ).fetchone()


def clear_fitbod_session_match_for_activity(conn: sqlite3.Connection, activity_id: str) -> None:
    conn.execute(
        """
        UPDATE fitbod_workout_sessions
        SET matched_activity_id = NULL,
            match_status = 'unmatched',
            match_confidence = NULL,
            match_provenance = NULL,
            match_reason = 'Match cleared in favor of another session.',
            updated_at = CURRENT_TIMESTAMP
        WHERE matched_activity_id = ?
        """,
        (activity_id,),
    )


def update_fitbod_session_match(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    matched_activity_id: Optional[str],
    match_status: str,
    match_confidence: Optional[float],
    match_provenance: Optional[str],
    match_reason: Optional[str],
) -> None:
    conn.execute(
        """
        UPDATE fitbod_workout_sessions
        SET matched_activity_id = ?,
            match_status = ?,
            match_confidence = ?,
            match_provenance = ?,
            match_reason = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            matched_activity_id,
            match_status,
            match_confidence,
            match_provenance,
            match_reason,
            session_id,
        ),
    )


def update_fitbod_workout_session(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    batch_id: int,
    session_key: str,
    workout_timestamp: str,
    workout_date: str,
    title: Optional[str],
    exercise_count: int,
    set_count: int,
    rep_count: int,
    total_volume_kg: Optional[float],
    total_duration_seconds: Optional[float],
    total_distance_m: Optional[float],
    calories: Optional[int],
    match_status: str,
    matched_activity_id: Optional[str],
    match_confidence: Optional[float],
    match_provenance: Optional[str],
    match_reason: Optional[str],
) -> None:
    conn.execute(
        """
        UPDATE fitbod_workout_sessions
        SET batch_id = ?,
            session_key = ?,
            workout_timestamp = ?,
            workout_date = ?,
            title = ?,
            exercise_count = ?,
            set_count = ?,
            rep_count = ?,
            total_volume_kg = ?,
            total_duration_seconds = ?,
            total_distance_m = ?,
            calories = ?,
            match_status = ?,
            matched_activity_id = ?,
            match_confidence = ?,
            match_provenance = ?,
            match_reason = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            batch_id,
            session_key,
            workout_timestamp,
            workout_date,
            title,
            exercise_count,
            set_count,
            rep_count,
            total_volume_kg,
            total_duration_seconds,
            total_distance_m,
            calories,
            match_status,
            matched_activity_id,
            match_confidence,
            match_provenance,
            match_reason,
            session_id,
        ),
    )


def mark_fitbod_import_rows_ignored_for_session(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    workout_timestamp: str,
    ignore_reason: str,
) -> None:
    conn.execute(
        """
        UPDATE fitbod_import_rows
        SET row_kind = 'ignored',
            ignore_reason = ?
        WHERE batch_id = ? AND workout_timestamp = ? AND row_kind = 'strength'
        """,
        (ignore_reason, batch_id, workout_timestamp),
    )


def delete_fitbod_workout_session_tree(conn: sqlite3.Connection, session_id: int) -> None:
    exercise_rows = conn.execute(
        """
        SELECT id
        FROM fitbod_workout_exercises
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchall()
    exercise_ids = [row["id"] for row in exercise_rows]
    if exercise_ids:
        placeholders = ",".join("?" for _ in exercise_ids)
        conn.execute(f"DELETE FROM fitbod_workout_sets WHERE exercise_id IN ({placeholders})", exercise_ids)
        conn.execute(f"DELETE FROM fitbod_workout_exercises WHERE id IN ({placeholders})", exercise_ids)
    conn.execute(
        """
        DELETE FROM fitbod_workout_sessions
        WHERE id = ?
        """,
        (session_id,),
    )


def refresh_fitbod_import_batch_counts(conn: sqlite3.Connection, batch_id: int) -> None:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS raw_row_count,
            SUM(CASE WHEN row_kind = 'strength' THEN 1 ELSE 0 END) AS strength_row_count,
            SUM(CASE WHEN row_kind = 'ignored' THEN 1 ELSE 0 END) AS ignored_row_count,
            SUM(CASE WHEN row_kind = 'rejected' THEN 1 ELSE 0 END) AS rejected_row_count
        FROM fitbod_import_rows
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    session_row = conn.execute(
        """
        SELECT
            COUNT(*) AS session_count,
            SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS matched_count,
            SUM(CASE WHEN match_status = 'ambiguous' THEN 1 ELSE 0 END) AS ambiguous_count,
            SUM(CASE WHEN match_status = 'unmatched' THEN 1 ELSE 0 END) AS unmatched_count
        FROM fitbod_workout_sessions
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE fitbod_import_batches
        SET raw_row_count = ?,
            strength_row_count = ?,
            ignored_row_count = ?,
            rejected_row_count = ?,
            session_count = ?,
            matched_count = ?,
            ambiguous_count = ?,
            unmatched_count = ?
        WHERE id = ?
        """,
        (
            int(row["raw_row_count"] or 0),
            int(row["strength_row_count"] or 0),
            int(row["ignored_row_count"] or 0),
            int(row["rejected_row_count"] or 0),
            int(session_row["session_count"] or 0),
            int(session_row["matched_count"] or 0),
            int(session_row["ambiguous_count"] or 0),
            int(session_row["unmatched_count"] or 0),
            batch_id,
        ),
    )


def get_fitbod_session_decision(conn: sqlite3.Connection, workout_timestamp: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM fitbod_session_decisions
        WHERE workout_timestamp = ?
        """,
        (workout_timestamp,),
    ).fetchone()


def upsert_fitbod_session_decision(
    conn: sqlite3.Connection,
    *,
    workout_timestamp: str,
    decision_type: str,
    activity_id: Optional[str],
    reason: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO fitbod_session_decisions
        (workout_timestamp, decision_type, activity_id, reason, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(workout_timestamp) DO UPDATE SET
            decision_type = excluded.decision_type,
            activity_id = excluded.activity_id,
            reason = excluded.reason,
            updated_at = CURRENT_TIMESTAMP
        """,
        (workout_timestamp, decision_type, activity_id, reason),
    )


def delete_fitbod_session_decision(conn: sqlite3.Connection, workout_timestamp: str) -> None:
    conn.execute(
        """
        DELETE FROM fitbod_session_decisions
        WHERE workout_timestamp = ?
        """,
        (workout_timestamp,),
    )
