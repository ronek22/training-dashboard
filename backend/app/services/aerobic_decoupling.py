"""Aerobic fitness from steady rides: heart-rate drift and power per heartbeat.

For each steady ride of 45 minutes or more with measured power and heart rate,
the middle of the ride (warm-up and cool-down trimmed) is split into two equal
halves by time:

* efficiency = average power / average heart rate (W/bpm), and
* decoupling (Pw:HR) = how much efficiency fell from the first to the second
  half, as a percent. Under 5% means heart rate held steady at that power.

Watching these on ordinary Zone 2 rides shows aerobic base improving without a
maximal test. Nothing here writes an FTP or changes the plan.
"""

from __future__ import annotations

import math
import sqlite3
from bisect import bisect_right
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

from .cycling_workouts import latest_ftp
from .plans import normalize_workout_intent
from .power_trends import _Segment, _build_segments, _confirmed_power_meter, _decode_json

MIN_RIDE_SECONDS = 45 * 60
WARMUP_SECONDS = 10 * 60
COOLDOWN_SECONDS = 5 * 60
MIN_POWER_COVERAGE = 0.9
MIN_HR_COVERAGE = 0.9
MAX_VARIABILITY_INDEX = 1.10
MAX_ZERO_POWER_SHARE = 0.10
MAX_INTENSITY_OF_FTP = 0.80
MIN_TREND_RIDES = 3
COUPLED_DECOUPLING_PCT = 5.0
COMPARABLE_POWER_PCT = 7.0
MIN_ADJUSTED_RIDES = 5
MIN_POWER_SPREAD_WATTS = 10.0
SAME_POWER_HR_CHANGE_BPM = 2.0
DEFAULT_WEEKS = 12
HARD_INTENTS = {"tempo", "interval", "race_specific"}

EXCLUSION_REASONS = {
    "too_short": "Shorter than 45 minutes",
    "hard_session": "Planned as a hard session",
    "no_measured_power": "No power meter or smart trainer",
    "no_streams": "Power and heart-rate streams are not cached",
    "missing_heart_rate": "Heart rate missing for more than 10% of the ride",
    "gappy_data": "Pauses or gaps cover more than 10% of the ride",
    "coasting": "Coasting (zero watts) for more than 10% of the ride",
    "not_steady": "Power too variable to be a steady ride",
    "too_hard": "Above endurance intensity (over 80% of FTP)",
}

METHODOLOGY = (
    "Rides (indoor and outdoor) of at least 45 minutes with measured power and heart rate. "
    "The first 10 minutes (warm-up) and last 5 minutes (cool-down) are trimmed and the rest is "
    "split into two equal halves by time. Efficiency is average power divided by average heart "
    "rate (W/bpm). Decoupling (Pw:HR) is how much efficiency fell from the first half to the "
    "second, in percent; under 5% means heart rate held steady at that power. A ride qualifies "
    "only when it was not planned as tempo, intervals or race-specific; power and heart rate "
    "cover at least 90% of the analysed time; zero watts cover at most 10%; normalized power is "
    "at most 1.10 times average power; and average power is at most 80% of the latest stored "
    "FTP (skipped when none is stored). Stored FTP is only used as a ceiling; nothing here "
    "estimates or writes one."
)

INTERPRETATION_LIMITS = [
    "Heat, hydration, fatigue, caffeine and sleep move heart rate; compare trends across several rides, not one ride.",
    "Indoor rides drift more without a fan; compare indoor with indoor and outdoor with outdoor.",
    "Longer or harder rides drift more. Decoupling is most comparable between rides of similar length and power.",
    "Power per heartbeat also rises on harder rides. The direction uses heart rate at the same power (fitted across rides) when there are five or more rides with a spread of power; with fewer it falls back to raw efficiency.",
    "Efficiency rising at the same power is the base-fitness signal; it is not an FTP and does not replace a test.",
]


def _environment(activity_type: str, detail: Any) -> str:
    if activity_type == "VirtualRide":
        return "indoor"
    if isinstance(detail, dict) and detail.get("trainer") is True:
        return "indoor"
    return "outdoor"


def _overlap(segment: _Segment, start: float, end: float) -> float:
    return max(0.0, min(segment.end, end) - max(segment.start, start))


def _window_stats(segments: list[_Segment], start: float, end: float) -> dict[str, float]:
    power_seconds = power_area = hr_seconds = hr_area = zero_seconds = 0.0
    for segment in segments:
        seconds = _overlap(segment, start, end)
        if seconds <= 0:
            continue
        power_seconds += seconds
        power_area += segment.watts * seconds
        if segment.watts <= 0:
            zero_seconds += seconds
        if segment.hr_complete and segment.hr is not None:
            hr_seconds += seconds
            hr_area += segment.hr * seconds
    return {
        "span": end - start,
        "power_seconds": power_seconds,
        "avg_watts": power_area / power_seconds if power_seconds else 0.0,
        "hr_seconds": hr_seconds,
        "avg_hr": hr_area / hr_seconds if hr_seconds else 0.0,
        "zero_seconds": zero_seconds,
    }


