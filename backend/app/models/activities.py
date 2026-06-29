from pydantic import BaseModel
from typing import Optional


class Activity(BaseModel):
    id: str
    date: str
    type: str
    workout_intent: Optional[str] = None
    name: Optional[str] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace: Optional[str] = None
    avg_watts: Optional[float] = None
    elevation_m: Optional[int] = None
    calories: Optional[int] = None
    zone2: Optional[bool] = False
    notes: Optional[str] = None
    linked_planned_session_id: Optional[str] = None


class ActivityPlanLink(BaseModel):
    planned_session_id: Optional[str] = None


class ActivityIntentUpdate(BaseModel):
    workout_intent: Optional[str] = None
