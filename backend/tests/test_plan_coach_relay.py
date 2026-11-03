import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.routers.plans import router
from backend.app.services import plan_coach_relay

PLAN_JOB = "a" * 32
CHAT_JOB = "b" * 32


class FakeHelper(BaseHTTPRequestHandler):
    received: list = []

    def log_message(self, *args):
        pass

    def send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeHelper.received.append((self.path, payload))
        kind = "weekly_plan" if self.path == "/weekly-plan" else "weekly_plan_revision"
        self.send(202, {"job_id": PLAN_JOB, "kind": kind, "status": "queued", "message": "Weekly planning is queued.",
                        "week_start": payload["week_start"], "summary": "", "created_at": "2026-11-03T12:00:00+00:00"})

    def do_GET(self):
        if self.path == "/health":
            self.send(200, {"status": "ok"})
        elif self.path == f"/weekly-plan/{PLAN_JOB}":
            self.send(200, {"job_id": PLAN_JOB, "kind": "weekly_plan", "status": "succeeded", "message": "The weekly plan was saved.",
                            "week_start": "2026-11-09", "summary": "Three lifts and two rides."})
        elif self.path == f"/weekly-plan/{CHAT_JOB}":
            self.send(200, {"job_id": CHAT_JOB, "kind": "coach_chat", "status": "running", "message": "Coach chat is queued."})
        else:
            self.send(404, {"detail": "Planning job not found"})


class PlanCoachRelayTests(unittest.TestCase):
    def setUp(self):
        FakeHelper.received = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeHelper)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        env = mock.patch.dict(os.environ, {"COACH_HELPER_URL": f"http://127.0.0.1:{self.server.server_port}/"})
        env.start()
        self.addCleanup(env.stop)

    def test_plan_forwards_week_and_brief(self):
        job = plan_coach_relay.start_plan("2026-11-09", "  Long ride Saturday  ")
        self.assertEqual(FakeHelper.received, [("/weekly-plan", {"week_start": "2026-11-09", "planning_brief": "Long ride Saturday"})])
        self.assertEqual((job["job_id"], job["kind"], job["status"]), (PLAN_JOB, "weekly_plan", "queued"))

    def test_revision_forwards_target_date_only_when_given(self):
        plan_coach_relay.start_revision("2026-11-02", "Lighter weekend")
        plan_coach_relay.start_revision("2026-11-02", "Shorter", "2026-11-06")
        self.assertEqual(FakeHelper.received, [
            ("/weekly-plan-revision", {"week_start": "2026-11-02", "feedback": "Lighter weekend"}),
            ("/weekly-plan-revision", {"week_start": "2026-11-02", "feedback": "Shorter", "target_date": "2026-11-06"}),
        ])

    def test_revision_needs_feedback(self):
        with self.assertRaises(HTTPException) as caught:
            plan_coach_relay.start_revision("2026-11-02", "   ")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(FakeHelper.received, [])

    def test_poll_returns_summary_and_hides_other_jobs(self):
        job = plan_coach_relay.get_job(PLAN_JOB)
        self.assertEqual((job["status"], job["summary"]), ("succeeded", "Three lifts and two rides."))
        for job_id in (CHAT_JOB, "../health"):
            with self.assertRaises(HTTPException) as caught:
                plan_coach_relay.get_job(job_id)
            self.assertEqual(caught.exception.status_code, 404)

    def test_status_reports_helper(self):
        self.assertEqual(plan_coach_relay.status(), {"available": True, "detail": None})
        with mock.patch.dict(os.environ, {"COACH_HELPER_URL": "http://127.0.0.1:9"}):
            self.assertFalse(plan_coach_relay.status()["available"])
            with self.assertRaises(HTTPException) as caught:
                plan_coach_relay.start_plan("2026-11-09")
            self.assertEqual(caught.exception.status_code, 503)

    def test_routes(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        self.assertEqual(client.get("/plans/weekly/coach/status").json()["available"], True)
        started = client.post("/plans/weekly/coach", json={"week_start": "2026-11-09"})
        self.assertEqual(started.status_code, 202)
        revised = client.post("/plans/weekly/coach/revise", json={"week_start": "2026-11-02", "feedback": "Less", "target_date": "2026-11-06"})
        self.assertEqual(revised.json()["kind"], "weekly_plan_revision")
        self.assertEqual(client.get(f"/plans/weekly/coach/{PLAN_JOB}").json()["week_start"], "2026-11-09")
        self.assertEqual(client.post("/plans/weekly/coach", json={"week_start": "next"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
