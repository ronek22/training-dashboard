"""Cycling-specific read of one ride for the activity detail page.

Power is only treated as measured when ``_confirmed_power_meter`` says so
(Strava's ``device_watts`` flag, or a backfilled VirtualRide watts stream).
Outdoor rides without a meter still carry Strava's *estimated* average power;
that is reported as ``power_source = "estimated"`` so the page can label it
and never use it for intensity, load, or power bests.
"""

from __future__ import annotations

import math
import sqlite3
from bisect import bisect_left, bisect_right
from typing import Any, Optional

from .aerobic_decoupling import EXCLUSION_REASONS, _environment, analyse_ride
from .ftp import ftp_on
from .power_trends import (
    POWER_EFFORT_LABELS,
    _best_effort_from_runs,
    _build_segments,
    _confirmed_power_meter,
    _decode_json,
    _stream_values,
    get_cycling_power_trends_data,
)

CYCLING_TYPES = {"Ride", "VirtualRide", "EBikeRide"}
# A short ladder from sprint to threshold; the full profile lives on Trends.
RIDE_POWER_DURATIONS = (15, 60, 300, 1200, 3600)


def _ftp_on(conn: sqlite3.Connection, day: Any) -> Optional[float]:
    """FTP in force on the ride date, matching the power-zone summary."""
    return ftp_on(conn, day)


def _power_records(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    try:
        profile = get_cycling_power_trends_data(conn)
    except sqlite3.Error:
        return {}
    return {record["duration_seconds"]: record for record in profile.get("records") or []}


def _route_segment(streams: Any, start_s: float, end_s: float) -> list[list[float]]:
    times = _stream_values(streams, "time")
    latlng = _stream_values(streams, "latlng")
    if not times or not latlng:
        return []
    try:
        numeric = [float(value) for value in times]
    except (TypeError, ValueError):
        return []
    first = bisect_left(numeric, start_s)
    last = bisect_right(numeric, end_s)
    segment = []
    for point in latlng[first:last]:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                segment.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                continue
    return segment


def _power_efforts(
    runs: list,
    streams: Any,
    activity_id: str,
    ftp: Optional[float],
    records: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    efforts = []
    for duration in RIDE_POWER_DURATIONS:
        effort = _best_effort_from_runs(runs, duration)
        if effort is None:
            continue
        watts = round(float(effort["watts"]), 1)
        record = records.get(duration)
        best_watts = float(record["watts"]) if record else None
        is_record = bool(record and str(record.get("activity_id")) == str(activity_id))
        item = {
            "duration_s": duration,
            "label": POWER_EFFORT_LABELS[duration],
            "watts": watts,
            "avg_hr": round(float(effort["avg_hr"])) if effort.get("avg_hr") is not None else None,
            "start_time_s": round(float(effort["start_seconds"]), 1),
            "end_time_s": round(float(effort["end_seconds"]), 1),
            "pct_of_ftp": round(watts / ftp * 100) if ftp else None,
            "best_watts": round(best_watts, 1) if best_watts is not None else None,
            "best_date": record.get("date") if record else None,
            "best_activity_id": str(record["activity_id"]) if record else None,
            "pct_of_best": round(watts / best_watts * 100) if best_watts else None,
            "is_record": is_record,
        }
        segment = _route_segment(streams, item["start_time_s"], item["end_time_s"])
        if segment:
            item["route_segment"] = segment
        efforts.append(item)
    return efforts


def _decoupling(streams: Any, ftp: Optional[float]) -> dict[str, Any]:
    result = analyse_ride(streams, ftp_watts=ftp)
    if not result.get("qualifies"):
        reason = result.get("reason")
        return {"available": False, "reason": reason, "reason_label": EXCLUSION_REASONS.get(reason)}
    return {
        "available": True,
        "decoupling_pct": result["decoupling_pct"],
        "coupled": result["decoupling_pct"] < 5,
        "efficiency": result["efficiency"],
        "first_half": result["first_half"],
        "second_half": result["second_half"],
        "analysed_min": result["analysed_min"],
    }


def build_ride_detail(
    conn: sqlite3.Connection,
    activity: dict,
    detail_row: Optional[sqlite3.Row],
    stream_summary: Optional[sqlite3.Row],
    *,
    power_records: Optional[dict[int, dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    """Return the ride block, or ``None`` for non-cycling activities."""
    activity_type = activity.get("type")
    if activity_type not in CYCLING_TYPES:
        return None

    detail = _decode_json(detail_row["detail_json"]) if detail_row else None
    streams_json = detail_row["streams_json"] if detail_row else None
    source_status = detail_row["source_status"] if detail_row and "source_status" in detail_row.keys() else None
    environment = _environment(activity_type, detail)
    measured = bool(streams_json) and _confirmed_power_meter(
        detail, activity_type=activity_type, source_status=source_status, streams_json=streams_json
    )
    ftp = _ftp_on(conn, activity.get("date"))
    hr_load = stream_summary["hr_trimp"] if stream_summary else None

    base = {
        "environment": environment,
        "ftp_watts": ftp,
        "hr_load": round(float(hr_load), 1) if hr_load is not None else None,
    }
    if not measured:
        estimated = activity.get("avg_watts")
        return {
            **base,
            "power_source": "estimated" if estimated else "none",
            "estimated_avg_watts": estimated,
            "power": None,
            "power_efforts": [],
            "decoupling": None,
        }

    streams = _decode_json(streams_json)
    runs = _build_segments(streams)
    normalized = stream_summary["normalized_power"] if stream_summary else None
    avg_watts = activity.get("avg_watts")
    tss = stream_summary["power_tss"] if stream_summary else None
    kilojoules = detail.get("kilojoules") if isinstance(detail, dict) else None
    if kilojoules is None and runs:
        kilojoules = sum(segment.watts * (segment.end - segment.start) for run in runs for segment in run) / 1000
    power = {
        "avg_watts": avg_watts,
        "normalized_watts": round(float(normalized)) if normalized else None,
        "intensity_factor": round(float(normalized) / ftp, 2) if normalized and ftp else None,
        "tss": round(float(tss)) if tss is not None else None,
        "variability_index": round(float(normalized) / float(avg_watts), 2) if normalized and avg_watts else None,
        "work_kj": round(float(kilojoules)) if kilojoules else None,
    }
    records = power_records if power_records is not None else _power_records(conn)
    return {
        **base,
        "power_source": "measured",
        "estimated_avg_watts": None,
        "power": power,
        "power_efforts": _power_efforts(runs, streams, str(activity.get("id")), ftp, records),
        "decoupling": _decoupling(streams, ftp),
    }
