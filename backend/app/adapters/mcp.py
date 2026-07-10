from typing import Optional

from ..db import get_db
from ..models.activities import Activity
from ..models.metrics import METRIC_CATALOG, Metric
from ..models.notes import CoachNote
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment
from ..models.weekly_summary import WeeklySummary
from ..repositories.plans import upsert_weekly_plan_row
from ..services.activities import (
    analyze_activity_data,
    activity_stats_data,
    fail_activity_analysis_data,
    get_calendar_weeks_data,
    get_activity_analysis_context_data,
    list_activities_data,
    save_activity_analysis_data,
    upsert_activity,
)
from ..services.settings import get_setting, set_setting
from ..services.strava import (
    fetch_strava_activity_detail,
    fetch_strava_activity_streams_by_keys,
    get_strava_access_token,
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
from ..services.strength import get_strength_context_data


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


def strength_context(weeks: int = 8, body_part: Optional[str] = None, exercise: Optional[str] = None):
    conn = get_db()
    try:
        return get_strength_context_data(
            conn,
            weeks=weeks,
            body_part=body_part,
            exercise=exercise,
        )
    finally:
        conn.close()


def analyze_activity(activity_id: str, force_refresh: bool = False):
    conn = get_db()
    try:
        return analyze_activity_data(
            conn,
            activity_id,
            force_refresh=force_refresh,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


def get_activity_analysis_context(activity_id: str):
    conn = get_db()
    try:
        return get_activity_analysis_context_data(
            conn,
            activity_id,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


def save_activity_analysis(
    activity_id: str,
    headline: str,
    summary: str,
    key_observations: list[str],
    limitations: list[str],
    confidence_note: str,
    generator: str = "llm",
    model_name: Optional[str] = None,
):
    conn = get_db()
    try:
        return save_activity_analysis_data(
            conn,
            activity_id,
            headline=headline,
            summary=summary,
            key_observations=key_observations,
            limitations=limitations,
            confidence_note=confidence_note,
            generator=generator,
            model_name=model_name,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


def fail_activity_analysis(activity_id: str, error: str):
    conn = get_db()
    try:
        return fail_activity_analysis_data(
            conn,
            activity_id,
            error_message=error,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
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
        "strength_context_fn": strength_context,
        "analyze_activity_fn": analyze_activity,
        "get_activity_analysis_context_fn": get_activity_analysis_context,
        "save_activity_analysis_fn": save_activity_analysis,
        "fail_activity_analysis_fn": fail_activity_analysis,
    }
