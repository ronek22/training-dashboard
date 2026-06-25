from fastapi import APIRouter

from ..db import get_db
from ..models.weekly_summary import WeeklySummary
from ..services.weekly_summary import create_weekly_summary_data, list_weekly_summary_data

router = APIRouter()


@router.post("/weekly", status_code=201)
def upsert_weekly(summary: WeeklySummary):
    conn = get_db()
    try:
        return create_weekly_summary_data(conn, summary.model_dump())
    finally:
        conn.close()


@router.get("/weekly")
def list_weekly(limit: int = 16):
    conn = get_db()
    try:
        return list_weekly_summary_data(conn, limit=limit)
    finally:
        conn.close()
