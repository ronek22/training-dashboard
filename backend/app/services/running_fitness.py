"""Running fitness: VDOT, race predictions, training paces and the comeback signals.

Three VDOT estimates sit side by side because each one fails differently:

* **Efforts** — Jack Daniels' VDOT from the fastest stretch of a mile or more
  inside any run (the cached best efforts the Records page uses), or the whole
  run when it has no streams. Exact when you raced; too low when every run was
  easy, which is the normal state during a comeback.
* **Heart rate** — for steady runs, the oxygen cost of the pace (Daniels) over
  the share of heart-rate reserve it took (Swain: %HRR ≈ %VO2 reserve), using
  that day's resting heart rate. Works from easy runs alone.
* **Resting HR formula** (Uth: 15.3 × max HR / resting HR) — a population
  formula, shown only as a sanity check.

The current VDOT is the higher of a recent effort and the heart-rate median,
since a real performance beats an estimate and an estimate beats easy-run
efforts. Predictions, Daniels training paces and the eight-week projection all
come from it. The peak is the best effort VDOT that another run within 60 days
confirmed (97 %+), so one GPS glitch cannot set it.

Around that: pace at the easy heart-rate cap over time (the earliest sign of
fitness returning), aerobic decoupling on longer runs, Apple Watch form and
power from ``run_dynamics``, a weekly build-up guard and the runs still waiting
for their HealthFit file.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

from ..request_cache import db_memo
from .heart_rate_zones import run_hr_cap
from .personal_records import _activity_rows, _load_efforts
from .power_trends import _decode_json, _stream_values
from .run_dynamics import dynamics_rows, first_dynamics_date

RACES = (
    ("5k", "5K", 5000.0),
    ("10k", "10K", 10000.0),
    ("half", "Half marathon", 21097.5),
    ("marathon", "Marathon", 42195.0),
)
MIN_EFFORT_M = 1609.0
MIN_EFFORT_S = 300.0
MAX_VDOT = 85.0
RECENT_EFFORT_DAYS = 42
HR_WINDOW_DAYS = 60
HR_RUNS = 8
PEAK_CONFIRM_DAYS = 60
PEAK_CONFIRM_RATIO = 0.97
PROJECTION_WEEKS = 8
PROJECTION_GAIN = 3.0  # VDOT points a detrained runner typically regains in eight consistent weeks
DEFAULT_RESTING_HR = 58.0
MAX_HR_LOOKBACK_DAYS = 730
DECOUPLING_MIN_MIN = 40
DECOUPLING_DAYS = 365
TREND_DAYS = 365
FORM_BASELINE_DAYS = 90
FATIGUE_RUNS = 10
GUARD_WEEKS = 10
GUARD_RATIO = 1.3
GUARD_MIN_JUMP_KM = 5.0
MISSING_DYNAMICS_DAYS = 30
W_PRIME_MIN_KJ = 3.0
# Daniels' paces as a share of VDOT (E is a range); M comes from the marathon prediction.
PACE_SHARES = {"easy": (0.64, 0.74), "threshold": 0.88, "interval": 0.98, "repetition": 1.04}


# ---------------------------------------------------------------------------
# Daniels and Gilbert
# ---------------------------------------------------------------------------


def vo2_cost(velocity_m_min: float) -> float:
    """Oxygen cost (ml/kg/min) of running at a speed in metres per minute."""
    return -4.60 + 0.182258 * velocity_m_min + 0.000104 * velocity_m_min ** 2


def share_of_max(minutes: float) -> float:
    """Share of VO2max that can be held for a race of this many minutes."""
    return 0.8 + 0.1894393 * math.exp(-0.012778 * minutes) + 0.2989558 * math.exp(-0.1932605 * minutes)


def vdot_from_performance(distance_m: float, seconds: float) -> Optional[float]:
    if distance_m <= 0 or seconds <= 0:
        return None
    minutes = seconds / 60
    value = vo2_cost(distance_m / minutes) / share_of_max(minutes)
    return value if 10 < value <= MAX_VDOT else None


def race_seconds(vdot: float, distance_m: float) -> float:
    """Race time for a VDOT (bisection; VDOT falls as the time grows)."""
    low, high = distance_m / 600 * 60, distance_m / 40 * 60
    for _ in range(80):
        mid = (low + high) / 2
        if vo2_cost(distance_m / (mid / 60)) / share_of_max(mid / 60) > vdot:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def velocity_for_vo2(vo2: float) -> float:
    """Speed (m/min) whose oxygen cost is vo2: the positive root of the cost quadratic."""
    a, b, c = 0.000104, 0.182258, -4.60 - vo2
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def pace_seconds_per_km(velocity_m_min: float) -> float:
    return 1000 / velocity_m_min * 60


def vo2max_from_heart_rate(velocity_m_min: float, avg_hr: float, resting_hr: float, max_hr: float) -> Optional[float]:
    if max_hr <= resting_hr:
        return None
    reserve = (avg_hr - resting_hr) / (max_hr - resting_hr)
    if not 0.5 <= reserve <= 0.95:
        return None
    value = (vo2_cost(velocity_m_min) - 3.5) / reserve + 3.5
    return value if 15 < value <= MAX_VDOT else None


def uth_vo2max(max_hr: float, resting_hr: float) -> float:
    return 15.3 * max_hr / resting_hr


def training_paces(vdot: float) -> dict[str, Any]:
    easy_slow, easy_fast = (pace_seconds_per_km(velocity_for_vo2(vdot * share)) for share in PACE_SHARES["easy"])
    marathon = race_seconds(vdot, 42195.0) / 42.195
    return {
        "easy": {"label": "Easy", "from_s": round(easy_fast), "to_s": round(easy_slow), "use": "Most of your running, long runs, recovery"},
        "marathon": {"label": "Marathon", "pace_s": round(marathon), "use": "Steady long-run segments"},
        "threshold": {"label": "Threshold", "pace_s": round(pace_seconds_per_km(velocity_for_vo2(vdot * PACE_SHARES["threshold"]))), "use": "20 min tempo or 5–6 × 1 km cruise intervals"},
        "interval": {"label": "Interval", "pace_s": round(pace_seconds_per_km(velocity_for_vo2(vdot * PACE_SHARES["interval"]))), "use": "3–5 min reps, equal jog recovery"},
        "repetition": {"label": "Repetition", "pace_s": round(pace_seconds_per_km(velocity_for_vo2(vdot * PACE_SHARES["repetition"]))), "use": "200–400 m reps for speed and form"},
    }


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _runs(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, date, name, distance_km, duration_min, avg_hr, max_hr, elevation_m
            FROM activities
            WHERE type = 'Run' AND distance_km > 0 AND duration_min > 0
            ORDER BY date ASC, id ASC
            """
        )
    ]


