from pydantic import BaseModel, Field
from typing import Optional


class ModalityRestriction(BaseModel):
    status: str = "allowed"
    reason: Optional[str] = None
    note: Optional[str] = None
    expected_end_date: Optional[str] = None


class ModalityRestrictionsPayload(BaseModel):
    modalities: dict[str, ModalityRestriction] = Field(default_factory=dict)
