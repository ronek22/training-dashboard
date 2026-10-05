from fastapi import APIRouter

from ..db import get_db
from ..models.activity_feedback import ActivityFeedbackInput
from ..services.activity_feedback import get_activity_feedback_data, upsert_activity_feedback_data
from ..services.what_worked import save_session_tags

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
        result = upsert_activity_feedback_data(conn, activity_id, feedback.model_dump())
        tags = {key: getattr(feedback, key) for key in ("verdict", "pre_fuel") if key in feedback.model_fields_set}
        if tags:
            result.update({key: value for key, value in save_session_tags(conn, activity_id, tags).items() if key in tags})
        return result
    finally:
        conn.close()