def resting_hr_by_day(conn: sqlite3.Connection) -> dict[str, float]:
    """Daily resting heart rate from Apple Health, falling back to logged metrics."""
    values: dict[str, list[float]] = defaultdict(list)
    try:
        for row in conn.execute("SELECT date, value FROM health_metric_samples WHERE metric = 'resting_hr' AND value > 25"):
            values[row["date"]].append(float(row["value"]))
    except sqlite3.OperationalError:
        pass
    for row in conn.execute("SELECT date, value FROM metrics WHERE metric = 'resting_hr' AND value > 25"):
        values.setdefault(row["date"], []).append(float(row["value"]))
    return {day: median(items) for day, items in values.items()}


class RestingHr:
    """Median resting HR over the 14 days up to a date; before any data, the first month's median."""

    def __init__(self, daily: dict[str, float]):
        self.days = sorted(daily)
        self.daily = daily
        first = [daily[day] for day in self.days[:30]]
        self.baseline = median(first) if first else DEFAULT_RESTING_HR

    def on(self, day: str) -> float:
        start = (date.fromisoformat(day) - timedelta(days=13)).isoformat()
        window = [self.daily[d] for d in self.days if start <= d <= day]
        return median(window) if window else self.baseline

    def latest(self, today: date) -> Optional[float]:
        if not self.days:
            return None
        return self.on(min(self.days[-1], today.isoformat()))


