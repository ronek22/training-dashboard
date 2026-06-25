import json
import sqlite3
from typing import Optional

from ..models.plans import WeeklyPlan


def get_weekly_plan_row(conn: sqlite3.Connection, week_start: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM weekly_plans WHERE week_start = ?",
        (week_start,),
    ).fetchone()


def upsert_weekly_plan_row(conn: sqlite3.Connection, plan: WeeklyPlan):
    conn.execute(
        """
        INSERT INTO weekly_plans
        (week_start, title, focus, overview, days_json, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            title=excluded.title,
            focus=excluded.focus,
            overview=excluded.overview,
            days_json=excluded.days_json,
            notes=excluded.notes
        """,
        (
            plan.week_start,
            plan.title,
            plan.focus,
            plan.overview,
            json.dumps([day.model_dump() for day in plan.days]),
            plan.notes,
        ),
    )


def list_weekly_plan_rows(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC LIMIT ?",
        (limit,),
    ).fetchall()
