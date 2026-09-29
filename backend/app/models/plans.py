from pydantic import BaseModel, Field, model_validator
from typing import Optional

from ..services.cycling_workouts import CYCLING_WORKOUT_IDS

RIDE_SESSION_TYPES = {"ride", "virtualride", "cycling", "bike"}


class WeeklyPlanDay(BaseModel):
    session_id: Optional[str] = None
    date: str
    label: str
    session_type: Optional[str] = None
    workout_intent: Optional[str] = None
    benchmark_tag: Optional[str] = None
    benchmark_label: Optional[str] = None
    template_id: Optional[str] = None
    template_label: Optional[str] = None
    template_summary: Optional[str] = None
    planning_rule_reason: Optional[str] = None
    title: str
    details: Optional[str] = None
    target_duration_min: Optional[int] = None
    target_distance_km: Optional[float] = None
    cycling_workout_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_cycling_workout(self):
        if not self.cycling_workout_id:
            self.cycling_workout_id = None
            return self
        if self.cycling_workout_id not in CYCLING_WORKOUT_IDS:
            raise ValueError(f"Unknown cycling_workout_id: {self.cycling_workout_id}")
        if (self.session_type or "").strip().lower() not in RIDE_SESSION_TYPES:
            raise ValueError("cycling_workout_id is only allowed on ride sessions")
        return self


class WeeklyPlan(BaseModel):
    week_start: str
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    notes: Optional[str] = None


class WeeklyPlanRevision(BaseModel):
    week_start: str
    effective_from: str
    adaptation_reason: Optional[str] = None
    changed_dates: list[str] = Field(default_factory=list)
    preserved_dates: list[str] = Field(default_factory=list)
    previous_plan: WeeklyPlan
    updated_plan: WeeklyPlan


class WeeklyPlanAdjustment(BaseModel):
    week_start: str
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    effective_from: Optional[str] = None
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    notes: Optional[str] = None
    adaptation_reason: Optional[str] = None
