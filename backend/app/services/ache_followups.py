"""Follow up on small aches named in session feedback or the morning check-in.

A note that names a body area with pain 1-3 opens a thread. From the next morning the
check-in asks "better, same or worse?" once a day. "Better" closes it quietly; "same"
twice or "worse" once offers a prefilled light recovery issue. Nothing is created and no
area is protected until the athlete taps it, and that protection expires on its own.
"""
import sqlite3
from datetime import date, timedelta
from typing import Optional

from .recovery import detect_body_areas, issue_body_areas
from .settings import BODY_AREAS

ANSWERS = ("better", "same", "worse")
SAME_TO_OFFER = 2
# A thread nobody answered for this long has gone quiet; stop asking.
QUIET_AFTER_DAYS = 7
DEFAULT_PROTECT_DAYS = 5
MAX_PROTECT_DAYS = 14
# One short routine from the guided-session library per area.
MOBILITY_FOR_AREA = {
    "lower_back": "gentle_stretch",
    "hip": "mobility_flow",
    "knee": "gentle_stretch",
    "heel": "gentle_stretch",
    "shoulder": "desk_mobility",
    "neck": "desk_mobility",
    "elbow": "desk_mobility",
    "wrist": "desk_mobility",
}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS ache_followups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area TEXT NOT NULL,
        source TEXT NOT NULL,
        source_ref TEXT NOT NULL,
        noted_on TEXT NOT NULL,
        pain INTEGER NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'open',
        same_count INTEGER NOT NULL DEFAULT 0,
        last_answer TEXT,
        last_answered_on TEXT,
        recovery_issue_id INTEGER,
        protect_until TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (source, source_ref, area)
    )""")


def _today(today: Optional[date]) -> date:
    return today or date.today()


def note_mention(conn: sqlite3.Connection, source: str, source_ref: str, day: str, pain, note) -> list[str]:
    """Open a thread for each area a mild-pain note names, unless one is already running."""
    if not note or not pain or not 1 <= int(pain) <= 3:
        return []
    init_schema(conn)
    covered = {item["area"] for item in issue_body_areas(conn)}
    opened = []
    for area in detect_body_areas(note):
        running = conn.execute(
            "SELECT 1 FROM ache_followups WHERE area = ? AND status IN ('open', 'offered')", (area,)
        ).fetchone()
        if running or area in covered:
            continue
        cursor = conn.execute(
            """INSERT OR IGNORE INTO ache_followups (area, source, source_ref, noted_on, pain, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (area, source, source_ref, day, int(pain), note.strip()[:300]),
        )
        if cursor.rowcount:
            opened.append(area)
    return opened


def _label(area: str) -> str:
    return BODY_AREAS[area]["label"]


def _mobility(area: str) -> Optional[dict]:
    from .guided_sessions import public_session

    session = public_session(MOBILITY_FOR_AREA.get(area, ""))
    return {key: session[key] for key in ("key", "title", "duration_min")} if session else None


def _serialize(row: dict, today: date) -> dict:
    item = {
        "id": row["id"],
        "area": row["area"],
        "label": _label(row["area"]),
        "question": f"{_label(row['area'])}: better, same or worse?",
        "noted_on": row["noted_on"],
        "source": row["source"],
        "pain": row["pain"],
        "note": row["note"],
        "status": row["status"],
        "same_count": row["same_count"],
        "answered_today": row["last_answered_on"] == today.isoformat(),
        "last_answer": row["last_answer"],
        "mobility": _mobility(row["area"]),
        "offer": None,
    }
    if row["status"] == "offered":
        item["offer"] = {
            "title": f"{_label(row['area'])} niggle",
            "body_area": _label(row["area"]).lower(),
            "side": "",
            "pain": row["pain"],
            "protect_days": DEFAULT_PROTECT_DAYS,
        }
    return item


def _close_quiet(conn: sqlite3.Connection, today: date) -> None:
    cutoff = (today - timedelta(days=QUIET_AFTER_DAYS)).isoformat()
    conn.execute(
        """UPDATE ache_followups SET status = 'closed', updated_at = CURRENT_TIMESTAMP
           WHERE status IN ('open', 'offered') AND COALESCE(last_answered_on, noted_on) < ?""",
        (cutoff,),
    )


