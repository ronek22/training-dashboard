from typing import Optional

from pydantic import BaseModel


class FitbodImportRequest(BaseModel):
    file_name: Optional[str] = None
    csv_text: str


class FitbodSessionLinkRequest(BaseModel):
    activity_id: Optional[str] = None


class FitbodSessionRejectRequest(BaseModel):
    reason: Optional[str] = None
