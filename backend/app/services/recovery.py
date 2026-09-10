import json
import uuid
from datetime import date

from ..models.recovery import Intake
from ..repositories import recovery as repo
from .recovery_library import reviewed_library, matches_location


QUESTIONS = {
    "location": "Where do you feel the symptoms, and on which side?",
    "onset": "When did this start, and was there a particular movement or injury?",
    "severity": "How strong are the symptoms from 0 (none) to 10 (worst imaginable)?",
    "trend": "Are symptoms improving, unchanged, or worsening?",
    "function": "Can you walk and use the affected area normally?",
    "emergency_signs": "Any deformity or a numb/cold injured limb; or back pain with new bladder/bowel changes, numbness around the genitals, or symptoms in both legs?",
    "urgent_signs": "Any severe or rapidly worsening pain, major swelling/bruising, or fever/feeling unwell with the symptoms?",
    "injury_or_surgery": "Is this related to an injury, a diagnosed condition, or recent surgery?",
    "persistent_symptoms": "Have the symptoms persisted or returned despite trying to manage them?",
    "general_soreness": "Does this feel like your usual muscle soreness following training?",
    "clinician_guidance": "Has a clinician given you instructions or training restrictions for this issue?",
}
PRIORITY = {"none": 0, "assessment": 1, "urgent": 2, "emergency": 3}
CARE = {
    "emergency": ("Get emergency help", "Contact local emergency services or an emergency department now. Do not wait for an AI reply or try a recovery routine."),
    "urgent": ("Seek urgent assessment", "Arrange urgent medical assessment for these symptoms. Exercise suggestions are paused; do not wait for this chat to decide whether to seek care."),
    "assessment": ("Professional assessment recommended", "A clinician or physiotherapist should assess this issue before a recovery routine is suggested. Keep any existing clinician instructions and training restrictions."),
    "incomplete": ("Complete your symptom check", "Confirm the missing or updated symptom details below. Unanswered questions stay unknown."),
    "review_required": ("Exercise suggestions unavailable", "You can track symptoms and discuss them here. Exercise suggestions are unavailable because the exercise catalogue is unavailable."),
    "unsupported": ("No matching routine available", "The source-backed library does not cover this location. Track the issue here and ask a clinician or physiotherapist about suitable exercises."),
    "eligible": ("Ready to review a routine", "You can request a general soreness or mobility routine from the source-backed library. This symptom check is not a diagnosis or clearance to exercise."),
}


def screening(issue):
    intake = Intake.model_validate_json(issue["intake_json"])
    concern = issue["concern"]
    if intake.emergency_signs is True:
        concern = "emergency"
    elif intake.urgent_signs is True or intake.function == "unable":
        concern = max((concern, "urgent"), key=PRIORITY.get)
    elif (intake.injury_or_surgery is True or intake.persistent_symptoms is True
          or intake.trend == "worsening" or intake.function == "limited"
          or intake.general_soreness is False or intake.clinician_guidance.strip()
          or (intake.severity is not None and intake.severity > 3)):
        concern = max((concern, "assessment"), key=PRIORITY.get)
    missing = []
    for key in QUESTIONS:
        if key == "clinician_guidance":
            continue
        value = getattr(intake, key)
        if value is None or value == "" or value == "unknown":
            missing.append(key)
    if intake.side == "unknown" and "location" not in missing:
        missing.append("location")
    library = reviewed_library()
    matching = [entry for entry in library if matches_location(entry, intake.location)]
    state = concern if concern != "none" else (
        "incomplete" if missing or issue["needs_review"] else
        "review_required" if not library else "eligible" if matching else "unsupported"
    )
    title, message = CARE[state]
    return {"state": state, "title": title, "message": message, "missing": missing,
            "can_generate": state == "eligible" and issue["status"] == "active"}