def pending(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict]:
    """Threads to ask about this morning: noted before today and not settled yet."""
    today = _today(today)
    init_schema(conn)
    _close_quiet(conn, today)
    rows = conn.execute(
        """SELECT * FROM ache_followups WHERE status IN ('open', 'offered') AND noted_on < ?
           ORDER BY noted_on, id""",
        (today.isoformat(),),
    ).fetchall()
    return [_serialize(dict(row), today) for row in rows]


def _row(conn: sqlite3.Connection, followup_id: int) -> dict:
    init_schema(conn)
    row = conn.execute("SELECT * FROM ache_followups WHERE id = ?", (followup_id,)).fetchone()
    if row is None:
        raise LookupError("Follow-up not found.")
    return dict(row)


def answer(conn: sqlite3.Connection, followup_id: int, reply: str, today: Optional[date] = None) -> dict:
    today = _today(today)
    row = _row(conn, followup_id)
    if reply not in ANSWERS:
        raise ValueError("Answer better, same or worse.")
    if row["status"] != "open":
        raise ValueError("This follow-up is already settled.")
    if row["noted_on"] >= today.isoformat():
        raise ValueError("Ask again tomorrow morning.")
    if row["last_answered_on"] == today.isoformat():
        raise ValueError("Already answered today.")
    same_count = row["same_count"] + (reply == "same")
    if reply == "better":
        status = "closed"
    elif reply == "worse" or same_count >= SAME_TO_OFFER:
        status = "offered"
    else:
        status = "open"
    conn.execute(
        """UPDATE ache_followups SET status = ?, same_count = ?, last_answer = ?, last_answered_on = ?,
           updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (status, same_count, reply, today.isoformat(), followup_id),
    )
    return _serialize(_row(conn, followup_id), today)


def accept(conn: sqlite3.Connection, followup_id: int, payload, today: Optional[date] = None) -> dict:
    """Open the light recovery issue the athlete tapped, and protect the area only if asked."""
    from ..models.recovery import IssueCreate
    from .recovery import create_issue

    today = _today(today)
    row = _row(conn, followup_id)
    if row["status"] != "offered":
        raise ValueError("Nothing to open for this follow-up yet.")
    issue = create_issue(conn, IssueCreate(title=payload.title, body_area=payload.body_area,
                                           side=payload.side, pain=payload.pain))
    # The issue follows the athlete's choice below rather than protecting the area indefinitely.
    conn.execute("UPDATE recovery_issues SET protects_area = 0 WHERE id = ?", (issue["id"],))
    # Protection covers today plus the following days, protect_days in all.
    protect_until = (today + timedelta(days=payload.protect_days - 1)).isoformat() if payload.protect_days else None
    conn.execute(
        """UPDATE ache_followups SET status = 'issue_opened', recovery_issue_id = ?, protect_until = ?,
           updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (issue["id"], protect_until, followup_id),
    )
    return {"followup": _serialize(_row(conn, followup_id), today), "issue_id": issue["id"],
            "protect_until": protect_until}


def dismiss(conn: sqlite3.Connection, followup_id: int, today: Optional[date] = None) -> dict:
    row = _row(conn, followup_id)
    if row["status"] not in ("open", "offered"):
        raise ValueError("This follow-up is already settled.")
    conn.execute("UPDATE ache_followups SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                 (followup_id,))
    return _serialize(_row(conn, followup_id), _today(today))


def protected_areas(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict]:
    """Areas the athlete chose to protect from a follow-up, until that choice runs out."""
    today = _today(today)
    try:
        rows = conn.execute(
            "SELECT * FROM ache_followups WHERE protect_until IS NOT NULL AND protect_until >= ?",
            (today.isoformat(),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"area": row["area"], "since": row["noted_on"], "note": f"Ache follow-up until {row['protect_until']}",
             "recovery_issue_id": row["recovery_issue_id"]} for row in rows]
