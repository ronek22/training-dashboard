import sqlite3
from typing import Optional


def insert_metric(
    conn: sqlite3.Connection,
    date: str,
    metric: str,
    value: float,
    unit: Optional[str],
    notes: Optional[str],
) -> int:
    cursor = conn.execute(
        "INSERT INTO metrics (date, metric, value, unit, notes) VALUES (?,?,?,?,?)",
        (date, metric, value, unit, notes),
    )
    return cursor.lastrowid


def list_metric_rows(conn: sqlite3.Connection, metric_name: str, limit: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM metrics WHERE metric = ? ORDER BY date DESC LIMIT ?",
        (metric_name, limit),
    ).fetchall()
