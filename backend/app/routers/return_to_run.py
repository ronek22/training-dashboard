from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..services.return_to_run import build_return_to_run, save_program, save_symptom_check

router = APIRouter()


class ReturnToRunProgramInput(BaseModel):
    active: bool = True
    symptom: Optional[str] = Field(default=None, max_length=40)
    started_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_stage: Optional[int] = Field(default=None, ge=1, le=6)


class RunSymptomInput(BaseModel):
    # Omitted fields are left unchanged; an explicit null clears them.
    during: Optional[int] = Field(default=None, ge=0, le=10)
    next_morning: Optional[int] = Field(default=None, ge=0, le=10)


@router.get("/return-to-run")
def return_to_run():
    conn = get_db()
    try:
        return build_return_to_run(conn)
    finally:
        conn.close()


@router.put("/return-to-run")
def update_return_to_run(payload: ReturnToRunProgramInput):
    conn = get_db()
    try:
        save_program(conn, payload.model_dump(exclude_unset=True))
        return build_return_to_run(conn)
    finally:
        conn.close()


@router.put("/activities/{activity_id}/symptoms")
def update_run_symptoms(activity_id: str, payload: RunSymptomInput):
    conn = get_db()
    try:
        return save_symptom_check(conn, activity_id, payload.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        conn.close()
