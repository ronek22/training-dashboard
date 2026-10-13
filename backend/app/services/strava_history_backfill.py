"""Fetch detailed Strava streams for the whole activity history, slowly.

After importing years of Strava history, most older runs and rides have only
summary numbers. Their streams unlock fastest-distance records, season bests,
charts and maps. There are thousands of them and Strava allows about 100
requests per 15 minutes and 1,000 per day, so this runs in the background in
small batches over several days and always leaves part of each limit free for
normal syncing and for opening activity pages.

Each activity is tried once: streams are cached like any detail page fetch;
an activity Strava has no streams for (a manual entry) is marked and skipped.
A stream summary for training load is stored only when the streams carry
heart rate or power; without either, a summary would count the whole session
as easy aerobic time, which is not known.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import httpx
from fastapi import HTTPException

from ..repositories.settings import get_setting_value, set_setting_value
from .dashboard import estimate_thresholds, intensity_bucket_from_hr
from .strava import (
    STRAVA_DETAIL_STREAM_KEYS,
    fetch_strava_activity_streams_by_keys,
    get_strava_access_token,
    summarize_activity_streams,
    upsert_activity_detail_stream_cache,
    upsert_activity_stream_summary,
)

logger = logging.getLogger(__name__)

SETTING_KEY = "strava_history_backfill"
BATCH_EVERY = timedelta(minutes=16)  # A little over Strava's 15-minute window.
MAX_REQUESTS_PER_BATCH = 60
RESERVE_SHARE = 0.35  # Keep this share of each Strava limit for everything else.
MAX_ATTEMPTS = 3
TYPES = ("Run", "Ride", "VirtualRide")

SCHEMA = """
CREATE TABLE IF NOT EXISTS strava_history_backfill (
    activity_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    attempted_at TEXT NOT NULL
);
"""

_CANDIDATES = f"""
    FROM activities a
    LEFT JOIN activity_details d ON d.activity_id = a.id
    LEFT JOIN activity_source_refs sr ON sr.activity_id = a.id AND sr.source = 'strava'
    LEFT JOIN strava_history_backfill b ON b.activity_id = a.id
    WHERE a.type IN ({", ".join(f"'{kind}'" for kind in TYPES)})
      AND d.streams_json IS NULL
      AND (sr.external_id IS NOT NULL OR a.id NOT LIKE 'healthfit:%')
      AND (b.activity_id IS NULL OR (b.status = 'failed' AND b.attempts < {MAX_ATTEMPTS}))
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _state(conn: sqlite3.Connection) -> dict[str, Any]:
    value = get_setting_value(conn, SETTING_KEY)
    try:
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}


def _save_state(conn: sqlite3.Connection, state: dict[str, Any]) -> None:
    set_setting_value(conn, SETTING_KEY, json.dumps(state))
    conn.commit()


