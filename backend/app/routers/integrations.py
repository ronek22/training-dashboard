from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..models.integrations import (
    StravaImportRequest,
    StravaImportResult,
    StravaStreamBackfillRequest,
    StravaStreamBackfillResult,
)
from ..repositories.activities import get_latest_activity_date
from ..services.activities import upsert_activity
from ..services.dashboard import estimate_thresholds, intensity_bucket_from_hr
from ..services.settings import get_setting, set_setting
from ..services.strava import (
    build_strava_authorize_url,
    exchange_strava_code,
    backfill_strava_streams_data,
    build_strava_status_data,
    import_strava_activities_data,
)
import os
from pathlib import Path

from ..services import strava_history_backfill
from ..services.strava_export_import import import_export_streams
from ..services.healthfit import apply_healthfit_import, preview_healthfit_import
from ..services.health_data import apply_health_data_import, preview_health_data_import

router = APIRouter()


@router.get("/integrations/health-data/preview")
def health_data_preview():
    conn = get_db()
    try:
        return preview_health_data_import(conn)
    finally:
        conn.close()


@router.post("/integrations/health-data/import")
def import_health_data_files():
    conn = get_db()
    try:
        return apply_health_data_import(conn)
    finally:
        conn.close()


@router.get("/integrations/healthfit/preview")
def healthfit_preview():
    conn = get_db()
    try:
        return preview_healthfit_import(conn)
    finally:
        conn.close()


@router.post("/integrations/healthfit/import")
def import_healthfit_files():
    conn = get_db()
    try:
        return apply_healthfit_import(conn)
    finally:
        conn.close()



class StravaAuthCode(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    scope: Optional[str] = Field(default=None, max_length=200)


@router.get("/integrations/strava/authorize-url")
def strava_authorize_url(redirect_uri: str):
    return {"url": build_strava_authorize_url(redirect_uri)}


@router.post("/integrations/strava/exchange")
def strava_exchange(payload: StravaAuthCode):
    return exchange_strava_code(payload.code, payload.scope, get_setting, set_setting)


@router.get("/integrations/strava/status")
def strava_status():
    conn = get_db()
    try:
        return build_strava_status_data(
            conn,
            get_setting_fn=get_setting,
            get_latest_activity_date_fn=get_latest_activity_date,
        )
    finally:
        conn.close()


@router.post("/integrations/strava/import", response_model=StravaImportResult)
def import_strava_activities(payload: StravaImportRequest):
    conn = get_db()
    try:
        result = import_strava_activities_data(
            conn,
            payload,
            get_latest_activity_date_fn=get_latest_activity_date,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            upsert_activity_fn=upsert_activity,
            estimate_thresholds_fn=estimate_thresholds,
            intensity_bucket_from_hr_fn=intensity_bucket_from_hr,
        )
    finally:
        conn.close()

    return StravaImportResult(
        imported=result["imported"],
        fetched=result["fetched"],
        start_date=result["start_date"],
        end_date=result["end_date"],
        streams_fetched=result["streams_fetched"],
    )


@router.post("/integrations/strava/streams/backfill", response_model=StravaStreamBackfillResult)
def backfill_strava_streams(payload: StravaStreamBackfillRequest):
    conn = get_db()
    try:
        result = backfill_strava_streams_data(
            conn,
            payload,
            get_setting_fn=get_setting,
            set_setting_fn=set_setting,
            estimate_thresholds_fn=estimate_thresholds,
            intensity_bucket_from_hr_fn=intensity_bucket_from_hr,
        )
    finally:
        conn.close()

    return StravaStreamBackfillResult(
        scanned=result["scanned"],
        streams_fetched=result["streams_fetched"],
        remaining_candidates=result["remaining_candidates"],
    )


@router.get("/integrations/strava/history-backfill")
def strava_history_backfill_status():
    """Progress of the slow background fetch of detailed streams for the whole history."""
    conn = get_db()
    try:
        return strava_history_backfill.status(conn)
    finally:
        conn.close()


@router.post("/integrations/strava/history-backfill")
def strava_history_backfill_toggle(payload: dict):
    """Start or pause the background fetch. Starting runs the first batch within a minute."""
    conn = get_db()
    try:
        return strava_history_backfill.set_enabled(conn, bool(payload.get("enabled")))
    finally:
        conn.close()


@router.post("/integrations/strava/export-import")
def strava_export_import(payload: dict):
    """Fill missing streams from a Strava bulk export copied to STRAVA_EXPORT_DIR (default /data/strava-export)."""
    directory = Path(os.getenv("STRAVA_EXPORT_DIR", "/data/strava-export"))
    conn = get_db()
    try:
        return import_export_streams(conn, directory, dry_run=bool(payload.get("dry_run")))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        conn.close()
