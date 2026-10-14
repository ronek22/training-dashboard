"""Planned vs ridden power for structured rides, and what it says about FTP.

A planned cycling workout stores its steps as FTP fractions. When a ride lands
on a day with one, its power stream is lined up against the planned profile
(the athlete may start the workout a few minutes into the ride) and each work
block's average power is compared with its target.

Zwift does not record a trainer bias or intensity change, but the power does:
a 215 W block ridden at 85% bias shows up as about 183 W. When the same gap
shows on several structured rides, FTP is probably set too high, and the
check suggests a working FTP scaled by that gap. One ride never moves it.

Easy workouts (endurance, recovery) have no blocks above tempo. Their steady
blocks get a lighter check instead: average power against target, time in the
target zone and heart-rate drift. Easy power says little about FTP, so these
rides never feed the FTP check.

Targets assume the FTP set in Zwift matches the FTP the app trained with that
day. Nothing here writes an FTP.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

from ..repositories.plans import get_weekly_plan_row
from ..request_cache import blob_memo
from .aerobic_decoupling import _window_stats
from .cycling_workouts import get_cycling_workout
from .ftp import ftp_on
from .plans import ensure_plan_day_ids, find_planned_session_by_id
from .power_trends import _build_segments, _confirmed_power_meter, _decode_json
from .power_zones import POWER_ZONE_LIMITS

BUCKET_SECONDS = 5
MAX_EARLY_START_SECONDS = 180
MAX_LATE_START_SECONDS = 20 * 60
MIN_ALIGNMENT = 0.6
MIN_PLAN_COVERAGE = 0.25
WORK_FRACTION = 0.75
MIN_WORK_SECONDS = 120
RAMP_SECONDS = 30
MIN_BLOCK_COVERAGE = 0.6
# Blocks between tempo and threshold say the most about FTP; VO2 blocks lean on anaerobic power.
FTP_SIGNAL_FRACTIONS = (0.80, 1.05)

ON_TARGET_RATIO = 0.97
UNDER_RATIO = 0.90
OVER_RATIO = 1.05

CHECK_WINDOW_DAYS = 42
MIN_SIGNAL_RIDES = 2
SIGNAL_RIDES = 3
SUGGEST_BELOW_RATIO = 0.95

VERDICTS = {
    "on_target": "On target",
    "slightly_under": "A little under",
    "under": "Well under",
    "over": "Above target",
}

# Easy rides: riding under target is fine, over it adds fatigue the plan didn't ask for.
STEADY_EASY_RATIO = 0.90
STEADY_HARD_RATIO = 1.08
MIN_HALF_HR_COVERAGE = 0.9
COUPLED_DRIFT_PCT = 5.0
STEADY_VERDICTS = {
    "on_target": "On target",
    "easy": "Easier than planned",
    "hard": "Harder than planned",
}


def _timeline(steps: list[dict]) -> list[dict]:
    """Planned steps as consecutive blocks with start/end seconds and target fractions."""
    blocks: list[dict] = []
    cursor = 0

    def add(kind: str, seconds: int, low: float, high: float, label: Optional[str]) -> None:
        nonlocal cursor
        blocks.append({"kind": kind, "start": cursor, "end": cursor + seconds, "low": low, "high": high, "label": label})
        cursor += seconds

    for step in steps:
        if step["kind"] == "intervals":
            for _ in range(step["repeat"]):
                add("work", step["on_duration_s"], step["on_power"], step["on_power"], step.get("label"))
                add("recovery", step["off_duration_s"], step["off_power"], step["off_power"], None)
        elif step["kind"] == "steady":
            add("steady", step["duration_s"], step["power"], step["power"], step.get("label"))
        else:
            add(step["kind"], step["duration_s"], step["power_low"], step["power_high"], None)
    for block in blocks:
        if block["kind"] == "steady" and block["low"] >= WORK_FRACTION:
            block["kind"] = "work"
    return blocks


def _target_buckets(blocks: list[dict]) -> list[float]:
    total = blocks[-1]["end"] if blocks else 0
    buckets = []
    for index in range(total // BUCKET_SECONDS):
        second = index * BUCKET_SECONDS + BUCKET_SECONDS / 2
        block = next(item for item in blocks if item["start"] <= second < item["end"])
        share = (second - block["start"]) / (block["end"] - block["start"])
        buckets.append(block["low"] + (block["high"] - block["low"]) * share)
    return buckets


def _power_buckets(segments: list, origin: float, count: int) -> list[Optional[float]]:
    """Average watts per 5-second bucket from ``origin``; None where under half the bucket has power."""
    area = [0.0] * count
    covered = [0.0] * count
    span = count * BUCKET_SECONDS
    for segment in segments:
        start, end = max(segment.start - origin, 0.0), min(segment.end - origin, span)
        while start < end:
            index = int(start // BUCKET_SECONDS)
            stop = min(end, (index + 1) * BUCKET_SECONDS)
            area[index] += segment.watts * (stop - start)
            covered[index] += stop - start
            start = stop
    return [area[i] / covered[i] if covered[i] >= BUCKET_SECONDS / 2 else None for i in range(count)]


def _correlation(target: list[float], power: list[Optional[float]], shift: int) -> tuple[Optional[float], float]:
    """Pearson r between plan and ride at ``shift`` buckets, and the share of the plan it covers."""
    pairs = [
        (target[index], power[index + shift])
        for index in range(len(target))
        if 0 <= index + shift < len(power) and power[index + shift] is not None
    ]
    coverage = len(pairs) / len(target)
    if coverage < MIN_PLAN_COVERAGE:
        return None, coverage
    mean_t = sum(pair[0] for pair in pairs) / len(pairs)
    mean_p = sum(pair[1] for pair in pairs) / len(pairs)
    cov = sum((t - mean_t) * (p - mean_p) for t, p in pairs)
    var_t = sum((t - mean_t) ** 2 for t, _ in pairs)
    var_p = sum((p - mean_p) ** 2 for _, p in pairs)
    if not var_t or not var_p:
        return None, coverage
    return cov / (var_t * var_p) ** 0.5, coverage


def _align(blocks: list[dict], segments: list) -> tuple[Optional[float], Optional[float]]:
    """Seconds into the ride where the planned workout starts, and how well it lines up (r)."""
    target = _target_buckets(blocks)
    ride_start = segments[0].start
    early = MAX_EARLY_START_SECONDS // BUCKET_SECONDS
    late = MAX_LATE_START_SECONDS // BUCKET_SECONDS
    power = _power_buckets(segments, ride_start - early * BUCKET_SECONDS, len(target) + early + late)
    # A ride that stops early covers less of the plan; prefer shifts that overlap more of it.
    best_shift, best_r, best_score = None, None, None
    for shift in range(0, early + late + 1):
        r, coverage = _correlation(target, power, shift)
        score = r * min(1.0, coverage / 0.8) if r is not None else None
        if score is not None and (best_score is None or score > best_score):
            best_shift, best_r, best_score = shift, r, score
    if best_shift is None:
        return None, None
    return (best_shift - early) * BUCKET_SECONDS, best_r


def _verdict(ratio: float) -> str:
    if ratio > OVER_RATIO:
        return "over"
    if ratio >= ON_TARGET_RATIO:
        return "on_target"
    if ratio >= UNDER_RATIO:
        return "slightly_under"
    return "under"


def compare_ride_to_workout(streams: Any, workout: dict, ftp_watts: float) -> dict:
    """Line one ride's power stream up with a planned workout and grade each work block."""
    runs = _build_segments(streams)
    segments = [segment for run in runs for segment in run]
    if not segments:
        return {"status": "unavailable", "reason": "No power stream for this ride."}
    blocks = _timeline(workout["steps"])
    work = [block for block in blocks if block["kind"] == "work" and block["end"] - block["start"] >= MIN_WORK_SECONDS]
    if not work:
        steady = [block for block in blocks if block["kind"] == "steady" and block["end"] - block["start"] >= MIN_WORK_SECONDS]
        if steady:
            return _compare_steady(blocks, steady, segments, ftp_watts)
        return {"status": "unavailable", "reason": "This workout has no work blocks to compare."}

    offset, alignment = _align(blocks, segments)
    if offset is None or alignment < MIN_ALIGNMENT:
        return {
            "status": "not_matched",
            "reason": "The power doesn't follow the planned blocks, so this looks like a different ride than the workout.",
            "alignment": round(alignment, 2) if alignment is not None else None,
        }

    origin = segments[0].start + offset
    graded = []
    for index, block in enumerate(work, start=1):
        target = block["low"] * ftp_watts
        ramp = min(RAMP_SECONDS, (block["end"] - block["start"]) / 5)
        start, end = origin + block["start"] + ramp, origin + block["end"]
        stats = _window_stats(segments, start, end)
        ridden = stats["power_seconds"] >= MIN_BLOCK_COVERAGE * stats["span"]
        last_third = _window_stats(segments, end - (end - start) / 3, end)
        graded.append({
            "index": index,
            "label": block["label"],
            "duration_min": round((block["end"] - block["start"]) / 60, 1),
            "target_fraction": block["low"],
            "target_watts": round(target),
            "ridden": ridden,
            "avg_watts": round(stats["avg_watts"]) if ridden else None,
            "ratio": round(stats["avg_watts"] / target, 3) if ridden else None,
            "avg_hr": round(stats["avg_hr"]) if ridden and stats["hr_seconds"] else None,
            "end_hr": round(last_third["avg_hr"]) if ridden and last_third["hr_seconds"] else None,
        })

    ridden = [block for block in graded if block["ridden"]]
    if not ridden:
        return {"status": "not_matched", "reason": "None of the work blocks were ridden.", "alignment": round(alignment, 2)}
    minutes = sum(block["duration_min"] for block in ridden)
    ratio = sum(block["ratio"] * block["duration_min"] for block in ridden) / minutes
    signal = [block for block in ridden if FTP_SIGNAL_FRACTIONS[0] <= block["target_fraction"] <= FTP_SIGNAL_FRACTIONS[1]]
    signal_ratio = (
        sum(block["ratio"] * block["duration_min"] for block in signal) / sum(block["duration_min"] for block in signal)
        if signal else None
    )
    verdict = _verdict(ratio)
    return {
        "status": "available",
        "mode": "blocks",
        "verdict": verdict,
        "verdict_label": VERDICTS[verdict],
        "ratio": round(ratio, 3),
        "ftp_signal_ratio": round(signal_ratio, 3) if signal_ratio is not None else None,
        "blocks_planned": len(graded),
        "blocks_ridden": len(ridden),
        "start_offset_min": round(offset / 60, 1),
        "alignment": round(alignment, 2),
        "blocks": graded,
        "timeline": _ride_timeline(blocks, origin, segments[-1].end, ftp_watts),
    }


