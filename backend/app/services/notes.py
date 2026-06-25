import sqlite3
from typing import Optional

from ..repositories.notes import insert_note, list_note_rows


def create_note_data(conn: sqlite3.Connection, date: str, category: str, content: str) -> dict:
    note_id = insert_note(conn, date, category, content)
    conn.commit()
    return {"status": "ok", "id": note_id}


def list_notes_data(conn: sqlite3.Connection, limit: int = 20, category: Optional[str] = None) -> list[dict]:
    rows = list_note_rows(conn, limit=limit, category=category)
    return [dict(row) for row in rows]
