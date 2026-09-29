"""Outcome and cost signals that say whether a goal is paying off.

Outcome signals measure what a goal is meant to improve (power, efficiency,
strength). Cost signals measure what training is taking out of the athlete
(HRV, resting heart rate, sleep). Every signal reports how much evidence backs
it; when data is sparse the trend is ``insufficient`` rather than a guess.
"""

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Any, Callable, Optional

from .plans import normalize_workout_intent
from .power_trends import get_cycling_power_trends_data
from .strength import get_strength_overview_data

OUTCOME_LOOKBACK_MONTHS = 6
MIN_MONTHS_WITH_DATA = 3
MIN_EVIDENCE_POINTS = 6
FLAT_THRESHOLD_PCT = 2.0
STEADY_RIDE_MIN_DURATION = 30
STEADY_RUN_MIN_DURATION = 20
HARD_INTENTS = {"tempo", "interval", "race_specific"}
TOP_LIFT_COUNT = 5
E1RM_MAX_REPS = 12
# Estimated maxes wobble set to set; smaller moves are noise, not change.
STRENGTH_FLAT_THRESHOLD_PCT = 3.0
STRENGTH_RECENT_DAYS = 42
STRENGTH_MIN_RECENT_SESSIONS = 2
STRENGTH_MIN_BASELINE_SESSIONS = 3

COST_RECENT_DAYS = 7
COST_BASELINE_DAYS = 28
COST_STALE_AFTER_DAYS = 4
COST_MIN_RECENT_DAYS = 4
COST_MIN_BASELINE_DAYS = 14
COST_THRESHOLDS_PCT = {"hrv": 5.0, "resting_hr": 3.0, "sleep": 5.0}

POWER_SIGNALS = {
    "cycling_power_5m": (300, "5-min power"),
    "cycling_power_20m": (1200, "20-min power"),
    "cycling_power_60m": (3600, "60-min power"),
}

DEFAULT_OUTCOME_SIGNALS = {
    "ride_km": ("cycling_efficiency", "cycling_power_20m"),
    "zone2_hours": ("cycling_efficiency", "cycling_power_20m"),
    "quality_sessions": ("cycling_power_20m",),
    "run_km": ("run_efficiency",),
    "strength_sessions": ("strength_maintenance",),
}


def _month_keys(today: date, months: int) -> list[str]:
    keys = []
    cursor = today.replace(day=1)
    for _ in range(months):
        keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(keys))


def classify_trend(
    points: list[tuple[str, float]],
    *,
    evidence_count: int,
    higher_is_better: bool = True,
    flat_threshold_pct: float = FLAT_THRESHOLD_PCT,
) -> tuple[str, Optional[float]]:
    """Compare the later half of the data months with the earlier half.

    Returns (trend, change_pct). ``points`` are (period, value) pairs in time
    order and only include periods that actually have data.
    """
    if len(points) < MIN_MONTHS_WITH_DATA or evidence_count < MIN_EVIDENCE_POINTS:
        return "insufficient", None
    values = [value for _, value in points]
    half = len(values) // 2
    earlier = median(values[:half])
    later = median(values[-half:])
    if not earlier:
        return "insufficient", None
    change_pct = round((later - earlier) / earlier * 100, 1)
    if abs(change_pct) < flat_threshold_pct:
        return "flat", change_pct
    improving = change_pct > 0 if higher_is_better else change_pct < 0
    return ("improving" if improving else "declining"), change_pct


def _signal(
    key: str,
    label: str,
    *,
    kind: str,
    unit: str,
    series: list[dict],
    evidence_count: int,
    higher_is_better: bool = True,
    note: Optional[str] = None,
    detail: Optional[list[dict]] = None,
    flat_threshold_pct: float = FLAT_THRESHOLD_PCT,
    trend_override: Optional[tuple[str, Optional[float]]] = None,
) -> dict[str, Any]:
    points = [(item["period"], item["value"]) for item in series if item["value"] is not None]
    trend, change_pct = trend_override or classify_trend(
        points,
        evidence_count=evidence_count,
        higher_is_better=higher_is_better,
        flat_threshold_pct=flat_threshold_pct,
    )
    months_with_data = len(points)
    if trend == "insufficient" and not note:
        note = (
            f"Only {months_with_data} of {len(series)} months have data ({evidence_count} data points); "
            f"a trend needs {MIN_MONTHS_WITH_DATA} months and {MIN_EVIDENCE_POINTS} points."
        )
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "unit": unit,
        "higher_is_better": higher_is_better,
        "series": series,
        "trend": trend,
        "change_pct": change_pct,
        "evidence_count": evidence_count,
        "months_with_data": months_with_data,
        "latest": points[-1][1] if points else None,
        "note": note,
        "detail": detail or [],
    }