def _normalized_power(runs: list[list[_Segment]], start: float, end: float) -> Optional[float]:
    """Normalized power from a 1 Hz resample and a 30-second rolling average, per valid run."""
    fourth_powers: list[float] = []
    for run in runs:
        starts = [segment.start for segment in run]
        first = max(math.ceil(run[0].start), math.ceil(start))
        last = min(math.floor(run[-1].end), math.floor(end))
        samples = []
        for second in range(first, last):
            index = bisect_right(starts, second + 1e-9) - 1
            if 0 <= index < len(run):
                samples.append(run[index].watts)
        if len(samples) < 30:
            continue
        rolling = sum(samples[:30])
        fourth_powers.append((rolling / 30) ** 4)
        for index in range(30, len(samples)):
            rolling += samples[index] - samples[index - 30]
            fourth_powers.append((rolling / 30) ** 4)
    if not fourth_powers:
        return None
    return (sum(fourth_powers) / len(fourth_powers)) ** 0.25


def analyse_ride(
    streams: Any,
    *,
    ftp_watts: Optional[float] = None,
) -> dict[str, Any]:
    """Return ``{"qualifies": bool, "reason": key | None, ...metrics}`` for one ride's streams."""
    runs = _build_segments(streams)
    segments = [segment for run in runs for segment in run]
    if not segments:
        return {"qualifies": False, "reason": "no_streams"}

    ride_start = segments[0].start
    ride_end = segments[-1].end
    if ride_end - ride_start < MIN_RIDE_SECONDS:
        return {"qualifies": False, "reason": "too_short"}

    start = ride_start + WARMUP_SECONDS
    end = ride_end - COOLDOWN_SECONDS
    whole = _window_stats(segments, start, end)
    if whole["power_seconds"] < MIN_POWER_COVERAGE * whole["span"]:
        return {"qualifies": False, "reason": "gappy_data"}
    if whole["hr_seconds"] < MIN_HR_COVERAGE * whole["power_seconds"]:
        return {"qualifies": False, "reason": "missing_heart_rate"}
    if whole["zero_seconds"] > MAX_ZERO_POWER_SHARE * whole["power_seconds"]:
        return {"qualifies": False, "reason": "coasting"}

    middle = start + (end - start) / 2
    first = _window_stats(segments, start, middle)
    second = _window_stats(segments, middle, end)
    for half in (first, second):
        if half["hr_seconds"] < MIN_HR_COVERAGE * half["power_seconds"] or not half["avg_hr"] or not half["avg_watts"]:
            return {"qualifies": False, "reason": "missing_heart_rate"}

    avg_watts = whole["avg_watts"]
    normalized = _normalized_power(runs, start, end)
    variability = normalized / avg_watts if normalized and avg_watts else None
    metrics = {
        "duration_min": round((ride_end - ride_start) / 60, 1),
        "analysed_min": round((end - start) / 60, 1),
        "avg_watts": round(avg_watts, 1),
        "avg_hr": round(whole["avg_hr"], 1),
        "normalized_watts": round(normalized, 1) if normalized else None,
        "variability_index": round(variability, 3) if variability else None,
    }
    if variability is None or variability > MAX_VARIABILITY_INDEX:
        return {"qualifies": False, "reason": "not_steady", **metrics}
    if ftp_watts and avg_watts > MAX_INTENSITY_OF_FTP * ftp_watts:
        return {"qualifies": False, "reason": "too_hard", **metrics}

    first_ef = first["avg_watts"] / first["avg_hr"]
    second_ef = second["avg_watts"] / second["avg_hr"]
    return {
        "qualifies": True,
        "reason": None,
        **metrics,
        "efficiency": round(whole["avg_watts"] / whole["avg_hr"], 3),
        "decoupling_pct": round((first_ef - second_ef) / first_ef * 100, 1),
        "first_half": {"avg_watts": round(first["avg_watts"], 1), "avg_hr": round(first["avg_hr"], 1), "efficiency": round(first_ef, 3)},
        "second_half": {"avg_watts": round(second["avg_watts"], 1), "avg_hr": round(second["avg_hr"], 1), "efficiency": round(second_ef, 3)},
    }


def _slope_per_day(points: list[tuple[float, float]]) -> Optional[float]:
    if len(points) < 2:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    spread = sum((x - mean_x) ** 2 for x, _ in points)
    if spread == 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / spread


