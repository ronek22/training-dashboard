from pydantic import BaseModel, Field
from typing import Optional


class ModalityRestriction(BaseModel):
    status: str = "allowed"
    reason: Optional[str] = None
    note: Optional[str] = None
    expected_end_date: Optional[str] = None


class BodyAreaRestriction(BaseModel):
    area: str
    side: Optional[str] = None
    note: Optional[str] = None
    since: Optional[str] = None
    recovery_issue_id: Optional[int] = None


class ModalityRestrictionsPayload(BaseModel):
    modalities: dict[str, ModalityRestriction] = Field(default_factory=dict)
    body_areas: list[BodyAreaRestriction] = Field(default_factory=list)


class AthleteProfilePayload(BaseModel):
    primary_focus: Optional[str] = None
    modality_preferences: list[str] = Field(default_factory=list)
    current_block: Optional[str] = None
    preferred_long_session_days: list[str] = Field(default_factory=list)
    weekly_availability_notes: Optional[str] = None
    planning_notes: Optional[str] = None
    # None keeps the default (Oct–Mar); an empty list means no off season.
    off_season_months: Optional[list[int]] = None
    # Heaviest dumbbell available; progression switches to reps once it is reached.
    max_dumbbell_kg: Optional[float] = None
    # Date each free-text note was last written or confirmed; sending today marks it reviewed.
    notes_reviewed_at: Optional[dict[str, Optional[str]]] = None


class WorkoutTemplateSettingsPayload(BaseModel):
    programs: dict = Field(default_factory=dict)


class PerformanceAnchorPayload(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None


class PerformanceZonesPayload(BaseModel):
    zone2_lower_pct: Optional[float] = None
    zone2_upper_pct: Optional[float] = None


class FtpChoicePayload(BaseModel):
    source: Optional[str] = None
    manual_watts: Optional[float] = None


class PerformanceSettingsPayload(BaseModel):
    anchors: dict[str, PerformanceAnchorPayload] = Field(default_factory=dict)
    zones: dict[str, PerformanceZonesPayload] = Field(default_factory=dict)
    ftp: Optional[FtpChoicePayload] = None
