"""What the coach needs to suggest a winter arc: recent weeks, FTP, goals, illness and busy weeks.

The coach helper reads this, asks the coach CLI for blocks and hands them to the Plan editor as a
draft. Nothing here writes: the athlete edits the draft and saves it through ``save_winter_arc``.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from .ftp import ftp_on
from .winter_arc import FOCUSES, _monday, _recent_ride_hours, list_blocks

HISTORY_WEEKS = 12
LOOKAHEAD_WEEKS = 20
RIDE_TYPES = ("Ride", "VirtualRide")
RUN_TYPES = ("Run", "TrailRun", "VirtualRun")
STRENGTH_TYPES = ("WeightTraining", "Workout")


def _safe(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def _weeks(conn: sqlite3.Connection, today: date) -> list[dict]:
    """The last full weeks, oldest first: ride hours and counts, runs and lifts."""
    end = _monday(today)
    start = end - timedelta(weeks=HISTORY_WEEKS)
    rows = _safe(conn, "SELECT date, type, duration_min FROM activities WHERE date >= ? AND date < ?",
                 (start.isoformat(), end.isoformat()))
    weeks = {(start + timedelta(weeks=n)).isoformat(): {"ride_hours": 0.0, "rides": 0, "runs": 0, "lifts": 0}
             for n in range(HISTORY_WEEKS)}
    for row in rows:
        week = _monday(date.fromisoformat(str(row["date"])[:10])).isoformat()
        if week not in weeks:
            continue
        if row["type"] in RIDE_TYPES:
            weeks[week]["ride_hours"] += float(row["duration_min"] or 0) / 60
            weeks[week]["rides"] += 1
        elif row["type"] in RUN_TYPES:
            weeks[week]["runs"] += 1
        elif row["type"] in STRENGTH_TYPES:
            weeks[week]["lifts"] += 1
    return [{"week_start": week, **values, "ride_hours": round(values["ride_hours"], 1)} for week, values in weeks.items()]


def _goals(conn: sqlite3.Connection, today: date) -> list[dict]:
    rows = _safe(conn, "SELECT title, metric_type, target_value, activity_type, commitment, end_date FROM goals "
                       "WHERE is_active = 1 AND COALESCE(lifecycle_status, 'active') = 'active' AND end_date >= ? "
                       "ORDER BY end_date LIMIT 12", (today.isoformat(),))
    return [{"title": row["title"], "metric": row["metric_type"], "target": row["target_value"],
             "sport": row["activity_type"], "commitment": row["commitment"] or "flexible", "ends": row["end_date"]}
            for row in rows]


def _illness(conn: sqlite3.Connection, today: date) -> list[dict]:
    since = (today - timedelta(days=60)).isoformat()
    rows = _safe(conn, "SELECT start_date, end_date, severity FROM sick_periods WHERE COALESCE(end_date, ?) >= ? "
                       "ORDER BY start_date", (today.isoformat(), since))
    return [{"start": row["start_date"], "end": row["end_date"], "severity": row["severity"]} for row in rows]


def _busy_weeks(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Weeks ahead with days tagged in life load (travel, work crunch, ...)."""
    start = _monday(today)
    rows = _safe(conn, "SELECT date, tags_json FROM life_load_days WHERE date >= ? AND date < ? ORDER BY date",
                 (start.isoformat(), (start + timedelta(weeks=LOOKAHEAD_WEEKS)).isoformat()))
    weeks: dict[str, dict] = {}
    for row in rows:
        try:
            tags = [str(tag) for tag in json.loads(row["tags_json"] or "[]") if tag]
        except (TypeError, ValueError):
            tags = []
        if not tags:
            continue
        week = weeks.setdefault(_monday(date.fromisoformat(row["date"])).isoformat(), {"days": 0, "tags": []})
        week["days"] += 1
        week["tags"] = sorted(set(week["tags"]) | set(tags))
    return [{"week_start": week, **values} for week, values in sorted(weeks.items())]


def default_window(today: date) -> tuple[str, str]:
    """Start this week if it is Monday or Tuesday, else next Monday; end on the last Sunday of February."""
    start = _monday(today) if today.weekday() <= 1 else _monday(today) + timedelta(weeks=1)
    year = start.year + 1 if start.month >= 3 else start.year
    end = date(year, 3, 1) - timedelta(days=1)
    end -= timedelta(days=(end.weekday() + 1) % 7)
    return start.isoformat(), end.isoformat()


def suggestion_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or date.today()
    start, end = default_window(today)
    return {
        "today": today.isoformat(),
        "window": {"start": start, "end": end},
        "focuses": [{"key": key, "label": label} for key, label in FOCUSES.items()],
        "ftp_watts": ftp_on(conn, today),
        "recent_ride_hours": _recent_ride_hours(conn, today),
        "weeks": _weeks(conn, today),
        "goals": _goals(conn, today),
        "illness": _illness(conn, today),
        "busy_weeks": _busy_weeks(conn, today),
        "current_arc": [{key: block[key] for key in ("start_date", "end_date", "focus", "label", "weekly_hours", "ride_mix", "lighter_every")}
                        for block in list_blocks(conn)],
    }