def candidates(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    """Runs first (the old records are there), newest first within each sport."""
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT a.id, COALESCE(sr.external_id, a.id) AS strava_id, a.date, a.type, a.name, a.duration_min, "
        "a.avg_hr, a.avg_watts, a.max_hr, a.distance_km, COALESCE(b.attempts, 0) AS attempts "
        + _CANDIDATES
        + " ORDER BY CASE a.type WHEN 'Run' THEN 0 ELSE 1 END, a.date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def status(conn: sqlite3.Connection, now: Optional[datetime] = None) -> dict[str, Any]:
    ensure_schema(conn)
    now = now or datetime.now()
    remaining = conn.execute("SELECT COUNT(*) " + _CANDIDATES).fetchone()[0]
    counts = {row["status"]: row["n"] for row in conn.execute("SELECT status, COUNT(*) AS n FROM strava_history_backfill GROUP BY status")}
    state = _state(conn)
    per_day = state.get("per_day") or 650
    next_run = None
    if state.get("enabled") and remaining:
        last = state.get("last_run_at")
        next_run = (datetime.fromisoformat(last) + BATCH_EVERY).isoformat() if last else now.isoformat()
    return {
        "enabled": bool(state.get("enabled")),
        "remaining": int(remaining),
        "fetched": int(counts.get("fetched", 0)),
        "no_streams": int(counts.get("no_streams", 0)),
        "failed": int(counts.get("failed", 0)),
        "last_run_at": state.get("last_run_at"),
        # A batch takes a minute or two; one "running" for 10 minutes was cut short by a restart.
        "running": bool(state.get("enabled") and state.get("running") and state.get("last_run_at")
                        and now - datetime.fromisoformat(state["last_run_at"]) < timedelta(minutes=10)),
        "next_run_at": next_run,  # Batches wait for Strava's 15-minute window; the background loop checks every minute.
        "batch_size": MAX_REQUESTS_PER_BATCH,
        "paused_reason": state.get("paused_reason"),
        "estimated_days": round(remaining / per_day, 1) if remaining else 0,
        "reserve_share": RESERVE_SHARE,
    }


def set_enabled(conn: sqlite3.Connection, enabled: bool) -> dict[str, Any]:
    state = _state(conn)
    state["enabled"] = bool(enabled)
    if enabled:
        state.setdefault("started_at", datetime.now().isoformat())
        state["last_run_at"] = None  # Run the first batch straight away.
        state["paused_reason"] = None
    else:
        state["paused_reason"] = "Paused by you."
    _save_state(conn, state)
    return status(conn)


def _mark(conn: sqlite3.Connection, activity_id: str, outcome: str, attempts: int, error: Optional[str] = None) -> None:
    conn.execute(
        "INSERT INTO strava_history_backfill (activity_id, status, attempts, error, attempted_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(activity_id) DO UPDATE SET status = excluded.status, attempts = excluded.attempts, "
        "error = excluded.error, attempted_at = excluded.attempted_at",
        (activity_id, outcome, attempts, error, datetime.now().isoformat()),
    )


def _over_reserve(rate_limit: Optional[dict]) -> Optional[str]:
    if not rate_limit:
        return None
    if rate_limit["daily_remaining"] <= rate_limit["daily_limit"] * RESERVE_SHARE:
        return "Daily share of Strava's limit used; continues tomorrow."
    if rate_limit["short_remaining"] <= rate_limit["short_limit"] * RESERVE_SHARE:
        return "Waiting for Strava's 15-minute limit."
    return None


def run_batch(
    conn: sqlite3.Connection,
    *,
    now: Optional[datetime] = None,
    force: bool = False,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    fetch_streams_fn: Callable[[httpx.Client, str, str], tuple[Optional[dict], Optional[dict]]] = fetch_strava_activity_streams_by_keys,
    token_fn: Callable = get_strava_access_token,
    client_factory: Callable[[str], Any] = lambda token: httpx.Client(timeout=20, headers={"Authorization": f"Bearer {token}"}),
) -> dict[str, Any]:
    """Fetch one batch when enabled and due. Returns what happened."""
    ensure_schema(conn)
    now = now or datetime.now()
    state = _state(conn)
    if not state.get("enabled"):
        return {"ran": False, "reason": "disabled"}
    last = state.get("last_run_at")
    if not force and last and now - datetime.fromisoformat(last) < BATCH_EVERY:
        return {"ran": False, "reason": "not due"}
    batch = candidates(conn, MAX_REQUESTS_PER_BATCH)
    state["last_run_at"] = now.isoformat()
    if not batch:
        state.update(enabled=False, paused_reason=None, finished_at=now.isoformat())
        _save_state(conn, state)
        return {"ran": True, "fetched": 0, "finished": True}

    state["running"] = True  # Lets the status say "fetching now" while the batch runs.
    _save_state(conn, state)
    thresholds = estimate_thresholds(conn)
    fetched = no_streams = failed = 0
    paused = None
    with client_factory(token_fn(get_setting_fn, set_setting_fn)) as client:
        for activity in batch:
            attempts = int(activity["attempts"]) + 1
            try:
                streams, rate_limit = fetch_streams_fn(client, str(activity["strava_id"]), STRAVA_DETAIL_STREAM_KEYS)
            except HTTPException as error:
                if "429" in str(error.detail) or "Rate Limit" in str(error.detail):
                    paused = "Strava's rate limit was reached; tries again in the next window."
                    break
                _mark(conn, activity["id"], "failed", attempts, str(error.detail)[:300])
                conn.commit()
                failed += 1
                continue
            except httpx.HTTPError as error:
                paused = f"Strava could not be reached ({type(error).__name__}); tries again later."
                break
            if not streams or not (streams.get("time") or {}).get("data"):
                _mark(conn, activity["id"], "no_streams", attempts)
                no_streams += 1
            else:
                upsert_activity_detail_stream_cache(conn, activity["id"], streams)
                if (streams.get("heartrate") or {}).get("data") or (streams.get("watts") or {}).get("data"):
                    summary = summarize_activity_streams(activity, streams, thresholds, intensity_bucket_from_hr)
                    if summary:
                        upsert_activity_stream_summary(conn, summary)
                _mark(conn, activity["id"], "fetched", attempts)
                fetched += 1
            conn.commit()  # Progress survives a restart.
            paused = _over_reserve(rate_limit)
            if paused:
                if rate_limit:
                    state["per_day"] = max(100, int(rate_limit["daily_limit"] * (1 - RESERVE_SHARE)))
                break
    state["paused_reason"] = paused
    state["running"] = False
    _save_state(conn, state)
    logger.info("Strava history backfill: %s fetched, %s without streams, %s failed", fetched, no_streams, failed)
    return {"ran": True, "fetched": fetched, "no_streams": no_streams, "failed": failed, "paused_reason": paused}
