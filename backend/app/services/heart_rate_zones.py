import copy
import json
import sqlite3
from typing import Optional

from ..request_cache import blob_memo


SUPPORTED_MODALITIES = {
    "Run": "run",
    "Ride": "ride",
    "VirtualRide": "ride",
}

# Where zones 2-5 start, in bpm. Zone 1 is everything below the first value.
DEFAULT_HR_ZONE_STARTS = {
    "run": [150, 163, 173, 183],
    "ride": [140, 153, 163, 173],
}
HR_ZONE_KEYS = ("zone1", "zone2", "zone3", "zone4", "zone5")
MIN_ZONE_BPM = 60
MAX_ZONE_BPM = 230
PERFORMANCE_SETTINGS_KEY = "performance_settings"


def normalize_hr_zone_starts(raw, modality: str) -> list[int]:
    """Four strictly rising whole bpm values, or the defaults when anything is off."""
    try:
        starts = [int(round(float(value))) for value in raw]
    except (TypeError, ValueError):
        return list(DEFAULT_HR_ZONE_STARTS[modality])
    valid = (
        len(starts) == 4
        and all(MIN_ZONE_BPM <= value <= MAX_ZONE_BPM for value in starts)
        and all(low < high for low, high in zip(starts, starts[1:]))
    )
    return starts if valid else list(DEFAULT_HR_ZONE_STARTS[modality])


def zone_definitions_from_starts(starts: list[int]) -> list[dict]:
    lowers = [None, *starts]
    uppers = [*(value - 1 for value in starts), None]
    return [
        {
            "key": key,
            "label": f"Zone {index + 1}",
            "lower_bpm": lowers[index],
            "upper_bpm": uppers[index] if index > 0 else starts[0],
            "highlight": key == "zone2",
        }
        for index, key in enumerate(HR_ZONE_KEYS)
    ]


def hr_zone_starts(conn: sqlite3.Connection) -> dict[str, list[int]]:
    """The athlete's saved zones (Athlete page), falling back to the defaults."""
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (PERFORMANCE_SETTINGS_KEY,)).fetchone()
        saved = (json.loads(row[0]) or {}).get("heart_rate_zones") if row and row[0] else None
    except (sqlite3.OperationalError, json.JSONDecodeError, AttributeError):
        saved = None
    saved = saved if isinstance(saved, dict) else {}
    return {modality: normalize_hr_zone_starts(saved.get(modality), modality) for modality in DEFAULT_HR_ZONE_STARTS}


def hr_zone_definitions(conn: sqlite3.Connection, modality: str) -> list[dict]:
    return zone_definitions_from_starts(hr_zone_starts(conn)[modality])


def hr_zone_top(conn: sqlite3.Connection, modality: str, key: str) -> Optional[int]:
    return next((zone["upper_bpm"] for zone in hr_zone_definitions(conn, modality) if zone["key"] == key), None)


def run_hr_cap(conn: sqlite3.Connection) -> int:
    """Easy runs stay at or below the top of running zone 2."""
    return hr_zone_top(conn, "run", "zone2")


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


def _classify_zone(hr_value: float, starts: list[int]) -> str:
    return HR_ZONE_KEYS[sum(1 for start in starts if hr_value >= start)]


def _summarize_zone2(zone2_pct: int, dominant_zone_key: Optional[str]) -> str:
    if zone2_pct >= 60:
        return "Mostly zone 2"
    if dominant_zone_key == "zone2" or zone2_pct >= 35:
        return "Meaningful zone 2 time"
    return "Limited zone 2 time"


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

    streams_json = detail_row["streams_json"] if detail_row else None
    if not streams_json:
        return _zone_summary(modality, [], None)
    starts = hr_zone_starts(conn)[modality]
    # Every plan view recounts the same streams second by second; the zones are part of the key.
    return copy.deepcopy(
        blob_memo(f"hr_zones:{modality}:{starts}", streams_json, lambda: _zone_summary(modality, starts, json.loads(streams_json)))
    )


def _zone_summary(modality: str, starts: list[int], streams: Optional[dict]) -> dict:
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

    zone_definitions = zone_definitions_from_starts(starts)
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
        zone_key = _classify_zone(hr, starts)
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
                "lower_bpm": lower_bpm,
                "upper_bpm": upper_bpm,
            }
        )

    zone2 = next(item for item in zones if item["key"] == "zone2")
    return {
        "available": True,
        "state": "available",
        "summary": _summarize_zone2(zone2["pct"], dominant_zone_key),
        "reason": None,
        "modality": modality,
        "zone_starts_bpm": list(starts),
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

    totals_by_zone = {key: 0 for key in HR_ZONE_KEYS}
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
    # Runs and rides each count against their own zones; the labels are shared.
    for zone in zone_definitions_from_starts(DEFAULT_HR_ZONE_STARTS["run"]):
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