def _ride_timeline(blocks: list[dict], origin: float, ride_end: float, ftp_watts: float) -> list[dict]:
    """Every planned block on the ride's elapsed clock, so the trace can show the workout behind it."""
    return [
        {
            "kind": block["kind"],
            "label": block["label"],
            "start_s": round(origin + block["start"], 1),
            "end_s": round(min(origin + block["end"], ride_end), 1),
            "low_fraction": block["low"],
            "high_fraction": block["high"],
            "low_watts": round(block["low"] * ftp_watts),
            "high_watts": round(block["high"] * ftp_watts),
        }
        for block in blocks
        if origin + block["start"] < ride_end
    ]


def _zone_bounds(fraction: float) -> tuple[int, float, Optional[float]]:
    """Power zone (1-based) holding ``fraction`` of FTP, with its lower and upper fractions."""
    lower = 0.0
    for index, upper in enumerate(POWER_ZONE_LIMITS, start=1):
        if fraction <= upper:
            return index, lower, upper
        lower = upper
    return len(POWER_ZONE_LIMITS) + 1, lower, None


def _zone_seconds(segments: list, start: float, end: float, low: float, high: Optional[float]) -> tuple[float, float, float]:
    """Seconds below, inside and above a watt band between ``start`` and ``end``; zero watts count as below."""
    below = inside = above = 0.0
    for segment in segments:
        seconds = min(segment.end, end) - max(segment.start, start)
        if seconds <= 0:
            continue
        if segment.watts <= 0 or segment.watts <= low:
            below += seconds
        elif high is not None and segment.watts > high:
            above += seconds
        else:
            inside += seconds
    return below, inside, above


