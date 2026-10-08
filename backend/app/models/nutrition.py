from typing import Optional

from pydantic import BaseModel


class ProteinTickInput(BaseModel):
    # None clears the tick.
    hit: Optional[bool] = None


class WeeklyBodyCheckinInput(BaseModel):
    protein_most_days: Optional[bool] = None
    weight_kg: Optional[float] = None
    skipped: bool = False
