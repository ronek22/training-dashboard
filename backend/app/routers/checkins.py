from typing import Optional

from fastapi import APIRouter

from ..db import get_db
from ..models.checkins import DailyCheckinInput
from ..services.checkins import get_daily_checkin, upsert_daily_checkin

router = APIRouter()


@router.get("/checkins/today")
def get_today_checkin(date: Optional[str] = None):
    conn = get_db()
    try:
        return {"checkin": get_daily_checkin(conn, date)}
    finally:
        conn.close()


@router.post("/checkins", status_code=201)
def save_checkin(checkin: DailyCheckinInput):
    conn = get_db()
    try:
        return {"checkin": upsert_daily_checkin(conn, checkin.model_dump())}
    finally:
        conn.close()
