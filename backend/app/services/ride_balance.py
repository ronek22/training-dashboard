"""Ride-type balance: recent rides split into Z2, sweet spot, VO2 and recovery.

Each ride is classified from what was actually ridden. A trusted power stream
is read against the FTP estimate from recent training efforts (no test), an
outdoor ride without a power meter falls back to its heart-rate stream, and a
ride with neither uses its intent label or averages. A type is flagged when it
showed up earlier in the window but not in the last two weeks.
"""

from __future__ import annotations

import sqlite3
from bisect import bisect_right
from datetime import date, timedelta
from typing import Any, Optional

from .heart_rate_zones import HR_ZONE_DEFINITIONS
from .power_trends import MAX_STREAM_GAP_SECONDS, _confirmed_power_meter, _decode_json, _finite_number, _stream_values

RIDE_TYPES = ("Ride", "VirtualRide")
TYPES = (
    ("z2", "Z2"),
    ("sweet_spot", "Sweet spot"),
    ("vo2", "VO2"),
    ("recovery", "Recovery"),
)
TYPE_LABELS = dict(TYPES)
DEFAULT_WEEKS = 6
MIN_RIDE_MINUTES = 20  # shorter rides are warm-up or cool-down fragments
GONE_AFTER_DAYS = 14

# Power, as fractions of the reference FTP, on a 60 s rolling average.
SWEET_SPOT_FTP = 0.85
VO2_FTP = 1.10
RECOVERY_MAX_FTP = 0.62
POWER_WINDOW_SECONDS = 60
# Heart rate on a 30 s rolling average; the bands come from the ride HR zones.
HR_WINDOW_SECONDS = 30
RECOVERY_MAX_AVG_HR = 130
RECOVERY_MAX_MINUTES = 75
# How much work makes a ride count as that type.
SWEET_SPOT_BLOCK_SECONDS = 5 * 60
SWEET_SPOT_MIN_SECONDS = 20 * 60
VO2_BLOCK_SECONDS = 60
VO2_MIN_POWER_SECONDS = 5 * 60
VO2_MIN_HR_SECONDS = 3 * 60

INTENT_TYPES = {
    "recovery": "recovery",
    "easy": "z2",
    "long": "z2",
    "endurance": "z2",
    "tempo": "sweet_spot",
    "sweet_spot": "sweet_spot",
    "threshold": "sweet_spot",
    "race_specific": "sweet_spot",
    "interval": "vo2",
    "vo2": "vo2",
}


def _hr_bands() -> tuple[float, float]:
    zones = {zone["key"]: zone for zone in HR_ZONE_DEFINITIONS["ride"]}
    return float(zones["zone3"]["lower_bpm"]), float(zones["zone5"]["lower_bpm"])


def _runs(streams: Any, key: str) -> list[list[tuple[float, float, float]]]:
    """Contiguous (start, end, value) intervals; a gap or bad sample ends a run."""
    times = _stream_values(streams, "time")
    values = _stream_values(streams, key)
    runs: list[list[tuple[float, float, float]]] = []
    current: list[tuple[float, float, float]] = []
    for index in range(min(len(times), len(values)) - 1):
        start, end, value = _finite_number(times[index]), _finite_number(times[index + 1]), _finite_number(values[index])
        if start is None or end is None or value is None or value < 0 or not 0 < end - start <= MAX_STREAM_GAP_SECONDS:
            if current:
                runs.append(current)
            current = []
            continue
        current.append((start, end, value))
    if current:
        runs.append(current)
    return runs


def _band_seconds(runs, window: float, low: float, high: Optional[float], min_block: float) -> float:
    """Seconds whose trailing rolling average sits in [low, high), counted only in blocks of min_block or longer."""
    total = 0.0
    for run in runs:
        starts = [segment[0] for segment in run]
        prefix = [0.0]
        for start, end, value in run:
            prefix.append(prefix[-1] + value * (end - start))

        def area_until(point: float) -> float:
            index = max(0, min(bisect_right(starts, point) - 1, len(run) - 1))
            start, _, value = run[index]
            return prefix[index] + (point - start) * value

        block = 0.0
        for start, end, _ in run:
            in_band = False
            if end - run[0][0] >= window:
                average = (area_until(end) - area_until(end - window)) / window
                in_band = average >= low and (high is None or average < high)
            if in_band:
                block += end - start
                continue
            if block >= min_block:
                total += block
            block = 0.0
        if block >= min_block:
            total += block
    return total


