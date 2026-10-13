import os
from pathlib import Path

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


def _zwift_dir() -> Path | None:
    """Zwift's per-account workouts folder, bind-mounted from the Mac."""
    if os.getenv("ZWIFT_SYNC_ENABLED", "").strip().lower() != "true":
        return None
    folder = Path(os.getenv("ZWIFT_WORKOUTS_DIR", "/zwift-workouts"))
    return folder if folder.is_dir() else None


@router.get("/zwift/workouts")
def list_zwift_workouts():
    folder = _zwift_dir()
    if not folder:
        return {"enabled": False, "workout_ids": []}
    return {"enabled": True, "workout_ids": sorted(path.stem for path in folder.glob("*.zwo"))}


@router.post("/cycling-workouts/{workout_id}/zwift")
def add_cycling_workout_to_zwift(workout_id: str):
    workout = _workout_or_404(workout_id)
    folder = _zwift_dir()
    if not folder:
        raise HTTPException(status_code=409, detail="Zwift folder is not connected; set ZWIFT_WORKOUTS_DIR in .env")
    (folder / f"{workout['id']}.zwo").write_text(build_zwo(workout), encoding="utf-8")
    return {"saved": True, "workout_id": workout["id"]}


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
