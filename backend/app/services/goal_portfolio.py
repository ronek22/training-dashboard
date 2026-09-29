"""Do the active goals fit into the time the athlete actually trains?

Each goal implies a weekly time cost (distance / typical speed, sessions x typical
session length, zone 2 hours as-is). The sum is compared with the hours trained
per week recently, or in the same season when the season is about to change.
Anchor goals count towards the budget but are never offered for reduction.
"""

import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

from .goal_history import _majority_season, recurring_period_windows
from .seasons import SEASON_LABELS, season_for

TREND_WEEKS = 8
SEASON_LOOKAHEAD_DAYS = 14
SEASON_LOOKBACK_WEEKS = 52
SEASON_MAX_WEEKS = 26
MIN_BASIS_WEEKS = 4
MIN_ACTUAL_WEEKLY_HOURS = 1.0
MIN_SPEED_SAMPLE_HOURS = 2.0
OVER_COMMIT_RATIO = 1.15
WEEKS_PER_MONTH = 52 / 12
MAX_CONTRIBUTORS = 3
MAX_REDUCTION_CANDIDATES = 2

RIDE_TYPES = ("Ride", "VirtualRide")
DISTANCE_SPORTS = {"ride_km": RIDE_TYPES, "run_km": ("Run",)}
SESSION_SPORTS = {"strength_sessions": ("WeightTraining",), "quality_sessions": RIDE_TYPES}
# Zone 2 and quality work happen inside rides, so alongside a ride-distance goal
# they share its hours instead of adding to them.
CYCLING_OVERLAP_METRICS = {"ride_km", "zone2_hours", "quality_sessions"}


def _hours(minutes: Optional[float]) -> float:
    return float(minutes or 0) / 60


def _load_activities(conn: sqlite3.Connection, start: date, end: date) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT date, type, distance_km, duration_min FROM activities WHERE date >= ? AND date <= ?",
        (start.isoformat(), end.isoformat()),
    ).fetchall()


def _basis_windows(conn: sqlite3.Connection, today: date, off_months: list[int]) -> tuple[list[tuple[date, date]], dict]:
    recent, _ = recurring_period_windows("week", TREND_WEEKS, today)
    first = conn.execute("SELECT MIN(date) AS day FROM activities").fetchone()["day"]
    data_start = date.fromisoformat(first[:10]) if first else None
    recent = [window for window in recent if not data_start or window[1] >= data_start]
    basis = {"kind": "recent", "label": f"last {TREND_WEEKS} weeks", "season": None}
    upcoming = season_for(today + timedelta(days=SEASON_LOOKAHEAD_DAYS), off_months) if off_months else None
    if upcoming and upcoming != _majority_season(recent, off_months):
        earlier, _ = recurring_period_windows("week", SEASON_LOOKBACK_WEEKS, today)
        same_season = [
            window for window in earlier
            if window not in recent
            and season_for(window[0] + timedelta(days=3), off_months) == upcoming
            and (not data_start or window[1] >= data_start)
        ][-SEASON_MAX_WEEKS:]
        if len(same_season) >= MIN_BASIS_WEEKS:
            label = SEASON_LABELS[upcoming]
            return same_season, {"kind": "season", "label": f"{len(same_season)} past {label} weeks", "season": upcoming}
    return recent, basis


def _period_weeks(goal: dict, today: date) -> Optional[float]:
    if goal.get("period_type") == "week":
        return 1.0
    if goal.get("period_type") == "month":
        return WEEKS_PER_MONTH
    end = goal.get("end_date")
    if not end:
        return None
    return max(1.0, (date.fromisoformat(end[:10]) - today).days / 7)


def _weekly_amount(goal: dict, today: date) -> Optional[float]:
    """Metric units per week the goal asks for (remaining work for long-running goals)."""
    target = float(goal.get("target_value") or 0)
    if goal.get("period_type") in {"week", "month"}:
        return target / _period_weeks(goal, today)
    remaining = max(0.0, target - float(goal.get("current_value") or 0))
    weeks = _period_weeks(goal, today)
    return remaining / weeks if weeks else None


def _sport_speed(rows: list[sqlite3.Row], types: tuple[str, ...]) -> Optional[float]:
    used = [row for row in rows if row["type"] in types and (row["distance_km"] or 0) > 0 and (row["duration_min"] or 0) > 0]
    hours = sum(_hours(row["duration_min"]) for row in used)
    if hours < MIN_SPEED_SAMPLE_HOURS:
        return None
    return sum(row["distance_km"] for row in used) / hours


def _median_session_hours(rows: list[sqlite3.Row], types: Optional[tuple[str, ...]]) -> Optional[float]:
    durations = [row["duration_min"] for row in rows if (types is None or row["type"] in types) and (row["duration_min"] or 0) > 0]
    return _hours(median(durations)) if durations else None


def _estimate_goal(goal: dict, rows: list[sqlite3.Row], today: date) -> dict[str, Any]:
    metric = goal.get("metric_type")
    amount = _weekly_amount(goal, today)
    item = {
        "goal_id": goal["id"], "title": goal["title"], "metric_type": metric,
        "commitment": goal.get("commitment") or "flexible",
        "weekly_hours": None, "counted_hours": None, "basis": None, "note": None,
    }
    if amount is None:
        return {**item, "note": "No end date to spread the goal over."}
    if amount <= 0:
        return {**item, "weekly_hours": 0.0, "basis": "already reached"}

    if metric in DISTANCE_SPORTS:
        speed = _sport_speed(rows, DISTANCE_SPORTS[metric])
        if not speed:
            return {**item, "note": "Not enough recent distance data to estimate speed."}
        return {**item, "weekly_hours": amount / speed, "basis": f"{amount:.0f} km/week at {speed:.1f} km/h"}
    if metric == "zone2_hours":
        return {**item, "weekly_hours": amount, "basis": f"{amount:.1f} h/week of zone 2"}
    if metric in SESSION_SPORTS or metric == "activities_count":
        activity_type = goal.get("activity_type")
        types = SESSION_SPORTS.get(metric) or ((RIDE_TYPES if activity_type == "Ride" else (activity_type,)) if activity_type else None)
        session = _median_session_hours(rows, types)
        if not session:
            return {**item, "note": "No recent sessions to estimate a typical length."}
        return {**item, "weekly_hours": amount * session, "basis": f"{amount:.1f} sessions/week x {session * 60:.0f} min"}
    return {**item, "note": "Time cost is not estimated for this kind of goal."}


