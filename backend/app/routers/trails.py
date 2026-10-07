import os

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..services.settings import get_setting, set_setting
from ..services.strava import get_strava_access_token
from ..services.hike_detail import hike_context
from ..services.route_ideas import HOUR_PRESETS, route_ideas
from ..services.trail_coverage import (
    import_region,
    list_regions,
    region_map,
    strava_client,
    sync_tracks,
)

router = APIRouter()


@router.get("/trails")
def trail_regions():
    conn = get_db()
    try:
        return list_regions(conn)
    finally:
        conn.close()


@router.get("/trails/activity/{activity_id}")
def trail_hike_context(activity_id: str):
    """Mountain context for one hike; {"region": null} when the activity isn't in a mapped range."""
    conn = get_db()
    try:
        return hike_context(conn, activity_id) or {"region": None}
    finally:
        conn.close()


@router.get("/trails/{region}")
def trail_region_map(region: str):
    conn = get_db()
    try:
        return region_map(conn, region, os.getenv("MAPY_API_KEY"))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        conn.close()


@router.get("/trails/{region}/routes")
def trail_route_ideas(region: str, park: str, length: str = "day", around: bool = False):
    if length not in HOUR_PRESETS:
        raise HTTPException(status_code=400, detail=f"length must be one of {', '.join(HOUR_PRESETS)}")
    conn = get_db()
    try:
        return route_ideas(conn, region, park, HOUR_PRESETS[length], around)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        conn.close()


@router.post("/trails/{region}/import")
def import_trail_region(region: str):
    conn = get_db()
    try:
        return import_region(conn, region)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))
    finally:
        conn.close()


@router.post("/trails/sync-hikes")
def sync_trail_hikes():
    access_token = get_strava_access_token(get_setting, set_setting)
    conn = get_db()
    try:
        with strava_client(access_token) as client:
            return sync_tracks(conn, client)
    except RuntimeError as error:
        raise HTTPException(status_code=429, detail=str(error))
    finally:
        conn.close()
