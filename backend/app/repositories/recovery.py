import json


def init_recovery_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recovery_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            intake_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            needs_review INTEGER NOT NULL DEFAULT 1,
            concern TEXT NOT NULL DEFAULT 'none',
            share_coaching INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recovery_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL REFERENCES recovery_issues(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recovery_requests (
            id TEXT PRIMARY KEY,
            issue_id INTEGER NOT NULL REFERENCES recovery_issues(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recovery_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL REFERENCES recovery_issues(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            exercises_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recovery_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL REFERENCES recovery_issues(id) ON DELETE CASCADE,
            routine_id INTEGER REFERENCES recovery_routines(id),
            severity INTEGER NOT NULL,
            before_severity INTEGER,
            trend TEXT NOT NULL,
            function TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recovery_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL REFERENCES recovery_issues(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS recovery_messages_issue ON recovery_messages(issue_id, id);
        CREATE INDEX IF NOT EXISTS recovery_requests_issue ON recovery_requests(issue_id);
        CREATE INDEX IF NOT EXISTS recovery_checkins_issue ON recovery_checkins(issue_id, id);
        CREATE INDEX IF NOT EXISTS recovery_routines_issue ON recovery_routines(issue_id, id);
        CREATE INDEX IF NOT EXISTS recovery_status_history_issue ON recovery_status_history(issue_id, id);
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(recovery_issues)")}
    for name, ddl in (
        ("share_coaching", "INTEGER NOT NULL DEFAULT 0"),
        ("proposed_intake_json", "TEXT"),
        ("body_area", "TEXT NOT NULL DEFAULT ''"),
        ("side", "TEXT NOT NULL DEFAULT ''"),
        ("started_on", "TEXT"),
        ("healed_on", "TEXT"),
        ("what_helped", "TEXT NOT NULL DEFAULT ''"),
        ("previous_issue_id", "INTEGER"),
        ("see_professional", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE recovery_issues ADD COLUMN {name} {ddl}")
    if "body_area" not in columns:
        _migrate_intake_issues(conn)


def _migrate_intake_issues(conn):
    """Carry the retired intake form's location/side/onset into the simple issue fields."""
    rows = conn.execute("SELECT id, intake_json, status, created_at, updated_at FROM recovery_issues").fetchall()
    for issue_id, intake_json, status, created_at, updated_at in rows:
        try:
            intake = json.loads(intake_json or "{}")
        except json.JSONDecodeError:
            intake = {}
        side = intake.get("side") if intake.get("side") in {"left", "right", "both"} else ""
        healed = status == "archived"
        conn.execute(
            """UPDATE recovery_issues SET body_area = ?, side = ?, started_on = ?, status = ?, healed_on = ?
               WHERE id = ?""",
            ((intake.get("location") or "").strip()[:80], side,
             intake.get("onset_date") or (created_at or "")[:10] or None,
             "healed" if healed else "active", (updated_at or "")[:10] if healed else None, issue_id),
        )


def issue_row(conn, issue_id):
    row = conn.execute("SELECT * FROM recovery_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise LookupError("Recovery issue not found.")
    return dict(row)


def children(conn, issue_id):
    # Explicit table allowlist; never accept identifiers from an API request.
    result = {}
    for table in ("messages", "routines", "checkins", "requests", "status_history"):
        rows = conn.execute(
            f"SELECT * FROM recovery_{table} WHERE issue_id = ? ORDER BY created_at, rowid",
            (issue_id,),
        ).fetchall()
        result[table] = [dict(row) for row in rows]
    plans = []
    for routine in result.pop("routines"):
        plan = json.loads(routine.pop("exercises_json"))
        # Rows from the retired exercise-library routines were lists; they are not plans.
        if isinstance(plan, dict):
            plans.append({"id": routine["id"], "status": routine["status"], "created_at": routine["created_at"], **plan})
    result["plans"] = plans
    return result


def delete_issue(conn, issue_id):
    issue_row(conn, issue_id)
    # Existing app connections do not enable foreign keys, so delete explicitly too.
    for table in ("status_history", "checkins", "routines", "requests", "messages"):
        conn.execute(f"DELETE FROM recovery_{table} WHERE issue_id = ?", (issue_id,))
    conn.execute("DELETE FROM recovery_issues WHERE id = ?", (issue_id,))


def append_status_history(conn, issue_id, status):
    """Record a lifecycle transition while retaining the issue itself."""
    conn.execute(
        "INSERT INTO recovery_status_history (issue_id, status) VALUES (?, ?)",
        (issue_id, status),
    )
