"""One inbox for missing and messy training data.

Five kinds of gaps, each from the last 30 days so the list never becomes a
backlog: workouts without feedback, planned sessions no activity matched,
runs and rides without heart-rate streams, runs whose HealthFit file (Apple
Watch running dynamics) has not arrived, and a stale FTP benchmark. Each
item resolves itself once the data is there (feedback saved, session linked,
streams fetched, FTP updated). The athlete can also mark an item as fine;
dismissals are stored by item key and stay dismissed.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Callable, Optional

from .ftp import FTP_STALE_AFTER_DAYS, working_ftp
from .strava_history_backfill import ensure_schema as ensure_history_backfill_schema

WINDOW_DAYS = 30
# Walks are commutes and errands; asking how they felt is noise.
FEEDBACK_SKIP_TYPES = ("Walk",)
STREAM_TYPES = ("Run", "Ride", "VirtualRide")
KIND_ORDER = {"feedback": 0, "unmatched_session": 1, "missing_streams": 2, "missing_dynamics": 3, "stale_benchmark": 4}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS data_inbox_dismissals (
        item_key TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        dismissed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")


def _dismissed(conn: sqlite3.Connection) -> set[str]:
    init_schema(conn)
    return {row[0] for row in conn.execute("SELECT item_key FROM data_inbox_dismissals")}


def _window_start(today: date) -> str:
    return (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()


def missing_feedback_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Workouts with no feedback. A lift recorded in Workout Studio already has per-set effort taps."""
    skip = ",".join("?" for _ in FEEDBACK_SKIP_TYPES)
    rows = conn.execute(
        f"""
        SELECT a.id, a.date, a.type, a.name, a.duration_min, a.distance_km, a.workout_intent
        FROM activities a
        LEFT JOIN activity_feedback f ON f.activity_id = a.id
        WHERE a.date BETWEEN ? AND ?
          AND f.activity_id IS NULL
          AND a.type NOT IN ({skip})
          AND NOT EXISTS (
              SELECT 1 FROM strength_workout_sessions s
              WHERE s.linked_activity_id = a.id AND s.status = 'completed'
          )
        ORDER BY a.date DESC, a.created_at DESC
        """,
        [_window_start(today), today.isoformat(), *FEEDBACK_SKIP_TYPES],
    ).fetchall()
    return [
        {
            "key": f"feedback:{row['id']}",
            "kind": "feedback",
            "date": row["date"],
            "title": row["name"] or row["type"],
            "detail": "No feedback yet. Effort and energy feed readiness and the coach.",
            "activity": dict(row),
        }
        for row in rows
    ]


