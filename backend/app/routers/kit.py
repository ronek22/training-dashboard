from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..services.kit import (
    activity_kit,
    annotate_strava_gear,
    assign_activity_kit,
    create_item,
    delete_event,
    gear_backfill_range,
    get_item,
    import_strava_gear,
    log_event,
    mark_gear_ids_known,
    replace_item,
    sync_assignments,
    list_kit,
    update_item,
)
from ..services.settings import get_setting, set_setting
from ..services.strava import backfill_strava_gear_ids, fetch_strava_gear

router = APIRouter()

DATE = r"^\d{4}-\d{2}-\d{2}$"


class KitItemInput(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    kind: Optional[str] = None
    sport: Optional[str] = None
    started_on: Optional[str] = Field(default=None, pattern=DATE)
    threshold_km: Optional[float] = Field(default=None, ge=0)
    threshold_hours: Optional[float] = Field(default=None, ge=0)
    start_km: Optional[float] = Field(default=None, ge=0)
    start_hours: Optional[float] = Field(default=None, ge=0)
    is_default: Optional[bool] = None
    retired_on: Optional[str] = Field(default=None, pattern=DATE)
    strava_gear_id: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=400)
    parent_id: Optional[int] = None
    service_action: Optional[str] = None
    service_every_km: Optional[float] = Field(default=None, ge=0)
    count_indoor: Optional[bool] = None


class KitReplaceInput(BaseModel):
    on: Optional[str] = Field(default=None, pattern=DATE)
    name: Optional[str] = Field(default=None, max_length=80)
    service_action: Optional[str] = None  # logged on the new item that day, e.g. waxed before fitting


class KitEventInput(BaseModel):
    action: str
    done_on: Optional[str] = Field(default=None, pattern=DATE)
    note: Optional[str] = Field(default=None, max_length=200)


class StravaGearImportInput(BaseModel):
    gear_ids: list[str] = Field(min_length=1, max_length=50)


class ActivityKitInput(BaseModel):
    slot: str
    kit_id: Optional[int] = None


def _run(fn, *args):
    conn = get_db()
    try:
        return fn(conn, *args)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        conn.close()


def _save_part(fn, *args):
    """Save, then fetch past rides' gear ids from Strava if a fitted part reaches back before them."""
    conn = get_db()
    try:
        item = fn(conn, *args)
        span = gear_backfill_range(conn, item["id"])
        if span is None:
            return item
        try:
            matched = backfill_strava_gear_ids(conn, span[0], span[1], get_setting, set_setting)
        except HTTPException as exc:
            # The item is saved either way; past rides can be matched on a later save.
            return {**item, "gear_backfill": {"error": exc.detail}}
        mark_gear_ids_known(conn, span[0])
        sync_assignments(conn)  # commits
        return {**get_item(conn, item["id"]), "gear_backfill": {"matched": matched, "from": span[0], "to": span[1]}}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/kit")
def get_kit():
    return _run(list_kit)


@router.post("/kit")
def add_kit_item(payload: KitItemInput):
    return _save_part(create_item, payload.model_dump(exclude_unset=True))


@router.get("/kit/strava-gear")
def strava_gear():
    gear = fetch_strava_gear(get_setting, set_setting)
    return {"gear": _run(annotate_strava_gear, gear)}


@router.post("/kit/strava-gear/import")
def import_gear(payload: StravaGearImportInput):
    gear = fetch_strava_gear(get_setting, set_setting)
    return _run(import_strava_gear, gear, payload.gear_ids)


@router.patch("/kit/{kit_id}")
def edit_kit_item(kit_id: int, payload: KitItemInput):
    # Omitted fields are left unchanged; an explicit null clears them.
    return _save_part(update_item, kit_id, payload.model_dump(exclude_unset=True))


@router.post("/kit/{kit_id}/replace")
def replace_kit_item(kit_id: int, payload: KitReplaceInput):
    return _run(replace_item, kit_id, payload.model_dump(exclude_unset=True))


@router.post("/kit/{kit_id}/events")
def add_kit_event(kit_id: int, payload: KitEventInput):
    return _run(log_event, kit_id, payload.model_dump(exclude_unset=True))


@router.delete("/kit/events/{event_id}")
def remove_kit_event(event_id: int):
    return _run(delete_event, event_id)


@router.get("/activities/{activity_id}/kit")
def get_activity_kit(activity_id: str):
    return _run(activity_kit, activity_id)


@router.put("/activities/{activity_id}/kit")
def set_activity_kit(activity_id: str, payload: ActivityKitInput):
    return _run(assign_activity_kit, activity_id, payload.slot, payload.kit_id)
