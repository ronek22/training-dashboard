"""Indoor rides (Zwift, MyWhoosh…) for the iOS app to save into Apple Health.

They reach the backend through Strava, which has no way into Health, so the phone pulls them
from here and writes each one as an indoor cycling workout. Rides that came from an Apple Watch
workout (a ``healthkit`` source ref) are already in Health and are left out.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

STREAM_KEYS = ("heartrate", "watts", "cadence", "distance")


def _start(started_at: Optional[str], detail_json: Optional[str]) -> Optional[str]:
    value = started_at
    if not value and detail_json:
        try:
            value = json.loads(detail_json).get("start_date")
        except (ValueError, AttributeError):
            value = None
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _streams(streams_json: Optional[str]) -> Optional[dict]:
    if not streams_json:
        return None
    try:
        raw = json.loads(streams_json)
    except ValueError:
        return None
    time = (raw.get("time") or {}).get("data")
    if not time:
        return None
    streams: dict[str, Any] = {"time": time}
    for key in STREAM_KEYS:
        data = (raw.get(key) or {}).get("data")
        if data and len(data) == len(time) and any(value is not None for value in data):
            streams[key] = data
    return streams


def _work_kcal(streams: Optional[dict]) -> Optional[float]:
    """Mechanical work in kJ, which is close to the kcal burned on a bike (~24% efficiency)."""
    if not streams or "watts" not in streams:
        return None
    time, watts = streams["time"], streams["watts"]
    joules = 0.0
    for index in range(1, len(time)):
        value = watts[index]
        if value is not None:
            joules += value * min(max(time[index] - time[index - 1], 0), 10)
    return round(joules / 1000) or None


def list_indoor_rides(conn, since: str) -> dict:
    rows = conn.execute(
        """
        SELECT a.id, a.name, a.date, a.duration_min, a.distance_km, a.calories, a.avg_hr,
               d.streams_json, d.detail_json,
               (SELECT r.started_at FROM activity_source_refs r
                 WHERE r.activity_id = a.id AND r.source = 'strava' LIMIT 1) AS started_at
          FROM activities a
          LEFT JOIN activity_details d ON d.activity_id = a.id
         WHERE a.type = 'VirtualRide' AND a.date >= ?
           AND NOT EXISTS (SELECT 1 FROM activity_source_refs h
                            WHERE h.activity_id = a.id AND h.source = 'healthkit')
         ORDER BY a.date, a.id
        """,
        (since,),
    ).fetchall()
    rides = []
    for row in rows:
        start = _start(row["started_at"], row["detail_json"])
        if start is None:
            continue
        streams = _streams(row["streams_json"])
        duration_s = streams["time"][-1] if streams else None
        if not duration_s and row["duration_min"]:
            duration_s = round(row["duration_min"] * 60)
        if not duration_s:
            continue
        rides.append({
            "id": str(row["id"]),
            "name": row["name"],
            "start": start,
            "duration_s": duration_s,
            "distance_m": round(row["distance_km"] * 1000) if row["distance_km"] else None,
            "energy_kcal": row["calories"] or _work_kcal(streams),
            "avg_hr": row["avg_hr"],
            "streams": streams,
        })
    return {"rides": rides}
