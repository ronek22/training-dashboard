from typing import Optional

from pydantic import BaseModel, Field


class ActivityFeedbackInput(BaseModel):
    rpe: int = Field(ge=1, le=10)
    energy: int = Field(ge=1, le=5)
    muscle_soreness: int = Field(ge=1, le=5)
    pain_level: int = Field(ge=0, le=10)
    note: Optional[str] = None
