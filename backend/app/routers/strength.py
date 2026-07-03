from typing import Optional

from fastapi import APIRouter

from ..db import get_db
from ..services.strength import get_strength_overview_data

router = APIRouter()


@router.get("/strength/overview")
def get_strength_overview(
    weeks: int = 8,
    body_part: Optional[str] = None,
    exercise: Optional[str] = None,
):
    conn = get_db()
    try:
        return get_strength_overview_data(
            conn,
            weeks=weeks,
            body_part=body_part,
            exercise=exercise,
        )
    finally:
        conn.close()
