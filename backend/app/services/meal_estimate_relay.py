"""Relays meal-estimate jobs to the coach helper for the iOS app.

The helper (scripts/coach_helper.py) listens only on the Mac's 127.0.0.1, which the phone can't
reach, so the backend forwards the request. Nothing is saved here: the phone shows the items and
saves them through /nutrition/food/entries, like the web Food page.
"""

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

# Inside Docker the Mac's loopback is host.docker.internal.
DEFAULT_HELPER_URL = "http://host.docker.internal:8765"
JOB_ID = re.compile(r"^[0-9a-f]{32}$")
HELPER_DOWN = "The coach helper on the Mac isn't running. Start it with `just coach-helper-start`."


def helper_url() -> str:
    return os.getenv("COACH_HELPER_URL", DEFAULT_HELPER_URL).rstrip("/")


def _call(path: str, body: dict | None = None, timeout: float = 10) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(helper_url() + path, data=data, method="POST" if body is not None else "GET")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise HTTPException(status_code=exc.code, detail=detail or "The meal estimate failed.") from exc
    except (URLError, TimeoutError, ConnectionError) as exc:
        raise HTTPException(status_code=503, detail=HELPER_DOWN) from exc


def _public(job: dict) -> dict:
    keys = ("job_id", "status", "message", "estimate")
    return {key: job.get(key) for key in keys if key in job}


def start_estimate(payload: dict) -> dict:
    body = {"text": payload.get("text") or ""}
    if payload.get("image"):
        body["image"] = payload["image"]
    return _public(_call("/meal-estimate", body, timeout=30))


def get_estimate(job_id: str) -> dict:
    if not JOB_ID.match(job_id):
        raise HTTPException(status_code=404, detail="Meal estimate job not found")
    return _public(_call(f"/meal-estimate/{job_id}"))
