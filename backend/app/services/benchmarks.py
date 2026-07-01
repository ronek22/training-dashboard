import json
import sqlite3
from typing import Optional


BENCHMARK_TAG_LABELS = {
    "benchmark": "Benchmark",
    "test": "Test",
    "rehearsal": "Rehearsal",
}

BENCHMARK_TAG_ALIASES = {
    "benchmark": "benchmark",
    "bench": "benchmark",
    "test": "test",
    "testing": "test",
    "time_trial": "test",
    "time-trial": "test",
    "tt": "test",
    "rehearsal": "rehearsal",
    "race_rehearsal": "rehearsal",
    "race-rehearsal": "rehearsal",
}


def normalize_benchmark_tag(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    return BENCHMARK_TAG_ALIASES.get(normalized)


def default_benchmark_label(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    return BENCHMARK_TAG_LABELS.get(tag, tag.replace("_", " ").title())


def normalize_benchmark_label(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_benchmark_fields(payload: dict) -> dict:
    normalized = dict(payload)
    tag = normalize_benchmark_tag(normalized.get("benchmark_tag"))
    label = normalize_benchmark_label(normalized.get("benchmark_label"))
    normalized["benchmark_tag"] = tag
    normalized["benchmark_label"] = label if tag else None
    if tag and not normalized["benchmark_label"]:
        normalized["benchmark_label"] = default_benchmark_label(tag)
    return normalized


def build_planned_session_id(week_start: str, day: dict, index: int) -> str:
    date_part = day.get("date") or f"idx-{index}"
    return f"plan-{week_start}-{date_part}-{index + 1}"


def ensure_benchmark_session_ids(week_start: str, days: list[dict]) -> list[dict]:
    normalized_days = []
    seen_ids: set[str] = set()
    for index, day in enumerate(days):
        normalized_day = normalize_benchmark_fields(day)
        session_id = normalized_day.get("session_id")
        if not session_id or session_id in seen_ids:
            session_id = build_planned_session_id(week_start, normalized_day, index)
        normalized_day["session_id"] = session_id
        seen_ids.add(session_id)
        normalized_days.append(normalized_day)
    return normalized_days


def build_benchmark_session_lookup(conn: sqlite3.Connection, limit: int = 400) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT week_start, days_json
        FROM weekly_plans
        ORDER BY week_start DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    lookup: dict[str, dict] = {}
    for row in rows:
        days = ensure_benchmark_session_ids(row["week_start"], json.loads(row["days_json"]))
        for day in days:
            if not day.get("benchmark_tag"):
                continue
            lookup[day["session_id"]] = {
                "benchmark_tag": day.get("benchmark_tag"),
                "benchmark_label": day.get("benchmark_label"),
                "planned_title": day.get("title"),
                "planned_date": day.get("date"),
                "planned_session_type": day.get("session_type"),
            }
    return lookup


def attach_benchmark_from_lookup(item: dict, lookup: dict[str, dict]) -> dict:
    normalized = normalize_benchmark_fields(item)
    if normalized.get("benchmark_tag"):
        return normalized
    linked_session_id = normalized.get("linked_planned_session_id")
    linked = lookup.get(linked_session_id) if linked_session_id else None
    if not linked:
        return normalized
    normalized["benchmark_tag"] = linked.get("benchmark_tag")
    normalized["benchmark_label"] = linked.get("benchmark_label")
    normalized["benchmark_source"] = "planned_session"
    return normalized
