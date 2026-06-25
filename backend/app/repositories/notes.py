import sqlite3
from typing import Optional


def insert_note(conn: sqlite3.Connection, date: str, category: str, content: str) -> int:
    cursor = conn.execute(
        "INSERT INTO coach_notes (date, category, content) VALUES (?,?,?)",
        (date, category, content),
    )
    return cursor.lastrowid


def list_note_rows(conn: sqlite3.Connection, limit: int = 20, category: Optional[str] = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM coach_notes WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY date DESC, created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()
