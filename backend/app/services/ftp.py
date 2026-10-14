"""The one FTP the app trains with.

There are three candidates: the FTP logged as a metric (a test or a manual
entry), the estimate from recent training efforts, and a working FTP the
athlete types in. The athlete picks the source on the Athlete page. Every
power reader (zones, load, workouts, ride balance) goes through ``ftp_on`` or
``working_ftp`` so they all agree.

Each choice applies from the day it was made and is kept in a dated history,
so a ride keeps the FTP that was in force on its day even after later switches.
Days before any choice use the logged FTP in force then.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime
from typing import Any, Optional

from ..repositories.settings import get_setting_value

PERFORMANCE_SETTINGS_KEY = "performance_settings"
FTP_STALE_AFTER_DAYS = 56
FTP_HISTORY_LIMIT = 60
FTP_SOURCES = {
    "stored": "Logged FTP",
    "estimate": "Training estimate",
    "manual": "Working FTP",
}


def _watts(value: Any) -> Optional[float]:
    try:
        watts = float(value)
    except (TypeError, ValueError):
        return None
    return round(watts, 1) if math.isfinite(watts) and 0 < watts <= 1000 else None


def _iso_day(value: Any) -> Optional[str]:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat() if value else None
    except ValueError:
        return None


def _normalize_history(raw: Any) -> list[dict]:
    """Dated FTP choices, oldest first, one per day. ``watts`` is None for the logged FTP."""
    by_day = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        day = _iso_day(item.get("from"))
        source = item.get("source") if item.get("source") in FTP_SOURCES else None
        if not day or not source:
            continue
        watts = None if source == "stored" else _watts(item.get("watts"))
        if source != "stored" and watts is None:
            continue
        by_day[day] = {"from": day, "source": source, "watts": watts}
    return [by_day[day] for day in sorted(by_day)][-FTP_HISTORY_LIMIT:]


def normalize_ftp_choice(raw: Any) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    source = raw.get("source") if raw.get("source") in FTP_SOURCES else "stored"
    choice = {
        "source": source,
        "source_label": FTP_SOURCES[source],
        "manual_watts": _watts(raw.get("manual_watts")),
        "estimate_watts": _watts(raw.get("estimate_watts")),
        "estimate_basis": raw.get("estimate_basis") or None,
        "estimate_date": _iso_day(raw.get("estimate_date")),
        "effective_from": _iso_day(raw.get("effective_from")),
    }
    history = _normalize_history(raw.get("history"))
    if not history and source != "stored" and choice["effective_from"] and _choice_watts(choice):
        # Settings saved before the history existed only know the current choice.
        history = [{"from": choice["effective_from"], "source": source, "watts": _choice_watts(choice)}]
    choice["history"] = history
    return choice


def record_ftp_choice(choice: dict, day: str) -> dict:
    """Add the current choice to the history from ``day``, replacing a same-day entry."""
    entry = {"from": day, "source": choice["source"], "watts": _choice_watts(choice)}
    history = [item for item in choice.get("history") or [] if item["from"] < day]
    if history and (history[-1]["source"], history[-1]["watts"]) == (entry["source"], entry["watts"]):
        return {**choice, "history": history}
    if not history and entry["source"] == "stored":
        return {**choice, "history": []}
    return {**choice, "history": _normalize_history([*history, entry])}


def ftp_choice(conn: sqlite3.Connection) -> dict:
    try:
        raw = get_setting_value(conn, PERFORMANCE_SETTINGS_KEY)
        parsed = json.loads(raw) if raw else {}
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        parsed = {}
    return normalize_ftp_choice((parsed or {}).get("ftp") if isinstance(parsed, dict) else None)


def _choice_watts(choice: dict) -> Optional[float]:
    if choice["source"] == "manual":
        return choice["manual_watts"]
    if choice["source"] == "estimate":
        return choice["estimate_watts"]
    return None


def _stored_row(conn: sqlite3.Connection, day: Optional[str]) -> Optional[sqlite3.Row]:
    try:
        if day:
            return conn.execute(
                "SELECT value, date FROM metrics WHERE metric = 'ftp' AND date <= ? ORDER BY date DESC, id DESC LIMIT 1",
                (day,),
            ).fetchone()
        return conn.execute(
            "SELECT value, date FROM metrics WHERE metric = 'ftp' ORDER BY date DESC, id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None


def _age(day: Optional[str], today: date) -> Optional[int]:
    try:
        return (today - datetime.strptime(day, "%Y-%m-%d").date()).days if day else None
    except (TypeError, ValueError):
        return None


def stored_ftp(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """The latest FTP logged as a metric, whatever source is chosen."""
    row = _stored_row(conn, None)
    watts = _watts(row["value"]) if row else None
    if watts is None:
        return {"available": False, "watts": None, "date": None, "age_days": None, "stale": False}
    age_days = _age(row["date"], today or date.today())
    return {
        "available": True, "watts": watts, "date": row["date"], "age_days": age_days,
        "stale": age_days is not None and age_days > FTP_STALE_AFTER_DAYS,
    }


def ftp_on(conn: sqlite3.Connection, day: Any = None) -> Optional[float]:
    """FTP in force on ``day`` (default today)."""
    day_iso = _iso_day(day) or date.today().isoformat()
    in_force = [item for item in ftp_choice(conn)["history"] if item["from"] <= day_iso]
    if in_force and in_force[-1]["watts"]:
        return in_force[-1]["watts"]
    row = _stored_row(conn, day_iso)
    return _watts(row["value"]) if row else None


def working_ftp(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """Today's FTP with where it came from, in the shape the readers expect."""
    today = today or date.today()
    choice = ftp_choice(conn)
    watts = _choice_watts(choice)
    if watts and choice["effective_from"] and today.isoformat() >= choice["effective_from"]:
        since = choice["estimate_date"] if choice["source"] == "estimate" else choice["effective_from"]
        age_days = _age(since, today)
        return {
            "available": True, "watts": watts, "date": since, "age_days": age_days,
            # The estimate refreshes itself; a typed value goes stale like a test does.
            "stale": choice["source"] == "manual" and age_days is not None and age_days > FTP_STALE_AFTER_DAYS,
            "source": choice["source"], "source_label": choice["source_label"],
        }
    stored = stored_ftp(conn, today)
    return {**stored, "source": "stored", "source_label": FTP_SOURCES["stored"]}
