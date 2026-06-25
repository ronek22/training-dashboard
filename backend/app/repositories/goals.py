import sqlite3
from typing import Optional


def insert_goal(
    conn: sqlite3.Connection,
    title: str,
    period_type: str,
    metric_type: str,
    target_value: float,
    start_date: str,
    end_date: str,
    activity_type: Optional[str],
    is_active: bool,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO goals
        (title, period_type, metric_type, target_value, start_date, end_date, activity_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            period_type,
            metric_type,
            target_value,
            start_date,
            end_date,
            activity_type,
            1 if is_active else 0,
        ),
    )
    return cursor.lastrowid


def list_goal_rows(conn: sqlite3.Connection, active_only: bool = False, limit: int = 24) -> list[sqlite3.Row]:
    query = "SELECT * FROM goals"
    params: list[int] = []
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY is_active DESC, created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()
