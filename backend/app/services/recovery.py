import json
import re
import uuid
from datetime import date

from ..repositories import recovery as repo

# Words that describe where on a body part, not which body part. Ignored when
# matching a new issue against past ones so "outside of left knee" finds "knee".
AREA_NOISE = {
    "a", "an", "and", "area", "both", "front", "inner", "inside", "left", "lower", "middle", "my",
    "of", "on", "outer", "outside", "pain", "rear", "right", "side", "sides", "sore", "soreness",
    "the", "upper",
}
AREA_ALIASES = {"calves": "calf", "feet": "foot", "achilles": "achilles", "quadriceps": "quad"}


def area_tokens(text):
    tokens = set()
    for word in re.findall(r"[a-z]+", (text or "").lower()):
        if word in AREA_NOISE:
            continue
        word = AREA_ALIASES.get(word, word)
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        tokens.add(word)
    return tokens


def _checkins(conn, issue_id, limit=None):
    sql = "SELECT * FROM recovery_checkins WHERE issue_id = ? ORDER BY created_at, id"
    rows = [dict(row) for row in conn.execute(sql, (issue_id,))]
    return rows[-limit:] if limit else rows


def _current_pain(conn, issue_id):
    row = conn.execute(
        "SELECT severity FROM recovery_checkins WHERE issue_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (issue_id,),
    ).fetchone()
    return row[0] if row else None


def _brief(conn, row):
    return {key: row[key] for key in (
        "id", "title", "body_area", "side", "status", "started_on", "healed_on", "what_helped",
        "previous_issue_id", "see_professional", "updated_at",
    )} | {"current_pain": _current_pain(conn, row["id"])}


def list_issues(conn):
    rows = conn.execute("""SELECT * FROM recovery_issues
        ORDER BY status = 'active' DESC, updated_at DESC, id DESC""").fetchall()
    return [_brief(conn, dict(row)) for row in rows]


def related_issues(conn, body_area, *, exclude_id=None, previous_issue_id=None):
    """Past episodes of the same problem: the explicit recurrence chain plus same-area issues."""
    rows = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM recovery_issues")}
    linked = set()
    cursor = previous_issue_id
    while cursor in rows and cursor not in linked:
        linked.add(cursor)
        cursor = rows[cursor]["previous_issue_id"]
    wanted = area_tokens(body_area)
    matches = [
        row for issue_id, row in rows.items()
        if issue_id != exclude_id and (issue_id in linked or (wanted and wanted & area_tokens(row["body_area"])))
    ]
    matches.sort(key=lambda row: (row["started_on"] or row["created_at"] or ""), reverse=True)
    return [_brief(conn, row) for row in matches]


def get_issue(conn, issue_id):
    conn.execute("""UPDATE recovery_requests SET status = 'failed'
        WHERE issue_id = ? AND status = 'pending' AND created_at < datetime('now', '-17 minutes')""", (issue_id,))
    issue = _brief(conn, repo.issue_row(conn, issue_id))
    children = repo.children(conn, issue_id)
    issue["messages"] = [{key: row[key] for key in ("id", "role", "content", "created_at")} for row in children["messages"]]
    issue["plans"] = children["plans"]
    issue["current_plan"] = next((plan for plan in reversed(children["plans"]) if plan["status"] == "current"), None)
    issue["checkins"] = [
        {"id": row["id"], "pain": row["severity"], "did_plan": bool(row["completed"]), "note": row["note"],
         "created_at": row["created_at"]}
        for row in children["checkins"]
    ]
    issue["latest_request"] = children["requests"][-1] if children["requests"] else None
    issue["related"] = related_issues(conn, issue["body_area"], exclude_id=issue_id,
                                      previous_issue_id=issue["previous_issue_id"])
    return issue


