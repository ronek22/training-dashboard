from fastapi import APIRouter

from ..db import get_db
from ..services.dashboard import build_dashboard_data, build_recent_context, build_training_load_summary
from ..services.goals import list_goals_data

router = APIRouter()


@router.get("/dashboard")
def dashboard():
    conn = get_db()
    try:
        return build_dashboard_data(conn, list_goals_data_fn=list_goals_data)
    finally:
        conn.close()


@router.get("/training-load")
def training_load(days: int = 42, focus_days: int = 28):
    conn = get_db()
    try:
        return build_training_load_summary(conn, days=days, focus_days=focus_days)
    finally:
        conn.close()


@router.get("/context/recent")
def recent_context(
    lookback_days: int = 14,
    context_days: int = 30,
    recent_activity_limit: int = 12,
    recent_note_limit: int = 5,
):
    safe_lookback = max(1, min(lookback_days, 60))
    safe_context = max(safe_lookback, min(context_days, 120))
    safe_activity_limit = max(1, min(recent_activity_limit, 30))
    safe_note_limit = max(1, min(recent_note_limit, 20))
    conn = get_db()
    try:
        return build_recent_context(
            conn,
            lookback_days=safe_lookback,
            context_days=safe_context,
            recent_activity_limit=safe_activity_limit,
            recent_note_limit=safe_note_limit,
        )
    finally:
        conn.close()
