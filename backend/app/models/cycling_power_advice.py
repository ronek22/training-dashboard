from pydantic import BaseModel, ConfigDict, Field


class CyclingPowerFocus(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    action: str = Field(min_length=1, max_length=500)
    success_check: str = Field(min_length=1, max_length=300)


class CyclingPowerAdviceSave(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    context_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    headline: str = Field(min_length=1, max_length=120)
    assessment: str = Field(min_length=1, max_length=900)
    focus: list[CyclingPowerFocus] = Field(min_length=1, max_length=3)
    uncertainty: str = Field(max_length=500)
    evidence_ids: list[str] = Field(max_length=12)
