import json
import sqlite3
from typing import Optional

from ..db import get_db
from ..repositories.settings import get_setting_value, set_setting_value

MODALITY_RESTRICTIONS_KEY = "modality_restrictions"
MODALITY_LABELS = {
    "run": "Running",
    "ride": "Riding",
    "strength": "Strength",
}
RESTRICTION_STATUSES = {"allowed", "limited", "blocked"}


def get_setting(key: str):
    conn = get_db()
    try:
        return get_setting_value(conn, key)
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_db()
    try:
        set_setting_value(conn, key, value)
        conn.commit()
    finally:
        conn.close()


def default_modality_restrictions() -> dict:
    modalities = {
        modality: {
            "modality": modality,
            "label": label,
            "status": "allowed",
            "reason": None,
            "note": None,
            "expected_end_date": None,
        }
        for modality, label in MODALITY_LABELS.items()
    }
    return {
        "modalities": modalities,
        "active": [],
        "summary": {
            "active_count": 0,
            "blocked_count": 0,
            "limited_count": 0,
            "headline": "All primary modalities are currently available.",
        },
    }


def normalize_modality(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    aliases = {
        "run": "run",
        "running": "run",
        "ride": "ride",
        "riding": "ride",
        "bike": "ride",
        "cycling": "ride",
        "strength": "strength",
        "weights": "strength",
        "weighttraining": "strength",
    }
    return aliases.get(normalized)


def modality_for_session_type(session_type: Optional[str]) -> Optional[str]:
    return normalize_modality(session_type)


def modality_for_goal(metric_type: Optional[str], activity_type: Optional[str] = None) -> Optional[str]:
    if metric_type == "run_km":
        return "run"
    if metric_type == "ride_km":
        return "ride"
    if metric_type == "strength_sessions":
        return "strength"
    if metric_type == "activities_count":
        return normalize_modality(activity_type)
    return None


def restriction_summary_text(restriction: dict) -> str:
    status = restriction.get("status")
    label = restriction.get("label", "This modality")
    reason = restriction.get("reason")
    expected_end_date = restriction.get("expected_end_date")
    if status == "blocked":
        summary = f"{label} is currently blocked."
    elif status == "limited":
        summary = f"{label} is currently limited."
    else:
        return f"{label} is currently available."
    if reason:
        summary = f"{summary} Reason: {reason}."
    if expected_end_date:
        summary = f"{summary} Expected through {expected_end_date}."
    return summary


def normalize_modality_restrictions(raw_value: Optional[dict]) -> dict:
    payload = default_modality_restrictions()
    source_modalities = (raw_value or {}).get("modalities", {}) if isinstance(raw_value, dict) else {}
    active = []

    for modality, base in payload["modalities"].items():
        incoming = source_modalities.get(modality, {}) if isinstance(source_modalities, dict) else {}
        status = incoming.get("status", "allowed")
        if status not in RESTRICTION_STATUSES:
            status = "allowed"
        normalized = {
            **base,
            "status": status,
            "reason": incoming.get("reason") or None,
            "note": incoming.get("note") or None,
            "expected_end_date": incoming.get("expected_end_date") or None,
        }
        payload["modalities"][modality] = normalized
        if status in {"limited", "blocked"}:
            active_item = {
                **normalized,
                "summary": restriction_summary_text(normalized),
            }
            active.append(active_item)

    blocked_count = sum(1 for item in active if item["status"] == "blocked")
    limited_count = sum(1 for item in active if item["status"] == "limited")
    if blocked_count:
        headline = f"{blocked_count} modality blocked."
        if blocked_count != 1:
            headline = f"{blocked_count} modalities blocked."
    elif limited_count:
        headline = f"{limited_count} modality limited."
        if limited_count != 1:
            headline = f"{limited_count} modalities limited."
    else:
        headline = "All primary modalities are currently available."

    payload["active"] = active
    payload["summary"] = {
        "active_count": len(active),
        "blocked_count": blocked_count,
        "limited_count": limited_count,
        "headline": headline,
    }
    return payload


def get_modality_restrictions_for_conn(conn: sqlite3.Connection) -> dict:
    raw_value = get_setting_value(conn, MODALITY_RESTRICTIONS_KEY)
    if not raw_value:
        return default_modality_restrictions()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_modality_restrictions()
    return normalize_modality_restrictions(parsed)


def get_modality_restrictions_data() -> dict:
    conn = get_db()
    try:
        return get_modality_restrictions_for_conn(conn)
    finally:
        conn.close()


def set_modality_restrictions_data(payload: dict) -> dict:
    conn = get_db()
    try:
        normalized = normalize_modality_restrictions(payload)
        set_setting_value(conn, MODALITY_RESTRICTIONS_KEY, json.dumps(normalized))
        conn.commit()
        return normalized
    finally:
        conn.close()
