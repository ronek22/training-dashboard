from typing import Optional

from ..db import get_db
from ..models.activities import Activity
from ..models.metrics import METRIC_CATALOG, Metric
from ..models.notes import CoachNote
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment
from ..models.weekly_summary import WeeklySummary
from ..repositories.plans import upsert_weekly_plan_row
from ..services.activities import (
    activity_stats_data,
    get_calendar_weeks_data,
    list_activities_data,
    upsert_activity,
)
from ..services.dashboard import (
    build_dashboard_data,
    build_recent_context,
    compute_activity_streak,
)
from ..services.coaching import build_weekly_coaching
from ..services.goals import draft_goal_data, list_goals_data
from ..services.metrics import get_metric_history_data
from ..services.notes import list_notes_data
from ..services.plans import adjust_weekly_plan_data, list_weekly_plans_data


def list_activities(limit: int = 50, type: Optional[str] = None, days: Optional[int] = None):
    conn = get_db()
    try:
        return list_activities_data(conn, limit=limit, activity_type=type, days=days)
    finally:
        conn.close()


def activity_stats(days: int = 30):
    conn = get_db()
    try:
        return activity_stats_data(conn, days=days)
    finally:
        conn.close()


def calendar_weeks(weeks: int = 8):
    conn = get_db()
    try:
        return get_calendar_weeks_data(conn, weeks=weeks)
    finally:
        conn.close()


def list_notes(limit: int = 20, category: Optional[str] = None):
    conn = get_db()
    try:
        return list_notes_data(conn, limit=limit, category=category)
    finally:
        conn.close()


def get_metric(metric_name: str, limit: int = 30):
    conn = get_db()
    try:
        return get_metric_history_data(
            conn,
            metric_name=metric_name,
            limit=limit,
            compute_activity_streak_fn=compute_activity_streak,
        )
    finally:
        conn.close()


def dashboard():
    conn = get_db()
    try:
        return build_dashboard_data(conn, list_goals_data_fn=list_goals_data)
    finally:
        conn.close()


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


def build_mcp_router_dependencies() -> dict:
    return {
        "get_db_fn": get_db,
        "activity_model": Activity,
        "coach_note_model": CoachNote,
        "metric_model": Metric,
        "weekly_summary_model": WeeklySummary,
        "weekly_plan_model": WeeklyPlan,
        "weekly_plan_adjustment_model": WeeklyPlanAdjustment,
        "upsert_activity_fn": upsert_activity,
        "upsert_weekly_plan_row_fn": upsert_weekly_plan_row,
        "adjust_weekly_plan_data_fn": adjust_weekly_plan_data,
        "dashboard_fn": dashboard,
        "recent_context_fn": recent_context,
        "weekly_coaching_fn": weekly_coaching,
        "list_activities_fn": list_activities,
        "activity_stats_fn": activity_stats,
        "list_notes_fn": list_notes,
        "get_metric_fn": get_metric,
        "list_weekly_plans_data_fn": list_weekly_plans_data,
        "calendar_weeks_fn": calendar_weeks,
        "metric_catalog": METRIC_CATALOG,
        "draft_goal_data_fn": draft_goal_data,
    }
