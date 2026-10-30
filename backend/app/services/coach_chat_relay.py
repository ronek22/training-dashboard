"""Relays coach chat turns to the coach helper for the iOS app.

The web page talks to the helper (scripts/coach_helper.py) on the Mac's 127.0.0.1 and saves both
sides of the chat itself. The phone can't reach the helper, so the backend does the whole turn:
it forwards the message with the conversation's history and context, saves the athlete's message,
and saves the coach's reply into the same conversation when the helper finishes. A watcher thread
saves the reply even when the phone has left the chat; polling saves it too, whichever comes first.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .. import db
from ..repositories.notes import get_chat_conversation_row, list_chat_message_rows
from . import meal_estimate_relay
from .notes import create_chat_message_data

HISTORY_LIMIT = 30
POLL_SECONDS = 3
WATCH_SECONDS = 16 * 60
BUSY = "The coach is still answering another chat. Try again in a minute."

# job_id -> {"conversation_id", "reply_id"}; the helper's jobs live in memory too.
_TURNS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _history(conn, conversation_id: int) -> list[dict]:
    rows = list_chat_message_rows(conn, conversation_id, limit=HISTORY_LIMIT)
    return [
        {"role": row["role"], "content": row["content"].strip()[:6000]}
        for row in rows
        if row["role"] in {"user", "assistant"} and row["content"].strip()
    ]


def _started_earlier(job: dict, sent_at: datetime) -> bool:
    try:
        created = datetime.fromisoformat(job.get("created_at") or "")
    except ValueError:
        return False
    return created < sent_at - timedelta(seconds=5)


def start_reply(conn, conversation_id: int, message: str) -> dict:
    """Send the athlete's message to the coach; the reply is saved when it's ready."""
    text = str(message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Write a message first.")
    if len(text) > 4000:
        raise HTTPException(status_code=400, detail="That message is too long.")
    conversation = get_chat_conversation_row(conn, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    body = {"message": text, "history": _history(conn, conversation_id)}
    if conversation["context_kind"]:
        body["context"] = {"kind": conversation["context_kind"], "id": conversation["context_id"]}
    sent_at = datetime.now(timezone.utc)
    job = meal_estimate_relay._call("/coach-chat", body, timeout=30)
    job_id = job.get("job_id") or ""
    with _LOCK:
        # The helper runs one chat at a time and hands back the running one instead.
        taken = job_id in _TURNS and _TURNS[job_id]["conversation_id"] != conversation_id
    if taken or _started_earlier(job, sent_at):
        raise HTTPException(status_code=409, detail=BUSY)

    saved = create_chat_message_data(conn, conversation_id, "user", text)
    with _LOCK:
        _TURNS[job_id] = {"conversation_id": conversation_id, "reply_id": None}
    threading.Thread(target=_watch, args=(job_id,), daemon=True).start()
    return {**_public(job), "message_id": saved["id"]}


def get_reply(job_id: str) -> dict:
    if not meal_estimate_relay.JOB_ID.match(job_id):
        raise HTTPException(status_code=404, detail="Coach chat job not found")
    with _LOCK:
        known = job_id in _TURNS
    if not known:
        raise HTTPException(status_code=404, detail="Coach chat job not found")
    job = meal_estimate_relay._call(f"/coach-chat/{job_id}")
    reply_id = _save_reply(job_id, job)
    return {**_public(job), "reply_id": reply_id}


def _public(job: dict) -> dict:
    return {key: job.get(key) for key in ("job_id", "status", "message")}


def _save_reply(job_id: str, job: dict):
    """Save a finished reply once and return its message id."""
    with _LOCK:
        turn = _TURNS.get(job_id)
        if not turn or turn["reply_id"] is not None:
            return turn and turn["reply_id"]
        summary = str(job.get("summary") or "").strip()
        if job.get("status") != "succeeded" or not summary:
            return None
        conn = db.get_db()
        try:
            saved = create_chat_message_data(conn, turn["conversation_id"], "assistant", summary[:12000])
        except ValueError:
            # The conversation was deleted while the coach was thinking.
            saved = {"id": 0}
        finally:
            conn.close()
        turn["reply_id"] = saved["id"]
        return saved["id"]


def _watch(job_id: str) -> None:
    deadline = time.monotonic() + WATCH_SECONDS
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        try:
            job = meal_estimate_relay._call(f"/coach-chat/{job_id}")
        except HTTPException as exc:
            if exc.status_code == 404:
                return
            continue
        if job.get("status") in {"succeeded", "failed"}:
            _save_reply(job_id, job)
            return
