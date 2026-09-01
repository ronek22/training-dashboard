import sqlite3
from typing import Optional

from ..repositories.notes import (
    delete_chat_conversation_row,
    get_chat_conversation_row,
    insert_chat_conversation,
    insert_chat_message,
    insert_note,
    list_chat_conversation_rows,
    list_chat_message_rows,
    list_note_rows,
    touch_chat_conversation,
)


def create_note_data(conn: sqlite3.Connection, date: str, category: str, content: str) -> dict:
    note_id = insert_note(conn, date, category, content)
    conn.commit()
    return {"status": "ok", "id": note_id}


def list_notes_data(conn: sqlite3.Connection, limit: int = 20, category: Optional[str] = None) -> list[dict]:
    rows = list_note_rows(conn, limit=limit, category=category)
    return [dict(row) for row in rows]


def create_chat_conversation_data(conn: sqlite3.Connection, title: str = "New conversation") -> dict:
    normalized_title = str(title or "").strip() or "New conversation"
    if len(normalized_title) > 80:
        raise ValueError("title is too long")
    conversation_id = insert_chat_conversation(conn, normalized_title)
    conn.commit()
    return dict(get_chat_conversation_row(conn, conversation_id))


def list_chat_conversations_data(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in list_chat_conversation_rows(conn)]


def delete_chat_conversation_data(conn: sqlite3.Connection, conversation_id: int) -> dict:
    if not delete_chat_conversation_row(conn, conversation_id):
        raise ValueError("conversation not found")
    conn.commit()
    return {"status": "ok", "id": conversation_id}


def create_chat_message_data(
    conn: sqlite3.Connection,
    conversation_id: int,
    role: str,
    content: str,
) -> dict:
    normalized_role = str(role or "").strip().lower()
    normalized_content = str(content or "").strip()
    if normalized_role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")
    if not normalized_content:
        raise ValueError("content must not be empty")
    if len(normalized_content) > 12000:
        raise ValueError("content is too long")
    conversation = get_chat_conversation_row(conn, conversation_id)
    if not conversation:
        raise ValueError("conversation not found")
    message_id = insert_chat_message(conn, conversation_id, normalized_role, normalized_content)
    title = None
    if normalized_role == "user" and conversation["title"] == "New conversation":
        title = normalized_content.replace("\n", " ")[:56]
        if len(normalized_content.replace("\n", " ")) > 56:
            title = f"{title.rstrip()}…"
    touch_chat_conversation(conn, conversation_id, title=title)
    conn.commit()
    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "role": normalized_role,
        "content": normalized_content,
    }


def list_chat_messages_data(conn: sqlite3.Connection, conversation_id: int, limit: int = 100) -> list[dict]:
    if not get_chat_conversation_row(conn, conversation_id):
        raise ValueError("conversation not found")
    safe_limit = max(1, min(int(limit), 200))
    return [dict(row) for row in list_chat_message_rows(conn, conversation_id, limit=safe_limit)]
