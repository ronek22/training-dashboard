from fastapi import APIRouter, HTTPException

from ..services.planning_status import get_planning_status

router = APIRouter()


@router.get("/planning/status")
def planning_status():
    try:
        return get_planning_status()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
