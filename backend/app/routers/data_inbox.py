from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..services import data_inbox as service
from ..services.settings import get_setting, set_setting

router = APIRouter(prefix="/data-inbox", tags=["data inbox"])


class Dismissal(BaseModel):
    key: str = Field(min_length=3, max_length=300)


@router.get("")
def inbox():
    conn = get_db()
    try:
        return service.build_inbox(conn)
    finally:
        conn.close()


@router.post("/dismiss")
def dismiss(payload: Dismissal):
    conn = get_db()
    try:
        return service.dismiss(conn, payload.key)
    except LookupError as exc:
        raise HTTPException(404, "That item is no longer in the inbox.") from exc
    finally:
        conn.close()


@router.post("/streams/{activity_id}/refetch")
def refetch_streams(activity_id: str):
    conn = get_db()
    try:
        return service.refetch_streams(conn, activity_id, get_setting_fn=get_setting, set_setting_fn=set_setting)
    except LookupError as exc:
        raise HTTPException(404, "This activity is not on Strava.") from exc
    finally:
        conn.close()
