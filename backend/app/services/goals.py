import json
import calendar
import sqlite3
import re
from math import ceil
from datetime import date, datetime, timedelta
from typing import Any, Optional

from ..repositories.goals import insert_goal, list_goal_rows
from .metrics import get_zone2_foundation_for_window
from .settings import modality_for_goal, get_modality_restrictions_for_conn, restriction_summary_text

GOAL_FAMILY_LABELS = {
    "accumulation": "Accumulation",
    "process": "Process",
    "event_performance": "Event",
    "benchmark": "Benchmark",
}

REQUIREMENT_TYPE_LABELS = {
    "aerobic_volume": "Aerobic volume",
    "aerobic_endurance": "Aerobic endurance",
    "strength_frequency": "Strength frequency",
    "session_frequency": "Session frequency",
    "event_specific_quality": "Event-specific quality",
    "long_aerobic_support": "Long aerobic support",
    "benchmark_specific_quality": "Benchmark-specific quality",
}

COUNT_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "once": 1.0,
    "two": 2.0,
    "twice": 2.0,
    "three": 3.0,
    "thrice": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}

MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def goal_metric_unit(metric_type: str) -> str:
    if metric_type in {"ride_km", "run_km"}:
        return "km"
    if metric_type == "strength_sessions":
        return "sessions"
    if metric_type == "activities_count":
        return "activities"
    if metric_type == "zone2_hours":
        return "hours"
    if metric_type == "event_time":
        return "min"
    if metric_type == "benchmark_power":
        return "W"
    if metric_type == "benchmark_time":
        return "min"
    return ""


def rounded_goal_value(metric_type: str, value: float) -> float:
    if metric_type in {"strength_sessions", "activities_count"}:
        if value >= 0:
            return float(ceil(value))
        return float(-ceil(abs(value)))
    if metric_type == "benchmark_power":
        return round(value, 0)
    return round(value, 1)


def goal_metric_label(metric_type: str) -> str:
    if metric_type == "ride_km":
        return "ride volume"
    if metric_type == "run_km":
        return "run volume"
    if metric_type == "strength_sessions":
        return "strength frequency"
    if metric_type == "activities_count":
        return "activity count"
    if metric_type == "zone2_hours":
        return "zone 2 time"
    if metric_type == "event_time":
        return "event performance"
    if metric_type == "benchmark_power":
        return "power benchmark"
    if metric_type == "benchmark_time":
        return "benchmark performance"
    return "goal"


def goal_family_label(goal_family: str) -> str:
    return GOAL_FAMILY_LABELS.get(goal_family, "Goal")


