from fastapi import APIRouter

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
    backfill_strava_streams_data,
    build_strava_status_data,
    import_strava_activities_data,
)

router = APIRouter()


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
