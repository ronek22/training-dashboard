from typing import Optional

from fastapi import APIRouter

from ..db import get_db
from ..models.checkins import DailyCheckinInput, VolumeTrendLabelInput
from ..services.checkins import get_daily_checkin, upsert_daily_checkin
from ..services.volume_trend import build_volume_trend, save_volume_trend_label

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


@router.post("/volume-trend/label")
def label_volume_trend(payload: VolumeTrendLabelInput):
    conn = get_db()
    try:
        save_volume_trend_label(conn, payload.week_start, payload.label, payload.note)
        return {"volume_trend": build_volume_trend(conn)}
    finally:
        conn.close()