def _apply_overlap(items: list[dict]) -> None:
    """Within the cycling group only the largest goal adds hours."""
    cycling = [item for item in items if item["metric_type"] in CYCLING_OVERLAP_METRICS and item["weekly_hours"]]
    largest = max(cycling, key=lambda item: item["weekly_hours"], default=None)
    for item in items:
        if item["weekly_hours"] is None:
            continue
        shared = item in cycling and item is not largest
        item["counted_hours"] = 0.0 if shared else item["weekly_hours"]
        if shared:
            item["note"] = f"Shares riding time with {largest['title']}."


def _explanation(implied: float, actual: float, ratio: float, basis: dict, contributors: list[dict],
                 candidates: list[dict], anchors: list[dict]) -> str:
    parts = [
        f"Your active goals ask for about {implied:.1f} h/week, but you trained {actual:.1f} h/week "
        f"over the {basis['label']} ({ratio:.2f}x)."
    ]
    if contributors:
        parts.append("Biggest: " + ", ".join(f"{item['title']} (~{item['counted_hours']:.1f} h)" for item in contributors) + ".")
    if candidates:
        parts.append("Easiest to scale back: " + ", ".join(item["title"] for item in candidates) + ".")
    if anchors:
        parts.append("Anchor goals (" + ", ".join(item["title"] for item in anchors) + ") count in the total but are not suggested for reduction.")
    return " ".join(parts)


def build_portfolio_check(
    conn: sqlite3.Connection,
    goals: list[dict],
    today: Optional[date] = None,
    off_season_months: Optional[list[int]] = None,
) -> dict[str, Any]:
    current = today or date.today()
    active = [goal for goal in goals if goal.get("is_active", True) and not goal.get("season_ended")]
    windows, basis = _basis_windows(conn, current, off_season_months or [])
    result: dict[str, Any] = {
        "status": "insufficient_evidence", "basis": basis, "threshold_ratio": OVER_COMMIT_RATIO,
        "implied_weekly_hours": None, "actual_weekly_hours": None, "ratio": None,
        "goals": [], "contributors": [], "reduction_candidates": [], "summary": None,
    }
    if len(windows) < MIN_BASIS_WEEKS:
        result["summary"] = "Not enough completed training weeks to compare against yet."
        return result

    rows = _load_activities(conn, windows[0][0], windows[-1][1])
    in_windows = [row for row in rows if any(start.isoformat() <= row["date"][:10] <= end.isoformat() for start, end in windows)]
    actual = sum(_hours(row["duration_min"]) for row in in_windows) / len(windows)
    result["actual_weekly_hours"] = round(actual, 1)
    if actual < MIN_ACTUAL_WEEKLY_HOURS:
        result["summary"] = "Too little recent training to judge the time budget."
        return result

    items = [_estimate_goal(goal, in_windows, current) for goal in active]
    _apply_overlap(items)
    estimated = [item for item in items if item["counted_hours"] is not None]
    for item in items:
        for key in ("weekly_hours", "counted_hours"):
            item[key] = None if item[key] is None else round(item[key], 1)
    result["goals"] = items
    if not estimated:
        result["status"] = "no_estimate"
        result["summary"] = "None of the active goals imply a time cost that can be estimated."
        return result

    implied = sum(item["counted_hours"] for item in estimated)
    ratio = implied / actual
    ranked = sorted((item for item in estimated if item["counted_hours"] > 0), key=lambda item: -item["counted_hours"])
    candidates = [item for item in ranked if item["commitment"] != "anchor"][:MAX_REDUCTION_CANDIDATES]
    anchors = [item for item in ranked if item["commitment"] == "anchor"]
    result.update(
        status="over_committed" if ratio > OVER_COMMIT_RATIO else "ok",
        implied_weekly_hours=round(implied, 1),
        ratio=round(ratio, 2),
        contributors=ranked[:MAX_CONTRIBUTORS],
        reduction_candidates=candidates if ratio > OVER_COMMIT_RATIO else [],
    )
    if result["status"] == "over_committed":
        result["summary"] = _explanation(implied, actual, ratio, basis, ranked[:MAX_CONTRIBUTORS], candidates, anchors)
    else:
        result["summary"] = (
            f"Your active goals ask for about {implied:.1f} h/week against {actual:.1f} h/week "
            f"trained over the {basis['label']}, so the budget fits."
        )
    return result


def portfolio_conflict(portfolio: Optional[dict]) -> Optional[dict]:
    """The portfolio check in the shape of plans._build_goal_conflicts entries."""
    if not portfolio or portfolio.get("status") != "over_committed":
        return None
    titles = [item["title"] for item in portfolio["reduction_candidates"] or portfolio["contributors"]]
    return {
        "type": "time_budget",
        "label": "Goals need more time than you train",
        "summary": portfolio["summary"],
        "goal_titles": titles[:MAX_CONTRIBUTORS],
    }
