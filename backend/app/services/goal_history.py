"""Per-period history of volume and process goals against their own target.

The history answers "how does this goal usually go?" rather than "how is the
current period going?". Goal verdicts and target calibration build on it, so
every value comes from ``goal_value_for_window`` and matches the progress bars.
"""

import sqlite3
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any, Callable, Optional

from .goals import goal_metric_unit, goal_value_for_window
from .seasons import SEASON_LABELS, next_season_change, season_for
from .settings import get_athlete_profile_for_conn

DEFAULT_HISTORY_PERIODS = 12
MAX_HISTORY_PERIODS = 52
RECENT_RATE_WEEKS = 8
ROLLING_BEST_WINDOW = 4
HISTORY_METRICS = {"ride_km", "run_km", "strength_sessions", "activities_count", "zone2_hours", "quality_sessions"}
# Weather-driven metrics: winter weeks are judged against past winter weeks.
SEASONAL_METRICS = {"ride_km", "run_km", "zone2_hours"}
SEASON_LOOKAHEAD_DAYS = 14
SEASON_REFERENCE_LOOKBACK = {"week": 52, "month": 12}
SEASON_REFERENCE_MAX_PERIODS = {"week": 26, "month": 6}

ValueFn = Callable[[str, str], float]


def _percentile(values: list[float], fraction: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _slope(values: list[float]) -> Optional[float]:
    """Least-squares change per period; None when there are too few points."""
    count = len(values)
    if count < 3:
        return None
    mean_x = (count - 1) / 2
    mean_y = sum(values) / count
    denominator = sum((index - mean_x) ** 2 for index in range(count))
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
    return numerator / denominator


def _best_rolling_mean(values: list[float], window: int) -> Optional[float]:
    if len(values) < window:
        return max(values) if values else None
    return max(sum(values[index:index + window]) / window for index in range(len(values) - window + 1))


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _previous_month_start(day: date) -> date:
    return (_month_start(day) - timedelta(days=1)).replace(day=1)


def _month_end(start: date) -> date:
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def recurring_period_windows(period_type: str, count: int, today: date) -> tuple[list[tuple[date, date]], tuple[date, date]]:
    """Return ``count`` completed windows (oldest first) and the current partial window."""
    windows: list[tuple[date, date]] = []
    if period_type == "week":
        current_start = _week_start(today)
        start = current_start
        for _ in range(count):
            start -= timedelta(days=7)
            windows.append((start, start + timedelta(days=6)))
        return list(reversed(windows)), (current_start, current_start + timedelta(days=6))

    current_start = _month_start(today)
    start = current_start
    for _ in range(count):
        start = _previous_month_start(start)
        windows.append((start, _month_end(start)))
    return list(reversed(windows)), (current_start, _month_end(current_start))


def _period_label(period_type: str, start: date) -> str:
    if period_type == "week":
        return start.strftime("%d %b").lstrip("0")
    return start.strftime("%b %Y")


def _data_start(conn: sqlite3.Connection) -> Optional[date]:
    row = conn.execute("SELECT MIN(date) AS first_day FROM activities").fetchone()
    if not row or not row["first_day"]:
        return None
    try:
        return datetime.strptime(row["first_day"][:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _created_on(goal: dict) -> Optional[date]:
    value = goal.get("created_at")
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _rounded(value: Optional[float]) -> Optional[float]:
    # Plain rounding: goal-style rounding ceils counts, which would report a
    # 2.5-session median as 3.
    return None if value is None else round(value, 1)


def _period_stats(values: list[float], target: float) -> dict[str, Any]:
    hits = sum(1 for value in values if target > 0 and value >= target)
    median_value = median(values) if values else None
    return {
        "periods": len(values),
        "hit_count": hits,
        "hit_rate": round(hits / len(values), 2) if values else None,
        "median": _rounded(median_value),
        "p75": _rounded(_percentile(values, 0.75)),
        "margin": round(median_value / target, 2) if median_value is not None and target > 0 else None,
    }


def _majority_season(windows: list[tuple[date, date]], off_months: list[int]) -> Optional[str]:
    seasons = [season_for(start + (end - start) / 2, off_months) for start, end in windows]
    if not seasons:
        return None
    return max(("off", "main"), key=seasons.count)


def _season_context(
    goal: dict,
    value_fn: ValueFn,
    recent_windows: list[tuple[date, date]],
    today: date,
    data_start: Optional[date],
    off_months: Optional[list[int]],
) -> Optional[dict[str, Any]]:
    """Compare the coming season with the one the recent history comes from.

    When they differ (e.g. autumn after a summer of outdoor riding), the same
    season last year becomes the reference for judging the goal.
    """
    if goal["metric_type"] not in SEASONAL_METRICS or not off_months or len(off_months) == 12:
        return None
    upcoming = season_for(today + timedelta(days=SEASON_LOOKAHEAD_DAYS), off_months)
    history_season = _majority_season(recent_windows, off_months)
    context: dict[str, Any] = {
        "upcoming": upcoming,
        "upcoming_label": SEASON_LABELS[upcoming],
        "history": history_season,
        "shift": history_season is not None and upcoming != history_season,
        "next_change": (next_season_change(today, off_months) or today).isoformat(),
        "reference": None,
    }
    if not context["shift"]:
        return context

    period_type = goal["period_type"]
    earlier, _ = recurring_period_windows(period_type, SEASON_REFERENCE_LOOKBACK[period_type], today)
    recent = set(recent_windows)
    candidates = [
        window for window in earlier
        if window not in recent
        and season_for(window[0] + (window[1] - window[0]) / 2, off_months) == upcoming
        and (not data_start or window[1] >= data_start)
    ][-SEASON_REFERENCE_MAX_PERIODS[period_type]:]
    if not candidates:
        return context
    target = float(goal.get("target_value") or 0)
    values = [value_fn(start.isoformat(), end.isoformat()) for start, end in candidates]
    context["reference"] = {
        **_period_stats(values, target),
        "from": candidates[0][0].isoformat(),
        "to": candidates[-1][1].isoformat(),
        "label": f"{candidates[0][0].strftime('%b %Y')}–{candidates[-1][1].strftime('%b %Y')}",
    }
    return context


def _recurring_history(
    goal: dict,
    value_fn: ValueFn,
    periods: int,
    today: date,
    data_start: Optional[date],
    off_months: Optional[list[int]] = None,
) -> dict[str, Any]:
    metric_type = goal["metric_type"]
    target = float(goal.get("target_value") or 0)
    windows, (current_start, current_end) = recurring_period_windows(goal["period_type"], periods, today)
    if data_start:
        # Periods before the first synced activity would read as misses.
        windows = [window for window in windows if window[1] >= data_start]
    created_on = _created_on(goal)

    entries = []
    for start, end in windows:
        value = value_fn(start.isoformat(), end.isoformat())
        entries.append({
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "label": _period_label(goal["period_type"], start),
            "value": _rounded(value),
            "hit": target > 0 and value >= target,
            "partial": False,
            "before_goal": bool(created_on and end < created_on),
        })
    current_value = value_fn(current_start.isoformat(), min(current_end, today).isoformat())
    current = {
        "period_start": current_start.isoformat(),
        "period_end": current_end.isoformat(),
        "label": "Now",
        "value": _rounded(current_value),
        "hit": target > 0 and current_value >= target,
        "partial": True,
        "before_goal": False,
    }

    values = [entry["value"] for entry in entries]
    hits = sum(1 for entry in entries if entry["hit"])
    median_value = median(values) if values else None
    streak = 0
    for entry in reversed(entries):
        if not entry["hit"]:
            break
        streak += 1
    slope = _slope(values)
    mean_value = sum(values) / len(values) if values else None

    return {
        "available": bool(entries),
        "reason": None if entries else "No completed periods with synced activity data yet.",
        "kind": "recurring",
        "period_type": goal["period_type"],
        "unit": goal_metric_unit(metric_type),
        "target": target,
        "entries": [*entries, current],
        "season": _season_context(goal, value_fn, list(windows), today, data_start, off_months),
        "stats": {
            "periods": len(entries),
            "periods_since_created": sum(1 for entry in entries if not entry["before_goal"]),
            "hit_count": hits,
            "hit_rate": round(hits / len(entries), 2) if entries else None,
            "median": _rounded(median_value),
            "p75": _rounded(_percentile(values, 0.75)),
            "mean": _rounded(mean_value),
            "best": _rounded(max(values) if values else None),
            "best_4_period_rate": _rounded(_best_rolling_mean(values, ROLLING_BEST_WINDOW)),
            "current_streak": streak,
            "trend_slope": None if slope is None else round(slope, 2),
            "trend_slope_pct": None if slope is None or not mean_value else round(slope / mean_value * 100, 1),
            "margin": round(median_value / target, 2) if median_value is not None and target > 0 else None,
        },
    }


def _seasonal_weekly_rates(
    value_fn: ValueFn,
    today: date,
    data_start: Optional[date],
    off_months: list[int],
    recent_windows: list[tuple[date, date]],
) -> dict[str, float]:
    """Average week per season over the past year, excluding the recent weeks."""
    earlier, _ = recurring_period_windows("week", SEASON_REFERENCE_LOOKBACK["week"], today)
    recent = set(recent_windows)
    by_season: dict[str, list[float]] = {"off": [], "main": []}
    for start, end in earlier:
        if (start, end) in recent or (data_start and end < data_start):
            continue
        by_season[season_for(start + timedelta(days=3), off_months)].append(value_fn(start.isoformat(), end.isoformat()))
    return {season: sum(values) / len(values) for season, values in by_season.items() if len(values) >= 4}


def _projected_total(
    cumulative: float,
    recent_rate: Optional[float],
    today: date,
    year_end: date,
    seasonal_rates: dict[str, float],
    recent_season: Optional[str],
    off_months: Optional[list[int]],
) -> tuple[Optional[float], str]:
    if recent_rate is None:
        return None, "recent"
    if not off_months or not seasonal_rates or recent_season is None:
        return cumulative + recent_rate * (year_end - today).days / 7, "recent"
    total = cumulative
    day = today + timedelta(days=1)
    while day <= year_end:
        season = season_for(day, off_months)
        rate = recent_rate if season == recent_season else seasonal_rates.get(season, recent_rate)
        total += rate / 7
        day += timedelta(days=1)
    return total, "seasonal"


def _yearly_history(
    goal: dict,
    value_fn: ValueFn,
    today: date,
    data_start: Optional[date],
    off_months: Optional[list[int]] = None,
) -> dict[str, Any]:
    metric_type = goal["metric_type"]
    target = float(goal.get("target_value") or 0)
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    days_in_year = (year_end - year_start).days + 1

    entries = []
    cumulative = 0.0
    reached_in = None
    month = year_start
    while month <= today:
        month_end = min(_month_end(month), today)
        value = value_fn(month.isoformat(), month_end.isoformat())
        cumulative += value
        elapsed_days = (month_end - year_start).days + 1
        pro_rata = target * elapsed_days / days_in_year
        if reached_in is None and target > 0 and cumulative >= target:
            reached_in = month.strftime("%Y-%m")
        entries.append({
            "period_start": month.isoformat(),
            "period_end": _month_end(month).isoformat(),
            "label": month.strftime("%b"),
            "value": _rounded(value),
            "cumulative": _rounded(cumulative),
            "pro_rata_target": _rounded(pro_rata),
            "on_pace": cumulative >= pro_rata,
            "partial": month_end < _month_end(month),
        })
        month = _month_end(month) + timedelta(days=1)

    weekly_windows, _ = recurring_period_windows("week", DEFAULT_HISTORY_PERIODS, today)
    if data_start:
        weekly_windows = [window for window in weekly_windows if window[1] >= data_start]
    weekly_values = [value_fn(start.isoformat(), end.isoformat()) for start, end in weekly_windows]
    recent_values = weekly_values[-RECENT_RATE_WEEKS:]
    recent_rate = sum(recent_values) / len(recent_values) if recent_values else None

    remaining = max(target - cumulative, 0.0)
    days_left = (year_end - today).days
    weeks_left = days_left / 7
    required_rate = remaining / weeks_left if weeks_left > 0 else None
    seasonal = metric_type in SEASONAL_METRICS and bool(off_months) and len(off_months or []) < 12
    recent_windows = weekly_windows[-RECENT_RATE_WEEKS:]
    projected_total, projection_basis = _projected_total(
        cumulative,
        recent_rate,
        today,
        year_end,
        _seasonal_weekly_rates(value_fn, today, data_start, off_months, recent_windows) if seasonal else {},
        _majority_season(recent_windows, off_months) if seasonal else None,
        off_months if seasonal else None,
    )
    if remaining == 0:
        required_rate_ratio = 0.0
    elif required_rate is None or not recent_rate:
        required_rate_ratio = None
    else:
        required_rate_ratio = round(required_rate / recent_rate, 2)

    return {
        "available": bool(entries),
        "reason": None,
        "kind": "yearly",
        "period_type": "year",
        "unit": goal_metric_unit(metric_type),
        "target": target,
        "entries": entries,
        "stats": {
            "year_to_date": _rounded(cumulative),
            "remaining": _rounded(remaining),
            "reached_in": reached_in,
            "days_left": days_left,
            "recent_rate_per_week": _rounded(recent_rate),
            "best_4_week_rate": _rounded(_best_rolling_mean(weekly_values, ROLLING_BEST_WINDOW)),
            "required_rate_per_week": _rounded(required_rate),
            "required_rate_ratio": required_rate_ratio,
            "projected_total": _rounded(projected_total),
            "projection_basis": projection_basis,
        },
    }


def build_goal_period_history(
    conn: sqlite3.Connection,
    goal: dict,
    *,
    periods: int = DEFAULT_HISTORY_PERIODS,
    today: Optional[date] = None,
    data_start: Optional[date] = None,
    off_season_months: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Build history for a serialized goal (or any mapping with the goal columns).

    ``off_season_months`` enables season-aware comparisons; ``None`` reads them
    from the athlete profile.
    """
    if goal.get("goal_family") not in {"accumulation", "process"} or goal.get("metric_type") not in HISTORY_METRICS:
        return _unavailable("History is tracked for volume and frequency goals; benchmark and event goals use their benchmark history.")
    current = today or datetime.now().date()
    periods = max(1, min(int(periods), MAX_HISTORY_PERIODS))
    first_day = data_start or _data_start(conn)
    off_months = off_season_months if off_season_months is not None else get_athlete_profile_for_conn(conn)["off_season_months"]

    def value_fn(start_date: str, end_date: str) -> float:
        return goal_value_for_window(conn, goal, start_date=start_date, end_date=end_date)

    if goal.get("period_type") == "year":
        return _yearly_history(goal, value_fn, current, first_day, off_months)
    if goal.get("period_type") in {"week", "month"}:
        return _recurring_history(goal, value_fn, periods, current, first_day, off_months)
    return _unavailable("Unknown goal period.")


def attach_goal_histories(conn: sqlite3.Connection, goals: list[dict], today: Optional[date] = None) -> list[dict]:
    first_day = _data_start(conn)
    off_months = get_athlete_profile_for_conn(conn)["off_season_months"]
    return [
        {**goal, "history": build_goal_period_history(conn, goal, today=today, data_start=first_day, off_season_months=off_months)}
        for goal in goals
    ]
