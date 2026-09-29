from typing import Any, Optional

from pydantic import BaseModel


class Goal(BaseModel):
    title: str
    period_type: str
    goal_family: Optional[str] = "accumulation"
    metric_type: Optional[str] = None
    target_value: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    activity_type: Optional[str] = None
    is_active: Optional[bool] = True
    target_config: Optional[dict[str, Any]] = None
    purpose: Optional[str] = None
    commitment: Optional[str] = None
    review_on: Optional[str] = None
    season_end: Optional[str] = None
    outcome_signal: Optional[str] = None


class GoalUpdate(BaseModel):
    """Partial edit: only fields present in the request are changed; null clears optional fields."""

    title: Optional[str] = None
    period_type: Optional[str] = None
    goal_family: Optional[str] = None
    metric_type: Optional[str] = None
    target_value: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    activity_type: Optional[str] = None
    target_config: Optional[dict[str, Any]] = None
    purpose: Optional[str] = None
    commitment: Optional[str] = None
    review_on: Optional[str] = None
    season_end: Optional[str] = None
    outcome_signal: Optional[str] = None


class GoalStatusChange(BaseModel):
    status: str
    reason: Optional[str] = None


class GoalReviewDecision(BaseModel):
    verdict: str
    decision: str
    days: Optional[int] = None
    note: Optional[str] = None


class GoalDraftRequest(BaseModel):
    text: str