def running_max_hr(runs: list[dict], today: date) -> dict[str, Any]:
    """Median of the three highest run maxima in two years: one optical spike cannot lift it."""
    since = (today - timedelta(days=MAX_HR_LOOKBACK_DAYS)).isoformat()
    peaks = sorted((run["max_hr"] for run in runs if run["max_hr"] and run["date"] >= since and 120 < run["max_hr"] < 225), reverse=True)[:3]
    if not peaks:
        return {"bpm": 190.0, "basis": "default"}
    return {"bpm": float(median(peaks)), "basis": f"median of your top {len(peaks)} run maxima since {since[:4]}"}


# ---------------------------------------------------------------------------
# VDOT per run
# ---------------------------------------------------------------------------


def effort_vdot(run: dict, efforts: Optional[dict]) -> Optional[dict]:
    """Best VDOT among a run's efforts of a mile or more, else the whole run."""
    best = None
    for item in (efforts or {}).get("distance") or []:
        distance, seconds = item.get("distance_m") or 0, item.get("duration_s") or 0
        if distance < MIN_EFFORT_M or seconds < MIN_EFFORT_S:
            continue
        value = vdot_from_performance(distance, seconds)
        if value and (best is None or value > best["vdot"]):
            best = {"vdot": value, "label": item.get("label"), "seconds": seconds, "distance_m": distance}
    if best is None and run["distance_km"] >= 3:
        value = vdot_from_performance(run["distance_km"] * 1000, run["duration_min"] * 60)
        if value:
            best = {"vdot": value, "label": "whole run", "seconds": run["duration_min"] * 60, "distance_m": run["distance_km"] * 1000}
    return best


def heart_rate_vdot(run: dict, resting_hr: float, max_hr: float) -> Optional[float]:
    """VO2max from a steady run's pace and heart rate; hills, walks and short jogs are skipped."""
    if not run["avg_hr"] or run["distance_km"] < 3 or not 15 <= run["duration_min"] <= 150:
        return None
    if run["elevation_m"] and run["elevation_m"] / run["distance_km"] > 15:
        return None
    velocity = run["distance_km"] * 1000 / run["duration_min"]
    if not 118 <= velocity <= 333:  # 8:30/km to 3:00/km
        return None
    return vo2max_from_heart_rate(velocity, float(run["avg_hr"]), resting_hr, max_hr)


def pick_peak(points: list[dict]) -> Optional[dict]:
    """Highest VDOT that another run within 60 days came close to (97 %+)."""
    ranked = sorted(points, key=lambda point: point["vdot"], reverse=True)
    for point in ranked:
        day = date.fromisoformat(point["date"])
        for other in points:
            if other is point:
                continue
            if abs((date.fromisoformat(other["date"]) - day).days) <= PEAK_CONFIRM_DAYS and other["vdot"] >= point["vdot"] * PEAK_CONFIRM_RATIO:
                return point
    return ranked[0] if ranked else None


def projection(now: float, peak: Optional[float]) -> float:
    if not peak or peak <= now:
        return now
    return now + min(PROJECTION_GAIN, (peak - now) * 0.5)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _clock(seconds: float) -> str:
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _round(value: Optional[float], digits: int = 1) -> Optional[float]:
    return round(value, digits) if value is not None else None


