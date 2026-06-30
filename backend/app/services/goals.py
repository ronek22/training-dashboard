import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from ..repositories.goals import insert_goal, list_goal_rows
from .settings import modality_for_goal, get_modality_restrictions_for_conn, restriction_summary_text


def goal_metric_unit(metric_type: str) -> str:
    if metric_type in {"ride_km", "run_km"}:
        return "km"
    if metric_type == "strength_sessions":
        return "sessions"
    if metric_type == "activities_count":
        return "activities"
    return ""


def rounded_goal_value(metric_type: str, value: float) -> float:
    if metric_type in {"strength_sessions", "activities_count"}:
        return round(value, 1)
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
    return "goal"


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

    return 0.0


def goal_planning_guidance(
    *,
    metric_type: str,
    unit: str,
    title: str,
    target_value: float,
    current_value: float,
    remaining_value: float,
    total_days: int,
    elapsed_days: int,
    today,
    end_day,
    forecast: dict,
) -> dict:
    remaining_days_including_today = max((end_day - today).days + 1, 1)
    required_per_week = required_per_day = 0.0
    current_per_week = round((current_value / max(elapsed_days, 1)) * 7, 2) if elapsed_days > 0 else 0.0
    if remaining_value <= 0:
        return {
            "remaining_days_including_today": remaining_days_including_today,
            "required_per_day": 0.0,
            "required_per_week": 0.0,
            "current_per_week": current_per_week,
            "status": "completed",
            "summary": "Target already met.",
        }

    base_daily_target = target_value / max(total_days, 1) if target_value > 0 else 0.0
    required_per_day = remaining_value / remaining_days_including_today
    required_per_week = required_per_day * 7
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
    if unit == "sessions":
        summary = f"Need about {rounded_required} {unit}/day from here."
    if unit == "activities":
        summary = f"Need about {rounded_required} {unit}/day from here."
    if forecast.get("projected_status") in {"behind", "at_risk"}:
        projected_gap = rounded_goal_value(metric_type, abs(float(forecast.get("projected_gap_value") or 0)))
        summary = f"{title} is slipping. Need about {rounded_goal_value(metric_type, required_per_week)} {unit}/week to recover pace."
        if projected_gap > 0:
            summary = f"{summary} Current trend finishes {projected_gap} {unit} short."
    elif forecast.get("projected_status") == "ahead":
        summary = f"Current trend keeps {title} ahead of pace."

    return {
        "remaining_days_including_today": remaining_days_including_today,
        "required_per_day": round(required_per_day, 2),
        "required_per_week": round(required_per_week, 2),
        "current_per_week": current_per_week,
        "status": status,
        "summary": summary,
    }


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


def goal_current_value(conn: sqlite3.Connection, goal: sqlite3.Row) -> float:
    start_day, end_day, _ = goal_period_window(goal["period_type"])
    return goal_value_for_window(conn, goal, start_date=start_day.isoformat(), end_date=end_day.isoformat())


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


def serialize_goal(row: sqlite3.Row, conn: sqlite3.Connection, restrictions: Optional[dict] = None) -> dict:
    current_value = round(goal_current_value(conn, row), 1)
    target_value = float(row["target_value"] or 0)
    today = datetime.now().date()
    start_day, end_day, period_label = goal_period_window(row["period_type"], today)
    total_days = max((end_day - start_day).days + 1, 1)
    elapsed_days = min(max((today - start_day).days + 1, 0), total_days)
    days_remaining = max((end_day - today).days, 0)
    progress_pct = round(min((current_value / target_value) * 100, 999), 1) if target_value > 0 else 0
    expected_pct = round((elapsed_days / total_days) * 100, 1)
    remaining_value = round(max(target_value - current_value, 0), 1)
    expected_value = round((target_value * elapsed_days) / total_days, 1) if target_value > 0 else 0.0
    pace_delta_value = round(current_value - expected_value, 1)
    pace_delta_pct = round(progress_pct - expected_pct, 1)
    unit = goal_metric_unit(row["metric_type"])
    metric_label = goal_metric_label(row["metric_type"])
    modality = modality_for_goal(row["metric_type"], row["activity_type"])
    normalized_restrictions = restrictions or get_modality_restrictions_for_conn(conn)
    modality_restriction = (
        normalized_restrictions.get("modalities", {}).get(modality)
        if modality else None
    )
    is_constrained = bool(modality_restriction and modality_restriction.get("status") in {"limited", "blocked"})

    if is_constrained:
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
    constraint_summary = None
    if is_constrained:
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
        constraint_summary = {
            "modality": modality,
            "status": modality_restriction["status"],
            "label": modality_restriction["label"],
            "reason": modality_restriction.get("reason"),
            "note": modality_restriction.get("note"),
            "expected_end_date": modality_restriction.get("expected_end_date"),
            "summary": restriction_summary_text(modality_restriction),
        }

    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
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
    }


def create_goal_data(
    conn: sqlite3.Connection,
    *,
    title: str,
    period_type: str,
    metric_type: str,
    target_value: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    activity_type: Optional[str] = None,
    is_active: bool = True,
) -> dict:
    start_day, end_day, _ = goal_period_window(period_type)
    goal_id = insert_goal(
        conn,
        title=title,
        period_type=period_type,
        metric_type=metric_type,
        target_value=target_value,
        start_date=start_date or start_day.isoformat(),
        end_date=end_date or end_day.isoformat(),
        activity_type=activity_type,
        is_active=is_active,
    )
    conn.commit()
    return {"status": "ok", "id": goal_id}


def list_goals_data(conn: sqlite3.Connection, active_only: bool = False, limit: int = 24) -> list[dict]:
    rows = list_goal_rows(conn, active_only=active_only, limit=limit)
    restrictions = get_modality_restrictions_for_conn(conn)
    return [serialize_goal(row, conn, restrictions) for row in rows]
