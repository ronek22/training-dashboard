"""Relays weekly planning and plan revisions to the coach helper for the iOS app.

The web Plan page calls the helper (scripts/coach_helper.py) on the Mac's 127.0.0.1 directly. The
phone can't reach it, so the backend forwards the request. Nothing is saved here: the coach writes
the plan through the MCP tools, and the phone reloads /plans/weekly when the job succeeds.
"""

import re

from fastapi import HTTPException

from . import meal_estimate_relay

PLANNING_KINDS = {"weekly_plan", "weekly_plan_revision"}
WEEK_START = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NOT_FOUND = "Planning job not found"


def _public(job: dict) -> dict:
    keys = ("job_id", "kind", "status", "message", "summary", "week_start", "target_date", "created_at", "started_at", "finished_at")
    return {key: job.get(key) for key in keys if key in job}


def _text(value, field: str, *, required: bool) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise HTTPException(status_code=400, detail="Tell the coach what to change.")
    if len(text) > 4000:
        raise HTTPException(status_code=400, detail=f"The {field} is too long.")
    return text


def _week(value) -> str:
    week_start = str(value or "")
    if not WEEK_START.match(week_start):
        raise HTTPException(status_code=400, detail="week_start must use YYYY-MM-DD")
    return week_start


def start_plan(week_start: str, planning_brief: str = "") -> dict:
    body = {"week_start": _week(week_start), "planning_brief": _text(planning_brief, "brief", required=False)}
    return _public(meal_estimate_relay._call("/weekly-plan", body, timeout=30))


def start_revision(week_start: str, feedback: str, target_date: str | None = None) -> dict:
    body = {"week_start": _week(week_start), "feedback": _text(feedback, "feedback", required=True)}
    if target_date:
        body["target_date"] = _week(target_date)
    return _public(meal_estimate_relay._call("/weekly-plan-revision", body, timeout=30))


def get_job(job_id: str) -> dict:
    if not meal_estimate_relay.JOB_ID.match(job_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    # The helper's /weekly-plan/{id} returns any job; only planning jobs are the phone's business.
    job = meal_estimate_relay._call(f"/weekly-plan/{job_id}")
    if job.get("kind") not in PLANNING_KINDS:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(job)


def status() -> dict:
    """Whether the helper answers, so the phone can say so before you type a brief."""
    try:
        health = meal_estimate_relay._call("/health", timeout=3)
    except HTTPException:
        return {"available": False, "detail": meal_estimate_relay.HELPER_DOWN}
    return {"available": health.get("status") == "ok", "detail": None}
