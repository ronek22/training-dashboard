from fastapi import APIRouter

from ..db import get_db
from ..models.nutrition import ProteinTickInput, WeeklyBodyCheckinInput
from ..services.protein import build_protein_status, set_protein_tick
from ..services.weekly_body_checkin import build_weekly_body_checkin, save_weekly_body_checkin

router = APIRouter()


@router.get("/nutrition/protein")
def get_protein_status():
    conn = get_db()
    try:
        return build_protein_status(conn)
    finally:
        conn.close()


@router.put("/nutrition/protein/{day}")
def put_protein_tick(day: str, payload: ProteinTickInput):
    conn = get_db()
    try:
        return set_protein_tick(conn, day, payload.hit)
    finally:
        conn.close()


@router.get("/nutrition/weekly-checkin")
def get_weekly_body_checkin():
    conn = get_db()
    try:
        return build_weekly_body_checkin(conn)
    finally:
        conn.close()


@router.put("/nutrition/weekly-checkin")
def put_weekly_body_checkin(payload: WeeklyBodyCheckinInput):
    conn = get_db()
    try:
        return save_weekly_body_checkin(conn, payload.protein_most_days, payload.weight_kg, payload.skipped)
    finally:
        conn.close()
