from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models.goals import Goal, GoalDraftRequest
from ..services.goals import create_goal_data, draft_goal_data, list_goals_data

router = APIRouter()


@router.post("/goals", status_code=201)
def create_goal(goal: Goal):
    conn = get_db()
    try:
        try:
            return create_goal_data(conn, **goal.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/goals/draft")
def draft_goal(request: GoalDraftRequest):
    return draft_goal_data(request.text)


@router.get("/goals")
def list_goals(active_only: bool = False, limit: int = 24):
    conn = get_db()
    try:
        return list_goals_data(conn, active_only=active_only, limit=limit)
    finally:
        conn.close()
