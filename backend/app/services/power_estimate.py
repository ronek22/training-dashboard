"""Estimated power for outdoor rides without a power meter.

A simple steady-state physics model turns the stored speed, distance and altitude
streams into watts: rolling resistance + gravity + air drag + the change in kinetic
energy, divided by drivetrain efficiency, floored at 0 (coasting or braking). Wind,
drafting and road surface are unknown, so the result is an estimate:

- it is used for training load and ride type only, always labelled as estimated;
- it never touches the stored streams, so personal records, the power curve and the
  FTP estimate (which all read measured ``watts`` streams) cannot see it.

Only rides with a recorded ``velocity_smooth`` stream are estimated. Old exports
whose speed would have to be derived from GPS distance disagreed with Strava's own
estimate by ~30%, so they keep the heart-rate fallback.

Calibration (``calibration_report``) runs the same model over VirtualRides, which
carry both measured power and the speed and elevation it produced.
"""

from __future__ import annotations

import math
import sqlite3
import threading
from collections import OrderedDict
from statistics import median
from typing import Any, Optional

from .power_trends import _confirmed_power_meter, _decode_json, _finite_number, _stream_values

MODEL_VERSION = "physics-v1"
G = 9.80665
AIR_DENSITY = 1.2  # kg/m³, ~15 °C at sea level; colder air is a little denser
DEFAULT_RIDER_KG = 80.0
MAX_WATTS = 1500.0
MOVING_SPEED = 0.5  # m/s; slower is standing still
MAX_SAMPLE_GAP_SECONDS = 10.0  # a longer gap is a stop, not riding
GRADE_HALF_WINDOW = 10  # samples either side for the grade, so altitude noise averages out
# Samples either side for speed. Watch-recorded speed jumps ~0.4 m/s every second; unsmoothed,
# the acceleration term turns that noise into phantom watts (coasting can't cancel it out).
SPEED_HALF_WINDOW = 4
MIN_GRADE_DISTANCE_M = 5.0
MAX_GRADE = 0.25
MIN_MOVING_SECONDS = 10 * 60
NP_WINDOW_SECONDS = 30

# cda m², crr, bike kg, drivetrain efficiency.
BIKE_PROFILES = {
    # Upright position on a hybrid (the outdoor bike is a Canyon Pathlite).
    "hybrid": {"cda": 0.40, "crr": 0.006, "bike_kg": 13.0, "efficiency": 0.97},
    "road": {"cda": 0.32, "crr": 0.004, "bike_kg": 8.5, "efficiency": 0.97},
    # Zwift's world: no drivetrain loss, a road bike on smooth tarmac. Used for calibration.
    "virtual": {"cda": 0.26, "crr": 0.004, "bike_kg": 8.0, "efficiency": 1.0},
}
DEFAULT_BIKE = "hybrid"

# Stated error band from the calibration on rides with measured power: the median ride's
# estimated normalized power within this fraction of the measured one.
CALIBRATION_BAND = 0.15
DRAFTING_NAMES = ("group ride", "pacer", "meetup", "race")


def instant_power(speed: float, prev_speed: float, dt: float, grade: float, mass_kg: float, profile: dict) -> float:
    """Watts at the pedals to hold ``speed`` (m/s) on ``grade`` after accelerating from ``prev_speed``."""
    if speed < MOVING_SPEED:
        return 0.0
    theta = math.atan(max(-MAX_GRADE, min(MAX_GRADE, grade)))
    rolling = mass_kg * G * profile["crr"] * math.cos(theta) * speed
    climbing = mass_kg * G * math.sin(theta) * speed
    drag = 0.5 * AIR_DENSITY * profile["cda"] * speed ** 3
    accelerating = mass_kg * (speed * speed - prev_speed * prev_speed) / (2 * dt) if dt > 0 else 0.0
    watts = (rolling + climbing + drag + accelerating) / profile["efficiency"]
    return max(0.0, min(watts, MAX_WATTS))


def _smoothed(values: list[Optional[float]]) -> list[Optional[float]]:
    """Centered moving average; a missing sample stays missing."""
    out: list[Optional[float]] = []
    for i, value in enumerate(values):
        if value is None:
            out.append(None)
            continue
        window = [item for item in values[max(0, i - SPEED_HALF_WINDOW): i + SPEED_HALF_WINDOW + 1] if item is not None]
        out.append(sum(window) / len(window))
    return out


