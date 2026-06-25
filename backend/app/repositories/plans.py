import json
import sqlite3
from typing import Optional

from ..models.plans import WeeklyPlan, WeeklyPlanRevision


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


def create_weekly_plan_revision_row(conn: sqlite3.Connection, revision: WeeklyPlanRevision):
    conn.execute(
        """
        INSERT INTO plan_revisions
        (
            week_start,
            effective_from,
            adaptation_reason,
            changed_dates_json,
            preserved_dates_json,
            previous_plan_json,
            updated_plan_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision.week_start,
            revision.effective_from,
            revision.adaptation_reason,
            json.dumps(revision.changed_dates),
            json.dumps(revision.preserved_dates),
            json.dumps(revision.previous_plan.model_dump()),
            json.dumps(revision.updated_plan.model_dump()),
        ),
    )


def get_latest_weekly_plan_revision_row(conn: sqlite3.Connection, week_start: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM plan_revisions
        WHERE week_start = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (week_start,),
    ).fetchone()


def count_weekly_plan_revision_rows(conn: sqlite3.Connection, week_start: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS revision_count
        FROM plan_revisions
        WHERE week_start = ?
        """,
        (week_start,),
    ).fetchone()
    return int(row["revision_count"] or 0)