def race_bests(runs: list[dict], efforts: dict[str, dict], today: date) -> dict[str, dict]:
    """Fastest stretch of each race distance, ever and in the last 365 days."""
    year_ago = (today - timedelta(days=365)).isoformat()
    out: dict[str, dict] = {}
    labels = {"5K": "5k", "10K": "10k", "Half marathon": "half", "Marathon": "marathon"}
    for run in runs:
        for item in (efforts.get(run["id"]) or {}).get("distance") or []:
            key = labels.get(item.get("label"))
            if not key or not item.get("duration_s"):
                continue
            entry = {"seconds": item["duration_s"], "date": run["date"], "activity_id": run["id"]}
            slot = out.setdefault(key, {"ever": None, "year": None})
            if slot["ever"] is None or entry["seconds"] < slot["ever"]["seconds"]:
                slot["ever"] = entry
            if run["date"] >= year_ago and (slot["year"] is None or entry["seconds"] < slot["year"]["seconds"]):
                slot["year"] = entry
    return out


def _monthly_timeline(effort_points: list[dict], hr_points: list[dict], runs: list[dict], today: date) -> list[dict]:
    months: dict[str, dict] = {}
    for run in runs:
        month = months.setdefault(run["date"][:7], {"month": run["date"][:7], "km": 0.0, "runs": 0, "effort": None, "hr": []})
        month["km"] += run["distance_km"]
        month["runs"] += 1
    for point in effort_points:
        month = months[point["date"][:7]]
        month["effort"] = max(month["effort"] or 0, point["vdot"])
    for point in hr_points:
        months[point["date"][:7]]["hr"].append(point["vdot"])
    if not months:
        return []
    first = date.fromisoformat(min(months) + "-01")
    # Through this month, so quiet months since the last run show as gaps.
    last = max(date.fromisoformat(max(months) + "-01"), date(today.year, today.month, 1))
    out = []
    cursor = first
    while cursor <= last:
        key = cursor.isoformat()[:7]
        month = months.get(key, {"km": 0.0, "runs": 0, "effort": None, "hr": []})
        out.append({
            "month": key,
            "km": round(month["km"], 1),
            "runs": month["runs"],
            "effort_vdot": _round(month["effort"]),
            "hr_vdot": _round(median(month["hr"])) if month["hr"] else None,
        })
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return out


def _decoupling(conn: sqlite3.Connection, runs: list[dict], today: date) -> dict[str, Any]:
    since = (today - timedelta(days=DECOUPLING_DAYS)).isoformat()
    candidates = [run for run in runs if run["date"] >= since and run["duration_min"] >= DECOUPLING_MIN_MIN and run["avg_hr"]]
    items = []
    for run in candidates:
        row = conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = ?", (run["id"],)).fetchone()
        streams = _decode_json(row["streams_json"]) if row else None
        heart = _stream_values(streams, "heartrate")
        speed = _stream_values(streams, "velocity_smooth")
        if not heart or len(heart) != len(speed):
            continue
        moving = [(float(v), float(h)) for v, h in zip(speed, heart) if v and h and float(v) >= 1.5 and float(h) > 60]
        if len(moving) < 600:
            continue
        half = len(moving) // 2
        def efficiency(part: list[tuple[float, float]]) -> float:
            return (sum(v for v, _ in part) / len(part)) / (sum(h for _, h in part) / len(part))
        first, second = efficiency(moving[:half]), efficiency(moving[half:])
        items.append({
            "activity_id": run["id"], "date": run["date"], "name": run["name"],
            "duration_min": run["duration_min"], "distance_km": run["distance_km"],
            "decoupling_pct": round((first - second) / first * 100, 1),
        })
    values = [item["decoupling_pct"] for item in items]
    return {
        "runs": items[-12:],
        "median_pct": _round(median(values)) if values else None,
        "good_below_pct": 5.0,
        "min_minutes": DECOUPLING_MIN_MIN,
    }