def create_issue(conn, payload):
    if payload.previous_issue_id is not None:
        repo.issue_row(conn, payload.previous_issue_id)
    title = payload.title or " ".join(part for part in (payload.side if payload.side != "both" else "", payload.body_area) if part)
    cursor = conn.execute(
        """INSERT INTO recovery_issues (title, body_area, side, started_on, previous_issue_id, needs_review)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (title[:1].upper() + title[1:], payload.body_area, payload.side, date.today().isoformat(), payload.previous_issue_id),
    )
    issue_id = cursor.lastrowid
    repo.append_status_history(conn, issue_id, "active")
    if payload.pain is not None:
        _insert_checkin(conn, issue_id, payload.pain, False, "Starting point")
    return get_issue(conn, issue_id)


def update_issue(conn, issue_id, payload):
    repo.issue_row(conn, issue_id)
    values = payload.model_dump(exclude_none=True)
    for key, value in values.items():
        # Keys come from the validated model, never from free-form request data.
        conn.execute(f"UPDATE recovery_issues SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, issue_id))
    return get_issue(conn, issue_id)


def heal(conn, issue_id, what_helped):
    issue = active_issue(conn, issue_id)
    invalidate_requests(conn, issue_id)
    conn.execute("""UPDATE recovery_issues SET status = 'healed', healed_on = ?, what_helped = ?,
        updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (date.today().isoformat(), what_helped, issue["id"]))
    repo.append_status_history(conn, issue_id, "healed")
    return get_issue(conn, issue_id)