def get_issue(conn, issue_id):
    issue = repo.issue_row(conn, issue_id)
    conn.execute("""UPDATE recovery_requests SET status = 'failed'
        WHERE issue_id = ? AND status = 'pending' AND created_at < datetime('now', '-17 minutes')""", (issue_id,))
    issue["screening"] = screening(issue)
    issue["intake"] = Intake.model_validate_json(issue.pop("intake_json")).model_dump(mode="json")
    proposal = json.loads(issue.pop("proposed_intake_json") or "null")
    issue["proposal"] = proposal if proposal and proposal["revision"] == issue["revision"] else None
    issue["next_action"] = next_action(issue)
    issue.update(repo.children(conn, issue_id))
    current = {entry["id"]: entry for entry in reviewed_library()}
    for routine in issue["routines"]:
        routine["usable"] = (routine["status"] == "saved" and issue["screening"]["can_generate"]
                             and routine["revision"] == issue["revision"]
                             and all(entry["id"] in current and current[entry["id"]]["version"] == entry["version"]
                                     for entry in routine["exercises"]))
    return issue


def next_action(issue):
    state = issue["screening"]["state"]
    if issue["status"] == "archived":
        return {"title": "This issue is archived", "description": "Reopen it to continue the conversation or log a check-in.", "target": None, "label": None}
    if state in {"urgent", "emergency"}:
        return {"title": issue["screening"]["title"], "description": issue["screening"]["message"], "target": None, "label": None}
    if issue["proposal"]:
        return {"title": "Review the details from your conversation", "description": "Your answers are filled in below. Correct anything that looks wrong, then confirm. Unanswered questions remain unknown.", "target": "symptom-summary", "label": "Review & confirm summary"}
    if not issue["needs_review"] and state == "assessment":
        return {"title": "Arrange a professional assessment", "description": "Your summary is saved. This issue has an assessment recommendation, so the app will not suggest an exercise routine. You can review training restrictions and record follow-up symptoms while arranging care.", "target": "training-options", "label": "Review training options"}
    if not issue["needs_review"] and issue["screening"]["missing"]:
        return {"title": "Answer the remaining symptom questions", "description": "Your summary is saved; it does not need to be entered again. The unanswered questions below are still needed before the app can finish the symptom check.", "target": "remaining-questions", "label": "See unanswered questions"}
    if issue["needs_review"]:
        return {"title": "Confirm what we know and answer the gaps", "description": "Continue chatting to prepare a summary, or complete the missing details in the symptom check. You can confirm a partial summary.", "target": "symptom-summary", "label": "Review symptom details"}
    if state == "eligible":
        return {"title": "Review a recovery routine", "description": "Your starter exercises are ready below. Review the instructions, then save your routine. You can also ask AI for an alternative.", "target": "recovery-routines", "label": "See my exercises"}
    return {"title": "Track how symptoms change", "description": issue["screening"]["message"] + " Use a follow-up check-in to record changes; confirming a summary does not unlock unavailable exercises.", "target": "recovery-checkins", "label": "Log a follow-up"}


def list_issues(conn):
    results = []
    for row in conn.execute("SELECT * FROM recovery_issues ORDER BY updated_at DESC, id DESC"):
        item = dict(row)
        item.pop("proposed_intake_json", None)
        item["screening"] = screening(item)
        intake = Intake.model_validate_json(item.pop("intake_json"))
        item["location"] = intake.location
        item["severity"] = intake.severity
        results.append(item)
    return results


def active_issue(conn, issue_id):
    issue = repo.issue_row(conn, issue_id)
    if issue["status"] != "active":
        raise ValueError("Reopen this issue before adding new information.")
    return issue


def coaching_summary(conn):
    summaries = []
    for row in conn.execute("SELECT * FROM recovery_issues WHERE status = 'active' AND share_coaching = 1 ORDER BY updated_at DESC, id DESC LIMIT 8"):
        item = dict(row)
        intake = Intake.model_validate_json(item["intake_json"])
        summaries.append({"issue_id": item["id"], "location": intake.location, "side": intake.side,
                          "severity": intake.severity, "trend": intake.trend, "function": intake.function,
                          "screening_state": screening(item)["state"], "needs_review": bool(item["needs_review"]),
                          "updated_at": item["updated_at"]})
    return {"issues": summaries, "instruction": "Athlete-shared symptom reports, not diagnoses or clearance. Respect existing restrictions; any plan changes require athlete approval. No symptom transcript is included."}


