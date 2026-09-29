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