def reopen(conn, issue_id):
    issue = repo.issue_row(conn, issue_id)
    if issue["status"] != "active":
        conn.execute("""UPDATE recovery_issues SET status = 'active', healed_on = NULL,
            updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (issue_id,))
        repo.append_status_history(conn, issue_id, "active")
    return get_issue(conn, issue_id)


def active_issue(conn, issue_id):
    issue = repo.issue_row(conn, issue_id)
    if issue["status"] != "active":
        raise ValueError("This issue is marked healed. Reopen it, or log that it came back.")
    return issue


def invalidate_requests(conn, issue_id):
    conn.execute("UPDATE recovery_requests SET status = 'stale' WHERE issue_id = ? AND status = 'pending'", (issue_id,))


def add_message(conn, issue_id, payload):
    active_issue(conn, issue_id)
    conn.execute("INSERT INTO recovery_messages (issue_id, role, content) VALUES (?, 'user', ?)", (issue_id, payload.content))
    conn.execute("UPDATE recovery_issues SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (issue_id,))
    return new_request(conn, issue_id)


def new_request(conn, issue_id):
    active_issue(conn, issue_id)
    if not conn.execute("SELECT 1 FROM recovery_messages WHERE issue_id = ? AND role = 'user'", (issue_id,)).fetchone():
        raise ValueError("Write a message first.")
    invalidate_requests(conn, issue_id)
    request_id = uuid.uuid4().hex
    conn.execute("INSERT INTO recovery_requests (id, issue_id, revision, kind) VALUES (?, ?, 0, 'chat')",
                 (request_id, issue_id))
    return {"request_id": request_id, "issue_id": issue_id}


def request_row(conn, issue_id, request_id):
    active_issue(conn, issue_id)
    row = conn.execute("SELECT * FROM recovery_requests WHERE id = ? AND issue_id = ?", (request_id, issue_id)).fetchone()
    if row is None:
        raise LookupError("Recovery request not found.")
    if row["status"] != "pending":
        raise ValueError("This reply is no longer current. Ask again.")
    return dict(row)


def _plan_brief(plan):
    return {key: plan.get(key) for key in ("summary", "exercises", "do", "avoid", "status", "created_at")}


def _episode(conn, brief):
    checkins = _checkins(conn, brief["id"])
    plans = repo.children(conn, brief["id"])["plans"]
    return {
        **{key: brief[key] for key in ("title", "body_area", "side", "status", "started_on", "healed_on", "what_helped")},
        "plans": [_plan_brief(plan) for plan in plans[-3:]],
        "checkins": [{"date": row["created_at"][:10], "pain": row["severity"], "did_plan": bool(row["completed"]),
                      "note": row["note"]} for row in checkins[-12:]],
    }


def training_context(conn):
    from .dashboard import build_recent_context
    context = build_recent_context(conn, recent_activity_limit=8, recent_note_limit=1)
    return {key: context.get(key) for key in ("readiness", "modality_restrictions", "recent_activities", "active_plan")}


def ai_context(conn, issue_id, request_id):
    request_row(conn, issue_id, request_id)
    issue = get_issue(conn, issue_id)
    history = conn.execute("""SELECT role, content, created_at FROM recovery_messages WHERE issue_id = ?
        ORDER BY id DESC LIMIT 30""", (issue_id,)).fetchall()
    related = issue["related"]
    all_past = [row for row in list_issues(conn) if row["id"] != issue_id and row["status"] == "healed"]
    return {
        "today": date.today().isoformat(),
        "issue": {key: issue[key] for key in ("title", "body_area", "side", "started_on", "current_pain")},
        "current_plan": _plan_brief(issue["current_plan"]) if issue["current_plan"] else None,
        "checkins": [{"date": row["created_at"][:10], "pain": row["pain"], "did_plan": row["did_plan"], "note": row["note"]}
                     for row in issue["checkins"][-15:]],
        "conversation": [dict(row) for row in reversed(history)],
        "previous_episodes_same_area": [_episode(conn, brief) for brief in related[:5]],
        "other_past_injuries": [
            {key: row[key] for key in ("title", "body_area", "side", "started_on", "healed_on", "what_helped")}
            for row in all_past if row["id"] not in {item["id"] for item in related}
        ][:15],
        "training_context": training_context(conn),
    }


def finish_request(conn, issue_id, request_id, result):
    request_row(conn, issue_id, request_id)
    conn.execute("INSERT INTO recovery_messages (issue_id, role, content) VALUES (?, 'assistant', ?)", (issue_id, result.reply))
    if result.plan is not None:
        conn.execute("UPDATE recovery_routines SET status = 'replaced' WHERE issue_id = ? AND status = 'current'", (issue_id,))
        conn.execute("INSERT INTO recovery_routines (issue_id, revision, status, exercises_json) VALUES (?, 0, 'current', ?)",
                     (issue_id, result.plan.model_dump_json()))
    conn.execute("""UPDATE recovery_issues SET see_professional = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?""", (result.see_professional, issue_id))
    conn.execute("UPDATE recovery_requests SET status = 'succeeded' WHERE id = ?", (request_id,))
    return {"status": "succeeded"}


def fail_request(conn, issue_id, request_id):
    conn.execute("UPDATE recovery_requests SET status = 'failed' WHERE id = ? AND issue_id = ? AND status = 'pending'",
                 (request_id, issue_id))
    return {"status": "failed"}


def _insert_checkin(conn, issue_id, pain, did_plan, note):
    plan = conn.execute("SELECT id FROM recovery_routines WHERE issue_id = ? AND status = 'current' ORDER BY id DESC LIMIT 1",
                        (issue_id,)).fetchone()
    conn.execute("""INSERT INTO recovery_checkins (issue_id, routine_id, severity, trend, function, completed, note)
        VALUES (?, ?, ?, 'unknown', 'unknown', ?, ?)""", (issue_id, plan[0] if plan and did_plan else None, pain, did_plan, note))
    conn.execute("UPDATE recovery_issues SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (issue_id,))


def add_checkin(conn, issue_id, payload):
    active_issue(conn, issue_id)
    _insert_checkin(conn, issue_id, payload.pain, payload.did_plan, payload.note)
    return get_issue(conn, issue_id)


def coaching_summary(conn):
    """Active injuries for Coach and planning context: no conversation text."""
    summaries = []
    for row in conn.execute("SELECT * FROM recovery_issues WHERE status = 'active' ORDER BY updated_at DESC, id DESC LIMIT 8"):
        item = dict(row)
        plan = conn.execute("""SELECT exercises_json FROM recovery_routines WHERE issue_id = ? AND status = 'current'
            ORDER BY id DESC LIMIT 1""", (item["id"],)).fetchone()
        plan = json.loads(plan[0]) if plan else {}
        summaries.append({"issue_id": item["id"], "title": item["title"], "body_area": item["body_area"], "side": item["side"],
                          "started_on": item["started_on"], "current_pain": _current_pain(conn, item["id"]),
                          "avoid": plan.get("avoid", []) if isinstance(plan, dict) else [],
                          "see_professional": bool(item["see_professional"])})
    return {"issues": summaries, "instruction": "Athlete-reported injuries and soreness, not diagnoses. Keep planned sessions from aggravating them; any plan changes require athlete approval."}