def training_context(conn):
    from .dashboard import build_recent_context
    context = build_recent_context(conn, recent_activity_limit=8, recent_note_limit=1)
    return {key: context.get(key) for key in (
        "readiness", "modality_restrictions", "recent_activities", "active_plan",
    )}


def invalidate(conn, issue_id):
    conn.execute("UPDATE recovery_requests SET status = 'stale' WHERE issue_id = ? AND status = 'pending'", (issue_id,))
    conn.execute("UPDATE recovery_routines SET status = 'stale' WHERE issue_id = ? AND status = 'draft'", (issue_id,))
    conn.execute("UPDATE recovery_routines SET status = 'paused' WHERE issue_id = ? AND status = 'saved'", (issue_id,))


def save_intake(conn, issue_id, payload):
    issue = active_issue(conn, issue_id)
    if issue["revision"] != payload.revision:
        raise ValueError("Symptoms changed in another session. Reload before saving.")
    if payload.intake.onset_date and payload.intake.onset_date > date.today():
        raise ValueError("Symptom onset cannot be in the future.")
    if payload.reassess_assessment and issue["concern"] == "assessment":
        # Only an explicit athlete review may supersede an earlier non-urgent AI concern.
        candidate = {**issue, "concern": "none", "needs_review": 0,
                     "intake_json": payload.intake.model_dump_json()}
        if screening(candidate)["can_generate"]:
            conn.execute("UPDATE recovery_issues SET concern = 'none' WHERE id = ?", (issue_id,))
    invalidate(conn, issue_id)
    conn.execute("""UPDATE recovery_issues SET intake_json = ?, revision = revision + 1,
        needs_review = 0, proposed_intake_json = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (payload.intake.model_dump_json(), issue_id))
    ensure_starter_routine(conn, issue_id)
    return get_issue(conn, issue_id)


def ensure_starter_routine(conn, issue_id):
    issue = repo.issue_row(conn, issue_id)
    if not screening(issue)["can_generate"]:
        return
    if conn.execute("SELECT 1 FROM recovery_routines WHERE issue_id = ? AND revision = ? AND status IN ('draft', 'saved')", (issue_id, issue["revision"])).fetchone():
        return
    location = json.loads(issue["intake_json"])["location"]
    entries = [{**entry, "repetitions": entry["repetitions_min"], "sets": entry["sets_min"]}
               for entry in reviewed_library() if matches_location(entry, location)][:2]
    conn.execute("INSERT INTO recovery_routines (issue_id, revision, exercises_json) VALUES (?, ?, ?)",
                 (issue_id, issue["revision"], json.dumps(entries)))


def new_request(conn, issue_id, kind, consent):
    issue = active_issue(conn, issue_id)
    if not consent:
        raise ValueError("Confirm AI data sharing before requesting a reply.")
    if kind == "routine" and not screening(issue)["can_generate"]:
        raise ValueError(screening(issue)["message"])
    if kind == "chat" and not conn.execute(
        "SELECT 1 FROM recovery_messages WHERE issue_id = ? AND role = 'user'", (issue_id,)
    ).fetchone():
        raise ValueError("Write a message first.")
    conn.execute("UPDATE recovery_requests SET status = 'stale' WHERE issue_id = ? AND status = 'pending'", (issue_id,))
    request_id = uuid.uuid4().hex
    conn.execute("INSERT INTO recovery_requests (id, issue_id, revision, kind) VALUES (?, ?, ?, ?)",
                 (request_id, issue_id, issue["revision"], kind))
    return {"request_id": request_id, "issue_id": issue_id}


def add_message(conn, issue_id, payload):
    active_issue(conn, issue_id)
    # Store the athlete's text even when they choose not to share it with AI.
    invalidate(conn, issue_id)
    conn.execute("INSERT INTO recovery_messages (issue_id, role, content) VALUES (?, 'user', ?)", (issue_id, payload.content))
    conn.execute("""UPDATE recovery_issues SET revision = revision + 1, needs_review = 1,
        updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (issue_id,))
    return new_request(conn, issue_id, "chat", True) if payload.ai_consent else {"issue_id": issue_id, "request_id": None}


