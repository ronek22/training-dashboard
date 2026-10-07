"""Things the coach has to say that the athlete hasn't opened yet.

A moment is offered until its linked chat exists: the latest training session's
win (for two days), and the week's wins on Sunday (this week) and Monday (last
week). Opening one creates the chat with the coach's opener, which retires it.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .week_wins import build_week_wins, session_wins_for_week

SESSION_DAYS = 2


def _has_chat(conn: sqlite3.Connection, kind: str, identifier: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM coach_chat_conversations WHERE context_kind = ? AND context_id = ? LIMIT 1", (kind, identifier)
    ).fetchone())


def _session_moment(conn: sqlite3.Connection, today: date) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT id, date FROM activities WHERE type != 'Walk' AND substr(date, 1, 10) BETWEEN ? AND ? ORDER BY date DESC LIMIT 1",
        ((today - timedelta(days=SESSION_DAYS - 1)).isoformat(), today.isoformat()),
    ).fetchone()
    if not row or _has_chat(conn, "activity", str(row["id"])):
        return None
    found = session_wins_for_week(conn, date.fromisoformat(str(row["date"])[:10]), today).get(str(row["id"]))
    if not found:
        return None
    activity, win = found
    return {
        "kind": "activity",
        "context_id": str(row["id"]),
        "label": "Your last session",
        "headline": win["headline"],
        "activity": {key: activity.get(key) for key in ("id", "type", "date", "name")},
        "win": {key: win[key] for key in ("kind", "headline", "detail", "opener")},
    }


def _week_moment(conn: sqlite3.Connection, today: date) -> Optional[dict[str, Any]]:
    if today.weekday() not in (6, 0):
        return None
    monday = today - timedelta(days=today.weekday()) - (timedelta(days=7) if today.weekday() == 0 else timedelta())
    if _has_chat(conn, "week", monday.isoformat()):
        return None
    week = build_week_wins(conn, monday, today=today)
    if not week["wins"]:
        return None
    count = len(week["wins"])
    return {
        "kind": "week",
        "context_id": monday.isoformat(),
        "label": "This week" if today.weekday() == 6 else "Last week",
        "headline": f"{count} {'win' if count == 1 else 'wins'}, 1 focus",
        "week": week,
    }


def build_coach_moments(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    today = today or datetime.now().date()
    moments = []
    for builder in (_session_moment, _week_moment):
        try:
            moment = builder(conn, today)
        except (sqlite3.Error, KeyError, ValueError):
            moment = None
        if moment:
            moments.append(moment)
    return moments