def _drift(segments: list, windows: list[tuple[float, float]]) -> Optional[dict]:
    """Power-to-heart-rate drift from the first half of the steady time to the second, or None without heart rate."""
    total = sum(end - start for start, end in windows)
    halves: list[list[tuple[float, float]]] = [[], []]
    cursor = 0.0
    for start, end in windows:
        middle = start + max(0.0, min(end - start, total / 2 - cursor))
        if middle > start:
            halves[0].append((start, middle))
        if end > middle:
            halves[1].append((middle, end))
        cursor += end - start
    stats = []
    for half in halves:
        parts = [_window_stats(segments, start, end) for start, end in half]
        power_seconds = sum(part["power_seconds"] for part in parts)
        hr_seconds = sum(part["hr_seconds"] for part in parts)
        if not power_seconds or hr_seconds < MIN_HALF_HR_COVERAGE * power_seconds:
            return None
        watts = sum(part["avg_watts"] * part["power_seconds"] for part in parts) / power_seconds
        hr = sum(part["avg_hr"] * part["hr_seconds"] for part in parts) / hr_seconds
        if not watts or not hr:
            return None
        stats.append((watts, hr))
    (first_w, first_hr), (second_w, second_hr) = stats
    first_ef, second_ef = first_w / first_hr, second_w / second_hr
    return {
        "first_hr": round(first_hr),
        "second_hr": round(second_hr),
        "first_watts": round(first_w),
        "second_watts": round(second_w),
        "decoupling_pct": round((first_ef - second_ef) / first_ef * 100, 1),
    }