def request_row(conn, issue_id, request_id):
    issue = active_issue(conn, issue_id)
    row = conn.execute("SELECT * FROM recovery_requests WHERE id = ? AND issue_id = ?", (request_id, issue_id)).fetchone()
    if row is None:
        raise LookupError("Recovery request not found.")
    request = dict(row)
    if request["status"] != "pending" or request["revision"] != issue["revision"]:
        raise ValueError("This reply is no longer current. Request a new reply.")
    return issue, request


def ai_context(conn, issue_id, request_id):
    issue, request = request_row(conn, issue_id, request_id)
    rows = conn.execute("""SELECT role, content FROM recovery_messages WHERE issue_id = ?
        ORDER BY id DESC LIMIT 20""", (issue_id,)).fetchall()
    # Explicit context allowlist: no unrelated coach notes or symptom transcripts.
    checkins = [dict(row) for row in conn.execute("""SELECT severity, trend, function, note, created_at
        FROM recovery_checkins WHERE issue_id = ? ORDER BY id DESC LIMIT 5""", (issue_id,))]
    return {"kind": request["kind"], "issue_title": issue["title"], "intake": json.loads(issue["intake_json"]),
            "previous_proposal": json.loads(issue["proposed_intake_json"] or "null"),
            "today": date.today().isoformat(),
            "screening": screening(issue), "history": [dict(row) for row in reversed(rows)],
            "recent_checkins": checkins,
            "questions": QUESTIONS, "training_context": training_context(conn),
            "exercises": [entry for entry in reviewed_library() if matches_location(entry, json.loads(issue["intake_json"]).get("location", ""))] if request["kind"] == "routine" else []}


