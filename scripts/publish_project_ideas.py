#!/usr/bin/env python3
"""Validate and append a daily review without replacing existing proposals."""
import argparse
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "project-ideas.json"


def validate(review):
    if not isinstance(review, dict):
        raise ValueError("Review must be an object")
    timestamp = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("reviewed_at requires a timezone")
    if not isinstance(review["summary"], str) or not 10 <= len(review["summary"]) <= 2000:
        raise ValueError("Summary must contain 10–2000 characters")
    if not isinstance(review["ideas"], list) or len(review["ideas"]) > 200:
        raise ValueError("Ideas must be a list of at most 200 proposals")
    ids, titles = set(), set()
    for idea in review["ideas"]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", idea["id"]):
            raise ValueError("Invalid idea ID")
        if idea["id"] in ids or idea["title"].casefold().strip() in titles:
            raise ValueError("Duplicate idea")
        ids.add(idea["id"]); titles.add(idea["title"].casefold().strip())
        for key, minimum, maximum in [("title", 3, 120), ("problem", 10, 2000), ("proposal", 10, 3000), ("benefit", 10, 1000)]:
            if not isinstance(idea[key], str) or not minimum <= len(idea[key]) <= maximum:
                raise ValueError(f"Invalid {key}")
        for key, allowed in [("category", {"Product", "Experience", "Reliability", "Engineering"}), ("effort", {"Small", "Medium", "Large"}), ("priority", {"High", "Medium", "Low"})]:
            if idea[key] not in allowed:
                raise ValueError(f"Invalid {key}")
        for key, minimum in [("evidence", 1), ("acceptance_criteria", 2)]:
            items = idea[key]
            if not isinstance(items, list) or not minimum <= len(items) <= 10 or any(not isinstance(item, str) or not item.strip() for item in items):
                raise ValueError(f"Invalid {key}")
        date.fromisoformat(idea["created_on"])
        if "status" in idea:
            raise ValueError("User decisions belong in the app, not generated proposals")


def publish(review, path=CATALOG):
    validate(review)
    path = Path(path)
    with path.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = json.loads(path.read_text()) if path.exists() else {"ideas": []}
        if existing.get("reviewed_at") and datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00")) < datetime.fromisoformat(existing["reviewed_at"].replace("Z", "+00:00")):
            raise ValueError("Cannot publish a review older than the current review")
        ids = {idea["id"] for idea in existing["ideas"]}
        titles = {idea["title"].casefold().strip() for idea in existing["ideas"]}
        additions = [idea for idea in review["ideas"] if idea["id"] not in ids and idea["title"].casefold().strip() not in titles]
        merged = {"reviewed_at": review["reviewed_at"], "summary": review["summary"], "ideas": existing["ideas"] + additions}
        validate(merged)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False) as handle:
                name = handle.name
                json.dump(merged, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush(); os.fsync(handle.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        return len(additions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    count = publish(json.loads(args.input.read_text()))
    print(f"Published review: {count} new ideas")