def _hr_change_at_same_power(rides: list[dict[str, Any]], days: list[int]) -> Optional[float]:
    """Heart-rate change across the window with power held constant.

    Least squares of ``avg_hr ~ avg_watts + day``: harder rides raise heart rate,
    so the day coefficient is the drift in heart rate at the same power. Needs
    enough rides, a spread of dates and a spread of power to separate the two.
    """
    if len(rides) < MIN_ADJUSTED_RIDES or days[-1] - days[0] < 7:
        return None
    watts = [ride["avg_watts"] for ride in rides]
    if max(watts) - min(watts) < MIN_POWER_SPREAD_WATTS:
        # Same power on every ride: the plain heart-rate slope is already power matched.
        slope = _slope_per_day([(day, ride["avg_hr"]) for day, ride in zip(days, rides)])
        return round(slope * (days[-1] - days[0]), 1) if slope is not None else None
    count = len(rides)
    mean_w = sum(watts) / count
    mean_d = sum(days) / count
    mean_hr = sum(ride["avg_hr"] for ride in rides) / count
    sww = sum((w - mean_w) ** 2 for w in watts)
    sdd = sum((d - mean_d) ** 2 for d in days)
    swd = sum((w - mean_w) * (d - mean_d) for w, d in zip(watts, days))
    swh = sum((w - mean_w) * (ride["avg_hr"] - mean_hr) for w, ride in zip(watts, rides))
    sdh = sum((d - mean_d) * (ride["avg_hr"] - mean_hr) for d, ride in zip(days, rides))
    determinant = sww * sdd - swd ** 2
    # Power and date nearly collinear (e.g. every ride harder than the last): can't separate them.
    if determinant <= 1e-9 * sww * sdd:
        return None
    day_coefficient = (sww * sdh - swd * swh) / determinant
    return round(day_coefficient * (days[-1] - days[0]), 1)


