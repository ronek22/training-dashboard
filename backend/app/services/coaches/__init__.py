"""One shared snapshot, three specialists, one HEAD COACH."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ...repositories.activities import list_activity_rows_between
from ..strength import get_strength_sessions_between
from . import running, cycling, strength
from .head import coordinate


def build_team_coaching(conn, *, week_start=None, today=None, context=None, recommendation=None, next_sessions=None):
    today = today or datetime.now(ZoneInfo("Europe/Warsaw")).date()
    start = week_start or today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    cutoff = min(end, today)
    baseline_start = start - timedelta(weeks=4)
    activities = list_activity_rows_between(conn, baseline_start.isoformat(), cutoff.isoformat())
    detail = get_strength_sessions_between(conn, start, cutoff) if cutoff >= start else []
    specialists = {name: module.analyze(activities, start, cutoff, detail)
                   for name, module in (("running", running), ("cycling", cycling), ("strength", strength))}
    # Current recovery/goal state is never silently applied to historical reviews.
    current = start <= today <= end
    head = coordinate(specialists, context if current else None, recommendation if current else None,
                      next_sessions if current else None)
    if not current:
        head["limitations"].append("Present-day recovery, restrictions and goals are omitted from this historical review.")
    return {"version": 1, "window": {"week_start": start.isoformat(), "week_end": end.isoformat(),
            "through_date": cutoff.isoformat(), "partial": cutoff < end, "timezone": "Europe/Warsaw",
            "baseline_start": baseline_start.isoformat()}, "specialists": specialists, "head_coach": head}
