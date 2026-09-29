from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..models.recovery import AIResult, CheckinCreate, HealIssue, IssueCreate, IssueUpdate, MessageCreate
from ..repositories import recovery as repo
from ..services import recovery as service

router = APIRouter(prefix="/recovery", tags=["recovery"])


def connection():
    conn = get_db()
    try:
        # Serialize mutations, including a reply landing while another tab writes.
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


@router.get("/issues")
def issues(conn=Depends(connection)):
    return service.list_issues(conn)


@router.get("/related")
def related(body_area: str, conn=Depends(connection)):
    return service.related_issues(conn, body_area[:80])


@router.post("/issues", status_code=201)
def create_issue(payload: IssueCreate, conn=Depends(connection)):
    return service.create_issue(conn, payload)


@router.get("/issues/{issue_id}")
def issue(issue_id: int, conn=Depends(connection)):
    return service.get_issue(conn, issue_id)


@router.patch("/issues/{issue_id}")
def update_issue(issue_id: int, payload: IssueUpdate, conn=Depends(connection)):
    return service.update_issue(conn, issue_id, payload)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, conn=Depends(connection)):
    repo.delete_issue(conn, issue_id)
    return {"status": "deleted"}


@router.post("/issues/{issue_id}/heal")
def heal(issue_id: int, payload: HealIssue, conn=Depends(connection)):
    return service.heal(conn, issue_id, payload.what_helped)


@router.post("/issues/{issue_id}/reopen")
def reopen(issue_id: int, conn=Depends(connection)):
    return service.reopen(conn, issue_id)


@router.post("/issues/{issue_id}/messages", status_code=201)
def message(issue_id: int, payload: MessageCreate, conn=Depends(connection)):
    return service.add_message(conn, issue_id, payload)


@router.post("/issues/{issue_id}/requests", status_code=201)
def request(issue_id: int, conn=Depends(connection)):
    return service.new_request(conn, issue_id)


@router.get("/issues/{issue_id}/requests/{request_id}/context")
def context(issue_id: int, request_id: str, conn=Depends(connection)):
    return service.ai_context(conn, issue_id, request_id)


@router.post("/issues/{issue_id}/requests/{request_id}/result")
def result(issue_id: int, request_id: str, payload: AIResult, conn=Depends(connection)):
    return service.finish_request(conn, issue_id, request_id, payload)


@router.post("/issues/{issue_id}/requests/{request_id}/failed")
def failed(issue_id: int, request_id: str, conn=Depends(connection)):
    return service.fail_request(conn, issue_id, request_id)


@router.post("/issues/{issue_id}/checkins", status_code=201)
def checkin(issue_id: int, payload: CheckinCreate, conn=Depends(connection)):
    return service.add_checkin(conn, issue_id, payload)
