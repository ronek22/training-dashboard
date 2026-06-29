from fastapi import APIRouter

from ..db import get_db
from ..models.activity_feedback import ActivityFeedbackInput
from ..services.activity_feedback import get_activity_feedback_data, upsert_activity_feedback_data

router = APIRouter()


@router.get("/activities/{activity_id}/feedback")
def get_activity_feedback(activity_id: str):
    conn = get_db()
    try:
        return get_activity_feedback_data(conn, activity_id)
    finally:
        conn.close()


@router.post("/activities/{activity_id}/feedback", status_code=201)
def upsert_activity_feedback(activity_id: str, feedback: ActivityFeedbackInput):
    conn = get_db()
    try:
        return upsert_activity_feedback_data(conn, activity_id, feedback.model_dump())
    finally:
        conn.close()

