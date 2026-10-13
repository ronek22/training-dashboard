"""Two-minute downshift: on a high-stress or rest day, offer a guided breathing or mobility block.

Offered when today's check-in rates stress 4-5/5, today is tagged a deadline or late-night
day, or today is a planned rest or recovery day with nothing recorded yet (so resting never
costs the streak). Never offered in sick mode (which has its own gentle sessions). A finished downshift keeps the
daily streak through its completion record; it does not create an activity, so a two-minute
breathing block never shows up as training volume.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .checkins import get_daily_checkin
from .guided_sessions import SESSIONS, completions_on, public_session
from .life_load import TAGS, get_life_load_days
from .sick_mode import get_active_sick_period

STRESS_LEVEL = 4
STRESS_TAGS = ("deadline", "late_night")
REST_SESSION_TYPES = {"rest": "planned rest day", "recovery": "planned recovery day"}


def _planned_rest_reason(conn: sqlite3.Connection, day: date) -> Optional[str]:
    """A reason when today is a planned rest or recovery day and no activity is recorded yet."""
    week_start = (day - timedelta(days=day.weekday())).isoformat()
    try:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
        if conn.execute("SELECT 1 FROM activities WHERE substr(date, 1, 10) = ? LIMIT 1", (day.isoformat(),)).fetchone():
            return None
    except sqlite3.OperationalError:
        return None
    planned = next((item for item in json.loads(row["days_json"]) if item.get("date") == day.isoformat()), None) if row else None
    if not planned:
        return None
    return REST_SESSION_TYPES.get(str(planned.get("session_type") or "").strip().lower())


def build_downshift(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    day = today.isoformat()
    if get_active_sick_period(conn):
        return {"offer": False}
    reasons = []
    try:
        checkin = get_daily_checkin(conn, day)
    except sqlite3.OperationalError:
        checkin = None
    if checkin and int(checkin["stress"]) >= STRESS_LEVEL:
        reasons.append(f"stress {checkin['stress']}/5 in today's check-in")
    tags = get_life_load_days(conn, day, day).get(day, {}).get("tags", [])
    reasons += [f"{TAGS[tag]['label'].lower()} day" for tag in STRESS_TAGS if tag in tags]
    rest_reason = _planned_rest_reason(conn, today)
    if rest_reason:
        reasons.append(rest_reason)
    completed = completions_on(conn, day, "stress")
    if not reasons and not completed:
        return {"offer": False}
    done_keys = {item["session_key"] for item in completed}
    return {
        "offer": True,
        "reasons": reasons,
        "rest_day": bool(rest_reason),
        "sessions": [
            {**public_session(key), "completed_today": key in done_keys}
            for key, session in SESSIONS.items()
            if session["context"] == "stress"
        ],
        "completed_today": completed,
    }


def downshift_coaching_context(conn: sqlite3.Connection) -> Optional[dict]:
    state = build_downshift(conn)
    if not state["offer"]:
        return None
    guidance = (
        "Planned rest day. A two-minute downshift or a light day under the recovery cap keeps the daily streak and still counts as rest."
        if state["rest_day"] and len(state["reasons"]) == 1
        else "High-stress day. Prefer easy or shorter sessions; a two-minute breathing downshift counts toward the daily streak."
    )
    return {
        "reasons": state["reasons"],
        "done_today": [item["title"] for item in state["completed_today"]],
        "guidance": guidance,
    }
