import sqlite3
from datetime import date
from typing import Any, Optional


def insert_goal(
    conn: sqlite3.Connection,
    title: str,
    period_type: str,
    metric_type: str,
    target_value: float,
    start_date: str,
    end_date: str,
    activity_type: Optional[str],
    is_active: bool,
    goal_family: str,
    target_config_json: Optional[str],
    lifecycle_fields: Optional[dict[str, Any]] = None,
) -> int:
    lifecycle_fields = lifecycle_fields or {}
    cursor = conn.execute(
        """
        INSERT INTO goals
        (title, period_type, goal_family, metric_type, target_value, start_date, end_date, activity_type, is_active, target_config_json,
         lifecycle_status, purpose, commitment, review_on, season_end, outcome_signal, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            title,
            period_type,
            goal_family,
            metric_type,
            target_value,
            start_date,
            end_date,
            activity_type,
            1 if is_active else 0,
            target_config_json,
            "active" if is_active else "paused",
            lifecycle_fields.get("purpose"),
            lifecycle_fields.get("commitment") or "flexible",
            lifecycle_fields.get("review_on"),
            lifecycle_fields.get("season_end"),
            lifecycle_fields.get("outcome_signal"),
        ),
    )
    return cursor.lastrowid


# Columns a goal update may write. Keeps the dynamic UPDATE below from ever
# interpolating caller-controlled column names.
UPDATABLE_GOAL_COLUMNS = (
    "title",
    "period_type",
    "goal_family",
    "metric_type",
    "target_value",
    "start_date",
    "end_date",
    "activity_type",
    "target_config_json",
    "purpose",
    "commitment",
    "review_on",
    "season_end",
    "outcome_signal",
)

# A recurring goal whose season has ended stops applying to planning even while
# its lifecycle status is still active; it waits for an explicit review.
ACTIVE_GOAL_CONDITION = "is_active = 1 AND (season_end IS NULL OR season_end = '' OR season_end >= ?)"


def list_goal_rows(
    conn: sqlite3.Connection,
    active_only: bool = False,
    limit: int = 24,
    lifecycle_status: Optional[str] = None,
    today: Optional[str] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM goals"
    clauses: list[str] = []
    params: list[Any] = []
    if active_only:
        clauses.append(ACTIVE_GOAL_CONDITION)
        params.append(today or date.today().isoformat())
    if lifecycle_status:
        clauses.append("lifecycle_status = ?")
        params.append(lifecycle_status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY is_active DESC, created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def get_goal_row(conn: sqlite3.Connection, goal_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()


def update_goal(conn: sqlite3.Connection, goal_id: int, fields: dict[str, Any]) -> None:
    columns = [column for column in UPDATABLE_GOAL_COLUMNS if column in fields]
    if not columns:
        return
    assignments = ", ".join(f"{column} = ?" for column in columns)
    conn.execute(
        f"UPDATE goals SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [*(fields[column] for column in columns), goal_id],
    )


def set_goal_status(conn: sqlite3.Connection, goal_id: int, lifecycle_status: str, reason: Optional[str]) -> None:
    conn.execute(
        """
        UPDATE goals
        SET lifecycle_status = ?,
            is_active = ?,
            status_reason = ?,
            status_changed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (lifecycle_status, 1 if lifecycle_status == "active" else 0, reason, goal_id),
    )


def insert_goal_review_decision(
    conn: sqlite3.Connection,
    goal_id: int,
    verdict: str,
    decision: str,
    until: Optional[str],
    note: Optional[str],
) -> int:
    cursor = conn.execute(
        "INSERT INTO goal_review_decisions (goal_id, verdict, decision, until, note) VALUES (?, ?, ?, ?, ?)",
        (goal_id, verdict, decision, until, note),
    )
    return cursor.lastrowid


def latest_goal_review_decisions(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT d.*
        FROM goal_review_decisions AS d
        JOIN (
            SELECT goal_id, MAX(id) AS id FROM goal_review_decisions GROUP BY goal_id
        ) AS latest ON latest.id = d.id
        """
    ).fetchall()
    return {row["goal_id"]: row for row in rows}


def insert_goal_suggestion_decision(
    conn: sqlite3.Connection,
    key: str,
    decision: str,
    until: Optional[str],
) -> int:
    cursor = conn.execute(
        "INSERT INTO goal_suggestion_decisions (key, decision, until) VALUES (?, ?, ?)",
        (key, decision, until),
    )
    return cursor.lastrowid


def latest_goal_suggestion_decisions(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT d.*
        FROM goal_suggestion_decisions AS d
        JOIN (
            SELECT key, MAX(id) AS id FROM goal_suggestion_decisions GROUP BY key
        ) AS latest ON latest.id = d.id
        """
    ).fetchall()
    return {row["key"]: row for row in rows}
