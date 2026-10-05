"""Local start time and time-of-day for activities.

Strava detail rows carry ``start_date``; streams-only backfills do not, so the
import reference (HealthFit, Strava, Zwift) fills the gap.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from .power_trends import _decode_json

LOCAL_TZ = ZoneInfo("Europe/Warsaw")


def start_times(conn: sqlite3.Connection, rows: Iterable[sqlite3.Row]) -> dict[str, datetime]:
    """Local start time per activity from Strava detail or the import reference."""
    starts: dict[str, datetime] = {}
    for row in rows:
        detail = _decode_json(row["detail_json"])
        value = detail.get("start_date") if isinstance(detail, dict) else None
        parsed = parse_timestamp(value)
        if parsed:
            starts[row["id"]] = parsed
    try:
        refs = conn.execute(
            "SELECT activity_id, started_at FROM activity_source_refs WHERE activity_id IS NOT NULL AND started_at IS NOT NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        refs = []
    for ref in refs:
        if ref["activity_id"] not in starts:
            parsed = parse_timestamp(ref["started_at"])
            if parsed:
                starts[ref["activity_id"]] = parsed
    return starts


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(LOCAL_TZ)


def time_of_day(start: Optional[datetime], offset_s: float = 0.0) -> Optional[dict[str, str]]:
    if start is None:
        return None
    moment = start + timedelta(seconds=offset_s)
    hour = moment.hour
    period = "night" if hour < 5 or hour >= 22 else "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return {"clock": moment.strftime("%H:%M"), "period": period}
