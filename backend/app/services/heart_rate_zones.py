import json
import sqlite3
from typing import Optional


SUPPORTED_MODALITIES = {
    "Run": "run",
    "Ride": "ride",
    "VirtualRide": "ride",
}

HR_ZONE_DEFINITIONS = {
    "run": [
        {"key": "zone1", "label": "Zone 1", "lower_bpm": None, "upper_bpm": 150, "highlight": False},
        {"key": "zone2", "label": "Zone 2", "lower_bpm": 150, "upper_bpm": 162, "highlight": True},
        {"key": "zone3", "label": "Zone 3", "lower_bpm": 163, "upper_bpm": 172, "highlight": False},
        {"key": "zone4", "label": "Zone 4", "lower_bpm": 173, "upper_bpm": 182, "highlight": False},
        {"key": "zone5", "label": "Zone 5", "lower_bpm": 183, "upper_bpm": None, "highlight": False},
    ],
    "ride": [
        {"key": "zone1", "label": "Zone 1", "lower_bpm": None, "upper_bpm": 140, "highlight": False},
        {"key": "zone2", "label": "Zone 2", "lower_bpm": 140, "upper_bpm": 152, "highlight": True},
        {"key": "zone3", "label": "Zone 3", "lower_bpm": 153, "upper_bpm": 162, "highlight": False},
        {"key": "zone4", "label": "Zone 4", "lower_bpm": 163, "upper_bpm": 172, "highlight": False},
        {"key": "zone5", "label": "Zone 5", "lower_bpm": 173, "upper_bpm": None, "highlight": False},
    ],
}


def _modality_for_activity(activity_type: Optional[str]) -> Optional[str]:
    return SUPPORTED_MODALITIES.get(activity_type or "")


def _format_range(lower_bpm: Optional[int], upper_bpm: Optional[int]) -> str:
    if lower_bpm is None and upper_bpm is None:
        return "—"
    if lower_bpm is None:
        return f"< {upper_bpm} bpm"
    if upper_bpm is None:
        return f"≥ {lower_bpm} bpm"
    return f"{lower_bpm}-{upper_bpm} bpm"


def _classify_zone(hr_value: float, modality: str) -> str:
    for zone in HR_ZONE_DEFINITIONS[modality]:
        lower = zone["lower_bpm"]
        upper = zone["upper_bpm"]
        if lower is None and upper is not None and hr_value < upper:
            return zone["key"]
        if upper is None and lower is not None and hr_value >= lower:
            return zone["key"]
        if lower is not None and upper is not None and lower <= hr_value <= upper:
            return zone["key"]
    return "zone5"


def _summarize_zone2(zone2_pct: int, dominant_zone_key: Optional[str]) -> str:
    if zone2_pct >= 60:
        return "Mostly zone 2"
    if dominant_zone_key == "zone2" or zone2_pct >= 35:
        return "Meaningful zone 2 time"
    return "Limited zone 2 time"


def _streams_from_detail_row(detail_row: Optional[sqlite3.Row]) -> Optional[dict]:
    if not detail_row or not detail_row["streams_json"]:
        return None
    return json.loads(detail_row["streams_json"])


def build_activity_heart_rate_zone_summary(
    conn: sqlite3.Connection,
    activity: dict,
    detail_row: Optional[sqlite3.Row],
    *,
    settings: Optional[dict] = None,
) -> dict:
    modality = _modality_for_activity(activity.get("type"))
    if modality is None:
        return {
            "available": False,
            "state": "unavailable",
            "summary": "Heart-rate zone review is only supported for runs and rides.",
            "reason": "unsupported_activity_type",
        }

    streams = _streams_from_detail_row(detail_row)
    if not streams:
        return {
            "available": False,
            "state": "unavailable",
            "summary": "Heart-rate zone review is unavailable until detail streams are cached for this activity.",
            "reason": "missing_streams",
        }

    time_stream = (streams.get("time") or {}).get("data") or []
    hr_stream = (streams.get("heartrate") or {}).get("data") or []
    if len(time_stream) < 2:
        return {
            "available": False,
            "state": "unavailable",
            "summary": "Heart-rate zone review needs a usable time stream.",
            "reason": "missing_time_stream",
        }
    if len(hr_stream) < 2:
        return {
            "available": False,
            "state": "unavailable",
            "summary": "Heart-rate zone review needs a heart-rate stream.",
            "reason": "missing_heartrate_stream",
        }

    zone_definitions = HR_ZONE_DEFINITIONS[modality]
    totals_by_zone = {zone["key"]: 0 for zone in zone_definitions}
    total_seconds = 0

    for index in range(1, min(len(time_stream), len(hr_stream))):
        previous_time = time_stream[index - 1]
        current_time = time_stream[index]
        hr_value = hr_stream[index]
        try:
            dt = max(int(float(current_time) - float(previous_time)), 1)
            hr = float(hr_value)
        except (TypeError, ValueError):
            continue
        if hr <= 0:
            continue
        zone_key = _classify_zone(hr, modality)
        totals_by_zone[zone_key] += dt
        total_seconds += dt

    if total_seconds <= 0:
        return {
            "available": False,
            "state": "unavailable",
            "summary": "Heart-rate zone review could not derive usable samples from this activity.",
            "reason": "empty_zone_samples",
        }

    zones = []
    dominant_zone_key = None
    dominant_seconds = -1
    for zone in zone_definitions:
        lower_bpm = zone["lower_bpm"]
        upper_bpm = zone["upper_bpm"]
        seconds = totals_by_zone[zone["key"]]
        if seconds > dominant_seconds:
            dominant_seconds = seconds
            dominant_zone_key = zone["key"]
        zones.append(
            {
                "key": zone["key"],
                "label": zone["label"],
                "seconds": seconds,
                "minutes": round(seconds / 60.0, 1),
                "pct": round((seconds / total_seconds) * 100),
                "highlight": zone["highlight"],
                "bpm_range": _format_range(lower_bpm, upper_bpm),
            }
        )

    zone2 = next(item for item in zones if item["key"] == "zone2")
    return {
        "available": True,
        "state": "available",
        "summary": _summarize_zone2(zone2["pct"], dominant_zone_key),
        "reason": None,
        "modality": modality,
        "lthr_bpm": None,
        "total_minutes": round(total_seconds / 60.0, 1),
        "zone2_minutes": zone2["minutes"],
        "zone2_pct": zone2["pct"],
        "dominant_zone_key": dominant_zone_key,
        "zones": zones,
    }