def estimated_watts(streams: Any, rider_kg: float, bike: str = DEFAULT_BIKE) -> Optional[dict]:
    """Return {"time": [...], "watts": [...]} at the stream's own samples, or None.

    A sample is None where it cannot be estimated (missing data or a stop), so the
    rolling-window readers end a run there, as they do for a real power stream.
    """
    times = _stream_values(streams, "time")
    speeds = _stream_values(streams, "velocity_smooth")
    distances = _stream_values(streams, "distance")
    altitudes = _stream_values(streams, "altitude")
    count = min(len(times), len(speeds), len(distances), len(altitudes))
    if count < 2:
        return None
    profile = BIKE_PROFILES.get(bike, BIKE_PROFILES[DEFAULT_BIKE])
    mass = float(rider_kg) + profile["bike_kg"]
    t = [_finite_number(value) for value in times[:count]]
    v = _smoothed([_finite_number(value) for value in speeds[:count]])
    d = [_finite_number(value) for value in distances[:count]]
    h = [_finite_number(value) for value in altitudes[:count]]

    watts: list[Optional[float]] = [None]
    for i in range(1, count):
        dt = t[i] - t[i - 1] if t[i] is not None and t[i - 1] is not None else None
        if dt is None or not 0 < dt <= MAX_SAMPLE_GAP_SECONDS or v[i] is None or v[i - 1] is None:
            watts.append(None)
            continue
        lo, hi = max(0, i - GRADE_HALF_WINDOW), min(count - 1, i + GRADE_HALF_WINDOW)
        grade = 0.0
        if None not in (d[lo], d[hi], h[lo], h[hi]) and d[hi] - d[lo] > MIN_GRADE_DISTANCE_M:
            grade = (h[hi] - h[lo]) / (d[hi] - d[lo])
        watts.append(instant_power(v[i], v[i - 1], dt, grade, mass, profile))
    return {"time": list(times[:count]), "watts": watts}


def _summarize(stream: dict) -> Optional[dict]:
    """Moving-time average and 30 s normalized power of an estimated stream."""
    times, watts = stream["time"], stream["watts"]
    seconds = 0.0
    work = 0.0
    per_second: list[float] = []
    for i in range(1, len(times)):
        if watts[i] is None:
            continue
        dt = float(times[i]) - float(times[i - 1])
        seconds += dt
        work += watts[i] * dt
        per_second.extend([watts[i]] * max(1, int(round(dt))))
    if seconds < MIN_MOVING_SECONDS:
        return None
    rolling = []
    total = 0.0
    for i, value in enumerate(per_second):
        total += value
        if i >= NP_WINDOW_SECONDS:
            total -= per_second[i - NP_WINDOW_SECONDS]
        if i >= NP_WINDOW_SECONDS - 1:
            rolling.append(total / NP_WINDOW_SECONDS)
    normalized = (sum(value ** 4 for value in rolling) / len(rolling)) ** 0.25 if rolling else work / seconds
    return {"avg_watts": work / seconds, "normalized_power": normalized, "moving_seconds": round(seconds)}


def estimate_from_streams(streams: Any, rider_kg: float, bike: str = DEFAULT_BIKE) -> Optional[dict]:
    stream = estimated_watts(streams, rider_kg, bike)
    summary = _summarize(stream) if stream else None
    if not summary:
        return None
    return {
        "avg_watts": round(summary["avg_watts"], 1),
        "normalized_power": round(summary["normalized_power"], 1),
        "moving_seconds": summary["moving_seconds"],
        "rider_kg": round(float(rider_kg), 1),
        "bike": bike,
        "model": MODEL_VERSION,
        "estimated": True,
    }


def estimated_tss(estimate: dict, ftp: Optional[float], duration_min: float = 0) -> Optional[float]:
    """TSS from the estimated normalized power, scored like a measured ride."""
    if not estimate or not ftp:
        return None
    hours = max(estimate["moving_seconds"] / 3600, float(duration_min or 0) / 60)
    intensity = min(estimate["normalized_power"] / ftp, 1.5)
    return hours * intensity ** 2 * 100


def rider_weight_on(conn: sqlite3.Connection, day: Optional[str]) -> float:
    """Latest logged body weight on or before ``day``; the first one after it; else the default."""
    day = str(day or "9999-12-31")[:10]
    row = conn.execute(
        "SELECT value FROM metrics WHERE metric = 'weight' AND date <= ? AND value > 0 ORDER BY date DESC LIMIT 1", (day,),
    ).fetchone() or conn.execute(
        "SELECT value FROM metrics WHERE metric = 'weight' AND value > 0 ORDER BY date ASC LIMIT 1",
    ).fetchone()
    return float(row["value"] if isinstance(row, sqlite3.Row) else row[0]) if row else DEFAULT_RIDER_KG


def estimable(activity_type: str, detail_json: Any, source_status: Any, streams: Any) -> bool:
    """An outdoor ride, no trainer flag, no power meter, and the streams the model needs."""
    if activity_type != "Ride" or not isinstance(streams, dict):
        return False
    detail = _decode_json(detail_json)
    if isinstance(detail, dict) and detail.get("trainer") is True:
        return False
    if _confirmed_power_meter(detail, activity_type=activity_type, source_status=source_status, streams_json=streams):
        return False
    return all(len(_stream_values(streams, key)) >= 2 for key in ("time", "velocity_smooth", "distance", "altitude"))


# Decoding a ride's streams is the slow part, so estimates are kept per process,
# keyed by the detail row's fetch stamp (a re-fetch changes it) and the rider weight.
_CACHE: "OrderedDict[tuple, Optional[dict]]" = OrderedDict()
_CACHE_SIZE = 4000
_CACHE_LOCK = threading.Lock()


def _cached(key: tuple, build) -> Optional[dict]:
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    value = build()
    with _CACHE_LOCK:
        _CACHE[key] = value
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return value


