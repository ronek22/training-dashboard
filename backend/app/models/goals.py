from pydantic import BaseModel
from typing import Optional


class Goal(BaseModel):
    title: str
    period_type: str
    metric_type: str
    target_value: float
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    activity_type: Optional[str] = None
    is_active: Optional[bool] = True
