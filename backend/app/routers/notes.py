from fastapi import APIRouter, HTTPException
from datetime import date
from typing import Optional

from ..db import get_db
from ..models.notes import CoachChatContextOpen, CoachChatConversationCreate, CoachChatMessageCreate, CoachNote
from ..services.notes import (
    create_chat_conversation_data,
    create_chat_message_data,
    create_note_data,
    delete_chat_conversation_data,
    list_chat_conversations_data,
    list_chat_messages_data,
    list_notes_data,
    mark_chat_conversation_read_data,
    open_context_conversation_data,
)
from ..services.coach_moments import build_coach_moments

router = APIRouter()


@router.get("/notes/chat/conversations")
def list_chat_conversations(context_kind: Optional[str] = None, context_id: Optional[str] = None):
    conn = get_db()
    try:
        try:
            return list_chat_conversations_data(conn, context_kind, context_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/notes/chat/conversations/open")
def open_context_conversation(request: CoachChatContextOpen):
    conn = get_db()
    try:
        try:
            return open_context_conversation_data(
                conn, request.context_kind, request.context_id, request.title, request.opener
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/notes/chat/conversations", status_code=201)
def create_chat_conversation(conversation: CoachChatConversationCreate):
    conn = get_db()
    try:
        try:
            return create_chat_conversation_data(conn, conversation.title)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.delete("/notes/chat/conversations/{conversation_id}")
def delete_chat_conversation(conversation_id: int):
    conn = get_db()
    try:
        try:
            return delete_chat_conversation_data(conn, conversation_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/notes/chat/conversations/{conversation_id}/read")
def mark_chat_conversation_read(conversation_id: int):
    conn = get_db()
    try:
        try:
            return mark_chat_conversation_read_data(conn, conversation_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/notes/chat/moments")
def list_coach_moments(day: Optional[date] = None):
    """``day`` is the browser's local date: the container clock is UTC."""
    conn = get_db()
    try:
        return build_coach_moments(conn, day)
    finally:
        conn.close()


@router.get("/notes/chat")
def list_chat_messages(conversation_id: int, limit: int = 100):
    conn = get_db()
    try:
        try:
            return list_chat_messages_data(conn, conversation_id=conversation_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/notes/chat", status_code=201)
def create_chat_message(message: CoachChatMessageCreate):
    conn = get_db()
    try:
        try:
            return create_chat_message_data(
                conn,
                message.conversation_id,
                message.role,
                message.content,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/notes", status_code=201)
def create_note(note: CoachNote):
    conn = get_db()
    try:
        return create_note_data(conn, note.date, note.category, note.content)
    finally:
        conn.close()


@router.get("/notes")
def list_notes(limit: int = 20, category: Optional[str] = None):
    conn = get_db()
    try:
        return list_notes_data(conn, limit=limit, category=category)
    finally:
        conn.close()
