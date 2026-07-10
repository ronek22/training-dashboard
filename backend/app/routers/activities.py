from fastapi import APIRouter
from typing import Optional

from ..db import get_db
from ..models.fitbod_imports import FitbodImportRequest, FitbodSessionLinkRequest, FitbodSessionRejectRequest
from ..models.activities import (
    Activity,
    ActivityAnalysisFailureRequest,
    ActivityAnalysisRequest,
    ActivityAnalysisSaveRequest,
    ActivityIntentUpdate,
    ActivityPlanLink,
)
from ..services.settings import get_setting, set_setting
from ..services.strava import (
    fetch_strava_activity_detail,
    fetch_strava_activity_streams_by_keys,
    get_strava_access_token,
)
from ..services.activities import (
    activity_stats_data,
    create_activity_data,
    analyze_activity_data,
    fail_activity_analysis_data,
    get_calendar_month_data,
    get_calendar_weeks_data,
    get_activity_detail_data,
    get_activity_analysis_context_data,
    link_activity_to_planned_session_data,
    list_activities_data,
    save_activity_analysis_data,
    update_activity_workout_intent_data,
)
from ..services.fitbod_imports import (
    get_latest_fitbod_import_data,
    import_fitbod_csv_data,
    link_fitbod_session_to_activity_data,
    reject_fitbod_session_data,
)

router = APIRouter()


@router.post("/activities", status_code=201)
def create_activity(activity: Activity):
    conn = get_db()
    try:
        return create_activity_data(conn, activity.model_dump())
    finally:
        conn.close()


@router.get("/activities")
def list_activities(limit: int = 50, type: Optional[str] = None, days: Optional[int] = None):
    conn = get_db()
    try:
        return list_activities_data(conn, limit=limit, activity_type=type, days=days)
    finally:
        conn.close()


@router.get("/activities/stats")
def activity_stats(days: int = 30):
    conn = get_db()
    try:
        return activity_stats_data(conn, days=days)
    finally:
        conn.close()


@router.get("/activities/{activity_id}")
def get_activity_detail(activity_id: str):
    conn = get_db()
    try:
        return get_activity_detail_data(
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


@router.post("/activities/{activity_id}/analysis")
def analyze_activity(activity_id: str, payload: ActivityAnalysisRequest):
    conn = get_db()
    try:
        return analyze_activity_data(
            conn,
            activity_id,
            force_refresh=payload.force_refresh,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


@router.get("/activities/{activity_id}/analysis/context")
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


@router.post("/activities/{activity_id}/analysis/save")
def save_activity_analysis(activity_id: str, payload: ActivityAnalysisSaveRequest):
    conn = get_db()
    try:
        return save_activity_analysis_data(
            conn,
            activity_id,
            headline=payload.headline,
            summary=payload.summary,
            key_observations=payload.key_observations,
            limitations=payload.limitations,
            confidence_note=payload.confidence_note,
            generator=payload.generator,
            model_name=payload.model_name,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


@router.post("/activities/{activity_id}/analysis/fail")
def fail_activity_analysis(activity_id: str, payload: ActivityAnalysisFailureRequest):
    conn = get_db()
    try:
        return fail_activity_analysis_data(
            conn,
            activity_id,
            error_message=payload.error,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            get_strava_access_token_fn=get_strava_access_token,
            fetch_strava_activity_detail_fn=fetch_strava_activity_detail,
            fetch_strava_activity_streams_fn=fetch_strava_activity_streams_by_keys,
        )
    finally:
        conn.close()


@router.post("/fitbod/import")
def import_fitbod_csv(payload: FitbodImportRequest):
    conn = get_db()
    try:
        return import_fitbod_csv_data(conn, file_name=payload.file_name, csv_text=payload.csv_text)
    finally:
        conn.close()


@router.get("/fitbod/imports/latest")
def get_latest_fitbod_import():
    conn = get_db()
    try:
        return get_latest_fitbod_import_data(conn)
    finally:
        conn.close()


@router.post("/fitbod/sessions/{session_id}/link")
def link_fitbod_session_to_activity(session_id: int, payload: FitbodSessionLinkRequest):
    conn = get_db()
    try:
        return link_fitbod_session_to_activity_data(conn, session_id, payload.activity_id)
    finally:
        conn.close()


@router.post("/fitbod/sessions/{session_id}/reject")
def reject_fitbod_session(session_id: int, payload: FitbodSessionRejectRequest):
    conn = get_db()
    try:
        return reject_fitbod_session_data(conn, session_id, payload.reason)
    finally:
        conn.close()


@router.post("/activities/{activity_id}/link-plan")
def link_activity_to_plan(activity_id: str, payload: ActivityPlanLink):
    conn = get_db()
    try:
        return link_activity_to_planned_session_data(conn, activity_id, payload.planned_session_id)
    finally:
        conn.close()


@router.post("/activities/{activity_id}/intent")
def update_activity_intent(activity_id: str, payload: ActivityIntentUpdate):
    conn = get_db()
    try:
        return update_activity_workout_intent_data(conn, activity_id, payload.workout_intent)
    finally:
        conn.close()


@router.get("/calendar/weeks")
def calendar_weeks(weeks: int = 8):
    conn = get_db()
    try:
        return get_calendar_weeks_data(conn, weeks=weeks)
    finally:
        conn.close()


@router.get("/calendar/month")
def calendar_month(month: Optional[str] = None):
    conn = get_db()
    try:
        return get_calendar_month_data(conn, month=month)
    finally:
        conn.close()
