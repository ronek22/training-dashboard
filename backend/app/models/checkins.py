from typing import Literal, Optional

from pydantic import BaseModel, Field


class VolumeTrendLabelInput(BaseModel):
    week_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    label: Literal["planned", "life", "illness_injury"]
    note: Optional[str] = Field(default=None, max_length=500)


class DailyCheckinInput(BaseModel):
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    energy: int = Field(ge=1, le=5)
    muscle_soreness: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    sleep_quality: int = Field(ge=1, le=5)
    pain_level: int = Field(default=0, ge=0, le=10)
    note: Optional[str] = Field(default=None, max_length=500)


class SickModeStartInput(BaseModel):
    severity: Literal["above_neck", "below_neck"] = "above_neck"
    note: Optional[str] = Field(default=None, max_length=500)


class SickModeLogInput(BaseModel):
    session_key: str = Field(min_length=1, max_length=40)


class SickSessionCompletionInput(BaseModel):
    session_key: str = Field(min_length=1, max_length=40)
    started_at: str = Field(min_length=10, max_length=40)
    elapsed_seconds: int = Field(ge=0, le=6 * 3600)
    completed_steps: int = Field(default=0, ge=0, le=500)
    extras: list[str] = Field(default_factory=list, max_length=20)


class LifeLoadDayInput(BaseModel):
    tags: list[Literal["travel", "deadline", "family", "poor_sleep", "late_night"]] = Field(default_factory=list, max_length=5)
    note: Optional[str] = Field(default=None, max_length=300)