def _pace_at_cap(hr_points: list[dict], cap: int, today: date) -> dict[str, Any]:
    since = (today - timedelta(days=TREND_DAYS)).isoformat()
    points = []
    for point in hr_points:
        if point["date"] < since:
            continue
        reserve = (cap - point["resting_hr"]) / (point["max_hr"] - point["resting_hr"])
        vo2 = reserve * (point["vdot"] - 3.5) + 3.5
        points.append({"date": point["date"], "activity_id": point["activity_id"], "pace_s": round(pace_seconds_per_km(velocity_for_vo2(vo2)))})
    for index, point in enumerate(points):
        window = [item["pace_s"] for item in points[max(0, index - 3): index + 1]]
        point["rolling_s"] = round(median(window))
    change = None
    if len(points) >= 4:
        cutoff = (today - timedelta(days=56)).isoformat()
        earlier = [item["rolling_s"] for item in points if item["date"] <= cutoff]
        if earlier:
            change = points[-1]["rolling_s"] - earlier[-1]
    return {"hr_bpm": cap, "points": points, "change_8w_s": change}


def _form(rows: list[dict], today: date) -> dict[str, Any]:
    keys = ("cadence_spm", "step_length_m", "vertical_oscillation_cm", "vertical_ratio_pct", "stance_time_ms", "avg_power_w")
    outdoor = [row for row in rows if row["vertical_oscillation_cm"] is not None]
    if not outdoor:
        return {"available": False, "runs": 0}
    series = [
        {"date": row["date"], "activity_id": row["activity_id"], "name": row["activity_name"], "distance_km": row["activity_distance_km"],
         "pace_s": round(row["activity_duration_min"] * 60 / row["activity_distance_km"]) if row["activity_distance_km"] else None,
         **{key: row[key] for key in keys}}
        for row in outdoor
    ]
    latest = series[-1]
    since = (date.fromisoformat(latest["date"]) - timedelta(days=FORM_BASELINE_DAYS)).isoformat()
    previous = [item for item in series[:-1] if item["date"] >= since] or series[-6:-1]
    baseline = {key: _round(median([item[key] for item in previous if item[key] is not None]), 2) if any(item[key] is not None for item in previous) else None for key in keys}

    fatigue_rows = [row for row in outdoor if len(row["splits"]) >= 4][-FATIGUE_RUNS:]
    fatigue = {}
    for key in ("cadence_spm", "stance_time_ms", "vertical_oscillation_cm", "step_length_m", "power_w"):
        deltas = [
            row["splits"][-1][key] - row["splits"][0][key]
            for row in fatigue_rows
            if row["splits"][0].get(key) and row["splits"][-1].get(key)
        ]
        fatigue[key] = _round(median(deltas), 3) if deltas else None
    latest_row = outdoor[-1]
    return {
        "available": True,
        "runs": len(series),
        "since": series[0]["date"],
        "latest": latest,
        "baseline": baseline,
        "series": series[-60:],
        "latest_splits": latest_row["splits"],
        "fatigue": {"runs": len(fatigue_rows), "first_vs_last_km": fatigue},
        "ranges": {
            "cadence_spm": {"good": [165, 185], "note": "Most efficient runners sit around 165–185 steps/min at easy pace; nudging it up 5 % lowers impact."},
            "stance_time_ms": {"good": [200, 260], "note": "Shorter ground contact usually means springier running; it rises as you tire."},
            "vertical_oscillation_cm": {"good": [6, 10], "note": "How much you bounce. Less is usually more economical."},
            "vertical_ratio_pct": {"good": [6, 8.5], "note": "Bounce per metre of step: the cleanest single economy number."},
        },
    }


