from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..models.recovery import (AIRequestCreate, AIResult, CheckinCreate, IntakeUpdate,
                               IssueCreate, IssueSharing, IssueStatus, MessageCreate, RoutineSave)
from ..repositories import recovery as repo
from ..services import recovery as service

router = APIRouter(prefix="/recovery", tags=["recovery"])


def connection():
    conn = get_db()
    try:
        # Serialize mutations and revision validation, including cross-tab updates.
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except LookupError as exc:
        conn.rollback()
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        conn.rollback()
        raise HTTPException(409, str(exc)) from exc
    finally:
        conn.close()


@router.get("/questions")
def questions():
    return service.QUESTIONS


@router.get("/issues")
def issues(conn=Depends(connection)):
    return service.list_issues(conn)


@router.post("/issues", status_code=201)
def create_issue(payload: IssueCreate, conn=Depends(connection)):
    cursor = conn.execute("INSERT INTO recovery_issues (title) VALUES (?)", (payload.title,))
    return service.get_issue(conn, cursor.lastrowid)


@router.get("/issues/{issue_id}")
def issue(issue_id: int, conn=Depends(connection)):
    return service.get_issue(conn, issue_id)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, conn=Depends(connection)):
    repo.delete_issue(conn, issue_id)
    return {"status": "deleted"}


@router.put("/issues/{issue_id}/status")
def status(issue_id: int, payload: IssueStatus, conn=Depends(connection)):
    repo.issue_row(conn, issue_id)
    service.invalidate(conn, issue_id)
    conn.execute("""UPDATE recovery_issues SET status = ?, revision = revision + 1,
        needs_review = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (payload.status, issue_id))
    return service.get_issue(conn, issue_id)


@router.put("/issues/{issue_id}/intake")
def intake(issue_id: int, payload: IntakeUpdate, conn=Depends(connection)):
    return service.save_intake(conn, issue_id, payload)


@router.put("/issues/{issue_id}/sharing")
def sharing(issue_id: int, payload: IssueSharing, conn=Depends(connection)):
    repo.issue_row(conn, issue_id)
    conn.execute("UPDATE recovery_issues SET share_coaching = ? WHERE id = ?", (payload.share_coaching, issue_id))
    return service.get_issue(conn, issue_id)


@router.post("/issues/{issue_id}/messages", status_code=201)
def message(issue_id: int, payload: MessageCreate, conn=Depends(connection)):
    return service.add_message(conn, issue_id, payload)


@router.post("/issues/{issue_id}/requests", status_code=201)
def request(issue_id: int, payload: AIRequestCreate, conn=Depends(connection)):
    return service.new_request(conn, issue_id, payload.kind, payload.ai_consent)


@router.get("/issues/{issue_id}/requests/{request_id}/context")
def context(issue_id: int, request_id: str, conn=Depends(connection)):
    return service.ai_context(conn, issue_id, request_id)


@router.post("/issues/{issue_id}/requests/{request_id}/result")
def result(issue_id: int, request_id: str, payload: AIResult, conn=Depends(connection)):
    return service.finish_request(conn, issue_id, request_id, payload)


@router.post("/issues/{issue_id}/requests/{request_id}/failed")
def failed(issue_id: int, request_id: str, conn=Depends(connection)):
    service.request_row(conn, issue_id, request_id)
    conn.execute("UPDATE recovery_requests SET status = 'failed' WHERE id = ?", (request_id,))
    return {"status": "failed"}


@router.post("/issues/{issue_id}/routines/{routine_id}/save")
def save_routine(issue_id: int, routine_id: int, payload: RoutineSave, conn=Depends(connection)):
    return service.save_routine(conn, issue_id, routine_id, payload.revision)


@router.post("/issues/{issue_id}/checkins", status_code=201)
def checkin(issue_id: int, payload: CheckinCreate, conn=Depends(connection)):
    return service.add_checkin(conn, issue_id, payload)
