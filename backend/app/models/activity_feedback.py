from typing import Literal, Optional

from pydantic import BaseModel, Field


class ActivityFeedbackInput(BaseModel):
    rpe: int = Field(ge=1, le=10)
    energy: int = Field(ge=1, le=5)
    muscle_soreness: int = Field(ge=1, le=5)
    pain_level: int = Field(ge=0, le=10)
    # How fuelling went on a long ride; None when not asked or skipped.
    fuelling: Optional[Literal["bonked", "fine", "overate"]] = None
    note: Optional[str] = None
