from fastapi import APIRouter
from typing import Optional

from ..db import get_db
from ..models.activities import Activity, ActivityIntentUpdate, ActivityPlanLink
from ..services.activities import (
    activity_stats_data,
    create_activity_data,
    get_calendar_weeks_data,
    link_activity_to_planned_session_data,
    list_activities_data,
    update_activity_workout_intent_data,
)

router = APIRouter()


@router.post("/activities", status_code=201)
def create_activity(activity: Activity):
    conn = get_db()
    try:
        return create_activity_data(conn, activity.model_dump())
    finally:
        conn.close()


@router.get("/activities")
def list_activities(limit: int = 50, type: Optional[str] = None, days: Optional[int] = None):
    conn = get_db()
    try:
        return list_activities_data(conn, limit=limit, activity_type=type, days=days)
    finally:
        conn.close()


@router.get("/activities/stats")
def activity_stats(days: int = 30):
    conn = get_db()
    try:
        return activity_stats_data(conn, days=days)
    finally:
        conn.close()


@router.post("/activities/{activity_id}/link-plan")
def link_activity_to_plan(activity_id: str, payload: ActivityPlanLink):
    conn = get_db()
    try:
        return link_activity_to_planned_session_data(conn, activity_id, payload.planned_session_id)
    finally:
        conn.close()


@router.post("/activities/{activity_id}/intent")
def update_activity_intent(activity_id: str, payload: ActivityIntentUpdate):
    conn = get_db()
    try:
        return update_activity_workout_intent_data(conn, activity_id, payload.workout_intent)
    finally:
        conn.close()


@router.get("/calendar/weeks")
def calendar_weeks(weeks: int = 8):
    conn = get_db()
    try:
        return get_calendar_weeks_data(conn, weeks=weeks)
    finally:
        conn.close()
