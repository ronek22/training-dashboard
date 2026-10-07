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


def insert_chat_conversation(
    conn: sqlite3.Connection,
    title: str,
    context_kind: Optional[str] = None,
    context_id: Optional[str] = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO coach_chat_conversations (title, context_kind, context_id) VALUES (?, ?, ?)",
        (title, context_kind, context_id),
    )
    return cursor.lastrowid


def list_chat_conversation_rows(
    conn: sqlite3.Connection,
    context_kind: Optional[str] = None,
    context_id: Optional[str] = None,
) -> list[sqlite3.Row]:
    where, params = "", []
    if context_kind:
        where = "WHERE c.context_kind = ? AND c.context_id = ?"
        params = [context_kind, context_id]
    return conn.execute(
        f"""
        SELECT c.*, COUNT(m.id) AS message_count,
            COALESCE(SUM(CASE WHEN m.role = 'assistant' AND m.id > COALESCE(c.last_read_message_id, 0) THEN 1 ELSE 0 END), 0) AS unread_count
        FROM coach_chat_conversations c
        LEFT JOIN coach_chat_messages m ON m.conversation_id = c.id
        {where}
        GROUP BY c.id
        ORDER BY c.updated_at DESC, c.id DESC
        """,
        params,
    ).fetchall()


def mark_chat_conversation_read(conn: sqlite3.Connection, conversation_id: int) -> bool:
    cursor = conn.execute(
        "UPDATE coach_chat_conversations SET last_read_message_id = "
        "(SELECT MAX(id) FROM coach_chat_messages WHERE conversation_id = ?) WHERE id = ?",
        (conversation_id, conversation_id),
    )
    return cursor.rowcount > 0


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
