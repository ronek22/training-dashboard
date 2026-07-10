import sqlite3
from typing import Optional


def get_activity_analysis_row(conn: sqlite3.Connection, activity_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            activity_id,
            context_signature,
            context_json,
            analysis_json,
            generated_at,
            generator,
            model_name,
            requested_via,
            created_at,
            updated_at
        FROM activity_analyses
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()


def upsert_activity_analysis_row(
    conn: sqlite3.Connection,
    *,
    activity_id: str,
    context_signature: str,
    context_json: str,
    analysis_json: str,
    generated_at: str,
    generator: str,
    model_name: Optional[str],
    requested_via: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO activity_analyses
        (
            activity_id, context_signature, context_json, analysis_json, generated_at,
            generator, model_name, requested_via, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            context_signature=excluded.context_signature,
            context_json=excluded.context_json,
            analysis_json=excluded.analysis_json,
            generated_at=excluded.generated_at,
            generator=excluded.generator,
            model_name=excluded.model_name,
            requested_via=excluded.requested_via,
            updated_at=CURRENT_TIMESTAMP
        """,
        (activity_id, context_signature, context_json, analysis_json, generated_at, generator, model_name, requested_via),
    )


def get_activity_analysis_request_row(conn: sqlite3.Connection, activity_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT activity_id, status, requested_at, updated_at, requested_via, context_signature, last_error
        FROM activity_analysis_requests
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()


def upsert_activity_analysis_request_row(
    conn: sqlite3.Connection,
    *,
    activity_id: str,
    status: str,
    requested_at: str,
    requested_via: str,
    context_signature: str,
    last_error: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO activity_analysis_requests
        (activity_id, status, requested_at, requested_via, context_signature, last_error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            status=excluded.status,
            requested_at=excluded.requested_at,
            requested_via=excluded.requested_via,
            context_signature=excluded.context_signature,
            last_error=excluded.last_error,
            updated_at=CURRENT_TIMESTAMP
        """,
        (activity_id, status, requested_at, requested_via, context_signature, last_error),
    )


def mark_activity_analysis_request_completed(conn: sqlite3.Connection, activity_id: str) -> None:
    conn.execute(
        """
        UPDATE activity_analysis_requests
        SET status = 'completed', last_error = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE activity_id = ?
        """,
        (activity_id,),
    )


def mark_activity_analysis_request_failed(conn: sqlite3.Connection, activity_id: str, error_message: str) -> None:
    conn.execute(
        """
        UPDATE activity_analysis_requests
        SET status = 'failed', last_error = ?, updated_at = CURRENT_TIMESTAMP
        WHERE activity_id = ?
        """,
        (error_message, activity_id),
    )
