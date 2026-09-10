from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from ..db import get_db
from ..services import project_ideas as service

router = APIRouter(prefix="/project-ideas", tags=["project ideas"])


class Decision(BaseModel):
    status: Literal["new", "shortlisted", "building", "done", "dismissed"]


def connection():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except LookupError as exc:
        conn.rollback()
        raise HTTPException(404, "Idea not found") from exc
    except (OSError, ValueError, ValidationError) as exc:
        conn.rollback()
        raise HTTPException(503, "The ideas review is unavailable. Try again after the next review.") from exc
    finally:
        conn.close()


@router.get("")
def board(conn=Depends(connection)):
    return service.get_board(conn)


@router.patch("/{idea_id}")
def update_decision(idea_id: str, decision: Decision, conn=Depends(connection)):
    return service.set_status(conn, idea_id, decision.status)
