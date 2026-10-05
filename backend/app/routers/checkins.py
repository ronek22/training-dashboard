from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models.checkins import DailyCheckinInput, GuidedSessionCompletionInput, SickModeLogInput, SickModeStartInput, VolumeTrendLabelInput
from ..services.checkins import get_daily_checkin, upsert_daily_checkin
from ..services.downshift import build_downshift
from ..services.guided_sessions import public_session, reconcile_guided_session_activities, save_guided_completion
from ..services.sick_mode import build_sick_mode, end_sick_mode, log_sick_session, sick_dates, start_sick_mode
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


@router.get("/sick-mode")
def get_sick_mode():
    conn = get_db()
    try:
        reconcile_guided_session_activities(conn)
        return {"sick_mode": build_sick_mode(conn)}
    finally:
        conn.close()


@router.get("/sick-mode/dates")
def get_sick_dates():
    conn = get_db()
    try:
        return {"dates": sorted(sick_dates(conn))}
    finally:
        conn.close()


@router.get("/guided-sessions/{session_key}")
def get_guided_session(session_key: str):
    session = public_session(session_key)
    if not session:
        raise HTTPException(status_code=404, detail=f"Unknown guided session: {session_key}")
    return {"session": session}


@router.post("/guided-sessions/complete")
def complete_guided_session(payload: GuidedSessionCompletionInput):
    conn = get_db()
    try:
        return save_guided_completion(conn, payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        conn.close()


@router.get("/downshift")
def get_downshift():
    conn = get_db()
    try:
        return {"downshift": build_downshift(conn)}
    finally:
        conn.close()


@router.post("/sick-mode")
def start_or_update_sick_mode(payload: SickModeStartInput):
    conn = get_db()
    try:
        return {"sick_mode": start_sick_mode(conn, payload.severity, payload.note)}
    finally:
        conn.close()


@router.post("/sick-mode/end")
def finish_sick_mode():
    conn = get_db()
    try:
        return {"sick_mode": end_sick_mode(conn)}
    finally:
        conn.close()


@router.post("/sick-mode/log", status_code=201)
def log_sick_mode_session(payload: SickModeLogInput):
    conn = get_db()
    try:
        return {"sick_mode": log_sick_session(conn, payload.session_key)}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        conn.close()

