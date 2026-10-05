from datetime import date

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..services.dashboard import select_active_weekly_plan_row
from ..services.plans import serialize_weekly_plan
from ..services.session_brief import build_briefs_for_date

router = APIRouter()


@router.get("/session-brief")
def session_brief(day: str | None = None):
    try:
        target = date.fromisoformat(day) if day else date.today()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="day must be YYYY-MM-DD") from exc
    conn = get_db()
    try:
        row = select_active_weekly_plan_row(conn)
        plan = serialize_weekly_plan(row, conn) if row else None
        return {"date": target.isoformat(), "briefs": build_briefs_for_date(conn, plan, target)}
    finally:
        conn.close()