def _comparison(rides: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Latest ride against the earliest ride in the window at similar average power."""
    if len(rides) < 2:
        return None
    latest = rides[-1]
    for earlier in rides[:-1]:
        if abs(earlier["avg_watts"] - latest["avg_watts"]) <= latest["avg_watts"] * COMPARABLE_POWER_PCT / 100:
            hr_delta = round(latest["avg_hr"] - earlier["avg_hr"])
            day = date.fromisoformat(earlier["date"])
            when = f"{day.day} {day:%b}"
            if hr_delta == 0:
                text = f"Same power, same heart rate as on {when}"
            else:
                text = f"Same power, {abs(hr_delta)} bpm {'lower' if hr_delta < 0 else 'higher'} than on {when}"
            return {
                "text": text,
                "hr_delta_bpm": hr_delta,
                "watts_delta": round(latest["avg_watts"] - earlier["avg_watts"], 1),
                "latest": {key: latest[key] for key in ("activity_id", "date", "avg_watts", "avg_hr")},
                "earlier": {key: earlier[key] for key in ("activity_id", "date", "avg_watts", "avg_hr")},
            }
    return None


def _trend(rides: list[dict[str, Any]], weeks: int) -> dict[str, Any]:
    if len(rides) < MIN_TREND_RIDES:
        return {
            "status": "unavailable",
            "rides": len(rides),
            "reason": f"Needs at least {MIN_TREND_RIDES} qualifying rides in the last {weeks} weeks; {len(rides)} so far.",
        }
    origin = date.fromisoformat(rides[0]["date"])
    days = [(date.fromisoformat(ride["date"]) - origin).days for ride in rides]
    ef_slope = _slope_per_day([(day, ride["efficiency"]) for day, ride in zip(days, rides)])
    drift_slope = _slope_per_day([(day, ride["decoupling_pct"]) for day, ride in zip(days, rides)])
    span_days = days[-1] - days[0]
    first_ef = rides[0]["efficiency"]
    ef_change_pct = round(ef_slope * span_days / first_ef * 100, 1) if ef_slope is not None and first_ef else None
    drift_change = round(drift_slope * span_days, 1) if drift_slope is not None else None
    hr_change = _hr_change_at_same_power(rides, days)
    # Efficiency rises with intensity too, so prefer the power-adjusted heart-rate change.
    if hr_change is not None:
        direction = "improving" if hr_change <= -SAME_POWER_HR_CHANGE_BPM else "declining" if hr_change >= SAME_POWER_HR_CHANGE_BPM else "steady"
    elif ef_change_pct is None:
        direction = "steady"
    elif ef_change_pct >= 2:
        direction = "improving"
    elif ef_change_pct <= -2:
        direction = "declining"
    else:
        direction = "steady"
    return {
        "status": "available",
        "rides": len(rides),
        "direction": direction,
        "direction_basis": "hr_at_same_power" if hr_change is not None else "efficiency",
        "hr_change_at_same_power_bpm": hr_change,
        "efficiency_change_pct": ef_change_pct,
        "decoupling_change_pct_points": drift_change,
        "span_days": span_days,
        "latest_efficiency": rides[-1]["efficiency"],
        "median_decoupling_pct": round(median(ride["decoupling_pct"] for ride in rides), 1),
        "coupled_rides": sum(ride["decoupling_pct"] < COUPLED_DECOUPLING_PCT for ride in rides),
        "comparison": _comparison(rides),
    }


def build_aerobic_decoupling(
    conn: sqlite3.Connection,
    *,
    weeks: int = DEFAULT_WEEKS,
    today: Optional[date] = None,
) -> dict[str, Any]:
    today = today or date.today()
    start_date = today - timedelta(weeks=weeks)
    ftp = latest_ftp(conn, today)
    ftp_watts = ftp["watts"] if ftp["available"] else None

    rows = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name, a.workout_intent, a.duration_min,
               d.detail_json, d.streams_json, d.source_status
        FROM activities AS a
        LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ('Ride', 'VirtualRide') AND substr(a.date, 1, 10) BETWEEN ? AND ?
        ORDER BY a.date ASC, a.id ASC
        """,
        (start_date.isoformat(), today.isoformat()),
    ).fetchall()

    rides: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "activity_id": str(row["id"]),
            "date": str(row["date"])[:10],
            "name": row["name"] or "Ride",
            "type": row["type"],
        }
        detail = _decode_json(row["detail_json"])
        base["environment"] = _environment(row["type"], detail)

        # Cheap checks first so long outdoor GPS streams are parsed only when they can qualify.
        if row["duration_min"] is not None and float(row["duration_min"]) < MIN_RIDE_SECONDS / 60:
            result = {"qualifies": False, "reason": "too_short"}
        elif normalize_workout_intent(row["workout_intent"], row["type"]) in HARD_INTENTS:
            result = {"qualifies": False, "reason": "hard_session"}
        elif not row["streams_json"]:
            result = {"qualifies": False, "reason": "no_streams"}
        else:
            streams = _decode_json(row["streams_json"])
            if not _confirmed_power_meter(detail, activity_type=row["type"], source_status=row["source_status"], streams_json=streams):
                result = {"qualifies": False, "reason": "no_measured_power"}
            else:
                result = analyse_ride(streams, ftp_watts=ftp_watts)

        reason = result.pop("reason")
        qualifies = result.pop("qualifies")
        if qualifies:
            rides.append({**base, **result})
        else:
            excluded.append({**base, "reason": reason, "reason_label": EXCLUSION_REASONS[reason]})

    environments = {
        environment: _trend([ride for ride in rides if ride["environment"] == environment], weeks)
        for environment in ("indoor", "outdoor")
    }
    reason_counts: dict[str, int] = {}
    for item in excluded:
        reason_counts[item["reason"]] = reason_counts.get(item["reason"], 0) + 1

    return {
        "as_of": today.isoformat(),
        "window": {"start_date": start_date.isoformat(), "end_date": today.isoformat(), "weeks": weeks},
        "status": "available" if any(trend["status"] == "available" for trend in environments.values()) else "unavailable",
        "rides": rides,
        "excluded": list(reversed(excluded)),
        "exclusion_counts": [
            {"reason": key, "label": EXCLUSION_REASONS[key], "count": count}
            for key, count in sorted(reason_counts.items(), key=lambda item: -item[1])
        ],
        "environments": environments,
        "ftp_ceiling_watts": round(MAX_INTENSITY_OF_FTP * ftp_watts) if ftp_watts else None,
        "thresholds": {
            "min_ride_min": MIN_RIDE_SECONDS // 60,
            "coupled_decoupling_pct": COUPLED_DECOUPLING_PCT,
            "max_variability_index": MAX_VARIABILITY_INDEX,
            "min_trend_rides": MIN_TREND_RIDES,
        },
        "methodology": METHODOLOGY,
        "interpretation_limits": INTERPRETATION_LIMITS,
    }


def aerobic_decoupling_coaching_context(conn: sqlite3.Connection, *, today: Optional[date] = None) -> dict[str, Any]:
    """Compact summary for the coach: trends per environment and the last few qualifying rides."""
    data = build_aerobic_decoupling(conn, today=today)
    return {
        "status": data["status"],
        "window": data["window"],
        "environments": data["environments"],
        "recent_rides": [
            {key: ride[key] for key in ("date", "name", "environment", "duration_min", "avg_watts", "avg_hr", "efficiency", "decoupling_pct")}
            for ride in data["rides"][-5:]
        ],
        "excluded_rides": len(data["excluded"]),
        "rules": "Steady rides of 45+ min with measured power and heart rate; decoupling under 5% means heart rate held steady at that power. Rising efficiency at the same power is base-fitness progress. No FTP is estimated or written.",
        "interpretation_limits": data["interpretation_limits"],
    }
