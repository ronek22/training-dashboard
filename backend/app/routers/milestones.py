from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..services.milestones import build_milestones, mark_seen, milestone_detail

router = APIRouter()


@router.get("/milestones")
def milestones(day: Optional[date] = None):
    """Every milestone reached, the one to celebrate now (``pending``) and what is next; ``day`` is the browser's date."""
    conn = get_db()
    try:
        return build_milestones(conn, today=day)
    finally:
        conn.close()


@router.get("/milestones/{milestone_id}")
def milestone(milestone_id: str, day: Optional[date] = None):
    conn = get_db()
    try:
        return milestone_detail(conn, milestone_id, today=day)
    except ValueError as error:
        raise HTTPException(404, str(error))
    finally:
        conn.close()


@router.post("/milestones/{milestone_id}/seen")
def milestone_seen(milestone_id: str, day: Optional[date] = None):
    """Marks a celebration as shown so it does not open again by itself."""
    conn = get_db()
    try:
        return {"seen": mark_seen(conn, milestone_id, today=day)}
    finally:
        conn.close()
