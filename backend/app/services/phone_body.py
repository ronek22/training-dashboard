"""The iOS app's Body screen: last night's sleep stages, vitals against their baselines,
training load (fitness, fatigue, form), what drives today's readiness, and the last week of
training and active injuries for the body map."""

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Optional

from .dashboard import build_training_load_summary
from .health_data import get_health_metric_history, get_sleep_history
from .guided_sessions import guided_label_for_activity
from .readiness import build_readiness_summary
from .recovery import _active_issue_rows, detect_body_areas
from .rehab_session import CONTEXT_LABEL as REHAB_LABEL
from .strength_progression import _session_index, _working_sets

BASELINE_DAYS = 30
TRAINING_DAYS = 7
LOAD_DAYS = 42
SLEEP_STAGES = {"awake", "rem", "core", "deep", "asleep_unspecified"}
DETAILED_STAGES = {"core", "deep", "rem"}


def _last_night(conn: sqlite3.Connection, today: date) -> Optional[dict]:
    history = get_sleep_history(conn, BASELINE_DAYS + 7)
    night = next((item for item in history if item["date"] <= today.isoformat()), None)
    if not night:
        return None
    rows = conn.execute(
        """
        SELECT DISTINCT timestamp, end_timestamp, category_label, duration_seconds, source_name, source_bundle
        FROM health_metric_samples
        WHERE metric = 'sleep' AND date = ? AND end_timestamp IS NOT NULL
          AND duration_seconds IS NOT NULL AND duration_seconds > 0
        ORDER BY timestamp ASC
        """,
        (night["date"],),
    ).fetchall()
    # Same source pick as the sleep history: the one with stages, then the longest.
    by_source = defaultdict(list)
    for row in rows:
        if row["category_label"] in SLEEP_STAGES:
            by_source[row["source_bundle"] or row["source_name"] or "unknown"].append(row)
    if not by_source:
        return None

    def rank(segments):
        detailed = any(row["category_label"] in DETAILED_STAGES for row in segments)
        asleep = sum(row["duration_seconds"] for row in segments if row["category_label"] != "awake")
        return (detailed, asleep)

    segments = max(by_source.values(), key=rank)
    before = [item["value"] for item in history if item["date"] < night["date"]][:BASELINE_DAYS]
    return {
        "date": night["date"],
        "asleep_h": night["value"],
        "stages": night["stages"],
        "start": segments[0]["timestamp"],
        "end": max(row["end_timestamp"] for row in segments),
        "baseline_h": round(mean(before), 2) if len(before) >= 5 else None,
        "segments": [
            {"stage": row["category_label"], "start": row["timestamp"], "end": row["end_timestamp"]}
            for row in segments
        ],
    }


def _typical(values: list[float]) -> tuple[Optional[float], Optional[float]]:
    """The middle 80% of the month before, like the Watch's Vitals range."""
    if len(values) < 7:
        return None, None
    ordered = sorted(values)
    at = lambda share: ordered[round(share * (len(ordered) - 1))]
    return round(at(0.1), 1), round(at(0.9), 1)


def _vital(conn: sqlite3.Connection, metric: str, today: date) -> Optional[dict]:
    history = [item for item in get_health_metric_history(conn, metric, BASELINE_DAYS + 7) if item["date"] <= today.isoformat()]
    if not history:
        return None
    latest = history[0]
    cutoff = (datetime.strptime(latest["date"], "%Y-%m-%d").date() - timedelta(days=BASELINE_DAYS)).isoformat()
    before = [item["value"] for item in history[1:] if item["date"] >= cutoff]
    low, high = _typical(before)
    week_start = (today - timedelta(days=6)).isoformat()
    return {
        "date": latest["date"],
        "value": latest["value"],
        "baseline": round(mean(before), 1) if len(before) >= 5 else None,
        "typical_low": low,
        "typical_high": high,
        # The last 7 days that have a reading, oldest first.
        "days": [{"date": item["date"], "value": item["value"]} for item in reversed(history) if item["date"] >= week_start],
    }


