from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..db import get_db
from ..models.checkins import LifeLoadDayInput
from ..services.life_load import get_life_load_days, public_tags, set_life_load_day

router = APIRouter()

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/life-load")
def list_life_load(start: Optional[str] = Query(default=None, pattern=DATE_PATTERN), end: Optional[str] = Query(default=None, pattern=DATE_PATTERN)):
    today = date.today()
    start = start or (today - timedelta(days=120)).isoformat()
    end = end or (today + timedelta(days=60)).isoformat()
    conn = get_db()
    try:
        return {"tags": public_tags(), "days": list(get_life_load_days(conn, start, end).values())}
    finally:
        conn.close()


@router.put("/life-load/{day}")
def update_life_load_day(day: str, payload: LifeLoadDayInput):
    conn = get_db()
    try:
        return {"day": set_life_load_day(conn, day, payload.tags, payload.note)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        conn.close()
