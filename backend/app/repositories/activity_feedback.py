import sqlite3


def get_activity_feedback_row(conn: sqlite3.Connection, activity_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            f.activity_id,
            f.rpe,
            f.energy,
            f.muscle_soreness,
            f.pain_level,
            f.note,
            f.created_at,
            f.updated_at,
            a.date AS activity_date,
            a.type AS activity_type,
            a.name AS activity_name
        FROM activity_feedback f
        JOIN activities a ON a.id = f.activity_id
        WHERE f.activity_id = ?
        """,
        (activity_id,),
    ).fetchone()


def upsert_activity_feedback_row(conn: sqlite3.Connection, activity_id: str, feedback: dict) -> None:
    conn.execute(
        """
        INSERT INTO activity_feedback
        (activity_id, rpe, energy, muscle_soreness, pain_level, note)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            rpe = excluded.rpe,
            energy = excluded.energy,
            muscle_soreness = excluded.muscle_soreness,
            pain_level = excluded.pain_level,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            activity_id,
            feedback["rpe"],
            feedback["energy"],
            feedback["muscle_soreness"],
            feedback["pain_level"],
            feedback.get("note"),
        ),
    )


def list_recent_feedback_rows(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            f.activity_id,
            f.rpe,
            f.energy,
            f.muscle_soreness,
            f.pain_level,
            f.note,
            f.created_at,
            f.updated_at,
            a.date AS activity_date,
            a.type AS activity_type,
            a.name AS activity_name
        FROM activity_feedback f
        JOIN activities a ON a.id = f.activity_id
        ORDER BY a.date DESC, f.updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
