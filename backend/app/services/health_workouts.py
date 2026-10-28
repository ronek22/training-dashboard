"""Apple Watch workouts pushed by the TrainLog iOS app as soon as HealthKit saves them.

The phone sends each workout's summary and its per-second streams (heart rate, route, speed,
power, cadence) in the Strava stream shape, so load, charts and the estimated ride power work
before Strava has the activity. Strava stays the enrichment source: when its import arrives
later, ``find_activity_match`` links it to the same activity by start time and its title,
power and photos land on the row the watch created.

Each HealthKit workout UUID is stored as a ``healthkit`` source ref, so a re-push is a no-op.
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional

from ..repositories.activities import upsert_activity_row
from .activity_sources import find_activity_match, upsert_source_ref
from .healthfit import _activity_needs_fit_streams, _store_fit_streams
from .strava import seconds_to_pace, summarize_activity_streams, upsert_activity_stream_summary, zone2_from_activity

HEALTHKIT_SOURCE = "healthkit"
ACTIVITY_TYPES = {
    "Run", "Ride", "VirtualRide", "Walk", "Hike", "WeightTraining", "Workout",
    "Swim", "Yoga", "Rowing", "Elliptical",
}
STREAM_KEYS = ("time", "heartrate", "latlng", "altitude", "velocity_smooth", "distance", "cadence", "watts")
# Columns a watch workout fills on an activity Strava (or HealthFit) created first, only where empty.
FILL_COLUMNS = ("distance_km", "duration_min", "avg_hr", "max_hr", "avg_pace", "avg_watts", "elevation_m", "calories")


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN


def _rounded(value: Any, digits: int = 0) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    return round(number, digits) if digits else round(number)


def build_activity(workout: dict) -> dict:
    started_at = str(workout["start"])
    activity_type = workout.get("type") if workout.get("type") in ACTIVITY_TYPES else "Workout"
    distance_m = _number(workout.get("distance_m"))
    duration_s = _number(workout.get("duration_s"))
    avg_hr = _rounded(workout.get("avg_hr"))
    pace = None
    if activity_type == "Run" and distance_m and duration_s:
        pace = seconds_to_pace(duration_s / (distance_m / 1000))
    return {
        "id": f"{HEALTHKIT_SOURCE}:{str(workout['uuid']).lower()}",
        # The phone sends local time with its offset, so the first ten characters are the local day.
        "date": started_at[:10],
        "type": activity_type,
        "name": workout.get("name") or activity_type,
        "distance_km": round(distance_m / 1000, 2) if distance_m else None,
        "duration_min": round(duration_s / 60, 1) if duration_s is not None else None,
        "avg_hr": avg_hr,
        "max_hr": _rounded(workout.get("max_hr")),
        "avg_pace": pace,
        "avg_watts": _rounded(workout.get("avg_watts"), 1),
        "elevation_m": _rounded(workout.get("elevation_m")),
        "calories": _rounded(workout.get("energy_kcal")),
        "zone2": zone2_from_activity(activity_type, avg_hr),
        "notes": None,
    }


def build_streams(workout: dict) -> Optional[dict]:
    raw = workout.get("streams") or {}
    times = raw.get("time") or []
    if not times:
        return None
    streams = {}
    for key in STREAM_KEYS:
        values = raw.get(key)
        if values and len(values) == len(times) and any(value is not None for value in values):
            streams[key] = {"data": values}
    return streams if "time" in streams else None


def _fill_empty_fields(conn: sqlite3.Connection, activity_id: str, activity: dict) -> None:
    assignments = ", ".join(f"{column} = COALESCE({column}, ?)" for column in FILL_COLUMNS)
    conn.execute(
        f"UPDATE activities SET {assignments} WHERE id = ?",
        (*[activity[column] for column in FILL_COLUMNS], activity_id),
    )


def _store_summary(conn: sqlite3.Connection, activity_id: str, streams: Optional[dict]) -> None:
    if not streams or conn.execute(
        "SELECT 1 FROM activity_stream_summaries WHERE activity_id = ?", (activity_id,)
    ).fetchone():
        return
    from .dashboard import estimate_thresholds, intensity_bucket_from_hr

    row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    summary = summarize_activity_streams(dict(row), streams, estimate_thresholds(conn), intensity_bucket_from_hr)
    if summary:
        upsert_activity_stream_summary(conn, summary)


def _apply_workout(conn: sqlite3.Connection, workout: dict) -> dict:
    uuid = str(workout["uuid"]).lower()
    activity = build_activity(workout)
    streams = build_streams(workout)
    started_at = str(workout["start"])
    ref = conn.execute(
        "SELECT activity_id FROM activity_source_refs WHERE source = ? AND external_id = ?",
        (HEALTHKIT_SOURCE, uuid),
    ).fetchone()
    if ref and ref["activity_id"]:
        activity_id = ref["activity_id"]
        if conn.execute("SELECT 1 FROM activities WHERE id = ?", (activity_id,)).fetchone():
            return {"uuid": uuid, "action": "already_processed", "activity_id": activity_id}

    match = find_activity_match(conn, {**activity, "started_at": started_at})
    if match["status"] == "ambiguous":
        upsert_source_ref(
            conn, source=HEALTHKIT_SOURCE, external_id=uuid, activity_id=None, started_at=started_at,
            status="ambiguous", match_reason=match["reason"], metadata=_metadata(workout),
        )
        return {"uuid": uuid, "action": "ambiguous", "activity_id": None, "reason": match["reason"]}

    if match["status"] == "matched":
        activity_id = match["activity"]["id"]
        _fill_empty_fields(conn, activity_id, activity)
        action, reason = "linked", match["reason"]
    else:
        activity_id = activity["id"]
        upsert_activity_row(conn, activity, preserve_annotations=True)
        action, reason = "created", "New Apple Watch workout."
    if streams and _activity_needs_fit_streams(conn, activity_id):
        _store_fit_streams(conn, activity_id=activity_id, streams=streams, source=HEALTHKIT_SOURCE)
    _store_summary(conn, activity_id, streams)
    upsert_source_ref(
        conn, source=HEALTHKIT_SOURCE, external_id=uuid, activity_id=activity_id, started_at=started_at,
        status=action, match_reason=reason, metadata=_metadata(workout),
    )
    from .strength_workouts import auto_link_activity

    session_id = auto_link_activity(conn, activity_id)
    return {"uuid": uuid, "action": action, "activity_id": activity_id, "strength_session_id": session_id}


def _metadata(workout: dict) -> dict:
    return {key: workout.get(key) for key in ("source_bundle", "device", "end") if workout.get(key)}


def push_health_workouts(conn: sqlite3.Connection, payload: dict) -> dict:
    items = []
    for workout in payload.get("workouts") or []:
        if not workout.get("uuid") or not workout.get("start"):
            items.append({"uuid": workout.get("uuid"), "action": "error", "reason": "Missing uuid or start."})
            continue
        items.append(_apply_workout(conn, workout))
        conn.commit()
    counts: dict[str, int] = {}
    for item in items:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    return {"received_at": datetime.now().isoformat(), "counts": counts, "items": items}
