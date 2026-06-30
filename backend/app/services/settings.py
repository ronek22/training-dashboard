import json
import sqlite3
from typing import Optional

from ..db import get_db
from ..repositories.settings import get_setting_value, set_setting_value

MODALITY_RESTRICTIONS_KEY = "modality_restrictions"
ATHLETE_PROFILE_KEY = "athlete_profile"
MODALITY_LABELS = {
    "run": "Running",
    "ride": "Riding",
    "strength": "Strength",
}
RESTRICTION_STATUSES = {"allowed", "limited", "blocked"}
ATHLETE_FOCUS_LABELS = {
    "endurance": "Endurance",
    "hybrid": "Hybrid",
    "strength": "Strength",
    "general_fitness": "General fitness",
}
WEEKDAY_LABELS = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}


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


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def normalize_modality(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("modality") or value.get("label")
    if value is None:
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


def normalize_weekday(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("day") or value.get("label")
    if value is None:
        return None
    normalized = value.strip().lower()[:3]
    return normalized if normalized in WEEKDAY_LABELS else None


def _format_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def default_athlete_profile() -> dict:
    return normalize_athlete_profile({})


def build_athlete_brief(profile: dict) -> dict:
    focus_label = profile["focus"]["label"]
    modality_labels = [item["label"] for item in profile.get("modality_preferences", [])]
    long_day_labels = [item["label"] for item in profile.get("preferred_long_session_days", [])]
    current_block = profile.get("current_block")
    availability_notes = profile.get("weekly_availability_notes")
    planning_notes = profile.get("planning_notes")

    if modality_labels:
        headline = f"{focus_label} athlete prioritizing {_format_list(modality_labels).lower()}."
    else:
        headline = f"{focus_label} athlete profile is active."

    coaching_summary_parts = [headline]
    if current_block:
        coaching_summary_parts.append(f"Current block: {current_block}.")
    if long_day_labels:
        coaching_summary_parts.append(f"Long sessions fit best on {_format_list(long_day_labels)}.")
    if availability_notes:
        coaching_summary_parts.append(f"Availability: {availability_notes}.")
    if planning_notes:
        coaching_summary_parts.append(f"Planning notes: {planning_notes}.")

    return {
        "headline": headline,
        "focus": {
            "value": profile["primary_focus"],
            "label": focus_label,
        },
        "current_block": current_block,
        "modality_priority": [item["value"] for item in profile.get("modality_preferences", [])],
        "modality_priority_labels": modality_labels,
        "preferred_long_session_days": [item["value"] for item in profile.get("preferred_long_session_days", [])],
        "preferred_long_session_day_labels": long_day_labels,
        "weekly_availability_notes": availability_notes,
        "planning_notes": planning_notes,
        "coaching_summary": " ".join(coaching_summary_parts),
    }


def normalize_athlete_profile(raw_value: Optional[dict]) -> dict:
    raw = raw_value if isinstance(raw_value, dict) else {}
    focus = _clean_text(raw.get("primary_focus")) or "general_fitness"
    if focus not in ATHLETE_FOCUS_LABELS:
        focus = "general_fitness"

    modality_preferences = []
    for item in raw.get("modality_preferences", []) if isinstance(raw.get("modality_preferences"), list) else []:
        normalized = normalize_modality(item)
        if normalized and normalized not in modality_preferences:
            modality_preferences.append(normalized)

    preferred_long_session_days = []
    for item in raw.get("preferred_long_session_days", []) if isinstance(raw.get("preferred_long_session_days"), list) else []:
        normalized = normalize_weekday(item)
        if normalized and normalized not in preferred_long_session_days:
            preferred_long_session_days.append(normalized)

    profile = {
        "primary_focus": focus,
        "focus": {
            "value": focus,
            "label": ATHLETE_FOCUS_LABELS[focus],
        },
        "modality_preferences": [
            {"value": item, "label": MODALITY_LABELS[item]}
            for item in modality_preferences
        ],
        "current_block": _clean_text(raw.get("current_block")),
        "preferred_long_session_days": [
            {"value": item, "label": WEEKDAY_LABELS[item]}
            for item in preferred_long_session_days
        ],
        "weekly_availability_notes": _clean_text(raw.get("weekly_availability_notes")),
        "planning_notes": _clean_text(raw.get("planning_notes")),
    }
    profile["athlete_brief"] = build_athlete_brief(profile)
    return profile


def serialize_athlete_profile_for_storage(profile: dict) -> dict:
    return {
        "primary_focus": profile.get("primary_focus"),
        "modality_preferences": [item.get("value") for item in profile.get("modality_preferences", []) if item.get("value")],
        "current_block": profile.get("current_block"),
        "preferred_long_session_days": [
            item.get("value") for item in profile.get("preferred_long_session_days", []) if item.get("value")
        ],
        "weekly_availability_notes": profile.get("weekly_availability_notes"),
        "planning_notes": profile.get("planning_notes"),
    }


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


def get_athlete_profile_for_conn(conn: sqlite3.Connection) -> dict:
    raw_value = get_setting_value(conn, ATHLETE_PROFILE_KEY)
    if not raw_value:
        return default_athlete_profile()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_athlete_profile()
    return normalize_athlete_profile(parsed)


def get_modality_restrictions_data() -> dict:
    conn = get_db()
    try:
        return get_modality_restrictions_for_conn(conn)
    finally:
        conn.close()


def get_athlete_profile_data() -> dict:
    conn = get_db()
    try:
        return get_athlete_profile_for_conn(conn)
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


def set_athlete_profile_data(payload: dict) -> dict:
    conn = get_db()
    try:
        normalized = normalize_athlete_profile(payload)
        set_setting_value(conn, ATHLETE_PROFILE_KEY, json.dumps(serialize_athlete_profile_for_storage(normalized)))
        conn.commit()
        return normalized
    finally:
        conn.close()
