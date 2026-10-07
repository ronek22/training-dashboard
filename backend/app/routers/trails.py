import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..services.settings import get_setting, set_setting
from ..services.strava import get_strava_access_token
from ..services.hike_detail import hike_context
from ..services.route_ideas import HOUR_PRESETS, route_ideas
from ..services.route_planner import delete_route, list_saved_routes, plan_route, save_route, update_route
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


class RoutePlanRequest(BaseModel):
    points: list[list[float]]  # [lat, lon] or [lat, lon, snap radius m]
    simplify: bool = False


@router.post("/trails/{region}/plan")
def trail_route_plan(region: str, request: RoutePlanRequest):
    conn = get_db()
    try:
        if any(len(p) not in (2, 3) for p in request.points):
            raise ValueError("Each point is [lat, lon] or [lat, lon, snap radius]")
        return plan_route(conn, region, request.points, request.simplify)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        conn.close()


class SavedRouteRequest(BaseModel):
    name: str
    collection: str = ""
    points: list[list[float]]


class SavedRouteUpdate(BaseModel):
    name: Optional[str] = None
    collection: Optional[str] = None
    points: Optional[list[list[float]]] = None


@router.get("/trails/{region}/saved-routes")
def trail_saved_routes(region: str):
    conn = get_db()
    try:
        return list_saved_routes(conn, region)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        conn.close()


@router.post("/trails/{region}/saved-routes")
def create_saved_route(region: str, request: SavedRouteRequest):
    conn = get_db()
    try:
        return save_route(conn, region, request.name, request.collection, request.points)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        conn.close()


@router.put("/trails/saved-routes/{route_id}")
def change_saved_route(route_id: int, request: SavedRouteUpdate):
    conn = get_db()
    try:
        return update_route(conn, route_id, request.name, request.collection, request.points)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        conn.close()


@router.delete("/trails/saved-routes/{route_id}")
def remove_saved_route(route_id: int):
    conn = get_db()
    try:
        delete_route(conn, route_id)
        return {"deleted": route_id}
    except LookupError as error:
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
