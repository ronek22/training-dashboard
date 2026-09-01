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


def insert_chat_conversation(conn: sqlite3.Connection, title: str) -> int:
    cursor = conn.execute(
        "INSERT INTO coach_chat_conversations (title) VALUES (?)",
        (title,),
    )
    return cursor.lastrowid


def list_chat_conversation_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.*, COUNT(m.id) AS message_count
        FROM coach_chat_conversations c
        LEFT JOIN coach_chat_messages m ON m.conversation_id = c.id
        GROUP BY c.id
        ORDER BY c.updated_at DESC, c.id DESC
        """
    ).fetchall()


def get_chat_conversation_row(conn: sqlite3.Connection, conversation_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM coach_chat_conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()


def delete_chat_conversation_row(conn: sqlite3.Connection, conversation_id: int) -> bool:
    conn.execute("DELETE FROM coach_chat_messages WHERE conversation_id = ?", (conversation_id,))
    cursor = conn.execute("DELETE FROM coach_chat_conversations WHERE id = ?", (conversation_id,))
    return cursor.rowcount > 0


def insert_chat_message(conn: sqlite3.Connection, conversation_id: int, role: str, content: str) -> int:
    cursor = conn.execute(
        "INSERT INTO coach_chat_messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content),
    )
    return cursor.lastrowid


def touch_chat_conversation(conn: sqlite3.Connection, conversation_id: int, title: Optional[str] = None) -> None:
    if title is None:
        conn.execute(
            "UPDATE coach_chat_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )
    else:
        conn.execute(
            "UPDATE coach_chat_conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, conversation_id),
        )


def list_chat_message_rows(conn: sqlite3.Connection, conversation_id: int, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM coach_chat_messages
            WHERE conversation_id = ?
            ORDER BY id DESC LIMIT ?
        ) ORDER BY id ASC
        """,
        (conversation_id, limit),
    ).fetchall()