def _steady_verdict(ratio: float) -> str:
    if ratio > STEADY_HARD_RATIO:
        return "hard"
    if ratio < STEADY_EASY_RATIO:
        return "easy"
    return "on_target"


def _compare_steady(blocks: list[dict], steady: list[dict], segments: list, ftp_watts: float) -> dict:
    """Easy workouts: power against target, time in zone and heart-rate drift over the steady blocks."""
    # A flat plan lines up loosely; when it doesn't, assume the workout started with the ride.
    offset, alignment = _align(blocks, segments)
    if offset is None or alignment < MIN_ALIGNMENT:
        offset = 0.0
    origin = segments[0].start + offset
    ride_end = segments[-1].end

    graded, windows = [], []
    for index, block in enumerate(steady, start=1):
        planned = block["end"] - block["start"]
        start, end = origin + block["start"], min(origin + block["end"], ride_end)
        stats = _window_stats(segments, start, end) if end > start else None
        ridden = bool(stats) and stats["power_seconds"] >= MIN_BLOCK_COVERAGE * planned
        zone, low, high = _zone_bounds(block["low"])
        target = block["low"] * ftp_watts
        entry = {
            "index": index,
            "label": block["label"],
            "duration_min": round(planned / 60, 1),
            "ridden_min": round(stats["power_seconds"] / 60, 1) if stats else 0.0,
            "target_fraction": block["low"],
            "target_watts": round(target),
            "zone": zone,
            "zone_low_watts": round(low * ftp_watts),
            "zone_high_watts": round(high * ftp_watts) if high is not None else None,
            "ridden": ridden,
            "avg_watts": None, "ratio": None, "avg_hr": None,
            "in_zone_pct": None, "below_zone_pct": None, "above_zone_pct": None,
        }
        if ridden:
            below, inside, above = _zone_seconds(segments, start, end, low * ftp_watts, high * ftp_watts if high is not None else None)
            seconds = below + inside + above
            entry.update({
                "avg_watts": round(stats["avg_watts"]),
                "ratio": round(stats["avg_watts"] / target, 3),
                "avg_hr": round(stats["avg_hr"]) if stats["hr_seconds"] else None,
                "in_zone_pct": round(inside / seconds * 100),
                "below_zone_pct": round(below / seconds * 100),
                "above_zone_pct": round(above / seconds * 100),
            })
            windows.append((start, end))
        graded.append(entry)

    ridden = [block for block in graded if block["ridden"]]
    if not ridden:
        return {"status": "not_matched", "reason": "The steady part of the workout wasn't ridden.", "alignment": round(alignment, 2) if alignment is not None else None}
    minutes = sum(block["ridden_min"] for block in ridden)
    ratio = sum(block["ratio"] * block["ridden_min"] for block in ridden) / minutes
    in_zone = sum(block["in_zone_pct"] * block["ridden_min"] for block in ridden) / minutes
    verdict = _steady_verdict(ratio)
    return {
        "status": "available",
        "mode": "steady",
        "verdict": verdict,
        "verdict_label": STEADY_VERDICTS[verdict],
        "ratio": round(ratio, 3),
        "in_zone_pct": round(in_zone),
        "drift": _drift(segments, windows),
        # Easy power says little about FTP; the FTP check skips these rides.
        "ftp_signal_ratio": None,
        "blocks_planned": len(graded),
        "blocks_ridden": len(ridden),
        "start_offset_min": round(offset / 60, 1),
        "alignment": round(alignment, 2) if alignment is not None else None,
        "blocks": graded,
        "timeline": _ride_timeline(blocks, origin, ride_end, ftp_watts),
    }


