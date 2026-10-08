"""A compact "today" file for the iPhone Home Screen widget (Scriptable reads it from iCloud Drive)."""

import json
import os
import sqlite3
import tempfile
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .checkins import get_daily_checkin
from .dashboard import build_training_load_summary
from .plans import serialize_weekly_plan
from .readiness import build_readiness_summary
from .session_brief import build_briefs_for_date
from .sick_mode import build_sick_mode

WIDGET_FILE_NAME = "trainlog-today.json"
DONE_STATUSES = {"matched", "linked", "rest_day_changed"}
REST_TYPES = {"rest", "recovery"}


def _plan_row_for(conn: sqlite3.Connection, today: date) -> Optional[sqlite3.Row]:
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = (today + timedelta(days=6 - today.weekday())).isoformat()
    return conn.execute(
        "SELECT * FROM weekly_plans WHERE week_start >= ? AND week_start <= ? ORDER BY week_start ASC LIMIT 1",
        (week_start, week_end),
    ).fetchone()


def _day_status(day: dict, today: date) -> str:
    comparison = (day.get("comparison") or {}).get("status")
    is_rest = str(day.get("session_type") or "").lower() in REST_TYPES
    if comparison in DONE_STATUSES:
        return "done"
    if comparison in {"skipped", "moved"}:
        return comparison
    if day.get("date") == today.isoformat():
        return "today"
    if day.get("date", "") > today.isoformat():
        return "upcoming"
    return "rest" if is_rest else "missed"


def _session(day: Optional[dict], brief: Optional[dict] = None) -> Optional[dict]:
    if not day:
        return None
    feel = (brief or {}).get("feel") or {}
    return {
        "title": day.get("title"),
        "session_type": day.get("session_type"),
        "intent_label": day.get("workout_intent_label"),
        "duration_min": day.get("target_duration_min"),
        "distance_km": day.get("target_distance_km"),
        "details": day.get("details"),
        "purpose": (brief or {}).get("purpose"),
        "rpe": feel.get("rpe"),
        "status": (day.get("comparison") or {}).get("status"),
    }


def build_widget_brief(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    training_load = build_training_load_summary(conn)
    readiness = build_readiness_summary(conn, training_load_summary=training_load)
    score = readiness.get("score") or {}

    row = _plan_row_for(conn, today)
    plan = serialize_weekly_plan(row, conn) if row else None
    days = (plan or {}).get("days") or []
    by_date = {day.get("date"): day for day in days}
    today_day = by_date.get(today.isoformat())
    tomorrow_day = by_date.get((today + timedelta(days=1)).isoformat())
    briefs = build_briefs_for_date(conn, plan, today)
    sick = build_sick_mode(conn, today)

    return {
        "version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "readiness": {
            "level": score.get("level", "unknown"),
            "label": score.get("label", "No read"),
            "advice": score.get("advice"),
            "drivers": score.get("drivers", [])[:3],
            "suggests_swap": bool(score.get("suggests_swap")),
        },
        "checkin_done": get_daily_checkin(conn, today.isoformat()) is not None,
        "sick": {"active": True, "label": sick.get("severity_label"), "day": sick.get("day_number")} if sick.get("active") else None,
        "today": _session(today_day, briefs[0] if briefs else None),
        "tomorrow": _session(tomorrow_day),
        "week": [
            {"date": day.get("date"), "label": day.get("label"), "title": day.get("title"), "session_type": day.get("session_type"), "status": _day_status(day, today)}
            for day in days
        ],
    }


def write_widget_brief(conn: sqlite3.Connection, directory: str | os.PathLike, today: Optional[date] = None) -> Path:
    """Write atomically so iCloud never syncs a half-written file."""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(build_widget_brief(conn, today), ensure_ascii=False, indent=1)
    handle, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".trainlog-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        target = target_dir / WIDGET_FILE_NAME
        os.replace(temp_path, target)
    except Exception:
        with suppress(OSError):
            os.unlink(temp_path)
        raise
    return target
