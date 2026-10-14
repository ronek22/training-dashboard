from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..services.personal_records import build_activity_record_ranks, build_personal_records
from ..services.season_history import build_season_history
from ..services.season_review import CoachNotOpen, build_season_review, season_review_status, write_coach_paragraph

router = APIRouter()


@router.get("/records")
def personal_records():
    conn = get_db()
    try:
        return build_personal_records(conn)
    finally:
        conn.close()


@router.get("/records/activities")
def activity_record_ranks():
    conn = get_db()
    try:
        return build_activity_record_ranks(conn)
    finally:
        conn.close()


@router.get("/season-review")
def season_review_years(day: Optional[date] = None):
    """Years with a season review; ``day`` is the browser's date (the current year opens on 1 December)."""
    conn = get_db()
    try:
        return season_review_status(conn, today=day)
    finally:
        conn.close()


@router.get("/season-review/history")
def season_history(sport: str = "ride", day: Optional[date] = None):
    """Every year of one sport side by side, for the All years view."""
    conn = get_db()
    try:
        return build_season_history(conn, sport, today=day)
    except ValueError as error:
        raise HTTPException(404, str(error))
    finally:
        conn.close()


@router.get("/season-review/{year}")
def season_review(year: int, day: Optional[date] = None):
    conn = get_db()
    try:
        return build_season_review(conn, year, today=day)
    except ValueError as error:
        raise HTTPException(404, str(error))
    finally:
        conn.close()


@router.post("/season-review/{year}/coach")
def season_review_coach(year: int, day: Optional[date] = None, rewrite: bool = False):
    """Write the year's coach paragraph on request. A saved one is returned as it was unless ``rewrite`` is asked for."""
    conn = get_db()
    try:
        coach, created = write_coach_paragraph(conn, year, today=day, rewrite=rewrite)
        return {"coach": coach, "created": created}
    except CoachNotOpen as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(404, str(error))
    finally:
        conn.close()