def finish_request(conn, issue_id, request_id, result):
    issue, request = request_row(conn, issue_id, request_id)
    if any(key not in QUESTIONS for key in result.question_ids):
        raise ValueError("The AI returned an unsupported question.")
    if result.exercises and request["kind"] != "routine":
        raise ValueError("Exercise suggestions require a separate routine request.")
    draft = None
    if result.proposed_intake is not None and request["kind"] == "chat":
        values = result.proposed_intake.model_dump(mode="json", exclude_unset=True)
        if result.proposed_intake.onset_date and result.proposed_intake.onset_date > date.today():
            raise ValueError("The proposed onset date is in the future.")
        if set(values) != set(result.intake_evidence):
            raise ValueError("Every proposed symptom field requires an athlete quote.")
        reports = [row[0] for row in conn.execute("SELECT content FROM recovery_messages WHERE issue_id = ? AND role = 'user'", (issue_id,))]
        for key, quote in result.intake_evidence.items():
            if not quote.strip() or len(quote) > 1000 or not any(quote in report for report in reports):
                raise ValueError("Symptom proposals must be grounded in the athlete's messages.")
        if values:
            draft = {"revision": issue["revision"], "values": values, "evidence": result.intake_evidence}
    concern = max((issue["concern"], result.concern), key=PRIORITY.get)
    proposed = {**issue, "concern": concern}
    entries = []
    if result.exercises and concern == "none":
        if not screening(proposed)["can_generate"]:
            raise ValueError("Exercise suggestions are unavailable for this symptom check.")
        library = {entry["id"]: entry for entry in reviewed_library()}
        seen = set()
        for selection in result.exercises:
            entry = library.get(selection.exercise_id)
            intake = json.loads(issue["intake_json"])
            if (not entry or entry["id"] in seen or not matches_location(entry, intake.get("location", ""))
                or not entry["repetitions_min"] <= selection.repetitions <= entry["repetitions_max"]
                or not entry["sets_min"] <= selection.sets <= entry["sets_max"]):
                raise ValueError("The AI returned an ineligible exercise or prescription.")
            seen.add(entry["id"])
            entries.append({**entry, "repetitions": selection.repetitions, "sets": selection.sets})
    if request["kind"] == "routine" and not entries and concern == "none":
        raise ValueError("No eligible routine was returned. Your issue has been preserved.")
    conn.execute("UPDATE recovery_issues SET concern = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (concern, issue_id))
    if draft:
        conn.execute("UPDATE recovery_issues SET proposed_intake_json = ?, needs_review = 1 WHERE id = ?", (json.dumps(draft), issue_id))
    if concern != "none":
        invalidate(conn, issue_id)
    # AI summary is clearly attributed and never used as confirmed intake or a prescription.
    content = result.summary
    if result.question_ids:
        content += "\n\n" + "\n".join(QUESTIONS[key] for key in dict.fromkeys(result.question_ids))
    conn.execute("INSERT INTO recovery_messages (issue_id, role, content) VALUES (?, 'assistant', ?)", (issue_id, content))
    if entries:
        conn.execute("UPDATE recovery_routines SET status = 'stale' WHERE issue_id = ? AND status = 'draft'", (issue_id,))
        conn.execute("INSERT INTO recovery_routines (issue_id, revision, exercises_json) VALUES (?, ?, ?)",
                     (issue_id, issue["revision"], json.dumps(entries)))
    conn.execute("UPDATE recovery_requests SET status = 'succeeded' WHERE id = ?", (request_id,))
    return {"status": "succeeded"}


def save_routine(conn, issue_id, routine_id, revision):
    issue = active_issue(conn, issue_id)
    routine = conn.execute("SELECT * FROM recovery_routines WHERE id = ? AND issue_id = ?", (routine_id, issue_id)).fetchone()
    if routine is None:
        raise LookupError("Routine not found.")
    if (routine["status"] != "draft" or routine["revision"] != revision or issue["revision"] != revision
        or not screening(issue)["can_generate"]):
        raise ValueError("This routine needs reassessment before it can be saved.")
    current = {entry["id"]: entry for entry in reviewed_library()}
    if any(entry["id"] not in current or current[entry["id"]]["version"] != entry["version"]
           for entry in json.loads(routine["exercises_json"])):
        raise ValueError("The exercise library changed. Request a new routine.")
    conn.execute("UPDATE recovery_routines SET status = 'saved' WHERE id = ?", (routine_id,))
    return get_issue(conn, issue_id)


def add_checkin(conn, issue_id, payload):
    issue = active_issue(conn, issue_id)
    if payload.completed and payload.routine_id is None:
        raise ValueError("Choose the saved routine you completed.")
    if payload.routine_id is not None:
        routine = conn.execute("SELECT * FROM recovery_routines WHERE id = ? AND issue_id = ?", (payload.routine_id, issue_id)).fetchone()
        if routine is None or routine["status"] not in {"saved", "paused"}:
            raise ValueError("Choose a previously saved routine from this issue.")
    conn.execute("""INSERT INTO recovery_checkins
        (issue_id, routine_id, severity, before_severity, trend, function, completed, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (issue_id, payload.routine_id, payload.severity,
        payload.before_severity, payload.trend, payload.function, payload.completed, payload.note))
    intake = Intake.model_validate_json(issue["intake_json"])
    increased = intake.severity is not None and payload.severity > intake.severity
    if payload.before_severity is not None:
        increased = increased or payload.severity > payload.before_severity
    intake.severity, intake.trend, intake.function = payload.severity, payload.trend, payload.function
    concern = issue["concern"]
    if payload.function == "unable":
        concern = max((concern, "urgent"), key=PRIORITY.get)
    elif increased or payload.trend == "worsening" or payload.function == "limited":
        concern = max((concern, "assessment"), key=PRIORITY.get)
    invalidate(conn, issue_id)
    conn.execute("""UPDATE recovery_issues SET intake_json = ?, concern = ?, needs_review = 1,
        revision = revision + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (intake.model_dump_json(), concern, issue_id))
    return get_issue(conn, issue_id)
