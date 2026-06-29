from fastapi import APIRouter

from ..db import get_db
from ..services.coaching import build_weekly_coaching, list_coaching_history_data

router = APIRouter()


@router.get("/coaching/weekly")
def weekly_coaching(
    lookback_days: int = 14,
    context_days: int = 30,
    recent_activity_limit: int = 12,
    recent_note_limit: int = 5,
    include_proposed_adjustment: bool = True,
):
    safe_lookback = max(1, min(lookback_days, 60))
    safe_context = max(safe_lookback, min(context_days, 120))
    safe_activity_limit = max(1, min(recent_activity_limit, 30))
    safe_note_limit = max(1, min(recent_note_limit, 20))
    conn = get_db()
    try:
        return build_weekly_coaching(
            conn,
            lookback_days=safe_lookback,
            context_days=safe_context,
            recent_activity_limit=safe_activity_limit,
            recent_note_limit=safe_note_limit,
            include_proposed_adjustment=include_proposed_adjustment,
        )
    finally:
        conn.close()


@router.get("/coaching/history")
def coaching_history(limit: int = 6):
    safe_limit = max(1, min(limit, 16))
    conn = get_db()
    try:
        return list_coaching_history_data(conn, limit=safe_limit)
    finally:
        conn.close()
