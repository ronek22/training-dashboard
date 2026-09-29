from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..models.goals import Goal, GoalDraftRequest, GoalReviewDecision, GoalStatusChange, GoalUpdate
from ..services.goal_review import build_goal_review, record_review_decision
from ..services.goal_suggestions import build_goal_suggestions, record_suggestion_decision
from ..services.goal_outcomes import attach_goal_outcomes, build_cost_signals, build_goal_outcomes, build_outcome_signals
from ..services.goal_history import DEFAULT_HISTORY_PERIODS, attach_goal_histories, build_goal_period_history
from ..services.goals import (
    create_goal_data,
    draft_goal_data,
    get_goal_data,
    list_goals_data,
    set_goal_status_data,
    update_goal_data,
)

router = APIRouter()


class GoalSuggestionDecision(BaseModel):
    decision: str
    until: Optional[str] = None


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
def list_goals(
    active_only: bool = False,
    limit: int = 24,
    status: Optional[str] = None,
    include_history: bool = False,
    include_outcomes: bool = False,
):
    conn = get_db()
    try:
        try:
            goals = list_goals_data(conn, active_only=active_only, limit=limit, lifecycle_status=status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if include_history:
            goals = attach_goal_histories(conn, goals)
        if include_outcomes:
            goals = attach_goal_outcomes(conn, goals)
        return goals
    finally:
        conn.close()


@router.get("/goals/review")
def goal_review():
    conn = get_db()
    try:
        return build_goal_review(conn)
    finally:
        conn.close()


@router.post("/goals/{goal_id}/review-decision", status_code=201)
def goal_review_decision(goal_id: int, decision: GoalReviewDecision):
    conn = get_db()
    try:
        try:
            return record_review_decision(conn, goal_id, **decision.model_dump())
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/goals/suggestions")
def goal_suggestions():
    conn = get_db()
    try:
        return build_goal_suggestions(conn)
    finally:
        conn.close()


@router.post("/goals/suggestions/{key}/decision", status_code=201)
def goal_suggestion_decision(key: str, decision: GoalSuggestionDecision):
    conn = get_db()
    try:
        try:
            return record_suggestion_decision(
                conn,
                key,
                decision=decision.decision,
                until=decision.until,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/goals/signals")
def goal_signals():
    """Every outcome and cost signal, independent of any goal."""
    conn = get_db()
    try:
        return {
            "outcomes": list(build_outcome_signals(conn).values()),
            "costs": list(build_cost_signals(conn).values()),
        }
    finally:
        conn.close()


@router.get("/goals/{goal_id}/outcomes")
def goal_outcomes(goal_id: int):
    conn = get_db()
    try:
        try:
            goal = get_goal_data(conn, goal_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "goal_id": goal_id,
            **build_goal_outcomes(conn, goal),
            "costs": list(build_cost_signals(conn).values()),
        }
    finally:
        conn.close()


@router.get("/goals/{goal_id}/history")
def goal_history(goal_id: int, periods: int = DEFAULT_HISTORY_PERIODS):
    conn = get_db()
    try:
        try:
            goal = get_goal_data(conn, goal_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return build_goal_period_history(conn, goal, periods=periods)
    finally:
        conn.close()


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, changes: GoalUpdate):
    conn = get_db()
    try:
        try:
            return update_goal_data(conn, goal_id, changes.model_dump(exclude_unset=True))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/goals/{goal_id}/status")
def change_goal_status(goal_id: int, change: GoalStatusChange):
    conn = get_db()
    try:
        try:
            return set_goal_status_data(conn, goal_id, change.status, change.reason)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
