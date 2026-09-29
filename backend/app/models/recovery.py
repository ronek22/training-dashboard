from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

Side = Literal["", "left", "right", "both"]


class RecoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IssueCreate(RecoveryModel):
    title: str = Field(default="", max_length=100)
    body_area: str = Field(min_length=1, max_length=80)
    side: Side = ""
    pain: int | None = Field(default=None, ge=0, le=10, strict=True)
    previous_issue_id: int | None = Field(default=None, ge=1)


class IssueUpdate(RecoveryModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    body_area: str | None = Field(default=None, min_length=1, max_length=80)
    side: Side | None = None


class HealIssue(RecoveryModel):
    what_helped: str = Field(default="", max_length=2000)


class MessageCreate(RecoveryModel):
    content: str = Field(min_length=1, max_length=4000)


class CheckinCreate(RecoveryModel):
    pain: int = Field(ge=0, le=10, strict=True)
    did_plan: StrictBool = False
    note: str = Field(default="", max_length=2000)


class PlanExercise(RecoveryModel):
    name: str = Field(min_length=1, max_length=120)
    dose: str = Field(default="", max_length=200)
    how: str = Field(default="", max_length=1000)


class RecoveryPlan(RecoveryModel):
    summary: str = Field(min_length=1, max_length=600)
    exercises: list[PlanExercise] = Field(default_factory=list, max_length=8)
    do: list[str] = Field(default_factory=list, max_length=6)
    avoid: list[str] = Field(default_factory=list, max_length=6)


class AIResult(RecoveryModel):
    reply: str = Field(min_length=1, max_length=4000)
    plan: RecoveryPlan | None = None
    see_professional: StrictBool = False
