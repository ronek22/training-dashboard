from fastapi import APIRouter
from typing import Optional

from ..db import get_db
from ..models.notes import CoachNote
from ..services.notes import create_note_data, list_notes_data

router = APIRouter()


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