def _steady_headline(result: dict) -> str:
    blocks = [block for block in result["blocks"] if block["ridden"]]
    minutes = sum(block["ridden_min"] for block in blocks)
    target = round(sum(block["target_watts"] * block["ridden_min"] for block in blocks) / minutes)
    ridden = round(sum(block["avg_watts"] * block["ridden_min"] for block in blocks) / minutes)
    zone = blocks[0]["zone"]
    return f"Z{zone} at {round(result['ratio'] * 100)}% of target ({ridden} W vs {target} W), {result['in_zone_pct']}% in zone"


def _steady_explanation(result: dict) -> str:
    if result["verdict"] == "hard":
        pace = "This was meant to be easy and ran above target, which adds fatigue without much extra base."
    elif result["verdict"] == "easy":
        pace = "Under target is fine on an easy day; the aerobic work still counts."
    else:
        pace = "Power sat where the plan wanted it."
    drift = result.get("drift")
    if not drift:
        return f"{pace} No heart rate on this ride, so drift can't be checked."
    pct = drift["decoupling_pct"]
    if pct < COUPLED_DRIFT_PCT:
        tail = f"Heart rate held steady ({drift['first_hr']} → {drift['second_hr']} bpm, {pct:+.1f}% drift), so this power is comfortably aerobic."
    else:
        tail = (
            f"Heart rate drifted {pct:.1f}% at this power ({drift['first_hr']} → {drift['second_hr']} bpm). "
            "Heat, fatigue or poor fueling can do it; if it repeats on cool, rested days, ease the target a little."
        )
    return f"{pace} {tail}"


def _headline(result: dict) -> str:
    blocks = [block for block in result["blocks"] if block["ridden"]]
    target = round(sum(block["target_watts"] for block in blocks) / len(blocks))
    ridden = round(sum(block["avg_watts"] for block in blocks) / len(blocks))
    pct = round(result["ratio"] * 100)
    missed = result["blocks_planned"] - result["blocks_ridden"]
    tail = f"; {missed} of {result['blocks_planned']} blocks not ridden" if missed else ""
    return f"Work blocks at {pct}% of target ({ridden} W vs {target} W){tail}"


def _explanation(result: dict) -> str:
    pct = round(result["ratio"] * 100)
    if result["verdict"] == "on_target":
        return "Power matched the plan, so the FTP behind these targets looks right for this session."
    if result["verdict"] == "over":
        return f"You rode about {pct}% of the targets. If it felt controlled, FTP may be set low."
    return (
        f"You rode about {pct}% of the targets, as if trainer bias or intensity was turned down to ~{pct}%. "
        "One ride can be fatigue; if the next structured rides show the same gap, FTP is probably set too high."
    )


def _compare_cached(streams_json: Any, workout: dict, ftp_watts: float) -> dict:
    if not isinstance(streams_json, str):
        return compare_ride_to_workout(_decode_json(streams_json), workout, ftp_watts)
    result = blob_memo(
        f"workout-execution:{workout['id']}:{ftp_watts}",
        streams_json,
        lambda: compare_ride_to_workout(_decode_json(streams_json), workout, ftp_watts),
    )
    return copy.deepcopy(result)


def planned_workout_day(conn: sqlite3.Connection, activity: dict) -> Optional[dict]:
    """The planned day with a structured cycling workout this ride fulfilled, if any."""
    linked = activity.get("linked_planned_session_id")
    if linked:
        day = find_planned_session_by_id(conn, linked)
        return day if day and day.get("cycling_workout_id") else None
    try:
        day_date = date.fromisoformat(str(activity.get("date"))[:10])
    except ValueError:
        return None
    week_start = (day_date - timedelta(days=day_date.weekday())).isoformat()
    row = get_weekly_plan_row(conn, week_start)
    if not row:
        return None
    for day in ensure_plan_day_ids(row["week_start"], json.loads(row["days_json"])):
        if day.get("date") == day_date.isoformat() and day.get("cycling_workout_id"):
            return day
    return None