def _power_signal(profile: dict, key: str, months: list[str]) -> dict[str, Any]:
    duration, label = POWER_SIGNALS[key]
    monthly = {
        entry["month"]: next((effort["watts"] for effort in entry["efforts"] if effort["duration_seconds"] == duration), None)
        for entry in profile.get("monthly", [])
    }
    efforts = [
        effort for effort in profile.get("efforts", [])
        if effort["duration_seconds"] == duration and (effort.get("date") or "")[:7] in months
    ]
    series = [
        {"period": month, "value": round(monthly[month]) if monthly.get(month) else None,
         "count": sum(1 for effort in efforts if effort["date"][:7] == month)}
        for month in months
    ]
    coverage = profile.get("coverage", {})
    note = None
    if sum(1 for item in series if item["value"] is not None) < MIN_MONTHS_WITH_DATA:
        note = (
            f"Monthly bests use rides with verified power only ({coverage.get('measured_power_activities', 0)} of "
            f"{coverage.get('cycling_activities', 0)} rides); most recent months have no verified power."
        )
    return _signal(key, f"{label} (monthly best)", kind="outcome", unit="W", series=series,
                   evidence_count=len(efforts), note=note)


def _cycling_efficiency_signal(conn: sqlite3.Connection, profile: dict, months: list[str]) -> dict[str, Any]:
    verified_ids = {effort["activity_id"] for effort in profile.get("efforts", [])}
    rows = conn.execute(
        """
        SELECT id, date, type, workout_intent, duration_min, avg_watts, avg_hr
        FROM activities
        WHERE type IN ('Ride', 'VirtualRide') AND date >= ? AND avg_watts > 0 AND avg_hr > 0
        """,
        (f"{months[0]}-01",),
    ).fetchall()
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if str(row["id"]) not in verified_ids or (row["duration_min"] or 0) < STEADY_RIDE_MIN_DURATION:
            continue
        if normalize_workout_intent(row["workout_intent"], row["type"]) in HARD_INTENTS:
            continue
        by_month[row["date"][:7]].append(float(row["avg_watts"]) / float(row["avg_hr"]))
    series = [
        {"period": month, "value": round(median(by_month[month]), 2) if by_month[month] else None, "count": len(by_month[month])}
        for month in months
    ]
    return _signal(
        "cycling_efficiency",
        "Cycling efficiency (watts per heartbeat)",
        kind="outcome",
        unit="W/bpm",
        series=series,
        evidence_count=sum(len(values) for values in by_month.values()),
        note=None if len([s for s in series if s["value"]]) >= MIN_MONTHS_WITH_DATA else
        "Uses steady rides with verified power; outdoor rides without a power meter are excluded.",
    )


