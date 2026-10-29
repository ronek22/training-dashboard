"""The iOS app's Body screen: last night's sleep stages, vitals against their baselines,
training load (fitness, fatigue, form) and what drives today's readiness."""

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Optional

from .dashboard import build_training_load_summary
from .health_data import get_health_metric_history, get_sleep_history
from .readiness import build_readiness_summary

BASELINE_DAYS = 30
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
        "vitals": {
            "resting_hr": _vital(conn, "resting_hr", today),
            "hrv": _vital(conn, "hrv", today),
            "steps": _vital(conn, "steps", today),
            "sleep": _vital(conn, "sleep", today),
        },
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