def unmatched_session_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Past planned sessions that no activity matched, with nearby activities to link."""
    from .plans import serialize_weekly_plan

    start = _window_start(today)
    # A week that started up to 6 days before the window still has days inside it.
    rows = conn.execute(
        "SELECT * FROM weekly_plans WHERE week_start >= ? AND week_start <= ? ORDER BY week_start DESC",
        ((today - timedelta(days=WINDOW_DAYS + 6)).isoformat(), today.isoformat()),
    ).fetchall()
    plans = [serialize_weekly_plan(row, conn) for row in rows]
    # An activity that already fulfils another planned session is not offered: linking it would unmatch
    # that session. One done on a rest day fulfils nothing, so it stays on offer.
    in_use = {
        activity["id"]
        for plan in plans for day in plan.get("days", [])
        if (day.get("comparison") or {}).get("planned_type") != "Rest"
        for activity in (day.get("comparison") or {}).get("completed_activities") or []
    }
    items = []
    for plan in plans:
        for day in plan.get("days", []):
            comparison = day.get("comparison") or {}
            if comparison.get("status") != "skipped" or comparison.get("planned_type") == "Rest":
                continue
            if not day.get("date") or not (start <= day["date"] < today.isoformat()):
                continue
            candidates = [
                {key: item.get(key) for key in ("id", "date", "type", "name", "duration_min")}
                for item in day.get("link_candidates") or []
                if not item.get("linked_planned_session_id") and item["id"] not in in_use
            ]
            items.append({
                "key": f"plan:{day['session_id']}",
                "kind": "unmatched_session",
                "date": day["date"],
                "title": day.get("title") or comparison.get("planned_type") or "Planned session",
                "detail": (
                    "No activity matched this planned session. Link the one you did instead, or mark it as skipped."
                    if candidates else "No activity matched and nothing nearby fits. Mark it as skipped if that is right."
                ),
                "session_id": day["session_id"],
                "session_type": comparison.get("planned_type"),
                "candidates": candidates,
            })
    return items


def missing_stream_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Strava runs and rides without detailed streams, or whose streams lack the heart rate Strava reported."""
    ensure_history_backfill_schema(conn)
    types = ",".join("?" for _ in STREAM_TYPES)
    rows = conn.execute(
        f"""
        SELECT a.id, a.date, a.type, a.name, a.avg_hr,
               d.streams_json IS NOT NULL AS has_streams,
               COALESCE(s.has_heartrate, 0) AS has_heartrate
        FROM activities a
        LEFT JOIN activity_details d ON d.activity_id = a.id
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        LEFT JOIN activity_source_refs sr ON sr.activity_id = a.id AND sr.source = 'strava'
        LEFT JOIN strava_history_backfill b ON b.activity_id = a.id
        WHERE a.date BETWEEN ? AND ?
          AND a.type IN ({types})
          AND (sr.external_id IS NOT NULL OR a.id NOT LIKE 'healthfit:%')
          AND COALESCE(b.status, '') != 'no_streams'
          AND (
              d.streams_json IS NULL
              OR (a.avg_hr IS NOT NULL AND COALESCE(s.has_heartrate, 0) = 0)
          )
        ORDER BY a.date DESC
        """,
        [_window_start(today), today.isoformat(), *STREAM_TYPES],
    ).fetchall()
    return [
        {
            "key": f"streams:{row['id']}",
            "kind": "missing_streams",
            "date": row["date"],
            "title": row["name"] or row["type"],
            "detail": (
                "Strava reported heart rate, but the stream is missing. Zones, load and decoupling skip this session."
                if row["has_streams"] else "No detailed streams yet. Heart-rate zones and load skip this session."
            ),
            "activity_id": row["id"],
            "activity_type": row["type"],
        }
        for row in rows
    ]


def missing_dynamics_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Runs synced from Strava whose HealthFit file, with the watch's running dynamics, is not in yet."""
    from .running_fitness import runs_missing_dynamics

    return [
        {
            "key": f"dynamics:{row['id']}",
            "kind": "missing_dynamics",
            "date": row["date"],
            "title": row["name"] or "Run",
            "detail": (
                "Strava has this run, but not the Apple Watch running dynamics (cadence, ground contact, "
                "vertical oscillation, power). Open HealthFit on your iPhone so it exports the run to iCloud; "
                "new files are read every 15 minutes, or check now."
            ),
            "activity_id": row["id"],
            "activity_type": "Run",
        }
        for row in runs_missing_dynamics(conn, today, WINDOW_DAYS)
    ]


def stale_benchmark_items(conn: sqlite3.Connection, today: date) -> list[dict]:
    """The FTP every power reader trains with, once it is older than the stale limit."""
    ftp = working_ftp(conn, today)
    if not ftp.get("available") or not ftp.get("stale"):
        return []
    return [{
        # Keyed by the FTP's date, so a newer FTP that later goes stale shows up again.
        "key": f"ftp:{ftp['source']}:{ftp['date']}",
        "kind": "stale_benchmark",
        "date": ftp["date"],
        "title": f"FTP {round(ftp['watts'])} W is {ftp['age_days']} days old",
        "detail": (
            f"{ftp['source_label']} from {ftp['date']}; older than {FTP_STALE_AFTER_DAYS} days. "
            "Power zones, ride load and workout targets all use it. Update it on the Athlete page, "
            "or mark it as fine if it still holds."
        ),
        "benchmark": "ftp",
        "watts": ftp["watts"],
        "age_days": ftp["age_days"],
    }]


