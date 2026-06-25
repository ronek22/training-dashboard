from pydantic import BaseModel
from typing import Optional


class WeeklySummary(BaseModel):
    week_start: str
    run_km: Optional[float] = 0
    ride_km: Optional[float] = 0
    strength_sessions: Optional[int] = 0
    total_elevation: Optional[int] = 0
    avg_hr: Optional[float] = None
    notes: Optional[str] = None
