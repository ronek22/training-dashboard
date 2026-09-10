from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class RecoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Intake(RecoveryModel):
    location: str = Field(default="", max_length=100)
    side: Literal["unknown", "left", "right", "both", "central"] = "unknown"
    onset_date: date | None = None
    onset: str = Field(default="", max_length=1000)
    severity: int | None = Field(default=None, ge=0, le=10, strict=True)
    trend: Literal["unknown", "improving", "unchanged", "worsening"] = "unknown"
    function: Literal["unknown", "normal", "limited", "unable"] = "unknown"
    emergency_signs: StrictBool | None = None
    urgent_signs: StrictBool | None = None
    injury_or_surgery: StrictBool | None = None
    persistent_symptoms: StrictBool | None = None
    general_soreness: StrictBool | None = None
    clinician_guidance: str = Field(default="", max_length=2000)


class IssueCreate(RecoveryModel):
    title: str = Field(min_length=1, max_length=100)


class IntakeUpdate(RecoveryModel):
    reassess_assessment: StrictBool = False
    revision: int = Field(ge=1)
    intake: Intake


class IssueStatus(RecoveryModel):
    status: Literal["active", "archived"]


class IssueSharing(RecoveryModel):
    share_coaching: StrictBool


class MessageCreate(RecoveryModel):
    content: str = Field(min_length=1, max_length=4000)
    ai_consent: StrictBool


class AIRequestCreate(RecoveryModel):
    kind: Literal["chat", "routine"] = "chat"
    ai_consent: StrictBool


class ExerciseSelection(RecoveryModel):
    exercise_id: str = Field(min_length=1, max_length=80)
    repetitions: int = Field(ge=1, le=30, strict=True)
    sets: int = Field(ge=1, le=3, strict=True)


class AIResult(RecoveryModel):
    summary: str = Field(min_length=1, max_length=1400)
    question_ids: list[str] = Field(default_factory=list, max_length=4)
    concern: Literal["none", "assessment", "urgent", "emergency"]
    exercises: list[ExerciseSelection] = Field(default_factory=list, max_length=4)
    proposed_intake: Intake | None = None
    intake_evidence: dict[str, str] = Field(default_factory=dict, max_length=14)


class RoutineSave(RecoveryModel):
    revision: int = Field(ge=1)


class CheckinCreate(RecoveryModel):
    severity: int = Field(ge=0, le=10, strict=True)
    trend: Literal["improving", "unchanged", "worsening"]
    function: Literal["normal", "limited", "unable"]
    note: str = Field(default="", max_length=2000)
    routine_id: int | None = Field(default=None, ge=1)
    completed: StrictBool = False
    before_severity: int | None = Field(default=None, ge=0, le=10, strict=True)
