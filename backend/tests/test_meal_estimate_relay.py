import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from fastapi import HTTPException

from backend.app.services import meal_estimate_relay

JOB = "a" * 32


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
        FakeHelper.received.append(payload)
        if not payload.get("text") and not payload.get("image"):
            self.send(400, {"detail": "Describe the meal or add a photo"})
            return
        self.send(202, {"job_id": JOB, "kind": "meal_estimate", "status": "queued", "message": "Queued.", "created_at": "x"})

    def do_GET(self):
        if self.path != f"/meal-estimate/{JOB}":
            self.send(404, {"detail": "Meal estimate job not found"})
            return
        self.send(200, {
            "job_id": JOB, "status": "succeeded", "message": "Ready.",
            "estimate": {"items": [{"name": "Ryż", "grams": 200, "kcal": 260, "protein_g": 5, "carbs_g": 56, "fat_g": 1, "confidence": "medium"}], "note": ""},
        })


class MealEstimateRelayTests(unittest.TestCase):
    def setUp(self):
        FakeHelper.received = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeHelper)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        env = mock.patch.dict(os.environ, {"COACH_HELPER_URL": f"http://127.0.0.1:{self.server.server_port}/"})
        env.start()
        self.addCleanup(env.stop)

    def test_start_forwards_text_and_photo(self):
        job = meal_estimate_relay.start_estimate({"text": "obiad", "image": {"media_type": "image/jpeg", "data": "AAAA"}})
        self.assertEqual(job, {"job_id": JOB, "status": "queued", "message": "Queued."})
        self.assertEqual(FakeHelper.received, [{"text": "obiad", "image": {"media_type": "image/jpeg", "data": "AAAA"}}])

    def test_poll_returns_estimate(self):
        job = meal_estimate_relay.get_estimate(JOB)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["estimate"]["items"][0]["kcal"], 260)

    def test_helper_errors_pass_through(self):
        with self.assertRaises(HTTPException) as caught:
            meal_estimate_relay.start_estimate({"text": ""})
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (400, "Describe the meal or add a photo"))
        with self.assertRaises(HTTPException) as caught:
            meal_estimate_relay.get_estimate("../health")
        self.assertEqual(caught.exception.status_code, 404)

    def test_helper_down_is_503(self):
        with mock.patch.dict(os.environ, {"COACH_HELPER_URL": "http://127.0.0.1:9"}):
            with self.assertRaises(HTTPException) as caught:
                meal_estimate_relay.get_estimate(JOB)
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