def build_recent_heart_rate_zone_summary(
    conn: sqlite3.Connection,
    *,
    days: int = 14,
    settings: Optional[dict] = None,
) -> dict:
    rows = conn.execute(
        """
        SELECT
            a.id,
            a.date,
            a.type,
            a.name,
            d.streams_json
        FROM activities a
        LEFT JOIN activity_details d ON d.activity_id = a.id
        WHERE a.date >= date('now', ?)
          AND a.type IN ('Run', 'Ride', 'VirtualRide')
        ORDER BY a.date DESC, a.created_at DESC
        """,
        (f"-{days} days",),
    ).fetchall()

    if not rows:
        return {
            "available": False,
            "state": "unavailable",
            "window_days": days,
            "summary": "No recent run or ride activities are available for heart-rate zone review.",
            "eligible_activities": 0,
            "usable_activities": 0,
            "unavailable_activities": 0,
            "zones": [],
            "zone2_minutes": 0.0,
            "zone2_hours": 0.0,
            "zone2_pct": 0,
        }

    totals_by_zone = {zone["key"]: 0 for zone in HR_ZONE_DEFINITIONS["run"]}
    total_seconds = 0
    usable_activities = 0
    unavailable_activities = 0

    for row in rows:
        summary = build_activity_heart_rate_zone_summary(conn, dict(row), row, settings=settings)
        if not summary["available"]:
            unavailable_activities += 1
            continue
        usable_activities += 1
        for zone in summary["zones"]:
            totals_by_zone[zone["key"]] += int(zone["seconds"])
            total_seconds += int(zone["seconds"])

    if usable_activities <= 0 or total_seconds <= 0:
        return {
            "available": False,
            "state": "unavailable",
            "window_days": days,
            "summary": "Recent heart-rate zone review is unavailable because no cached activities had usable streams and configuration.",
            "eligible_activities": len(rows),
            "usable_activities": 0,
            "unavailable_activities": unavailable_activities,
            "zones": [],
            "zone2_minutes": 0.0,
            "zone2_hours": 0.0,
            "zone2_pct": 0,
        }

    zones = []
    for zone in HR_ZONE_DEFINITIONS["run"]:
        seconds = totals_by_zone[zone["key"]]
        zones.append(
            {
                "key": zone["key"],
                "label": zone["label"],
                "seconds": seconds,
                "minutes": round(seconds / 60.0, 1),
                "pct": round((seconds / total_seconds) * 100),
                "highlight": zone["highlight"],
            }
        )

    zone2 = next(item for item in zones if item["key"] == "zone2")
    state = "complete" if unavailable_activities == 0 else "partial"
    coverage_copy = (
        f"Based on {usable_activities} of {len(rows)} recent heart-rate activities."
        if state == "partial"
        else f"Based on {usable_activities} recent heart-rate activities."
    )
    return {
        "available": True,
        "state": state,
        "window_days": days,
        "summary": f"{_summarize_zone2(zone2['pct'], 'zone2' if zone2['pct'] >= 35 else None)}. {coverage_copy}",
        "eligible_activities": len(rows),
        "usable_activities": usable_activities,
        "unavailable_activities": unavailable_activities,
        "zones": zones,
        "zone2_minutes": zone2["minutes"],
        "zone2_hours": round(zone2["minutes"] / 60.0, 1),
        "zone2_pct": zone2["pct"],
        "total_minutes": round(total_seconds / 60.0, 1),
    }
