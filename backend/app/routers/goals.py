from fastapi import APIRouter

from ..db import get_db
from ..models.goals import Goal
from ..services.goals import create_goal_data, list_goals_data

router = APIRouter()


@router.post("/goals", status_code=201)
def create_goal(goal: Goal):
    conn = get_db()
    try:
        return create_goal_data(conn, **goal.model_dump())
    finally:
        conn.close()


@router.get("/goals")
def list_goals(active_only: bool = False, limit: int = 24):
    conn = get_db()
    try:
        return list_goals_data(conn, active_only=active_only, limit=limit)
    finally:
        conn.close()