DETECTORS: tuple[Callable[[sqlite3.Connection, date], list[dict]], ...] = (
    missing_feedback_items,
    unmatched_session_items,
    missing_stream_items,
    missing_dynamics_items,
    stale_benchmark_items,
)


def build_inbox(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or date.today()
    dismissed = _dismissed(conn)
    items = [item for detect in DETECTORS for item in detect(conn, today) if item["key"] not in dismissed]
    items.sort(key=lambda item: (KIND_ORDER[item["kind"]], -int((item.get("date") or "0000-00-00").replace("-", ""))))
    counts = {kind: 0 for kind in KIND_ORDER}
    for item in items:
        counts[item["kind"]] += 1
    return {
        "window_days": WINDOW_DAYS,
        "since": _window_start(today),
        "count": len(items),
        "counts": counts,
        "items": items,
    }


def dismiss(conn: sqlite3.Connection, item_key: str, today: Optional[date] = None) -> dict:
    """Mark an open item as fine. Only keys currently in the inbox are accepted."""
    open_items = {item["key"]: item for detect in DETECTORS for item in detect(conn, today or date.today())}
    item = open_items.get(item_key)
    if not item:
        raise LookupError("Inbox item not found")
    init_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO data_inbox_dismissals (item_key, kind) VALUES (?, ?)",
        (item_key, item["kind"]),
    )
    conn.commit()
    return build_inbox(conn, today)


def refetch_streams(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
) -> dict:
    """Fetch one activity's Strava streams again and store them."""
    from .dashboard import estimate_thresholds, intensity_bucket_from_hr
    from .strava import (
        STRAVA_DETAIL_STREAM_KEYS,
        fetch_strava_activity_streams_by_keys,
        get_strava_access_token,
        summarize_activity_streams,
        upsert_activity_detail_stream_cache,
        upsert_activity_stream_summary,
    )
    import httpx

    row = conn.execute(
        """
        SELECT a.id, COALESCE(sr.external_id, a.id) AS strava_id, a.date, a.type, a.name,
               a.duration_min, a.avg_hr, a.avg_watts, a.max_hr, a.distance_km
        FROM activities a
        LEFT JOIN activity_source_refs sr ON sr.activity_id = a.id AND sr.source = 'strava'
        WHERE a.id = ? AND (sr.external_id IS NOT NULL OR a.id NOT LIKE 'healthfit:%')
        """,
        (activity_id,),
    ).fetchone()
    if not row:
        raise LookupError("Activity not found on Strava")
    activity = dict(row)
    token = get_strava_access_token(get_setting_fn, set_setting_fn)
    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {token}"}) as client:
        streams, _ = fetch_strava_activity_streams_by_keys(client, str(activity["strava_id"]), STRAVA_DETAIL_STREAM_KEYS)
    if not streams or not (streams.get("time") or {}).get("data"):
        return {"fetched": False, "has_heartrate": False, "message": "Strava has no streams for this activity."}
    upsert_activity_detail_stream_cache(conn, activity_id, streams)
    has_heartrate = bool((streams.get("heartrate") or {}).get("data"))
    if has_heartrate or (streams.get("watts") or {}).get("data"):
        summary = summarize_activity_streams(activity, streams, estimate_thresholds(conn), intensity_bucket_from_hr)
        if summary:
            upsert_activity_stream_summary(conn, summary)
    conn.commit()
    return {
        "fetched": True,
        "has_heartrate": has_heartrate,
        "message": "Streams fetched." if has_heartrate else "Streams fetched, but Strava has no heart rate for this one.",
    }