def _power(rows: list[dict], today: date) -> dict[str, Any]:
    durations = ("60", "180", "300", "720", "1200", "1800", "3600")
    recent_since = (today - timedelta(days=90)).isoformat()
    best_ever: dict[str, dict] = {}
    best_recent: dict[str, dict] = {}
    for row in rows:
        for key, watts in (row["power_bests"] or {}).items():
            entry = {"watts": watts, "date": row["date"], "activity_id": row["activity_id"]}
            if key not in best_ever or watts > best_ever[key]["watts"]:
                best_ever[key] = entry
            if row["date"] >= recent_since and (key not in best_recent or watts > best_recent[key]["watts"]):
                best_recent[key] = entry
    if not best_ever:
        return {"available": False}
    source = best_recent if "180" in best_recent and "720" in best_recent else best_ever
    critical = None
    if "180" in source and "720" in source:
        p3, p12 = source["180"]["watts"], source["720"]["watts"]
        cp = (p12 * 720 - p3 * 180) / 540
        if 0 < cp < p12:
            w_prime = (p3 - cp) * 180 / 1000
            critical = {
                "watts": round(cp), "w_prime_kj": round(w_prime, 1),
                "window": "last 90 days" if source is best_recent else "all time",
                # A tiny W' means the 3-minute best was not a hard effort: CP is then just steady-run power.
                "steady_only": w_prime < W_PRIME_MIN_KJ,
            }
    return {
        "available": True,
        "durations": [
            {"seconds": int(key), "ever": best_ever.get(key), "recent": best_recent.get(key)}
            for key in durations if key in best_ever
        ],
        "critical_power": critical,
        "note": "Apple Watch running power is its own scale (wind and grade included); compare it with itself, not with Stryd or bike watts.",
    }


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _build_up(runs: list[dict], today: date) -> dict[str, Any]:
    this_week = _week_start(today)
    weeks = []
    for offset in range(GUARD_WEEKS - 1, -1, -1):
        start = this_week - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        inside = [run for run in runs if start.isoformat() <= run["date"] <= end.isoformat()]
        weeks.append({
            "week_start": start.isoformat(),
            "km": round(sum(run["distance_km"] for run in inside), 1),
            "runs": len(inside),
            "longest_km": round(max((run["distance_km"] for run in inside), default=0), 1),
            "current": offset == 0,
        })
    last7_start = (today - timedelta(days=6)).isoformat()
    prior_start = (today - timedelta(days=34)).isoformat()
    acute = sum(run["distance_km"] for run in runs if last7_start <= run["date"] <= today.isoformat())
    chronic = sum(run["distance_km"] for run in runs if prior_start <= run["date"] < last7_start) / 4
    ratio = acute / chronic if chronic > 0 else None
    allowed = max(chronic * GUARD_RATIO, chronic + GUARD_MIN_JUMP_KM)
    if acute == 0:
        status, message = "idle", "No runs in the last 7 days."
    elif acute > allowed:
        status = "caution"
        message = f"{acute:.1f} km in 7 days against {chronic:.1f} km a week before: a bigger jump than tendons like. Hold next week."
    else:
        status = "ok"
        message = f"{acute:.1f} km in 7 days; up to {allowed:.0f} km keeps the build gentle."
    return {
        "weeks": weeks,
        "last7_km": round(acute, 1),
        "previous_weekly_avg_km": round(chronic, 1),
        "ratio": _round(ratio, 2),
        "next_week_cap_km": round(max(allowed, 5.0), 1),
        "status": status,
        "message": message,
    }


def runs_missing_dynamics(conn: sqlite3.Connection, today: date, days: int = MISSING_DYNAMICS_DAYS) -> list[dict]:
    """Recent runs (usually from Strava) whose HealthFit file has not arrived yet."""
    first = first_dynamics_date(conn)
    if not first:
        return []
    since = max(first, (today - timedelta(days=days - 1)).isoformat())
    rows = conn.execute(
        """
        SELECT a.id, a.date, a.name, a.distance_km, a.duration_min
        FROM activities a
        LEFT JOIN activity_details d ON d.activity_id = a.id
        WHERE a.type = 'Run' AND a.date BETWEEN ? AND ?
          AND NOT EXISTS (SELECT 1 FROM run_dynamics r WHERE r.activity_id = a.id)
          AND COALESCE(json_extract(d.detail_json, '$.trainer'), 0) != 1
        ORDER BY a.date DESC
        """,
        (since, today.isoformat()),
    ).fetchall()
    return [dict(row) for row in rows]