def _from_power(streams: Any, ftp: float) -> dict[str, Any]:
    runs = _runs(streams, "watts")
    vo2 = _band_seconds(runs, POWER_WINDOW_SECONDS, ftp * VO2_FTP, None, VO2_BLOCK_SECONDS)
    sweet = _band_seconds(runs, POWER_WINDOW_SECONDS, ftp * SWEET_SPOT_FTP, ftp * VO2_FTP, SWEET_SPOT_BLOCK_SECONDS)
    seconds = sum(end - start for run in runs for start, end, _ in run)
    average = sum(value * (end - start) for run in runs for start, end, value in run) / seconds if seconds else None
    return {"vo2_seconds": vo2, "sweet_spot_seconds": sweet, "average": average, "vo2_needed": VO2_MIN_POWER_SECONDS}


def _from_heart_rate(streams: Any) -> dict[str, Any]:
    sweet_low, vo2_low = _hr_bands()
    runs = _runs(streams, "heartrate")
    vo2 = _band_seconds(runs, HR_WINDOW_SECONDS, vo2_low, None, VO2_BLOCK_SECONDS)
    sweet = _band_seconds(runs, HR_WINDOW_SECONDS, sweet_low, vo2_low, SWEET_SPOT_BLOCK_SECONDS)
    return {"vo2_seconds": vo2, "sweet_spot_seconds": sweet, "vo2_needed": VO2_MIN_HR_SECONDS}


def _intent(value: Any) -> Optional[str]:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return INTENT_TYPES.get(key)


def classify_ride(ride: dict[str, Any], detail: Optional[sqlite3.Row], ftp: Optional[float]) -> dict[str, Any]:
    """Return {type, basis, reason} for one ride. Hard work found in a stream wins over the label."""
    minutes = float(ride.get("duration_min") or 0)
    intent = _intent(ride.get("workout_intent"))
    streams = _decode_json(detail["streams_json"]) if detail is not None and detail["streams_json"] else None
    power_ok = bool(
        streams and ftp and _confirmed_power_meter(
            detail["detail_json"], activity_type=ride["type"], source_status=detail["source_status"], streams_json=streams,
        )
    )
    evidence = None
    basis = None
    if power_ok:
        evidence, basis = _from_power(streams, ftp), "power"
    elif streams and len(_stream_values(streams, "heartrate")) >= 2:
        evidence, basis = _from_heart_rate(streams), "heart_rate"

    if evidence:
        if evidence["vo2_seconds"] >= evidence["vo2_needed"]:
            return {"type": "vo2", "basis": basis, "reason": f"{round(evidence['vo2_seconds'] / 60)} min at VO2 effort"}
        if evidence["sweet_spot_seconds"] >= SWEET_SPOT_MIN_SECONDS:
            return {"type": "sweet_spot", "basis": basis, "reason": f"{round(evidence['sweet_spot_seconds'] / 60)} min at sweet spot or above"}
        if intent == "recovery":
            return {"type": "recovery", "basis": "intent", "reason": "Marked as a recovery ride"}
        if minutes <= RECOVERY_MAX_MINUTES:
            if basis == "power" and evidence["average"] is not None and evidence["average"] <= ftp * RECOVERY_MAX_FTP:
                return {"type": "recovery", "basis": basis, "reason": f"Short and easy: {round(evidence['average'])} W average"}
            if basis == "heart_rate" and ride.get("avg_hr") and ride["avg_hr"] <= RECOVERY_MAX_AVG_HR:
                return {"type": "recovery", "basis": basis, "reason": f"Short and easy: {round(ride['avg_hr'])} bpm average"}
        return {"type": "z2", "basis": basis, "reason": "Steady aerobic riding"}

    if intent:
        return {"type": intent, "basis": "intent", "reason": f"Marked as {ride.get('workout_intent')}"}
    if minutes <= RECOVERY_MAX_MINUTES and ride.get("avg_hr") and ride["avg_hr"] <= RECOVERY_MAX_AVG_HR:
        return {"type": "recovery", "basis": "average", "reason": f"Short and easy: {round(ride['avg_hr'])} bpm average"}
    return {"type": "z2", "basis": "average", "reason": "No stream or label; counted as aerobic riding"}