def _estimate_detail(activity_type: str, detail: Any, rider_kg: float) -> Optional[dict]:
    streams = _decode_json(detail["streams_json"])
    if not estimable(activity_type, detail["detail_json"], detail["source_status"], streams):
        return None
    return estimate_from_streams(streams, rider_kg)


def estimate_for_detail(conn: sqlite3.Connection, activity: dict, detail: Any) -> Optional[dict]:
    """Estimated power for one ride whose activity_details row is already in hand."""
    if activity.get("type") != "Ride" or detail is None or not detail["streams_json"]:
        return None
    rider_kg = rider_weight_on(conn, activity.get("date"))
    fetched_at = detail["fetched_at"] if "fetched_at" in detail.keys() else None
    key = (str(activity.get("id")), fetched_at, len(detail["streams_json"]), MODEL_VERSION, rider_kg)
    return _cached(key, lambda: _estimate_detail("Ride", detail, rider_kg))


def estimates_for(conn: sqlite3.Connection, activity_ids: list[str]) -> dict[str, dict]:
    """Estimated power for the given outdoor rides, by activity id (missing when not estimable)."""
    if not activity_ids:
        return {}
    found: dict[str, dict] = {}
    placeholders = ",".join("?" for _ in activity_ids)
    rows = conn.execute(
        f"""
        SELECT a.id, a.date, d.fetched_at, length(d.streams_json) AS streams_length
        FROM activities a JOIN activity_details d ON d.activity_id = a.id
        WHERE a.id IN ({placeholders}) AND a.type = 'Ride' AND d.streams_json IS NOT NULL
        """,
        list(activity_ids),
    ).fetchall()
    weights: dict[str, float] = {}
    for row in rows:
        day = str(row["date"])[:10]
        if day not in weights:
            weights[day] = rider_weight_on(conn, day)

        def build(activity_id=row["id"], rider_kg=weights[day]):
            detail = conn.execute(
                "SELECT detail_json, streams_json, source_status FROM activity_details WHERE activity_id = ?", (activity_id,),
            ).fetchone()
            return _estimate_detail("Ride", detail, rider_kg)

        estimate = _cached((row["id"], row["fetched_at"], row["streams_length"], MODEL_VERSION, weights[day]), build)
        if estimate:
            found[row["id"]] = estimate
    return found


def calibration_report(conn: sqlite3.Connection, min_minutes: float = 20) -> dict:
    """Run the model on rides with measured power and report how far off it is.

    VirtualRides carry Zwift's speed and elevation next to the trainer's power, so
    they are the rides that have both. Group rides, pacer rides and meetups are left
    out: Zwift drafting lowers the power they need, which outdoors-style physics
    cannot know (they read 15-35% high). The band is stated for the median ride.
    """
    rows = conn.execute(
        """
        SELECT a.id, a.name, a.date, a.duration_min, d.streams_json
        FROM activities a JOIN activity_details d ON d.activity_id = a.id
        WHERE a.type = 'VirtualRide' AND a.duration_min >= ? AND d.streams_json IS NOT NULL
        """,
        (min_minutes,),
    ).fetchall()
    avg_errors: list[float] = []
    np_errors: list[float] = []
    for row in rows:
        if any(word in str(row["name"] or "").lower() for word in DRAFTING_NAMES):
            continue
        streams = _decode_json(row["streams_json"])
        if len(_stream_values(streams, "watts")) < 2:
            continue
        estimate = estimate_from_streams(streams, rider_weight_on(conn, row["date"]), "virtual")
        watts = _measured_watts(streams)
        measured = _summarize({"time": _stream_values(streams, "time")[:len(watts)], "watts": watts})
        if not estimate or not measured or measured["avg_watts"] <= 0:
            continue
        avg_errors.append(estimate["avg_watts"] / measured["avg_watts"] - 1)
        np_errors.append(estimate["normalized_power"] / measured["normalized_power"] - 1)
    if not avg_errors:
        return {"rides": 0, "band": CALIBRATION_BAND, "within_band": None}
    np_abs = sorted(abs(value) for value in np_errors)
    return {
        "rides": len(avg_errors),
        "band": CALIBRATION_BAND,
        "avg_bias": round(median(avg_errors), 3),
        "avg_median_abs_error": round(median(abs(value) for value in avg_errors), 3),
        "np_bias": round(median(np_errors), 3),
        "np_median_abs_error": round(median(np_abs), 3),
        "np_p80_abs_error": round(np_abs[int(0.8 * (len(np_abs) - 1))], 3),
        "within_band": median(np_abs) <= CALIBRATION_BAND,
    }


def _measured_watts(streams: Any) -> list[Optional[float]]:
    times = _stream_values(streams, "time")
    watts = _stream_values(streams, "watts")
    out: list[Optional[float]] = [None]
    for i in range(1, min(len(times), len(watts))):
        dt = (_finite_number(times[i]) or 0) - (_finite_number(times[i - 1]) or 0)
        value = _finite_number(watts[i])
        out.append(value if value is not None and value >= 0 and 0 < dt <= MAX_SAMPLE_GAP_SECONDS else None)
    return out
