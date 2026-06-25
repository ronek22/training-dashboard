from pydantic import BaseModel
from typing import Optional


class StravaImportRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    fetch_streams: Optional[bool] = True


class StravaImportResult(BaseModel):
    imported: int
    fetched: int
    start_date: str
    end_date: str
    streams_fetched: int = 0


class StravaStreamBackfillRequest(BaseModel):
    limit: Optional[int] = 12


class StravaStreamBackfillResult(BaseModel):
    scanned: int
    streams_fetched: int
    remaining_candidates: int
