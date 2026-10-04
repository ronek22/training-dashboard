from fastapi import APIRouter

from ..db import get_db
from ..services.personal_records import build_activity_record_ranks, build_personal_records

router = APIRouter()


@router.get("/records")
def personal_records():
    conn = get_db()
    try:
        return build_personal_records(conn)
    finally:
        conn.close()


@router.get("/records/activities")
def activity_record_ranks():
    conn = get_db()
    try:
        return build_activity_record_ranks(conn)
    finally:
        conn.close()
