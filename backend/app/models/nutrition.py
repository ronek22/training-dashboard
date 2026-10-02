from typing import Optional

from pydantic import BaseModel


class ProteinTickInput(BaseModel):
    # None clears the tick.
    hit: Optional[bool] = None