def _run_efficiency_signal(conn: sqlite3.Connection, months: list[str]) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT date, type, workout_intent, duration_min, distance_km, avg_hr
        FROM activities
        WHERE type = 'Run' AND date >= ? AND avg_hr > 0 AND distance_km > 0 AND duration_min >= ?
        """,
        (f"{months[0]}-01", STEADY_RUN_MIN_DURATION),
    ).fetchall()
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if normalize_workout_intent(row["workout_intent"], row["type"]) in HARD_INTENTS:
            continue
        metres_per_minute = float(row["distance_km"]) * 1000 / float(row["duration_min"])
        by_month[row["date"][:7]].append(metres_per_minute / float(row["avg_hr"]))
    series = [
        {"period": month, "value": round(median(by_month[month]), 3) if by_month[month] else None, "count": len(by_month[month])}
        for month in months
    ]
    return _signal("run_efficiency", "Running efficiency (metres per heartbeat)", kind="outcome", unit="m/beat",
                   series=series, evidence_count=sum(len(values) for values in by_month.values()))


def _estimated_1rm(weight_kg: float, reps: int) -> float:
    # Epley. Sets above 12 reps say little about maximal strength.
    return weight_kg * (1 + reps / 30)


def _strength_signal(conn: sqlite3.Connection, months: list[str], today: date) -> dict[str, Any]:
    sessions = get_strength_overview_data(conn, weeks=26)["sessions"]
    recent_start = (today - timedelta(days=STRENGTH_RECENT_DAYS)).isoformat()
    # Per lift, the best estimated max of each session: (date, e1rm).
    session_bests: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for session in sessions:
        if session["workout_date"][:7] not in months:
            continue
        for exercise in session["exercises"]:
            estimates = [
                _estimated_1rm(float(item["weight_kg"]), int(item["reps"]))
                for item in exercise["sets"]
                if not item["is_warmup"] and (item["weight_kg"] or 0) > 0 and 0 < (item["reps"] or 0) <= E1RM_MAX_REPS
            ]
            if estimates:
                session_bests[exercise["exercise_name"]].append((session["workout_date"], max(estimates)))

    # The lifts trained most often are the ones a maintenance goal is protecting.
    top_lifts = sorted(session_bests, key=lambda name: (-len(session_bests[name]), name))[:TOP_LIFT_COUNT]
    index_by_month: dict[str, list[float]] = defaultdict(list)
    detail = []
    lift_changes = []
    months_with_any_lift: set[str] = set()
    for name in top_lifts:
        bests = sorted(session_bests[name])
        by_month: dict[str, list[float]] = defaultdict(list)
        for day, value in bests:
            by_month[day[:7]].append(value)
        lift_months = [month for month in months if by_month[month]]
        months_with_any_lift.update(lift_months)
        base_month = median(by_month[lift_months[0]])
        for month in lift_months:
            index_by_month[month].append(median(by_month[month]) / base_month * 100)

        # Typical recent level against the established level before it. Medians
        # of session bests ignore one-off peak days and single off days, which
        # matters with coarse dumbbell jumps.
        baseline = [value for day, value in bests if day < recent_start]
        recent = [value for day, value in bests if day >= recent_start]
        change = None
        if len(baseline) >= STRENGTH_MIN_BASELINE_SESSIONS and len(recent) >= STRENGTH_MIN_RECENT_SESSIONS:
            change = round((median(recent) - median(baseline)) / median(baseline) * 100, 1)
            lift_changes.append(change)
        detail.append({
            "exercise": name,
            "sessions": len(bests),
            "baseline_e1rm_kg": round(median(baseline), 1) if baseline else None,
            "recent_e1rm_kg": round(median(recent), 1) if recent else None,
            "change_pct": change,
        })

    evidence = sum(len(session_bests[name]) for name in top_lifts)
    if len(months_with_any_lift) < MIN_MONTHS_WITH_DATA or evidence < MIN_EVIDENCE_POINTS or not lift_changes:
        trend_override = ("insufficient", None)
        note = "Needs 3+ months of logged sets and at least 2 sessions of a top lift in the last 6 weeks."
    else:
        overall = round(median(lift_changes), 1)
        trend = "flat" if abs(overall) < STRENGTH_FLAT_THRESHOLD_PCT else "improving" if overall > 0 else "declining"
        trend_override = (trend, overall)
        note = f"Median change across {len(lift_changes)} top lifts, last 6 weeks vs the months before."
    series = [
        {"period": month, "value": round(mean(index_by_month[month]), 1) if index_by_month[month] else None,
         "count": len(index_by_month[month])}
        for month in months
    ]
    return _signal(
        "strength_maintenance",
        "Top-lift strength (estimated 1RM)",
        kind="outcome",
        unit="index",
        series=series,
        evidence_count=evidence,
        detail=detail,
        note=note,
        trend_override=trend_override,
    )


def build_outcome_signals(conn: sqlite3.Connection, keys: Optional[list[str]] = None, today: Optional[date] = None) -> dict[str, dict]:
    current = today or datetime.now().date()
    months = _month_keys(current, OUTCOME_LOOKBACK_MONTHS)
    wanted = set(keys) if keys else {*POWER_SIGNALS, "cycling_efficiency", "run_efficiency", "strength_maintenance"}
    signals: dict[str, dict] = {}
    profile = get_cycling_power_trends_data(conn) if wanted & {*POWER_SIGNALS, "cycling_efficiency"} else {}
    for key in POWER_SIGNALS:
        if key in wanted:
            signals[key] = _power_signal(profile, key, months)
    if "cycling_efficiency" in wanted:
        signals["cycling_efficiency"] = _cycling_efficiency_signal(conn, profile, months)
    if "run_efficiency" in wanted:
        signals["run_efficiency"] = _run_efficiency_signal(conn, months)
    if "strength_maintenance" in wanted:
        signals["strength_maintenance"] = _strength_signal(conn, months, current)
    return signals


OUTCOME_SIGNAL_KEYS = (*POWER_SIGNALS, "cycling_efficiency", "run_efficiency", "strength_maintenance")


def outcome_keys_for_goal(goal: dict) -> list[str]:
    override = goal.get("outcome_signal")
    if override in OUTCOME_SIGNAL_KEYS:
        return [override]
    return list(DEFAULT_OUTCOME_SIGNALS.get(goal.get("metric_type"), ()))


def _health_history(conn: sqlite3.Connection, metric: str, days: int) -> list[dict]:
    # Imported lazily: the health importer pulls in streaming-JSON parsing that
    # goal signals never need.
    from .health_data import get_health_metric_history

    return get_health_metric_history(conn, metric, days)


HealthHistoryFn = Callable[[sqlite3.Connection, str, int], list[dict]]

COST_SIGNALS = {
    "hrv": ("HRV", "ms", True),
    "resting_hr": ("Resting heart rate", "bpm", False),
    "sleep": ("Sleep", "h", True),
}


def _cost_signal(metric: str, history: list[dict], today: date) -> dict[str, Any]:
    label, unit, higher_is_better = COST_SIGNALS[metric]
    daily = {item["date"]: float(item["value"]) for item in history if item.get("value") is not None}
    latest_date = max(daily) if daily else None
    base = {
        "key": metric,
        "label": label,
        "kind": "cost",
        "unit": unit,
        "higher_is_better": higher_is_better,
        "latest_date": latest_date,
        "stale": True,
        "trend": "insufficient",
        "change_pct": None,
        "recent_mean": None,
        "baseline_mean": None,
        "series": [],
        "note": None,
    }
    if not latest_date:
        return {**base, "note": f"No {label.lower()} data imported."}

    anchor = datetime.strptime(latest_date, "%Y-%m-%d").date()
    days_old = (today - anchor).days
    recent_days = [(anchor - timedelta(days=offset)).isoformat() for offset in range(COST_RECENT_DAYS)]
    baseline_days = [(anchor - timedelta(days=offset)).isoformat() for offset in range(COST_RECENT_DAYS, COST_RECENT_DAYS + COST_BASELINE_DAYS)]
    recent = [daily[day] for day in recent_days if day in daily]
    baseline = [daily[day] for day in baseline_days if day in daily]
    series = []
    for week in range(5, 0, -1):
        days = [(anchor - timedelta(days=offset)).isoformat() for offset in range((week - 1) * 7, week * 7)]
        values = [daily[day] for day in days if day in daily]
        series.append({"period": days[-1], "value": round(mean(values), 1) if values else None, "count": len(values)})

    result = {
        **base,
        "stale": days_old > COST_STALE_AFTER_DAYS,
        "series": series,
        "recent_mean": round(mean(recent), 1) if recent else None,
        "baseline_mean": round(mean(baseline), 1) if baseline else None,
    }
    if len(recent) < COST_MIN_RECENT_DAYS or len(baseline) < COST_MIN_BASELINE_DAYS:
        return {**result, "note": f"Needs {COST_MIN_RECENT_DAYS}+ recent days and {COST_MIN_BASELINE_DAYS}+ baseline days of {label.lower()}."}

    change_pct = round((mean(recent) - mean(baseline)) / mean(baseline) * 100, 1)
    threshold = COST_THRESHOLDS_PCT[metric]
    if abs(change_pct) < threshold:
        trend = "flat"
    else:
        trend = "improving" if (change_pct > 0) == higher_is_better else "declining"
    note = f"Last data {latest_date} ({days_old} days ago); treat as stale." if result["stale"] else None
    return {**result, "trend": trend, "change_pct": change_pct, "note": note}


def build_cost_signals(
    conn: sqlite3.Connection,
    today: Optional[date] = None,
    history_fn: Optional[HealthHistoryFn] = None,
) -> dict[str, dict]:
    current = today or datetime.now().date()
    load = history_fn or _health_history
    lookback = COST_RECENT_DAYS + COST_BASELINE_DAYS + 30
    return {metric: _cost_signal(metric, load(conn, metric, lookback), current) for metric in COST_SIGNALS}


def build_goal_outcomes(
    conn: sqlite3.Connection,
    goal: dict,
    *,
    signals: Optional[dict[str, dict]] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    keys = outcome_keys_for_goal(goal)
    if not keys:
        return {"linked": [], "signals": [], "reason": "No outcome signal is linked to this goal type yet."}
    available = signals if signals is not None else build_outcome_signals(conn, keys, today)
    return {
        "linked": keys,
        "overridden": bool(goal.get("outcome_signal") in OUTCOME_SIGNAL_KEYS),
        "signals": [available[key] for key in keys if key in available],
        "reason": None,
    }


def attach_goal_outcomes(conn: sqlite3.Connection, goals: list[dict], today: Optional[date] = None) -> list[dict]:
    keys = sorted({key for goal in goals for key in outcome_keys_for_goal(goal)})
    signals = build_outcome_signals(conn, keys, today) if keys else {}
    return [{**goal, "outcomes": build_goal_outcomes(conn, goal, signals=signals, today=today)} for goal in goals]
