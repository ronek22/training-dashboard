from fastapi import APIRouter, HTTPException, Response

from ..db import get_db
from ..services.cycling_workouts import (
    build_cycling_workout_library,
    build_zwo,
    get_cycling_workout,
    latest_ftp,
    render_cycling_workout,
)

router = APIRouter()


def _workout_or_404(workout_id: str) -> dict:
    workout = get_cycling_workout(workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Cycling workout not found")
    return workout


@router.get("/cycling-workouts")
def list_cycling_workouts():
    conn = get_db()
    try:
        return build_cycling_workout_library(conn)
    finally:
        conn.close()


@router.get("/cycling-workouts/{workout_id}")
def get_cycling_workout_detail(workout_id: str):
    workout = _workout_or_404(workout_id)
    conn = get_db()
    try:
        ftp = latest_ftp(conn)
    finally:
        conn.close()
    return {"ftp": ftp, "workout": render_cycling_workout(workout, ftp["watts"])}


@router.get("/cycling-workouts/{workout_id}/zwo")
def download_cycling_workout_zwo(workout_id: str):
    workout = _workout_or_404(workout_id)
    return Response(
        content=build_zwo(workout),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{workout["id"]}.zwo"'},
    )
