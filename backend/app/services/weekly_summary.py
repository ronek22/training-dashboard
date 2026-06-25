import sqlite3

from ..repositories.weekly_summary import list_weekly_summary_rows, upsert_weekly_summary_row


def create_weekly_summary_data(conn: sqlite3.Connection, summary: dict) -> dict:
    upsert_weekly_summary_row(conn, summary)
    conn.commit()
    return {"status": "ok"}


def list_weekly_summary_data(conn: sqlite3.Connection, limit: int = 16) -> list[dict]:
    rows = list_weekly_summary_rows(conn, limit=limit)
    return [dict(row) for row in rows]
