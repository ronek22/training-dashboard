from pydantic import BaseModel, Field
from typing import Optional


class WeeklyPlanDay(BaseModel):
    date: str
    label: str
    session_type: Optional[str] = None
    title: str
    details: Optional[str] = None
    target_duration_min: Optional[int] = None
    target_distance_km: Optional[float] = None


class WeeklyPlan(BaseModel):
    week_start: str
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    notes: Optional[str] = None


class WeeklyPlanAdjustment(BaseModel):
    week_start: str
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    effective_from: Optional[str] = None
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    notes: Optional[str] = None
    adaptation_reason: Optional[str] = None
