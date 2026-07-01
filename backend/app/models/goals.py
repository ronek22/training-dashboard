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


class GoalDraftRequest(BaseModel):
    text: str
