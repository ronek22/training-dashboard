from pydantic import BaseModel, Field, model_validator
from datetime import date as Date
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


class WeeklyPlanSwap(BaseModel):
    from_date: str
    to_date: str


class TodayOptionApply(BaseModel):
    reason: str
    key: str
    day: Optional[Date] = None


class TodayOptionUndo(BaseModel):
    undo: dict
    day: Optional[Date] = None


class WinterArcRideMix(BaseModel):
    """Rides per week of each type the block aims for."""
    z2: int = Field(default=2, ge=0, le=7)
    sweet_spot: int = Field(default=0, ge=0, le=3)
    vo2: int = Field(default=0, ge=0, le=3)


class WinterArcBlock(BaseModel):
    start_date: Date
    end_date: Date
    focus: str
    label: Optional[str] = Field(default=None, max_length=60)
    weekly_hours: float = Field(gt=0, le=25)
    ride_mix: WinterArcRideMix = Field(default_factory=WinterArcRideMix)
    lighter_every: int = Field(default=0, ge=0, le=8)  # every Nth week of the block is lighter; 0 = none


class WinterArc(BaseModel):
    blocks: list[WinterArcBlock] = Field(min_length=1, max_length=12)


class WinterArcAdjustment(BaseModel):
    """Confirm the arc's extend-or-accept suggestion; block_start and weeks must match it."""
    action: str
    block_start: Date
    weeks: int = Field(default=0, ge=0, le=4)


class WinterArcAdjustmentUndo(BaseModel):
    id: int