def _training(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Every session of the last week, any sport. Lifts carry their exercises and working-set
    counts; the phone maps exercise names to muscles, as it does on Activity detail."""
    from .phone_today import sport_of  # phone_today imports this module

    start = (today - timedelta(days=TRAINING_DAYS - 1)).isoformat()
    end = today.isoformat()
    lifts: dict[str, dict] = {}
    unlinked: list[dict] = []
    for session in _session_index(conn):
        day = session["workout_date"][:10]
        if not start <= day <= end:
            continue
        exercises = [
            {"name": item["exercise_name"], "sets": len(_working_sets(item))}
            for item in session.get("exercises", [])
        ]
        entry = {"title": session.get("title"), "exercises": [item for item in exercises if item["sets"]]}
        linked = (session.get("matched_activity") or {}).get("id")
        if linked:
            lifts[str(linked)] = entry
        else:
            unlinked.append({"date": day, "sport": "strength", "minutes": round((session.get("total_duration_seconds") or 0) / 60) or None, **entry})
    items = []
    try:
        rows = conn.execute(
            "SELECT id, date, type, workout_intent, name, duration_min FROM activities WHERE date BETWEEN ? AND ? ORDER BY date, id",
            (start, end),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        guided = guided_label_for_activity(conn, str(row["id"]))
        lift = lifts.pop(str(row["id"]), None)
        if guided:
            sport = "rehab" if guided["context_label"] == REHAB_LABEL else "mobility"
        elif lift:
            sport = "strength"
        else:
            sport = sport_of(row["type"], row["workout_intent"])
        items.append({
            "date": row["date"],
            "sport": sport,
            "title": (lift or {}).get("title") or (guided or {}).get("title") or row["name"],
            "minutes": round(row["duration_min"]) if row["duration_min"] else None,
            "exercises": (lift or {}).get("exercises", []),
        })
    return sorted(items + unlinked, key=lambda item: item["date"])


def _issues(conn: sqlite3.Connection) -> list[dict]:
    """Active injuries that protect a body area (knee, hip, back...), for the pin on the map."""
    return [
        {"id": row["id"], "title": row["title"], "side": row.get("side"), "since": row.get("started_on"), "areas": areas}
        for row in _active_issue_rows(conn)
        if row.get("protects_area", 1) and (areas := detect_body_areas(f"{row['title']} {row['body_area'] or ''}"))
    ]


def _sleep_debt(readiness: dict) -> Optional[dict]:
    """The readiness sleep-debt numbers, for the Tonight card's target."""
    factor = next((item for item in readiness.get("factors", []) if item.get("key") == "sleep_debt"), None)
    summary = (factor or {}).get("summary") or {}
    if summary.get("debt_hours") is None:
        return None
    return {
        "hours": summary["debt_hours"],
        "nights": summary.get("nights"),
        "need_h": summary.get("baseline_hours"),
        "status": summary.get("status"),
    }


def build_phone_body(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    load = build_training_load_summary(conn, days=LOAD_DAYS, today=today)
    readiness = (build_readiness_summary(conn, training_load_summary=load).get("score") or {})
    current = load.get("current") or {}
    ratio = load.get("ratio") or {}
    return {
        "date": today.isoformat(),
        "readiness": {
            "level": readiness.get("level", "unknown"),
            "label": readiness.get("label", "No read"),
            "advice": readiness.get("advice"),
            "points": readiness.get("points", 0),
            "factors": [
                {"key": item["key"], "label": item["label"], "detail": item["detail"], "tone": item["tone"], "points": item.get("points", 0)}
                for item in readiness.get("factors", [])
            ],
        },
        "sleep": _last_night(conn, today),
        "sleep_debt": _sleep_debt(readiness),
        "vitals": {
            "resting_hr": _vital(conn, "resting_hr", today),
            "hrv": _vital(conn, "hrv", today),
            "steps": _vital(conn, "steps", today),
            "sleep": _vital(conn, "sleep", today),
        },
        "training": _training(conn, today),
        "issues": _issues(conn),
        "load": {
            "fitness": current.get("fitness", 0),
            "fatigue": current.get("fatigue", 0),
            "form": current.get("form", 0),
            "ratio": ratio.get("value", 0),
            "ratio_status": ratio.get("status", "low"),
            "chart": [
                {"date": item["date"], "load": item["load"], "fitness": item["ctl"], "fatigue": item["atl"], "form": item["tsb"]}
                for item in load.get("chart", [])
            ],
        },
    }