def requirement_type_label(requirement_type: str) -> str:
    return REQUIREMENT_TYPE_LABELS.get(requirement_type, "Requirement")


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _compact_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _number_from_token(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    token = value.strip().lower()
    if token in COUNT_WORDS:
        return COUNT_WORDS[token]
    try:
        return float(token)
    except ValueError:
        return None


def _month_deadline(month_token: str, today: Optional[date] = None) -> Optional[date]:
    month_number = MONTH_ALIASES.get((month_token or "").strip().lower())
    if not month_number:
        return None
    current = today or datetime.now().date()
    year = current.year
    if month_number < current.month:
        year += 1
    last_day = calendar.monthrange(year, month_number)[1]
    return date(year, month_number, last_day)


def _empty_goal_target_config() -> dict[str, Any]:
    return {
        "distance_km": None,
        "target_duration_min": None,
        "duration_min": None,
        "target_watts": None,
    }


def _parse_target_config(row: sqlite3.Row) -> dict[str, Any]:
    raw_value = row["target_config_json"] if "target_config_json" in row.keys() else None
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _int_requirement_count(value: float, floor_value: int = 1, cap: int = 4) -> int:
    return max(floor_value, min(cap, int(round(value))))


def build_goal_requirements(
    *,
    goal_family: str,
    metric_type: Optional[str],
    activity_type: Optional[str],
    target_value: float,
    target_config: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    target_config = target_config or {}
    modality = _goal_modality(goal_family, metric_type or "", activity_type)
    session_type = activity_type or ("Run" if metric_type == "run_km" else "Ride" if metric_type == "ride_km" else "WeightTraining" if metric_type == "strength_sessions" else None)
    requirements: list[dict[str, Any]] = []

    def add_requirement(
        requirement_type: str,
        *,
        priority: str,
        minimum_sessions: int,
        summary: str,
        session_types: list[str],
        preferred_intents: Optional[list[str]] = None,
        fallback_intents: Optional[list[str]] = None,
    ) -> None:
        requirements.append({
            "type": requirement_type,
            "label": requirement_type_label(requirement_type),
            "priority": priority,
            "minimum_sessions": minimum_sessions,
            "summary": summary,
            "modality": modality,
            "session_types": session_types,
            "preferred_intents": preferred_intents or [],
            "fallback_intents": fallback_intents or [],
        })

    if goal_family == "event_performance":
        distance_km = _safe_float(target_config.get("distance_km"))
        event_descriptor = f"event-specific {activity_type or 'event'}"
        add_requirement(
            "event_specific_quality",
            priority="primary",
            minimum_sessions=1,
            summary=f"Include 1 {event_descriptor.lower()} session this week.",
            session_types=[session_type] if session_type else [],
            preferred_intents=["tempo", "interval", "race_specific"],
            fallback_intents=["easy", "long"],
        )
        add_requirement(
            "long_aerobic_support",
            priority="secondary",
            minimum_sessions=1,
            summary=f"Keep 1 longer aerobic {activity_type or 'event'} support session in the week{f' for {distance_km:g} km demands' if distance_km else ''}.",
            session_types=[session_type] if session_type else [],
            preferred_intents=["long", "easy"],
            fallback_intents=["tempo"],
        )
        return requirements

    if goal_family == "benchmark":
        add_requirement(
            "benchmark_specific_quality",
            priority="primary",
            minimum_sessions=1,
            summary=f"Include 1 benchmark-focused quality or rehearsal session for {activity_type or 'this goal'} this week.",
            session_types=[session_type] if session_type else [],
            preferred_intents=["tempo", "interval", "race_specific"],
            fallback_intents=["easy"],
        )
        return requirements

    if metric_type == "run_km":
        add_requirement(
            "aerobic_volume",
            priority="primary",
            minimum_sessions=2 if target_value >= 35 else 1,
            summary=f"Keep {2 if target_value >= 35 else 1} run volume-supporting session{'s' if target_value >= 35 else ''} in the week.",
            session_types=["Run"],
            preferred_intents=["easy", "long", "tempo", "interval", "race_specific"],
        )
    elif metric_type == "ride_km":
        add_requirement(
            "aerobic_volume",
            priority="primary",
            minimum_sessions=2 if target_value >= 80 else 1,
            summary=f"Keep {2 if target_value >= 80 else 1} ride volume-supporting session{'s' if target_value >= 80 else ''} in the week.",
            session_types=["Ride", "VirtualRide"],
            preferred_intents=["easy", "long", "tempo", "interval", "race_specific"],
        )
    elif metric_type == "strength_sessions":
        required_sessions = _int_requirement_count(target_value, floor_value=1, cap=4)
        add_requirement(
            "strength_frequency",
            priority="primary",
            minimum_sessions=required_sessions,
            summary=f"Keep {required_sessions} strength session{'s' if required_sessions != 1 else ''} in the week.",
            session_types=["WeightTraining"],
            preferred_intents=["strength_general", "strength_lower", "strength_upper"],
            fallback_intents=["mobility"],
        )
    elif metric_type == "zone2_hours":
        minimum_sessions = 2 if target_value >= 3.5 else 1
        add_requirement(
            "aerobic_endurance",
            priority="primary",
            minimum_sessions=minimum_sessions,
            summary=f"Include {minimum_sessions} aerobic endurance session{'s' if minimum_sessions != 1 else ''} with easy or long intent this week.",
            session_types=["Run", "Ride", "VirtualRide"],
            preferred_intents=["easy", "long"],
            fallback_intents=["tempo"],
        )
    elif metric_type == "activities_count":
        normalized_activity_type = activity_type or session_type
        session_types = [normalized_activity_type] if normalized_activity_type else ["Run", "Ride", "VirtualRide", "WeightTraining", "Walk", "Hike"]
        required_sessions = _int_requirement_count(target_value, floor_value=1, cap=4)
        add_requirement(
            "session_frequency",
            priority="primary",
            minimum_sessions=required_sessions,
            summary=f"Keep {required_sessions} counted session{'s' if required_sessions != 1 else ''} in the week.",
            session_types=session_types,
            preferred_intents=[],
        )

    return requirements


def build_requirement_summary(requirements: list[dict[str, Any]]) -> str:
    if not requirements:
        return "No specific weekly requirement is mapped yet."
    parts = [item["summary"] for item in requirements[:2] if item.get("summary")]
    return " ".join(parts)


def normalize_goal_family(value: Optional[str]) -> str:
    normalized = (value or "accumulation").strip().lower()
    if normalized in {"accumulation", "process", "event_performance", "benchmark"}:
        return normalized
    return "accumulation"


def goal_period_window(period_type: str, today: Optional[date] = None) -> tuple[date, date, str]:
    current = today or datetime.now().date()

    if period_type == "week":
        start_day = current - timedelta(days=current.weekday())
        end_day = start_day + timedelta(days=6)
        return start_day, end_day, "This week"

    if period_type == "month":
        start_day = current.replace(day=1)
        if start_day.month == 12:
            next_month = start_day.replace(year=start_day.year + 1, month=1, day=1)
        else:
            next_month = start_day.replace(month=start_day.month + 1, day=1)
        end_day = next_month - timedelta(days=1)
        return start_day, end_day, "This month"

    start_day = current.replace(month=1, day=1)
    end_day = current.replace(month=12, day=31)
    return start_day, end_day, "This year"


def goal_tracking_window(row: sqlite3.Row, today: Optional[date] = None) -> tuple[date, date, str]:
    current = today or datetime.now().date()
    fallback_start, fallback_end, fallback_label = goal_period_window(row["period_type"], current)
    goal_family = normalize_goal_family(row["goal_family"] if "goal_family" in row.keys() else None)

    # Recurring goals should always float with the active calendar window even if
    # older rows still carry explicit dates from when they were first created.
    if goal_family in {"accumulation", "process", "benchmark"}:
        return fallback_start, fallback_end, fallback_label

    explicit_start = _parse_date(row["start_date"])
    explicit_end = _parse_date(row["end_date"])
    if explicit_start and explicit_end and explicit_start <= explicit_end:
        if row["period_type"] == "week":
            label = "This week"
        elif row["period_type"] == "month":
            label = "This month"
        elif row["period_type"] == "year":
            label = "This year"
        else:
            label = f"{explicit_start.isoformat()} to {explicit_end.isoformat()}"
        return explicit_start, explicit_end, label
    return fallback_start, fallback_end, fallback_label


def goal_value_for_window(
    conn: sqlite3.Connection,
    goal: sqlite3.Row,
    *,
    start_date: str,
    end_date: str,
) -> float:
    metric_type = goal["metric_type"]

    if metric_type == "ride_km":
        row = conn.execute(
            """
            SELECT COALESCE(SUM(distance_km), 0) AS value
            FROM activities
            WHERE type IN ('Ride', 'VirtualRide')
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "run_km":
        row = conn.execute(
            """
            SELECT COALESCE(SUM(distance_km), 0) AS value
            FROM activities
            WHERE type = 'Run'
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "strength_sessions":
        row = conn.execute(
            """
            SELECT COUNT(*) AS value
            FROM activities
            WHERE type = 'WeightTraining'
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "activities_count":
        if goal["activity_type"]:
            row = conn.execute(
                """
                SELECT COUNT(*) AS value
                FROM activities
                WHERE type = ?
                  AND date >= ? AND date <= ?
                """,
                (goal["activity_type"], start_date, end_date),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT COUNT(*) AS value
                FROM activities
                WHERE date >= ? AND date <= ?
                """,
                (start_date, end_date),
            ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "zone2_hours":
        summary = get_zone2_foundation_for_window(
            conn,
            start_date=start_date,
            end_date=end_date,
        )
        if not summary["available"]:
            return 0.0
        return round(float(summary["total_hours"] or 0), 1)

    return 0.0


def goal_planning_guidance(
    *,
    period_type: str,
    metric_type: str,
    unit: str,
    title: str,
    target_value: float,
    current_value: float,
    remaining_value: float,
    total_days: int,
    elapsed_days: int,
    today: date,
    end_day: date,
    forecast: dict,
) -> dict:
    remaining_days_including_today = max((end_day - today).days + 1, 1)
    current_per_week = round((current_value / max(elapsed_days, 1)) * 7, 2) if elapsed_days > 0 else 0.0
    if remaining_value <= 0:
        return {
            "remaining_days_including_today": remaining_days_including_today,
            "required_per_day": 0.0,
            "required_per_week": 0.0,
            "required_next_label": "Needed this week" if period_type == "week" else "Needed next",
            "required_next_value": 0.0,
            "current_per_week": current_per_week,
            "status": "completed",
            "summary": "Target already met.",
        }

    base_daily_target = target_value / max(total_days, 1) if target_value > 0 else 0.0
    required_per_day = remaining_value / remaining_days_including_today
    required_per_week = required_per_day * 7
    required_next_label = "Needed this week" if period_type == "week" else "Needed next"
    required_next_value = remaining_value if period_type == "week" else required_per_week
    pressure_ratio = (required_per_day / base_daily_target) if base_daily_target > 0 else 0.0

    if pressure_ratio <= 1.05:
        status = "comfortable"
    elif pressure_ratio <= 1.35:
        status = "steady"
    elif pressure_ratio <= 1.75:
        status = "pressured"
    else:
        status = "urgent"

    rounded_required = rounded_goal_value(metric_type, required_per_day)
    summary = f"Need {rounded_required} {unit}/day from here.".replace(" /", "/")
    if unit in {"sessions", "activities"}:
        summary = f"Need about {rounded_required} {unit}/day from here."
    if period_type == "week":
        summary = f"Need about {rounded_goal_value(metric_type, remaining_value)} {unit} this week."
    if forecast.get("projected_status") in {"behind", "at_risk"}:
        projected_gap = rounded_goal_value(metric_type, abs(float(forecast.get("projected_gap_value") or 0)))
        if period_type == "week":
            summary = f"{title} is slipping. Need about {rounded_goal_value(metric_type, remaining_value)} {unit} this week to recover pace."
        else:
            summary = f"{title} is slipping. Need about {rounded_goal_value(metric_type, required_per_week)} {unit}/week to recover pace."
        if projected_gap > 0:
            summary = f"{summary} Current trend finishes {projected_gap} {unit} short."
    elif forecast.get("projected_status") == "ahead":
        summary = f"Current trend keeps {title} ahead of pace."

    return {
        "remaining_days_including_today": remaining_days_including_today,
        "required_per_day": round(required_per_day, 2),
        "required_per_week": round(required_per_week, 2),
        "required_next_label": required_next_label,
        "required_next_value": round(required_next_value, 2),
        "current_per_week": current_per_week,
        "status": status,
        "summary": summary,
    }


def build_goal_forecast(
    conn: sqlite3.Connection,
    goal: sqlite3.Row,
    *,
    current_value: float,
    target_value: float,
    start_day: date,
    end_day: date,
    today: date,
    elapsed_days: int,
    total_days: int,
) -> dict:
    recent_window_days = min(7, max(elapsed_days, 1))
    recent_start = max(start_day, today - timedelta(days=recent_window_days - 1))
    recent_value = goal_value_for_window(
        conn,
        goal,
        start_date=recent_start.isoformat(),
        end_date=today.isoformat(),
    )
    recent_rate_per_day = recent_value / max((today - recent_start).days + 1, 1)
    current_rate_per_day = current_value / max(elapsed_days, 1)
    remaining_days_including_today = max((end_day - today).days + 1, 1)
    projected_finish_value = current_value + (recent_rate_per_day * remaining_days_including_today)
    projected_gap_value = projected_finish_value - target_value
    projected_finish_pct = round((projected_finish_value / target_value) * 100, 1) if target_value > 0 else 0.0

    if current_value >= target_value:
        projected_status = "completed"
    elif projected_gap_value >= target_value * 0.05:
        projected_status = "ahead"
    elif projected_gap_value >= 0:
        projected_status = "on_track"
    elif projected_gap_value >= -(target_value * 0.1):
        projected_status = "behind"
    else:
        projected_status = "at_risk"

    return {
        "recent_window_days": recent_window_days,
        "recent_value": round(recent_value, 1),
        "current_rate_per_day": round(current_rate_per_day, 2),
        "recent_rate_per_day": round(recent_rate_per_day, 2),
        "current_rate_per_week": round(current_rate_per_day * 7, 2),
        "recent_rate_per_week": round(recent_rate_per_day * 7, 2),
        "projected_finish_value": round(projected_finish_value, 1),
        "projected_finish_pct": projected_finish_pct,
        "projected_gap_value": round(projected_gap_value, 1),
        "projected_status": projected_status,
        "remaining_days_including_today": remaining_days_including_today,
        "elapsed_days": elapsed_days,
        "total_days": total_days,
    }


def build_goal_risk_summary(
    *,
    title: str,
    metric_type: str,
    unit: str,
    pace_delta_pct: float,
    remaining_value: float,
    forecast: dict,
    planning_guidance_status: str,
) -> dict:
    if forecast["projected_status"] == "completed" or remaining_value <= 0:
        return {"status": "completed", "label": "Done", "summary": "Target already met."}

    if forecast["projected_status"] == "at_risk" or planning_guidance_status == "urgent":
        status = "at_risk"
        label = "At risk"
    elif forecast["projected_status"] == "behind" or planning_guidance_status == "pressured":
        status = "under_pressure"
        label = "Under pressure"
    elif pace_delta_pct < -5 or planning_guidance_status == "steady":
        status = "watch"
        label = "Watch"
    else:
        status = "on_track"
        label = "On track"

    projected_gap = rounded_goal_value(metric_type, abs(float(forecast.get("projected_gap_value") or 0)))
    if status == "at_risk":
        summary = f"{title} is trending {projected_gap} {unit} short at the recent pace."
    elif status == "under_pressure":
        summary = f"{title} needs a stronger than usual week to stay realistic."
    elif status == "watch":
        summary = f"{title} is close enough, but recent execution should tighten up."
    else:
        summary = f"{title} is tracking well enough to stay realistic."
    return {
        "status": status,
        "label": label,
        "summary": summary,
    }


def aggregate_goal_risk_summary(goals: list[dict]) -> dict:
    counts = {
        "constrained": 0,
        "at_risk": 0,
        "under_pressure": 0,
        "watch": 0,
        "on_track": 0,
        "completed": 0,
    }
    for goal in goals:
        status = goal.get("risk_summary", {}).get("status", "on_track")
        if status not in counts:
            status = "on_track"
        counts[status] += 1

    if counts["constrained"]:
        status = "constrained"
        label = "Goals constrained"
    elif counts["at_risk"]:
        status = "at_risk"
        label = "Goals at risk"
    elif counts["under_pressure"]:
        status = "under_pressure"
        label = "Goals under pressure"
    elif counts["watch"]:
        status = "watch"
        label = "Watch goal pace"
    elif counts["on_track"]:
        status = "on_track"
        label = "Goals on track"
    else:
        status = "completed" if goals else "no_active_goals"
        label = "Goals complete" if goals else "No active goals"

    most_pressured = sorted(
        goals,
        key=lambda goal: (
            {"constrained": 0, "at_risk": 1, "under_pressure": 2, "watch": 3, "on_track": 4, "completed": 5}.get(
                goal.get("risk_summary", {}).get("status", "on_track"),
                6,
            ),
            goal.get("days_remaining", 9999),
        ),
    )[:3]

    return {
        "status": status,
        "label": label,
        "counts": counts,
        "most_pressured": most_pressured,
    }


def _recent_best_run_effort(conn: sqlite3.Connection, activity_type: str, target_distance_km: float) -> Optional[dict]:
    min_distance = max(target_distance_km * 0.9, target_distance_km - 1.0)
    max_distance = target_distance_km * 1.1
    row = conn.execute(
        """
        SELECT id, date, name, distance_km, duration_min
        FROM activities
        WHERE type = ?
          AND distance_km >= ? AND distance_km <= ?
          AND duration_min IS NOT NULL
        ORDER BY duration_min ASC, date DESC
        LIMIT 1
        """,
        (activity_type, min_distance, max_distance),
    ).fetchone()
    return dict(row) if row else None


def _recent_best_ride_power(conn: sqlite3.Connection, minimum_duration_min: float) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT id, date, name, duration_min, avg_watts
        FROM activities
        WHERE type IN ('Ride', 'VirtualRide')
          AND duration_min >= ?
          AND avg_watts IS NOT NULL
        ORDER BY avg_watts DESC, date DESC
        LIMIT 1
        """,
        (minimum_duration_min,),
    ).fetchone()
    return dict(row) if row else None


def _goal_modality(goal_family: str, metric_type: str, activity_type: Optional[str]) -> Optional[str]:
    if goal_family in {"event_performance", "benchmark"}:
        if activity_type in {"Run", "Ride", "VirtualRide"}:
            return "run" if activity_type == "Run" else "ride"
        if activity_type == "WeightTraining":
            return "strength"
    return modality_for_goal(metric_type, activity_type)


def _constraint_details(modality: Optional[str], restrictions: dict) -> tuple[bool, Optional[dict], Optional[dict]]:
    modality_restriction = (
        restrictions.get("modalities", {}).get(modality)
        if modality else None
    )
    is_constrained = bool(modality_restriction and modality_restriction.get("status") in {"limited", "blocked"})
    constraint_summary = None
    if is_constrained:
        constraint_summary = {
            "modality": modality,
            "status": modality_restriction["status"],
            "label": modality_restriction["label"],
            "reason": modality_restriction.get("reason"),
            "note": modality_restriction.get("note"),
            "expected_end_date": modality_restriction.get("expected_end_date"),
            "summary": restriction_summary_text(modality_restriction),
        }
    return is_constrained, modality_restriction, constraint_summary


def _serialize_volume_goal(
    row: sqlite3.Row,
    conn: sqlite3.Connection,
    restrictions: dict,
    goal_family: str,
    target_config: dict[str, Any],
) -> dict:
    today = datetime.now().date()
    start_day, end_day, period_label = goal_tracking_window(row, today)
    current_value = round(
        goal_value_for_window(
            conn,
            row,
            start_date=start_day.isoformat(),
            end_date=end_day.isoformat(),
        ),
        1,
    )
    target_value = float(row["target_value"] or 0)
    total_days = max((end_day - start_day).days + 1, 1)
    elapsed_days = min(max((today - start_day).days + 1, 0), total_days)
    days_remaining = max((end_day - today).days, 0)
    progress_pct = round(min((current_value / target_value) * 100, 999), 1) if target_value > 0 else 0
    expected_pct = round((elapsed_days / total_days) * 100, 1)
    remaining_value = round(max(target_value - current_value, 0), 1)
    expected_value = round((target_value * elapsed_days) / total_days, 1) if target_value > 0 else 0.0
    pace_delta_value = round(current_value - expected_value, 1)
    pace_delta_pct = round(progress_pct - expected_pct, 1)
    derived_foundation = None
    if row["metric_type"] == "zone2_hours":
        derived_foundation = get_zone2_foundation_for_window(
            conn,
            start_date=start_day.isoformat(),
            end_date=end_day.isoformat(),
        )
        current_value = round(float(derived_foundation["total_hours"] or 0), 1) if derived_foundation["available"] else 0.0
        remaining_value = round(max(target_value - current_value, 0), 1)
        progress_pct = round(min((current_value / target_value) * 100, 999), 1) if target_value > 0 else 0
        pace_delta_value = round(current_value - expected_value, 1)
        pace_delta_pct = round(progress_pct - expected_pct, 1)
        derived_foundation = {
            **derived_foundation,
            "summary": (
                f"Zone 2 foundation ready. {derived_foundation['session_count']} qualifying session"
                f"{'' if derived_foundation['session_count'] == 1 else 's'} in this window."
                if derived_foundation["available"] else
                "Zone 2 hours stay unavailable until a running threshold pace or cycling threshold power anchor is set."
            ),
            "status": "available" if derived_foundation["available"] else "unavailable",
        }
    unit = goal_metric_unit(row["metric_type"])
    metric_label = goal_metric_label(row["metric_type"])
    modality = _goal_modality(goal_family, row["metric_type"], row["activity_type"])
    is_constrained, modality_restriction, constraint_summary = _constraint_details(modality, restrictions)

    if derived_foundation and derived_foundation["status"] == "unavailable":
        status = "behind_pace"
    elif is_constrained:
        status = "constrained"
    elif current_value >= target_value:
        status = "completed"
    elif pace_delta_pct >= 5:
        status = "ahead_of_pace"
    elif pace_delta_pct >= -5:
        status = "on_pace"
    else:
        status = "behind_pace"

    forecast = build_goal_forecast(
        conn,
        row,
        current_value=current_value,
        target_value=target_value,
        start_day=start_day,
        end_day=end_day,
        today=today,
        elapsed_days=elapsed_days,
        total_days=total_days,
    )
    planning_guidance = goal_planning_guidance(
        period_type=row["period_type"],
        metric_type=row["metric_type"],
        unit=unit,
        title=row["title"],
        target_value=target_value,
        current_value=current_value,
        remaining_value=remaining_value,
        total_days=total_days,
        elapsed_days=elapsed_days,
        today=today,
        end_day=end_day,
        forecast=forecast,
    )
    risk_summary = build_goal_risk_summary(
        title=row["title"],
        metric_type=row["metric_type"],
        unit=unit,
        pace_delta_pct=pace_delta_pct,
        remaining_value=remaining_value,
        forecast=forecast,
        planning_guidance_status=planning_guidance["status"],
    )

    if derived_foundation and derived_foundation["status"] == "unavailable":
        planning_guidance = {
            **planning_guidance,
            "status": "constrained",
            "summary": derived_foundation["summary"],
        }
        risk_summary = {
            "status": "watch",
            "label": "Missing anchor",
            "summary": derived_foundation["summary"],
        }
    elif is_constrained:
        planning_guidance = {
            **planning_guidance,
            "status": "constrained",
            "summary": restriction_summary_text(modality_restriction),
        }
        risk_summary = {
            "status": "constrained",
            "label": "Constrained",
            "summary": restriction_summary_text(modality_restriction),
        }

    if goal_family == "process" and row["metric_type"] == "zone2_hours":
        target_summary = f"Build {rounded_goal_value(row['metric_type'], target_value)} hours of zone 2 work by {end_day.isoformat()}."
    elif goal_family == "process":
        target_summary = f"Hold {rounded_goal_value(row['metric_type'], target_value)} {unit} of {metric_label} through {period_label.lower()}."
    else:
        target_summary = f"Reach {rounded_goal_value(row['metric_type'], target_value)} {unit} of {metric_label} by {end_day.isoformat()}."

    weekly_requirements = build_goal_requirements(
        goal_family=goal_family,
        metric_type=row["metric_type"],
        activity_type=row["activity_type"],
        target_value=target_value,
        target_config=target_config,
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
        "goal_family": goal_family,
        "family_label": goal_family_label(goal_family),
        "metric_type": row["metric_type"],
        "target_value": target_value,
        "current_value": current_value,
        "unit": unit,
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "activity_type": row["activity_type"],
        "is_active": bool(row["is_active"]),
        "progress_pct": progress_pct,
        "remaining_value": remaining_value,
        "days_remaining": days_remaining,
        "expected_pct": expected_pct,
        "expected_value": expected_value,
        "pace_delta_value": pace_delta_value,
        "pace_delta_pct": pace_delta_pct,
        "status": status,
        "metric_label": metric_label,
        "modality": modality,
        "modality_restriction": modality_restriction,
        "is_constrained": is_constrained,
        "constraint_summary": constraint_summary,
        "forecast": forecast,
        "risk_summary": risk_summary,
        "planning_guidance": planning_guidance,
        "target_config": target_config,
        "target_summary": target_summary,
        "weekly_requirements": weekly_requirements,
        "weekly_requirement_summary": build_requirement_summary(weekly_requirements),
        "compact_summary": planning_guidance["summary"],
        "display_mode": "volume",
        "derived_foundation": derived_foundation,
    }


def _serialize_event_goal(
    row: sqlite3.Row,
    conn: sqlite3.Connection,
    restrictions: dict,
    target_config: dict[str, Any],
) -> dict:
    today = datetime.now().date()
    start_day, end_day, period_label = goal_tracking_window(row, today)
    days_remaining = max((end_day - today).days, 0)
    target_duration_min = float(row["target_value"] or 0)
    distance_km = _safe_float(target_config.get("distance_km"))
    activity_type = row["activity_type"] or "Run"
    best_match = _recent_best_run_effort(conn, activity_type, distance_km) if activity_type == "Run" else _recent_best_run_effort(conn, activity_type, distance_km)
    best_duration = _safe_float((best_match or {}).get("duration_min"))
    progress_pct = round(min((target_duration_min / best_duration) * 100, 100), 1) if best_duration > 0 and target_duration_min > 0 else 0.0
    remaining_value = round(max(best_duration - target_duration_min, 0), 1) if best_duration > 0 else target_duration_min
    modality = _goal_modality("event_performance", row["metric_type"], activity_type)
    is_constrained, modality_restriction, constraint_summary = _constraint_details(modality, restrictions)

    if best_duration and best_duration <= target_duration_min:
        status = "completed"
        risk_summary = {"status": "completed", "label": "Done", "summary": "Recent performance already meets the event target."}
        planning_guidance = {"status": "completed", "summary": "Event target already looks realistic at the current best."}
    else:
        gap_ratio = ((best_duration - target_duration_min) / target_duration_min) if best_duration and target_duration_min else 1.0
        if is_constrained:
            status = "constrained"
            risk_summary = {"status": "constrained", "label": "Constrained", "summary": restriction_summary_text(modality_restriction)}
            planning_guidance = {"status": "constrained", "summary": restriction_summary_text(modality_restriction)}
        elif not best_duration and days_remaining <= 21:
            status = "behind_pace"
            risk_summary = {"status": "at_risk", "label": "At risk", "summary": "No recent race-like effort is logged and the event date is close."}
            planning_guidance = {"status": "urgent", "summary": "Use the remaining weeks to include at least one event-specific session or rehearsal."}
        elif gap_ratio <= 0.03:
            status = "on_pace"
            risk_summary = {"status": "on_track", "label": "On track", "summary": "Recent performance is close enough to the event target to stay realistic."}
            planning_guidance = {"status": "steady", "summary": "Keep sessions specific to event pace and avoid unnecessary extra volume."}
        elif gap_ratio <= 0.08:
            status = "behind_pace"
            risk_summary = {"status": "watch", "label": "Watch", "summary": "Recent performance is close, but the event target still needs sharpening."}
            planning_guidance = {"status": "pressured", "summary": "Prioritize one or two target-specific sessions rather than generic volume."}
        else:
            status = "behind_pace"
            risk_summary = {"status": "at_risk", "label": "At risk", "summary": "Recent performance is still materially short of the event target."}
            planning_guidance = {"status": "urgent", "summary": "The event goal needs specific work, not just more background mileage."}

    performance_snapshot = {
        "target_duration_min": target_duration_min,
        "target_distance_km": distance_km,
        "recent_best_duration_min": round(best_duration, 1) if best_duration else None,
        "recent_best_date": (best_match or {}).get("date"),
        "recent_best_name": (best_match or {}).get("name"),
    }
    target_summary = f"{activity_type} {distance_km:g} km in under {target_duration_min:g} min by {end_day.isoformat()}."
    compact_summary = risk_summary["summary"]
    derived_foundation = {
        "type": "run_benchmark",
        "status": "available" if performance_snapshot["recent_best_duration_min"] else "unavailable",
        "summary": (
            f"Recent best {distance_km:g}k is {performance_snapshot['recent_best_duration_min']:.1f} min from {performance_snapshot['recent_best_date']}."
            if performance_snapshot["recent_best_duration_min"] else
            f"No recent {distance_km:g}k benchmark is available yet."
        ),
    }
    weekly_requirements = build_goal_requirements(
        goal_family="event_performance",
        metric_type=row["metric_type"],
        activity_type=activity_type,
        target_value=target_duration_min,
        target_config=target_config,
    )

    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
        "goal_family": "event_performance",
        "family_label": goal_family_label("event_performance"),
        "metric_type": row["metric_type"],
        "target_value": target_duration_min,
        "current_value": round(best_duration, 1) if best_duration else 0.0,
        "unit": "min",
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "activity_type": activity_type,
        "is_active": bool(row["is_active"]),
        "progress_pct": progress_pct,
        "remaining_value": remaining_value,
        "days_remaining": days_remaining,
        "expected_pct": 0.0,
        "expected_value": 0.0,
        "pace_delta_value": round(target_duration_min - best_duration, 1) if best_duration else 0.0,
        "pace_delta_pct": 0.0,
        "status": status,
        "metric_label": "event performance",
        "modality": modality,
        "modality_restriction": modality_restriction,
        "is_constrained": is_constrained,
        "constraint_summary": constraint_summary,
        "forecast": None,
        "risk_summary": risk_summary,
        "planning_guidance": planning_guidance,
        "target_config": target_config,
        "target_summary": target_summary,
        "weekly_requirements": weekly_requirements,
        "weekly_requirement_summary": build_requirement_summary(weekly_requirements),
        "compact_summary": compact_summary,
        "display_mode": "performance",
        "performance_snapshot": performance_snapshot,
        "derived_foundation": derived_foundation,
    }


def _serialize_benchmark_goal(
    row: sqlite3.Row,
    conn: sqlite3.Connection,
    restrictions: dict,
    target_config: dict[str, Any],
) -> dict:
    today = datetime.now().date()
    start_day, end_day, period_label = goal_tracking_window(row, today)
    days_remaining = max((end_day - today).days, 0)
    activity_type = row["activity_type"] or "Ride"
    modality = _goal_modality("benchmark", row["metric_type"], activity_type)
    is_constrained, modality_restriction, constraint_summary = _constraint_details(modality, restrictions)

    performance_snapshot: dict[str, Any]
    target_summary: str
    if activity_type == "Run":
        distance_km = _safe_float(target_config.get("distance_km"))
        best_match = _recent_best_run_effort(conn, "Run", distance_km)
        best_duration = _safe_float((best_match or {}).get("duration_min"))
        target_duration_min = float(row["target_value"] or 0)
        progress_pct = round(min((target_duration_min / best_duration) * 100, 100), 1) if best_duration > 0 and target_duration_min > 0 else 0.0
        remaining_value = round(max(best_duration - target_duration_min, 0), 1) if best_duration > 0 else target_duration_min
        performance_snapshot = {
            "target_distance_km": distance_km,
            "target_duration_min": target_duration_min,
            "recent_best_duration_min": round(best_duration, 1) if best_duration else None,
            "recent_best_date": (best_match or {}).get("date"),
            "recent_best_name": (best_match or {}).get("name"),
        }
        target_summary = f"Run {distance_km:g} km in under {target_duration_min:g} min during this block."
        achieved = bool(best_duration and best_duration <= target_duration_min)
        gap_ratio = ((best_duration - target_duration_min) / target_duration_min) if best_duration and target_duration_min else 1.0
        derived_foundation = {
            "type": "run_benchmark",
            "status": "available" if best_duration else "unavailable",
            "summary": (
                f"Recent best {distance_km:g}k is {best_duration:.1f} min."
                if best_duration else
                f"No recent {distance_km:g}k benchmark is available yet."
            ),
        }
    else:
        duration_min = _safe_float(target_config.get("duration_min"))
        best_match = _recent_best_ride_power(conn, duration_min)
        best_power = _safe_float((best_match or {}).get("avg_watts"))
        target_watts = float(row["target_value"] or 0)
        progress_pct = round(min((best_power / target_watts) * 100, 100), 1) if best_power > 0 and target_watts > 0 else 0.0
        remaining_value = round(max(target_watts - best_power, 0), 1) if best_power > 0 else target_watts
        performance_snapshot = {
            "target_duration_min": duration_min,
            "target_watts": target_watts,
            "recent_best_watts": round(best_power, 0) if best_power else None,
            "recent_best_date": (best_match or {}).get("date"),
            "recent_best_name": (best_match or {}).get("name"),
        }
        target_summary = f"Hold {target_watts:g} W for {duration_min:g} min during this block."
        achieved = bool(best_power and best_power >= target_watts)
        gap_ratio = ((target_watts - best_power) / target_watts) if best_power and target_watts else 1.0
        derived_foundation = {
            "type": "ride_power_benchmark",
            "status": "available" if best_power else "unavailable",
            "summary": (
                f"Best recent {duration_min:g}-minute power is {round(best_power):g} W."
                if best_power else
                f"No recent {duration_min:g}-minute power benchmark is available yet."
            ),
        }

    if achieved:
        status = "completed"
        risk_summary = {"status": "completed", "label": "Done", "summary": "Recent benchmark work already meets the target."}
        planning_guidance = {"status": "completed", "summary": "Maintain the level rather than chasing extra confirmation too early."}
    elif is_constrained:
        status = "constrained"
        risk_summary = {"status": "constrained", "label": "Constrained", "summary": restriction_summary_text(modality_restriction)}
        planning_guidance = {"status": "constrained", "summary": restriction_summary_text(modality_restriction)}
    elif gap_ratio <= 0.05:
        status = "on_pace"
        risk_summary = {"status": "on_track", "label": "On track", "summary": "The benchmark is close enough that targeted sharpening should be enough."}
        planning_guidance = {"status": "steady", "summary": "Keep one benchmark-supporting quality session in the week."}
    elif gap_ratio <= 0.12:
        status = "behind_pace"
        risk_summary = {"status": "watch", "label": "Watch", "summary": "The benchmark still needs visible progress, not just maintenance."}
        planning_guidance = {"status": "pressured", "summary": "Bias quality work toward the benchmark demand instead of generic volume."}
    else:
        status = "behind_pace"
        risk_summary = {"status": "at_risk", "label": "At risk", "summary": "The benchmark is still materially away from the recent best."}
        planning_guidance = {"status": "urgent", "summary": "The current block should deliberately include benchmark-specific work."}

    compact_summary = risk_summary["summary"]
    weekly_requirements = build_goal_requirements(
        goal_family="benchmark",
        metric_type=row["metric_type"],
        activity_type=activity_type,
        target_value=float(row["target_value"] or 0),
        target_config=target_config,
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
        "goal_family": "benchmark",
        "family_label": goal_family_label("benchmark"),
        "metric_type": row["metric_type"],
        "target_value": float(row["target_value"] or 0),
        "current_value": round(_safe_float(performance_snapshot.get("recent_best_duration_min") or performance_snapshot.get("recent_best_watts")), 1),
        "unit": goal_metric_unit(row["metric_type"]),
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "activity_type": activity_type,
        "is_active": bool(row["is_active"]),
        "progress_pct": progress_pct,
        "remaining_value": remaining_value,
        "days_remaining": days_remaining,
        "expected_pct": 0.0,
        "expected_value": 0.0,
        "pace_delta_value": 0.0,
        "pace_delta_pct": 0.0,
        "status": status,
        "metric_label": goal_metric_label(row["metric_type"]),
        "modality": modality,
        "modality_restriction": modality_restriction,
        "is_constrained": is_constrained,
        "constraint_summary": constraint_summary,
        "forecast": None,
        "risk_summary": risk_summary,
        "planning_guidance": planning_guidance,
        "target_config": target_config,
        "target_summary": target_summary,
        "weekly_requirements": weekly_requirements,
        "weekly_requirement_summary": build_requirement_summary(weekly_requirements),
        "compact_summary": compact_summary,
        "display_mode": "performance",
        "performance_snapshot": performance_snapshot,
        "derived_foundation": derived_foundation,
    }


def serialize_goal(row: sqlite3.Row, conn: sqlite3.Connection, restrictions: Optional[dict] = None) -> dict:
    goal_family = normalize_goal_family(row["goal_family"] if "goal_family" in row.keys() else None)
    target_config = _parse_target_config(row)
    normalized_restrictions = restrictions or get_modality_restrictions_for_conn(conn)

    if goal_family == "event_performance":
        return _serialize_event_goal(row, conn, normalized_restrictions, target_config)
    if goal_family == "benchmark":
        return _serialize_benchmark_goal(row, conn, normalized_restrictions, target_config)
    return _serialize_volume_goal(row, conn, normalized_restrictions, goal_family, target_config)


def _base_goal_draft(text: str) -> dict[str, Any]:
    return {
        "source_text": text,
        "goal": {
            "title": "",
            "goal_family": "accumulation",
            "period_type": "week",
            "metric_type": None,
            "target_value": None,
            "start_date": None,
            "end_date": None,
            "activity_type": None,
            "target_config": _empty_goal_target_config(),
        },
        "title_suggestion": "",
        "warnings": [],
        "missing_fields": [],
        "confidence": "low",
        "is_supported": False,
        "is_ready": False,
    }


def _build_event_goal_draft(
    *,
    source_text: str,
    activity_type: str,
    distance_km: float,
    target_duration_min: float,
    end_date: str,
    title: str,
    warning: Optional[str] = None,
) -> dict[str, Any]:
    draft = _base_goal_draft(source_text)
    draft["goal"] = {
        "title": title,
        "goal_family": "event_performance",
        "period_type": "year",
        "metric_type": None,
        "target_value": None,
        "start_date": None,
        "end_date": end_date,
        "activity_type": activity_type,
        "target_config": {
            "distance_km": distance_km,
            "target_duration_min": target_duration_min,
            "duration_min": None,
            "target_watts": None,
            "event_date": end_date,
        },
    }
    draft["title_suggestion"] = title
    draft["confidence"] = "high"
    draft["is_supported"] = True
    if warning:
        draft["warnings"].append(warning)
    return draft


def _parse_goal_text(text: str, today: Optional[date] = None) -> dict[str, Any]:
    normalized = _compact_text(text)
    draft = _base_goal_draft(text)
    current = today or datetime.now().date()
    if not normalized:
        draft["warnings"].append("Enter a goal idea to draft from natural language.")
        draft["missing_fields"].append("text")
        return draft

    event_match = re.search(
        r"\b(run|ride|virtual ride)\s+(\d+(?:\.\d+)?)\s*k(?:m)?\s+in\s+(?:under\s+)?(\d+(?:\.\d+)?)\s*(?:minutes|min)\s+by\s+([a-z]+)\b",
        normalized,
    )
    if event_match:
        activity_raw, distance_raw, duration_raw, month_raw = event_match.groups()
        deadline = _month_deadline(month_raw, current)
        activity_type = "VirtualRide" if activity_raw == "virtual ride" else activity_raw.capitalize()
        distance_km = float(distance_raw)
        target_duration_min = float(duration_raw)
        if deadline:
            activity_label = "Virtual ride" if activity_type == "VirtualRide" else activity_type
            title = f"{activity_label} {distance_km:g} km under {target_duration_min:g} min"
            warning = None
            if len(month_raw) > 0:
                warning = f"Interpreted 'by {month_raw.title()}' as {deadline.isoformat()}."
            return _build_event_goal_draft(
                source_text=text,
                activity_type=activity_type,
                distance_km=distance_km,
                target_duration_min=target_duration_min,
                end_date=deadline.isoformat(),
                title=title,
                warning=warning,
            )

    ride_benchmark_match = re.search(
        r"\bhold\s+(\d+(?:\.\d+)?)\s*w(?:atts?)?\s+for\s+(\d+(?:\.\d+)?)\s*(?:minutes|min)\b",
        normalized,
    )
    if ride_benchmark_match:
        watts_raw, duration_raw = ride_benchmark_match.groups()
        watts = float(watts_raw)
        duration_min = float(duration_raw)
        draft["goal"] = {
            "title": f"Hold {watts:g} W for {duration_min:g} min",
            "goal_family": "benchmark",
            "period_type": "year",
            "metric_type": None,
            "target_value": None,
            "start_date": None,
            "end_date": None,
            "activity_type": "Ride",
            "target_config": {
                "distance_km": None,
                "target_duration_min": None,
                "duration_min": duration_min,
                "target_watts": watts,
            },
        }
        draft["title_suggestion"] = draft["goal"]["title"]
        draft["confidence"] = "high"
        draft["is_supported"] = True
        return draft

    zone2_match = re.search(
        r"\b(ride|run)\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?)\s+of\s+zone\s*2\s+(?:per|a)\s+(week|month|year)\b",
        normalized,
    )
    if zone2_match:
        activity_raw, hours_raw, _, period_raw = zone2_match.groups()
        activity_type = activity_raw.capitalize()
        period_type = {"week": "week", "month": "month", "year": "year"}[period_raw]
        hours = float(hours_raw)
        draft["goal"] = {
            "title": f"{activity_type} {hours:g} hours of zone 2 per {period_type}",
            "goal_family": "process",
            "period_type": period_type,
            "metric_type": "zone2_hours",
            "target_value": hours,
            "start_date": None,
            "end_date": None,
            "activity_type": activity_type,
            "target_config": _empty_goal_target_config(),
        }
        draft["title_suggestion"] = draft["goal"]["title"]
        draft["confidence"] = "high"
        draft["is_supported"] = True
        return draft

    lift_match = re.search(
        r"\b(lift|strength train|do strength)\s+([a-z0-9.]+)\s+(?:times?\s+)?(?:per|a)\s+(week|month)\b",
        normalized,
    )
    if lift_match:
        _, count_raw, period_raw = lift_match.groups()
        count = _number_from_token(count_raw)
        if count is not None:
            period_type = {"week": "week", "month": "month"}[period_raw]
            draft["goal"] = {
                "title": f"Lift {count:g} times per {period_type}",
                "goal_family": "process",
                "period_type": period_type,
                "metric_type": "strength_sessions",
                "target_value": count,
                "start_date": None,
                "end_date": None,
                "activity_type": "WeightTraining",
                "target_config": _empty_goal_target_config(),
            }
            draft["title_suggestion"] = draft["goal"]["title"]
            draft["confidence"] = "high"
            draft["is_supported"] = True
            return draft

    accumulation_match = re.search(
        r"\b(run|ride)\s+(\d+(?:\.\d+)?)\s*k(?:m)?\s+(?:this\s+|per\s+)?(week|month|year)\b",
        normalized,
    )
    if accumulation_match:
        activity_raw, distance_raw, period_raw = accumulation_match.groups()
        activity_type = activity_raw.capitalize()
        metric_type = "run_km" if activity_type == "Run" else "ride_km"
        period_type = {"week": "week", "month": "month", "year": "year"}[period_raw]
        distance_km = float(distance_raw)
        draft["goal"] = {
            "title": f"{activity_type} {distance_km:g} km this {period_type}",
            "goal_family": "accumulation",
            "period_type": period_type,
            "metric_type": metric_type,
            "target_value": distance_km,
            "start_date": None,
            "end_date": None,
            "activity_type": activity_type,
            "target_config": _empty_goal_target_config(),
        }
        draft["title_suggestion"] = draft["goal"]["title"]
        draft["confidence"] = "high"
        draft["is_supported"] = True
        return draft

    if "zone 2" in normalized:
        draft["goal"].update({
            "goal_family": "process",
            "metric_type": "zone2_hours",
            "activity_type": "Ride" if "ride" in normalized else "Run" if "run" in normalized else None,
        })
        draft["title_suggestion"] = "Zone 2 goal"
        draft["warnings"].append("I found a zone 2 goal, but I still need a target amount and time period.")
        draft["missing_fields"].extend(["target_value", "period_type"])
        draft["is_supported"] = True
        draft["confidence"] = "medium"
        return draft

    if any(token in normalized for token in ["lift", "strength"]):
        draft["goal"].update({
            "goal_family": "process",
            "metric_type": "strength_sessions",
            "activity_type": "WeightTraining",
        })
        draft["title_suggestion"] = "Strength frequency goal"
        draft["warnings"].append("I found a strength-frequency goal, but I still need how often and over what period.")
        draft["missing_fields"].extend(["target_value", "period_type"])
        draft["is_supported"] = True
        draft["confidence"] = "medium"
        return draft

    if "run" in normalized or "ride" in normalized:
        draft["goal"]["activity_type"] = "Run" if "run" in normalized else "Ride"
        draft["warnings"].append("I found an endurance goal, but the current parser only supports a few high-confidence patterns.")
        draft["warnings"].append("Try a phrase like 'run 10k in under 40 minutes by October' or 'ride 6 hours of zone 2 per week'.")
        draft["missing_fields"].extend(["goal_family", "target_value"])
        return draft

    draft["warnings"].append("That goal wording is not supported yet. Try a simpler measurable phrase.")
    return draft


def draft_goal_data(text: str, today: Optional[date] = None) -> dict[str, Any]:
    draft = _parse_goal_text(text, today=today)
    goal = draft["goal"]
    if not goal.get("title"):
        goal["title"] = draft["title_suggestion"] or ""

    if draft["missing_fields"]:
        draft["missing_fields"] = list(dict.fromkeys(draft["missing_fields"]))
    if draft["warnings"]:
        draft["warnings"] = list(dict.fromkeys(draft["warnings"]))

    try:
        normalized = _validate_goal_payload(
            title=goal["title"],
            period_type=goal["period_type"],
            goal_family=goal.get("goal_family"),
            metric_type=goal.get("metric_type"),
            target_value=goal.get("target_value"),
            start_date=goal.get("start_date"),
            end_date=goal.get("end_date"),
            activity_type=goal.get("activity_type"),
            target_config=goal.get("target_config"),
        )
        draft["goal"] = {
            "title": goal["title"],
            "period_type": goal["period_type"],
            **normalized,
        }
        draft["title_suggestion"] = goal["title"]
        draft["is_ready"] = True
        if not draft["warnings"]:
            draft["confidence"] = "high"
    except ValueError as exc:
        message = str(exc)
        if message not in draft["warnings"]:
            draft["warnings"].append(message)
        draft["is_ready"] = False

    return draft


def _validate_goal_payload(
    *,
    title: str,
    period_type: str,
    goal_family: Optional[str],
    metric_type: Optional[str],
    target_value: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    activity_type: Optional[str],
    target_config: Optional[dict[str, Any]],
) -> dict[str, Any]:
    family = normalize_goal_family(goal_family)
    config = target_config or {}
    today = datetime.now().date()
    default_start, default_end, _ = goal_period_window(period_type, today)

    if family in {"accumulation", "process"}:
        if not metric_type:
            raise ValueError("metric_type is required for accumulation and process goals.")
        if target_value is None or float(target_value) <= 0:
            raise ValueError("target_value must be greater than zero.")
        normalized_start = start_date or default_start.isoformat()
        normalized_end = end_date or default_end.isoformat()
        return {
            "goal_family": family,
            "metric_type": metric_type,
            "target_value": float(target_value),
            "start_date": normalized_start,
            "end_date": normalized_end,
            "activity_type": activity_type,
            "target_config": config,
        }

    if family == "event_performance":
        if activity_type not in {"Run", "Ride", "VirtualRide"}:
            raise ValueError("event-performance goals currently support Run or Ride.")
        distance_km = _safe_float(config.get("distance_km"))
        target_duration_min = _safe_float(config.get("target_duration_min"))
        normalized_end = end_date or config.get("event_date")
        if distance_km <= 0 or target_duration_min <= 0 or not normalized_end:
            raise ValueError("Event goals need activity_type, event date, distance, and target time.")
        normalized_start = start_date or today.isoformat()
        return {
            "goal_family": family,
            "metric_type": "event_time",
            "target_value": target_duration_min,
            "start_date": normalized_start,
            "end_date": normalized_end,
            "activity_type": activity_type,
            "target_config": {
                "distance_km": distance_km,
                "target_duration_min": target_duration_min,
                "event_date": normalized_end,
            },
        }

    if activity_type == "Run":
        distance_km = _safe_float(config.get("distance_km"))
        target_duration_min = _safe_float(config.get("target_duration_min"))
        if distance_km <= 0 or target_duration_min <= 0:
            raise ValueError("Run benchmark goals need distance and target time.")
        return {
            "goal_family": family,
            "metric_type": "benchmark_time",
            "target_value": target_duration_min,
            "start_date": start_date or default_start.isoformat(),
            "end_date": end_date or default_end.isoformat(),
            "activity_type": activity_type,
            "target_config": {
                "distance_km": distance_km,
                "target_duration_min": target_duration_min,
            },
        }

    if activity_type not in {"Ride", "VirtualRide"}:
        raise ValueError("Benchmark goals currently support Run or Ride.")
    duration_min = _safe_float(config.get("duration_min"))
    target_watts = _safe_float(config.get("target_watts"))
    if duration_min <= 0 or target_watts <= 0:
        raise ValueError("Ride benchmark goals need target duration and watts.")
    return {
        "goal_family": family,
        "metric_type": "benchmark_power",
        "target_value": target_watts,
        "start_date": start_date or default_start.isoformat(),
        "end_date": end_date or default_end.isoformat(),
        "activity_type": activity_type,
        "target_config": {
            "duration_min": duration_min,
            "target_watts": target_watts,
        },
    }


def create_goal_data(
    conn: sqlite3.Connection,
    *,
    title: str,
    period_type: str,
    goal_family: Optional[str] = None,
    metric_type: Optional[str] = None,
    target_value: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    activity_type: Optional[str] = None,
    is_active: bool = True,
    target_config: Optional[dict[str, Any]] = None,
) -> dict:
    normalized = _validate_goal_payload(
        title=title,
        period_type=period_type,
        goal_family=goal_family,
        metric_type=metric_type,
        target_value=target_value,
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        target_config=target_config,
    )
    goal_id = insert_goal(
        conn,
        title=title,
        period_type=period_type,
        goal_family=normalized["goal_family"],
        metric_type=normalized["metric_type"],
        target_value=normalized["target_value"],
        start_date=normalized["start_date"],
        end_date=normalized["end_date"],
        activity_type=normalized["activity_type"],
        is_active=is_active,
        target_config_json=json.dumps(normalized["target_config"]),
    )
    conn.commit()
    return {"status": "ok", "id": goal_id}


def list_goals_data(conn: sqlite3.Connection, active_only: bool = False, limit: int = 24) -> list[dict]:
    rows = list_goal_rows(conn, active_only=active_only, limit=limit)
    restrictions = get_modality_restrictions_for_conn(conn)
    return [serialize_goal(row, conn, restrictions) for row in rows]
