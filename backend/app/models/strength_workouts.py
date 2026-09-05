from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StrengthTemplateExerciseInput(BaseModel):
    exercise_name: str = Field(min_length=1, max_length=120)
    set_count: int = Field(ge=1, le=20)
    target_reps: int = Field(ge=1, le=100)
    target_weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    rest_seconds: int = Field(default=90, ge=0, le=1800)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("exercise_name")
    @classmethod
    def clean_exercise_name(cls, value: str) -> str:
        return value.strip()


class StrengthTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=1000)
    exercises: list[StrengthTemplateExerciseInput] = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class StrengthSessionStartRequest(BaseModel):
    template_id: int


class StrengthSessionExerciseAddRequest(StrengthTemplateExerciseInput):
    switch_to: bool = True


class StrengthSetCompletionRequest(BaseModel):
    actual_reps: int = Field(ge=0, le=100)
    actual_weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)


class StrengthWarmupSetAddRequest(BaseModel):
    target_reps: Optional[int] = Field(default=None, ge=1, le=100)
    target_weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    rest_seconds: int = Field(default=60, ge=0, le=1800)
    switch_to: bool = True


class StrengthSessionPositionRequest(BaseModel):
    exercise_order: int = Field(ge=1)
    set_order: Optional[int] = Field(default=None, ge=1)


class StrengthSessionFinishRequest(BaseModel):
    linked_activity_id: Optional[str] = None


class StrengthActivityLinkRequest(BaseModel):
    activity_id: Optional[str] = None
