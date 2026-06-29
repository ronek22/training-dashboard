import json
import sqlite3


def upsert_coaching_snapshot_row(
    conn: sqlite3.Connection,
    *,
    week_start: str,
    week_end: str | None,
    summary_status: str,
    headline: str,
    rationale_summary: str | None,
    recommendation_status: str,
    recommendation_action: str | None,
    focus_for_next_48h: str | None,
    proposed_changed_dates: list[str],
    revision_count: int,
    generated_at: str,
):
    conn.execute(
        """
        INSERT INTO coaching_snapshots
        (
            week_start,
            week_end,
            summary_status,
            headline,
            rationale_summary,
            recommendation_status,
            recommendation_action,
            focus_for_next_48h,
            proposed_changed_dates_json,
            revision_count,
            generated_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(week_start) DO UPDATE SET
            week_end=excluded.week_end,
            summary_status=excluded.summary_status,
            headline=excluded.headline,
            rationale_summary=excluded.rationale_summary,
            recommendation_status=excluded.recommendation_status,
            recommendation_action=excluded.recommendation_action,
            focus_for_next_48h=excluded.focus_for_next_48h,
            proposed_changed_dates_json=excluded.proposed_changed_dates_json,
            revision_count=excluded.revision_count,
            generated_at=excluded.generated_at,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            week_start,
            week_end,
            summary_status,
            headline,
            rationale_summary,
            recommendation_status,
            recommendation_action,
            focus_for_next_48h,
            json.dumps(proposed_changed_dates),
            revision_count,
            generated_at,
        ),
    )


def list_coaching_snapshot_rows(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM coaching_snapshots
        ORDER BY week_start DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