def _reference_ftp(conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    try:
        from .personal_records import build_personal_records

        estimate = build_personal_records(conn, today)["cycling_power"]["ftp_estimate"]
    except (sqlite3.OperationalError, KeyError):
        estimate = {}
    if estimate.get("available") and estimate.get("watts"):
        return {"watts": float(estimate["watts"]), "source": "estimate", "basis": estimate.get("basis")}
    stored = estimate.get("stored") or {}
    if stored.get("available") and stored.get("watts"):
        return {"watts": float(stored["watts"]), "source": "stored", "basis": "stored FTP"}
    return {"watts": None, "source": None, "basis": None}


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def build_ride_balance(conn: sqlite3.Connection, today: Optional[date] = None, weeks: int = DEFAULT_WEEKS) -> dict[str, Any]:
    today = today or date.today()
    weeks = max(4, min(int(weeks or DEFAULT_WEEKS), 8))
    current_week = _week_start(today)
    window_start = current_week - timedelta(weeks=weeks - 1)
    reference = _reference_ftp(conn, today)

    rows = conn.execute(
        f"""
        SELECT a.id, a.date, a.type, a.name, a.duration_min, a.avg_hr, a.workout_intent,
               d.detail_json, d.streams_json, d.source_status
        FROM activities AS a LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ({",".join("?" for _ in RIDE_TYPES)}) AND a.date >= ? AND a.date <= ?
        ORDER BY a.date, a.id
        """,
        (*RIDE_TYPES, window_start.isoformat(), today.isoformat()),
    ).fetchall()

    week_rows = [
        {"week_start": (window_start + timedelta(weeks=i)).isoformat(), "partial": i == weeks - 1,
         "counts": {key: 0 for key, _ in TYPES}, "minutes": {key: 0 for key, _ in TYPES}, "rides": []}
        for i in range(weeks)
    ]
    rides = []
    for row in rows:
        ride = dict(row)
        minutes = float(ride.get("duration_min") or 0)
        if minutes < MIN_RIDE_MINUTES:
            continue
        has_detail = row["streams_json"] is not None or row["detail_json"] is not None
        result = classify_ride(ride, row if has_detail else None, reference["watts"])
        ride_day = date.fromisoformat(str(ride["date"])[:10])
        week = week_rows[(_week_start(ride_day) - window_start).days // 7]
        week["counts"][result["type"]] += 1
        week["minutes"][result["type"]] += round(minutes)
        item = {"id": ride["id"], "date": ride_day.isoformat(), "name": ride["name"], "minutes": round(minutes), **result}
        week["rides"].append(item)
        rides.append(item)

    recent_cutoff = (today - timedelta(days=GONE_AFTER_DAYS - 1)).isoformat()
    types = []
    for key, label in TYPES:
        own = [ride for ride in rides if ride["type"] == key]
        last = own[-1]["date"] if own else None
        status = "absent" if not own else "gone" if last < recent_cutoff else "ok"
        types.append({
            "key": key, "label": label, "rides": len(own), "minutes": sum(ride["minutes"] for ride in own),
            "last_date": last, "days_since": (today - date.fromisoformat(last)).days if last else None, "status": status,
        })

    recent_rides = [ride for ride in rides if ride["date"] >= recent_cutoff]
    flags = []
    if rides and not recent_rides:
        flags.append({"type": None, "message": f"No rides in the last {GONE_AFTER_DAYS} days, so every type has dropped out."})
    else:
        for item in types:
            if item["status"] == "gone":
                flags.append({"type": item["key"], "message": f"{item['label']} has disappeared: the last one was {item['days_since']} days ago ({item['last_date']})."})

    if not rides:
        summary = f"No rides in the last {weeks} weeks."
    elif flags:
        summary = flags[0]["message"]
    else:
        present = [item["label"] for item in types if item["status"] == "ok"]
        missing = [item["label"] for item in types if item["status"] == "absent"]
        summary = f"{len(rides)} rides: {', '.join(present)} all in the last two weeks."
        if missing:
            summary += f" No {' or '.join(missing)} in {weeks} weeks."

    ftp_note = (
        f"{round(reference['watts'])} W from {reference['basis']} in recent rides (no test)" if reference["source"] == "estimate"
        else f"stored FTP {round(reference['watts'])} W (no recent 20 or 60 min effort)" if reference["source"] == "stored"
        else "no FTP reference, so heart rate only"
    )
    sweet_low, vo2_low = _hr_bands()
    method = (
        f"Each ride of {MIN_RIDE_MINUTES}+ min gets one type from what you rode. With a power meter: 60 s power at "
        f"{round(VO2_FTP * 100)}%+ of FTP for {VO2_MIN_POWER_SECONDS // 60}+ min is VO2, and {round(SWEET_SPOT_FTP * 100)}%+ in "
        f"5 min blocks for {SWEET_SPOT_MIN_SECONDS // 60}+ min is sweet spot. FTP is {ftp_note}. Without power, heart rate "
        f"≥ {vo2_low:g} bpm counts as VO2 and {sweet_low:g}–{vo2_low - 1:g} bpm as sweet spot. Short, easy rides and rides "
        f"marked recovery count as recovery; the rest is Z2. A type is flagged when none has happened in {GONE_AFTER_DAYS} days."
    )
    return {
        "window_start": window_start.isoformat(),
        "today": today.isoformat(),
        "weeks": week_rows,
        "types": types,
        "flags": flags,
        "summary": summary,
        "reference_ftp": reference,
        "ride_count": len(rides),
        "method": method,
    }
