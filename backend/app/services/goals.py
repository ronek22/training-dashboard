import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from ..repositories.goals import insert_goal, list_goal_rows


def goal_metric_unit(metric_type: str) -> str:
    if metric_type in {"ride_km", "run_km"}:
        return "km"
    if metric_type == "strength_sessions":
        return "sessions"
    if metric_type == "activities_count":
        return "activities"
    return ""


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
    metric_type = goal["metric_type"]
    start_day, end_day, _ = goal_period_window(goal["period_type"])
    start_date = start_day.isoformat()
    end_date = end_day.isoformat()

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


def serialize_goal(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
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

    if current_value >= target_value:
        status = "completed"
    elif pace_delta_pct >= 5:
        status = "ahead_of_pace"
    elif pace_delta_pct >= -5:
        status = "on_pace"
    else:
        status = "behind_pace"

    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
        "metric_type": row["metric_type"],
        "target_value": target_value,
        "current_value": current_value,
        "unit": goal_metric_unit(row["metric_type"]),
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
    return [serialize_goal(row, conn) for row in rows]
