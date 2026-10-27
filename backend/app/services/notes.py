import sqlite3
from datetime import date
from typing import Optional

from ..repositories.notes import (
    delete_chat_conversation_row,
    get_chat_conversation_row,
    get_preference_row,
    insert_chat_conversation,
    insert_chat_message,
    insert_note,
    insert_preference,
    list_chat_conversation_rows,
    list_chat_message_rows,
    list_note_rows,
    list_preference_rows,
    mark_chat_conversation_read,
    touch_chat_conversation,
    update_preference_row,
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


def list_chat_conversations_data(
    conn: sqlite3.Connection,
    context_kind: Optional[str] = None,
    context_id: Optional[str] = None,
) -> list[dict]:
    if context_kind:
        context_kind, context_id = _validate_context(context_kind, context_id)
    return [dict(row) for row in list_chat_conversation_rows(conn, context_kind, context_id)]


def mark_chat_conversation_read_data(conn: sqlite3.Connection, conversation_id: int) -> dict:
    if not mark_chat_conversation_read(conn, conversation_id):
        raise ValueError("conversation not found")
    conn.commit()
    return {"status": "ok", "id": conversation_id}


CHAT_CONTEXT_KINDS = {"activity", "day", "week"}


def _validate_context(context_kind: str, context_id: str) -> tuple[str, str]:
    kind = str(context_kind or "").strip().lower()
    identifier = str(context_id or "").strip()
    if kind not in CHAT_CONTEXT_KINDS:
        raise ValueError(f"context_kind must be one of: {', '.join(sorted(CHAT_CONTEXT_KINDS))}")
    if not identifier or len(identifier) > 64:
        raise ValueError("context_id is invalid")
    if kind in {"day", "week"}:
        try:
            parsed = date.fromisoformat(identifier)
        except ValueError as exc:
            raise ValueError(f"context_id must be an ISO date for a {kind}") from exc
        if kind == "week" and parsed.weekday() != 0:
            raise ValueError("context_id for a week must be its Monday")
        identifier = parsed.isoformat()
    return kind, identifier


def open_context_conversation_data(
    conn: sqlite3.Connection,
    context_kind: str,
    context_id: str,
    title: str,
    opener: Optional[str] = None,
) -> dict:
    """The latest chat about this context, or a new one that starts with the coach's opener."""
    kind, identifier = _validate_context(context_kind, context_id)
    existing = list_chat_conversation_rows(conn, kind, identifier)
    if existing:
        return {**dict(existing[0]), "created": False}
    normalized_title = " ".join(str(title or "").split())[:80] or "New conversation"
    conversation_id = insert_chat_conversation(conn, normalized_title, kind, identifier)
    normalized_opener = str(opener or "").strip()[:6000]
    if normalized_opener:
        insert_chat_message(conn, conversation_id, "assistant", normalized_opener)
    conn.commit()
    row = list_chat_conversation_rows(conn, kind, identifier)[0]
    return {**dict(row), "created": True}


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


PREFERENCE_MAX_LENGTH = 300
PREFERENCE_STATUSES = {"active", "retired"}


def _preference_text(content: str) -> str:
    text = " ".join(str(content or "").split())
    if not text:
        raise ValueError("the preference must not be empty")
    if len(text) > PREFERENCE_MAX_LENGTH:
        raise ValueError(f"keep the preference under {PREFERENCE_MAX_LENGTH} characters")
    return text


def list_preferences_data(conn: sqlite3.Connection, include_retired: bool = False) -> list[dict]:
    return [dict(row) for row in list_preference_rows(conn, include_retired)]


def create_preference_data(
    conn: sqlite3.Connection,
    content: str,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
    today: Optional[date] = None,
) -> dict:
    """A standing preference agreed in the coach chat; planning and later chats follow it until it is retired."""
    text = _preference_text(content)
    if conversation_id is not None and not get_chat_conversation_row(conn, conversation_id):
        raise ValueError("conversation not found")
    if message_id is not None:
        message = conn.execute("SELECT conversation_id FROM coach_chat_messages WHERE id = ?", (message_id,)).fetchone()
        if not message or (conversation_id is not None and message["conversation_id"] != conversation_id):
            raise ValueError("message not found in that conversation")
        conversation_id = message["conversation_id"]
    preference_id = insert_preference(conn, (today or date.today()).isoformat(), text, conversation_id, message_id)
    conn.commit()
    return next(item for item in list_preferences_data(conn, include_retired=True) if item["id"] == preference_id)


def update_preference_data(
    conn: sqlite3.Connection,
    preference_id: int,
    content: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    row = get_preference_row(conn, preference_id)
    if not row:
        raise LookupError("preference not found")
    text = row["content"] if content is None else _preference_text(content)
    new_status = row["status"] if status is None else str(status).strip().lower()
    if new_status not in PREFERENCE_STATUSES:
        raise ValueError("status must be active or retired")
    update_preference_row(conn, preference_id, text, new_status)
    conn.commit()
    return next(item for item in list_preferences_data(conn, include_retired=True) if item["id"] == preference_id)


def active_preferences_context(conn: sqlite3.Connection) -> list[dict]:
    """What the planner and coach chat read: the rule and when it was agreed."""
    return [{"id": row["id"], "preference": row["content"], "since": row["date"]} for row in list_preference_rows(conn)]
