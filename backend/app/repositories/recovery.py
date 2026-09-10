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
        CREATE INDEX IF NOT EXISTS recovery_messages_issue ON recovery_messages(issue_id, id);
        CREATE INDEX IF NOT EXISTS recovery_requests_issue ON recovery_requests(issue_id);
        CREATE INDEX IF NOT EXISTS recovery_checkins_issue ON recovery_checkins(issue_id, id);
        CREATE INDEX IF NOT EXISTS recovery_routines_issue ON recovery_routines(issue_id, id);
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(recovery_issues)")}
    if "share_coaching" not in columns:
        conn.execute("ALTER TABLE recovery_issues ADD COLUMN share_coaching INTEGER NOT NULL DEFAULT 0")
    if "proposed_intake_json" not in columns:
        conn.execute("ALTER TABLE recovery_issues ADD COLUMN proposed_intake_json TEXT")


def issue_row(conn, issue_id):
    row = conn.execute("SELECT * FROM recovery_issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise LookupError("Recovery issue not found.")
    return dict(row)


def children(conn, issue_id):
    # Explicit table allowlist; never accept identifiers from an API request.
    result = {}
    for table in ("messages", "routines", "checkins", "requests"):
        rows = conn.execute(
            f"SELECT * FROM recovery_{table} WHERE issue_id = ? ORDER BY created_at, rowid",
            (issue_id,),
        ).fetchall()
        result[table] = [dict(row) for row in rows]
    for routine in result["routines"]:
        routine["exercises"] = json.loads(routine.pop("exercises_json"))
    return result


def delete_issue(conn, issue_id):
    issue_row(conn, issue_id)
    # Existing app connections do not enable foreign keys, so delete explicitly too.
    for table in ("checkins", "routines", "requests", "messages"):
        conn.execute(f"DELETE FROM recovery_{table} WHERE issue_id = ?", (issue_id,))
    conn.execute("DELETE FROM recovery_issues WHERE id = ?", (issue_id,))
