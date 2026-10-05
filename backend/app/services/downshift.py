"""Two-minute downshift: on a high-stress day, offer a guided breathing or mobility block.

Offered when today's check-in rates stress 4-5/5 or today is tagged a deadline or late-night
day, and never in sick mode (which has its own gentle sessions). A finished downshift keeps the
daily streak through its completion record; it does not create an activity, so a two-minute
breathing block never shows up as training volume.
"""
import sqlite3
from datetime import date, datetime
from typing import Optional

from .checkins import get_daily_checkin
from .guided_sessions import SESSIONS, completions_on, public_session
from .life_load import TAGS, get_life_load_days
from .sick_mode import get_active_sick_period

STRESS_LEVEL = 4
STRESS_TAGS = ("deadline", "late_night")


def build_downshift(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    day = (today or datetime.now().date()).isoformat()
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
    completed = completions_on(conn, day, "stress")
    if not reasons and not completed:
        return {"offer": False}
    done_keys = {item["session_key"] for item in completed}
    return {
        "offer": True,
        "reasons": reasons,
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
    return {
        "reasons": state["reasons"],
        "done_today": [item["title"] for item in state["completed_today"]],
        "guidance": "High-stress day. Prefer easy or shorter sessions; a two-minute breathing downshift counts toward the daily streak.",
    }
