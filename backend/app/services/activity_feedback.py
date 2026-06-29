import sqlite3

from fastapi import HTTPException

from ..repositories.activity_feedback import (
    get_activity_feedback_row,
    list_recent_feedback_rows,
    upsert_activity_feedback_row,
)


def serialize_activity_feedback(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    return {
        "activity_id": row["activity_id"],
        "activity_date": row["activity_date"],
        "activity_type": row["activity_type"],
        "activity_name": row["activity_name"],
        "rpe": row["rpe"],
        "energy": row["energy"],
        "muscle_soreness": row["muscle_soreness"],
        "pain_level": row["pain_level"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_activity_feedback_data(conn: sqlite3.Connection, activity_id: str) -> dict | None:
    activity = conn.execute("SELECT id FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        raise HTTPException(status_code=404, detail=f"Activity {activity_id} not found")
    return serialize_activity_feedback(get_activity_feedback_row(conn, activity_id))


def upsert_activity_feedback_data(conn: sqlite3.Connection, activity_id: str, feedback: dict) -> dict:
    activity = conn.execute("SELECT id FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        raise HTTPException(status_code=404, detail=f"Activity {activity_id} not found")
    upsert_activity_feedback_row(conn, activity_id, feedback)
    conn.commit()
    return get_activity_feedback_data(conn, activity_id) or {}


def attach_feedback_by_activity_id(conn: sqlite3.Connection, items: list[dict], activity_id_key: str = "id") -> list[dict]:
    if not items:
        return items

    activity_ids = [item.get(activity_id_key) for item in items if item.get(activity_id_key)]
    if not activity_ids:
        return items

    placeholders = ",".join("?" for _ in activity_ids)
    rows = conn.execute(
        f"""
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
        WHERE f.activity_id IN ({placeholders})
        """,
        activity_ids,
    ).fetchall()
    by_id = {row["activity_id"]: serialize_activity_feedback(row) for row in rows}

    for item in items:
        item["feedback"] = by_id.get(item.get(activity_id_key))
    return items


def list_recent_feedback_data(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    rows = list_recent_feedback_rows(conn, limit=limit)
    return [serialize_activity_feedback(row) for row in rows]
