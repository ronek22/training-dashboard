import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from fastapi import HTTPException

from backend.app import db
from backend.app.services import coach_chat_relay
from backend.app.services.notes import create_chat_conversation_data, list_chat_messages_data, open_context_conversation_data

JOB = "b" * 32


class FakeHelper(BaseHTTPRequestHandler):
    received: list = []
    status = "running"
    created_at = None

    def log_message(self, *args):
        pass

    def send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def job(self):
        created = FakeHelper.created_at or datetime.now(timezone.utc).isoformat()
        summary = "Easy spin today, legs need it." if FakeHelper.status == "succeeded" else ""
        return {"job_id": JOB, "kind": "coach_chat", "status": FakeHelper.status, "message": "x", "summary": summary, "created_at": created}

    def do_POST(self):
        FakeHelper.received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send(202, self.job())

    def do_GET(self):
        if self.path != f"/coach-chat/{JOB}":
            self.send(404, {"detail": "Coach chat job not found"})
            return
        self.send(200, self.job())


class CoachChatRelayTests(unittest.TestCase):
    def setUp(self):
        FakeHelper.received, FakeHelper.status, FakeHelper.created_at = [], "running", None
        coach_chat_relay._TURNS.clear()
        self.server = HTTPServer(("127.0.0.1", 0), FakeHelper)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        env = mock.patch.dict(os.environ, {"COACH_HELPER_URL": f"http://127.0.0.1:{self.server.server_port}"})
        env.start()
        self.addCleanup(env.stop)
        # The watcher thread would race the test's own polling.
        watcher = mock.patch.object(coach_chat_relay, "_watch")
        watcher.start()
        self.addCleanup(watcher.stop)

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp_dir.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db(snapshot=False)
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)

    def messages(self, conversation_id):
        return [(m["role"], m["content"]) for m in list_chat_messages_data(self.conn, conversation_id)]

    def test_turn_sends_history_and_context_then_saves_reply_once(self):
        conversation = open_context_conversation_data(self.conn, "day", "2026-10-30", "Today", "How are the legs?")
        job = coach_chat_relay.start_reply(self.conn, conversation["id"], "  Heavy. Swap the intervals?  ")

        self.assertEqual(job["status"], "running")
        self.assertEqual(FakeHelper.received, [{
            "message": "Heavy. Swap the intervals?",
            "history": [{"role": "assistant", "content": "How are the legs?"}],
            "context": {"kind": "day", "id": "2026-10-30"},
        }])
        self.assertIsNone(coach_chat_relay.get_reply(JOB)["reply_id"])

        FakeHelper.status = "succeeded"
        first = coach_chat_relay.get_reply(JOB)["reply_id"]
        self.assertEqual(coach_chat_relay.get_reply(JOB)["reply_id"], first)
        self.assertEqual(self.messages(conversation["id"]), [
            ("assistant", "How are the legs?"),
            ("user", "Heavy. Swap the intervals?"),
            ("assistant", "Easy spin today, legs need it."),
        ])

    def test_general_chat_has_no_context(self):
        conversation = create_chat_conversation_data(self.conn)
        coach_chat_relay.start_reply(self.conn, conversation["id"], "Hi")
        self.assertNotIn("context", FakeHelper.received[0])

    def test_busy_helper_is_409_and_saves_nothing(self):
        conversation = create_chat_conversation_data(self.conn)
        FakeHelper.created_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        with self.assertRaises(HTTPException) as caught:
            coach_chat_relay.start_reply(self.conn, conversation["id"], "Hi")
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.messages(conversation["id"]), [])

    def test_helper_down_is_503_and_saves_nothing(self):
        conversation = create_chat_conversation_data(self.conn)
        with mock.patch.dict(os.environ, {"COACH_HELPER_URL": "http://127.0.0.1:9"}):
            with self.assertRaises(HTTPException) as caught:
                coach_chat_relay.start_reply(self.conn, conversation["id"], "Hi")
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(self.messages(conversation["id"]), [])

    def test_unknown_job_is_404(self):
        for job_id in ("../health", "c" * 32):
            with self.assertRaises(HTTPException) as caught:
                coach_chat_relay.get_reply(job_id)
            self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