def _return_to_run(conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    from .return_to_run import STAGES, build_return_to_run

    data = build_return_to_run(conn, today)
    if not data.get("active"):
        return {"active": False, "quality_allowed": True}
    stage = data["stage"]["stage"]
    return {
        "active": True,
        "stage": stage,
        "stage_name": data["stage"]["name"],
        "quality_allowed": stage >= len(STAGES),
        "message": data["next"].get("message"),
    }


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


def build_running_fitness(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    return db_memo(conn, ("running_fitness", today.isoformat()), lambda: _build(conn, today))


def _build(conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    runs = _runs(conn)
    if not runs:
        return {"available": False, "reason": "No runs yet."}
    run_rows = [row for row in _activity_rows(conn) if row["type"] == "Run"]
    efforts = _load_efforts(conn, run_rows)
    resting = RestingHr(resting_hr_by_day(conn))
    max_hr = running_max_hr(runs, today)
    cap = run_hr_cap(conn)

    effort_points, hr_points = [], []
    for run in runs:
        best = effort_vdot(run, efforts.get(run["id"]))
        if best:
            effort_points.append({"date": run["date"], "activity_id": run["id"], "name": run["name"], "vdot": best["vdot"],
                                  "effort": best["label"], "seconds": best["seconds"], "distance_m": best["distance_m"]})
        rest = resting.on(run["date"])
        estimate = heart_rate_vdot(run, rest, max_hr["bpm"])
        if estimate:
            hr_points.append({"date": run["date"], "activity_id": run["id"], "vdot": estimate, "resting_hr": rest, "max_hr": max_hr["bpm"]})

    peak = pick_peak(effort_points)
    recent_since = (today - timedelta(days=RECENT_EFFORT_DAYS)).isoformat()
    recent_efforts = [point for point in effort_points if point["date"] >= recent_since]
    recent_effort = max(recent_efforts, key=lambda point: point["vdot"]) if recent_efforts else None
    hr_since = (today - timedelta(days=HR_WINDOW_DAYS)).isoformat()
    hr_recent = [point for point in hr_points if point["date"] >= hr_since][-HR_RUNS:]
    hr_now = median([point["vdot"] for point in hr_recent]) if hr_recent else None
    last_hr = hr_points[-HR_RUNS:] if hr_points else []
    hr_last_known = median([point["vdot"] for point in last_hr]) if last_hr else None
    latest_effort = effort_points[-1] if effort_points else None

    candidates = []
    if recent_effort:
        candidates.append((recent_effort["vdot"], "effort"))
    if hr_now:
        candidates.append((hr_now, "heart_rate"))
    if candidates:
        current, basis = max(candidates)
        stale = False
    else:
        # Nothing recent: carry the last heart-rate median (or last effort) and say how old it is.
        fallback = hr_last_known or (latest_effort["vdot"] if latest_effort else None)
        current, basis, stale = fallback, "last_known", True
    last_run = runs[-1]
    resting_now = resting.latest(today)

    if current is None:
        return {"available": False, "reason": "Not enough runs with distance and time to estimate VDOT."}
    projected = projection(current, peak["vdot"] if peak else None)
    bests = race_bests(runs, efforts, today)
    predictions = []
    for key, label, distance in RACES:
        best = bests.get(key) or {}
        predictions.append({
            "key": key, "label": label, "distance_m": distance,
            "now_s": round(race_seconds(current, distance)),
            "projected_s": round(race_seconds(projected, distance)),
            "peak_s": round(race_seconds(peak["vdot"], distance)) if peak else None,
            "best_ever": best.get("ever"),
            "best_year": best.get("year"),
        })

    rtr = _return_to_run(conn, today)
    dynamics = dynamics_rows(conn)
    missing = runs_missing_dynamics(conn, today)
    total_km = sum(run["distance_km"] for run in runs)
    year_start = date(today.year, 1, 1).isoformat()
    return {
        "available": True,
        "today": today.isoformat(),
        "summary": {
            "runs": len(runs),
            "total_km": round(total_km),
            "first_run": runs[0]["date"],
            "last_run": {"date": last_run["date"], "activity_id": last_run["id"], "name": last_run["name"], "distance_km": last_run["distance_km"],
                         "days_ago": (today - date.fromisoformat(last_run["date"])).days},
            "year_km": round(sum(run["distance_km"] for run in runs if run["date"] >= year_start), 1),
            "year_runs": sum(1 for run in runs if run["date"] >= year_start),
        },
        "vdot": {
            "current": round(current, 1),
            "basis": basis,
            "stale": stale,
            "peak": {**peak, "vdot": round(peak["vdot"], 1)} if peak else None,
            "projected": round(projected, 1),
            "projection_weeks": PROJECTION_WEEKS,
            "share_of_peak_pct": round(current / peak["vdot"] * 100) if peak else None,
            "estimates": {
                "effort": {
                    "vdot": _round(recent_effort["vdot"]) if recent_effort else None,
                    "window_days": RECENT_EFFORT_DAYS,
                    "source": {k: recent_effort[k] for k in ("date", "activity_id", "name", "effort", "seconds", "distance_m")} if recent_effort else None,
                    "last_known": {"vdot": round(latest_effort["vdot"], 1), "date": latest_effort["date"]} if latest_effort else None,
                },
                "heart_rate": {
                    "vdot": _round(hr_now),
                    "runs": len(hr_recent),
                    "window_days": HR_WINDOW_DAYS,
                    "last_known": {"vdot": round(hr_last_known, 1), "date": last_hr[-1]["date"], "runs": len(last_hr)} if hr_last_known else None,
                    "since": hr_points[0]["date"] if hr_points else None,
                },
                "resting_formula": {
                    "vo2max": _round(uth_vo2max(max_hr["bpm"], resting_now)) if resting_now else None,
                    "resting_hr": _round(resting_now),
                    "max_hr": max_hr["bpm"],
                },
            },
            "inputs": {"max_hr": max_hr, "resting_hr": _round(resting_now), "resting_hr_basis": "14-day median from Apple Health" if resting_now else f"default {DEFAULT_RESTING_HR:.0f} bpm"},
        },
        "predictions": predictions,
        "paces": {
            "vdot": round(current, 1),
            "zones": training_paces(current),
            "quality_allowed": rtr["quality_allowed"],
            "hr_cap_bpm": cap,
        },
        "return_to_run": rtr,
        "timeline": _monthly_timeline(effort_points, hr_points, runs, today),
        "pace_at_cap": _pace_at_cap(hr_points, cap, today),
        "decoupling": _decoupling(conn, runs, today),
        "form": _form(dynamics, today),
        "power": _power(dynamics, today),
        "build_up": _build_up(runs, today),
        "healthfit": {
            "runs_with_dynamics": len(dynamics),
            "first_date": first_dynamics_date(conn),
            "missing": missing,
        },
        "method": [
            "Effort VDOT: Daniels–Gilbert from the fastest mile-or-longer stretch inside each run.",
            "Heart-rate VDOT: oxygen cost of a steady run's pace ÷ share of heart-rate reserve (Swain), with that fortnight's resting HR; hilly, short and walk-paced runs are skipped.",
            f"Projection: +{PROJECTION_GAIN:.0f} VDOT over {PROJECTION_WEEKS} consistent weeks (3+ runs a week), capped at half the gap to your peak.",
        ],
    }
