from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models.activity_feedback import SessionTagsInput
from ..services.what_worked import build_what_worked, get_session_tags, save_session_tags

router = APIRouter()


@router.get("/activities/{activity_id}/tags")
def session_tags(activity_id: str):
    conn = get_db()
    try:
        return get_session_tags(conn, activity_id)
    finally:
        conn.close()


@router.put("/activities/{activity_id}/tags")
def update_session_tags(activity_id: str, payload: SessionTagsInput):
    conn = get_db()
    try:
        return save_session_tags(conn, activity_id, payload.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/what-worked")
def what_worked():
    conn = get_db()
    try:
        return build_what_worked(conn)
    finally:
        conn.close()
