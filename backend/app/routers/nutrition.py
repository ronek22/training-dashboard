from fastapi import APIRouter

from ..db import get_db
from ..models.nutrition import ProteinTickInput
from ..services.protein import build_protein_status, set_protein_tick

router = APIRouter()


@router.get("/nutrition/protein")
def get_protein_status():
    conn = get_db()
    try:
        return build_protein_status(conn)
    finally:
        conn.close()


@router.put("/nutrition/protein/{day}")
def put_protein_tick(day: str, payload: ProteinTickInput):
    conn = get_db()
    try:
        return set_protein_tick(conn, day, payload.hit)
    finally:
        conn.close()