def build_workout_execution(
    conn: sqlite3.Connection,
    activity: dict,
    detail_json: Any,
    streams_json: Any,
    source_status: Any,
) -> Optional[dict]:
    """Planned vs ridden power for one ride, or None when the ride had no structured workout planned."""
    if activity.get("type") not in ("Ride", "VirtualRide"):
        return None
    day = planned_workout_day(conn, activity)
    workout = get_cycling_workout(day["cycling_workout_id"]) if day else None
    if not workout:
        return None
    base = {
        "workout_id": workout["id"],
        "workout_name": workout["name"],
        "planned_date": day.get("date"),
        "activity_id": str(activity.get("id")),
        "activity_date": str(activity.get("date"))[:10],
    }
    ftp_watts = ftp_on(conn, base["activity_date"])
    if not ftp_watts:
        return {**base, "status": "unavailable", "reason": "Set an FTP to compare watts with the plan."}
    if not streams_json:
        return {**base, "status": "unavailable", "reason": "The power stream for this ride isn't cached yet."}
    if not _confirmed_power_meter(detail_json, activity_type=activity.get("type"), source_status=source_status, streams_json=streams_json):
        return {**base, "status": "unavailable", "reason": "No power meter or smart trainer on this ride."}
    result = _compare_cached(streams_json, workout, ftp_watts)
    payload = {**base, "ftp_watts": round(ftp_watts), **result}
    if result["status"] == "available":
        steady = result["mode"] == "steady"
        payload["headline"] = _steady_headline(result) if steady else _headline(result)
        payload["explanation"] = _steady_explanation(result) if steady else _explanation(result)
        payload["assumption"] = f"Targets use the {round(ftp_watts)} W FTP the app had that day; Zwift uses the FTP in your Zwift profile."
        if steady:
            payload["assumption"] += " Easy rides don't count toward the FTP check."
    return payload


def build_ftp_workout_check(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """Structured rides from the last six weeks and whether they point to a lower FTP."""
    today = today or date.today()
    start = today - timedelta(days=CHECK_WINDOW_DAYS)
    rows = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name, a.linked_planned_session_id,
               d.detail_json, d.streams_json, d.source_status
        FROM activities AS a
        LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ('Ride', 'VirtualRide') AND substr(a.date, 1, 10) BETWEEN ? AND ?
        ORDER BY a.date ASC, a.id ASC
        """,
        (start.isoformat(), today.isoformat()),
    ).fetchall()

    rides = []
    for row in rows:
        result = build_workout_execution(conn, dict(row), row["detail_json"], row["streams_json"], row["source_status"])
        if not result or result["status"] != "available" or result["mode"] != "blocks" or result.get("ftp_signal_ratio") is None:
            continue
        rides.append({
            "activity_id": result["activity_id"],
            "date": result["activity_date"],
            "name": row["name"] or result["workout_name"],
            "workout_name": result["workout_name"],
            "ratio": result["ftp_signal_ratio"],
            "ftp_watts": result["ftp_watts"],
        })

    current = ftp_on(conn, today.isoformat())
    recent = rides[-SIGNAL_RIDES:]
    summary: dict[str, Any] = {
        "window_days": CHECK_WINDOW_DAYS,
        "rides": list(reversed(rides)),
        "current_ftp_watts": round(current) if current else None,
        "suggestion": None,
    }
    if len(recent) < MIN_SIGNAL_RIDES or not current:
        summary["status"] = "not_enough"
        summary["note"] = (
            f"No structured rides compared yet. After {MIN_SIGNAL_RIDES}, this shows whether you're holding the planned watts."
            if not rides else
            f"1 structured ride compared so far; needs {MIN_SIGNAL_RIDES} to judge FTP."
        )
        return summary

    ratio = median(ride["ratio"] for ride in recent)
    under = [ride for ride in recent if ride["ratio"] <= SUGGEST_BELOW_RATIO]
    pct = round(ratio * 100)
    summary["median_ratio"] = round(ratio, 3)
    if ratio <= SUGGEST_BELOW_RATIO and len(under) >= MIN_SIGNAL_RIDES:
        watts = round(current * ratio)
        summary["status"] = "lower"
        summary["suggestion"] = {
            "watts": watts,
            "title": f"Structured rides point to about {watts} W.",
            "detail": (
                f"Your last {len(recent)} structured rides held about {pct}% of their targets. "
                f"A working FTP of {watts} W would make those targets match what you rode."
            ),
        }
    else:
        summary["status"] = "holding"
        summary["note"] = f"Your last {len(recent)} structured rides held about {pct}% of their targets; FTP looks fine."
    return summary
