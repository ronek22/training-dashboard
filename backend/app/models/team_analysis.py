from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SpecialistAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    sport: Literal['running', 'cycling', 'strength']
    verdict: str = Field(min_length=1, max_length=100)
    assessment: str = Field(min_length=1, max_length=600)
    next_week_focus: str = Field(min_length=1, max_length=350)
    evidence_ids: list[str] = Field(max_length=6)
    uncertainty: str = Field(max_length=300)


class HeadAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    headline: str = Field(min_length=1, max_length=100)
    verdict: str = Field(min_length=1, max_length=700)
    tradeoff: str = Field(min_length=1, max_length=500)
    next_week_change: str = Field(min_length=1, max_length=400)
    success_check: str = Field(min_length=1, max_length=300)
    uncertainty: str = Field(max_length=300)


class TeamAnalysisSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    specialists: list[SpecialistAnalysis] = Field(min_length=3, max_length=3)
    head_coach: HeadAnalysis
