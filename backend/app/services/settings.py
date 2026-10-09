import json
import re
import sqlite3
from typing import Optional

from datetime import date

from ..db import get_db
from ..repositories.settings import get_setting_value, set_setting_value
from .ftp import ftp_on, normalize_ftp_choice, stored_ftp, working_ftp
from .seasons import normalize_off_season_months, season_label

MODALITY_RESTRICTIONS_KEY = "modality_restrictions"
ATHLETE_PROFILE_KEY = "athlete_profile"
WORKOUT_TEMPLATE_SETTINGS_KEY = "workout_template_settings"
PERFORMANCE_SETTINGS_KEY = "performance_settings"
MODALITY_LABELS = {
    "run": "Running",
    "ride": "Riding",
    "strength": "Strength",
}
RESTRICTION_STATUSES = {"allowed", "limited", "blocked"}
# Protected body areas and the lifts that load them. The weekly lift top-up
# never adds or extends these while an area is protected.
BODY_AREAS = {
    "knee": {"label": "Knee", "avoid": r"\bsquats?\b|\blunges?\b|\bstep ?ups?\b|\bleg (?:extension|press)\b|\bpistol\b|\bjumps?\b|\bbox\b"},
    "heel": {"label": "Heel / Achilles", "avoid": r"\bcalf\b|\bcalves\b|\bjumps?\b|\bhops?\b|\bskip"},
    "hip": {"label": "Hip", "avoid": r"\blunges?\b|\bsplit squats?\b|\bstep ?ups?\b|\bhip thrusts?\b|\b(?:ab|ad)duct"},
    "lower_back": {"label": "Lower back", "avoid": r"\bdeadlifts?\b|\brdl\b|\bgood mornings?\b|\b(?:back|lumbar) extensions?\b|\bhyperextensions?\b|\bbent over rows?\b|\bkettlebell swings?\b"},
    "shoulder": {"label": "Shoulder", "avoid": r"\b(?:overhead|military|arnold|push|shoulder) press\b|\blateral raises?\b|\bupright rows?\b|\bdips?\b|\bpull ?ups?\b|\bchin ?ups?\b"},
    "elbow": {"label": "Elbow", "avoid": r"\bskull ?crushers?\b|\btriceps?\b|(?<!leg )(?<!hamstring )\bcurls?\b|\bclose grip\b|\bdips?\b"},
    "wrist": {"label": "Wrist", "avoid": r"\bpush ?ups?\b|\bfront squats?\b|\bplank\b"},
    "neck": {"label": "Neck", "avoid": r"\bshrugs?\b|\bupright rows?\b"},
}
BODY_SIDES = {"left": "Left", "right": "Right", "both": "Both"}
NOTE_FIELDS = ("current_block", "weekly_availability_notes", "planning_notes")
NOTE_STALE_AFTER_DAYS = 42
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
DEFAULT_PERFORMANCE_ZONES = {
    "run": {"zone2_lower_pct": 1.15, "zone2_upper_pct": 1.3},
    "ride": {"zone2_lower_pct": 0.56, "zone2_upper_pct": 0.75},
}
DEFAULT_STRENGTH_TEMPLATES = [
    {
        "id": "strength-a",
        "code": "A",
        "label": "Workout A",
        "title": "Upper Chest",
        "summary": "Upper-body push emphasis with stable pressing volume.",
        "session_type": "WeightTraining",
        "workout_intent": "strength_upper",
        "focus_area": "upper",
    },
    {
        "id": "strength-b",
        "code": "B",
        "label": "Workout B",
        "title": "Back + Arms",
        "summary": "Pulling and arm work without extra lower-body fatigue.",
        "session_type": "WeightTraining",
        "workout_intent": "strength_upper",
        "focus_area": "upper",
    },
    {
        "id": "strength-c",
        "code": "C",
        "label": "Workout C",
        "title": "Wide Shoulders",
        "summary": "Shoulder-focused upper-body session that keeps the rotation moving.",
        "session_type": "WeightTraining",
        "workout_intent": "strength_upper",
        "focus_area": "upper",
    },
    {
        "id": "strength-d",
        "code": "D",
        "label": "Workout D",
        "title": "Lower + Core",
        "summary": "Lower-body and trunk work for the next heavier strength slot.",
        "session_type": "WeightTraining",
        "workout_intent": "strength_lower",
        "focus_area": "lower",
    },
]


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
        "body_areas": [],
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


def default_workout_template_settings() -> dict:
    return normalize_workout_template_settings({})


def default_performance_settings() -> dict:
    return normalize_performance_settings({})


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
    off_season = profile.get("off_season") or {}
    if off_season.get("months"):
        coaching_summary_parts.append(f"Off season (mostly indoor): {off_season['label']}.")

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
        "off_season": off_season,
        "coaching_summary": " ".join(coaching_summary_parts),
    }


def _template_order_lookup(templates: list[dict]) -> dict[str, int]:
    return {
        item["id"]: index
        for index, item in enumerate(templates)
        if item.get("id")
    }


def _next_template_id(templates: list[dict], template_id: Optional[str]) -> Optional[str]:
    if not templates:
        return None
    if not template_id:
        return templates[0]["id"]
    lookup = _template_order_lookup(templates)
    index = lookup.get(template_id)
    if index is None:
        return templates[0]["id"]
    return templates[(index + 1) % len(templates)]["id"]


def _template_by_id(templates: list[dict], template_id: Optional[str]) -> Optional[dict]:
    for item in templates:
        if item.get("id") == template_id:
            return item
    return None


def _template_display_name(template: Optional[dict]) -> Optional[str]:
    if not template:
        return None
    label = template.get("label")
    title = template.get("title")
    if label and title:
        return f"{label} · {title}"
    return label or title


def _normalize_template(raw_template: dict, fallback_index: int) -> dict:
    raw = raw_template if isinstance(raw_template, dict) else {}
    template_id = _clean_text(raw.get("id")) or f"strength-template-{fallback_index + 1}"
    code = _clean_text(raw.get("code")) or chr(ord("A") + fallback_index)
    label = _clean_text(raw.get("label")) or f"Workout {code}"
    session_type = _clean_text(raw.get("session_type")) or "WeightTraining"
    workout_intent = raw.get("workout_intent") or "strength_general"
    if workout_intent not in {"strength_general", "strength_lower", "strength_upper", "mobility"}:
        workout_intent = "strength_general"
    focus_area = (_clean_text(raw.get("focus_area")) or ("lower" if workout_intent == "strength_lower" else "upper")).lower()
    if focus_area not in {"upper", "lower", "full_body", "mobility"}:
        focus_area = "upper"
    normalized = {
        "id": template_id,
        "code": code,
        "label": label,
        "title": _clean_text(raw.get("title")) or label,
        "summary": _clean_text(raw.get("summary")),
        "session_type": session_type,
        "workout_intent": workout_intent,
        "focus_area": focus_area,
        "display_name": None,
    }
    normalized["display_name"] = _template_display_name(normalized)
    return normalized


def _normalize_strength_program(raw_program: Optional[dict]) -> dict:
    raw = raw_program if isinstance(raw_program, dict) else {}
    incoming_templates = raw.get("templates") if isinstance(raw.get("templates"), list) else DEFAULT_STRENGTH_TEMPLATES
    templates = []
    seen_template_ids: set[str] = set()
    for index, item in enumerate(incoming_templates):
        normalized = _normalize_template(item, index)
        if normalized["id"] in seen_template_ids:
            continue
        seen_template_ids.add(normalized["id"])
        templates.append(normalized)
    if not templates:
        templates = [_normalize_template(item, index) for index, item in enumerate(DEFAULT_STRENGTH_TEMPLATES)]

    rules_source = raw.get("rules") if isinstance(raw.get("rules"), dict) else {}
    rules = {
        "continue_across_weeks": rules_source.get("continue_across_weeks", True) is not False,
        "skip_behavior": "postpone" if rules_source.get("skip_behavior") != "skip" else "skip",
        "avoid_consecutive_repeat": rules_source.get("avoid_consecutive_repeat", True) is not False,
        "prefer_ride_when_run_blocked": rules_source.get("prefer_ride_when_run_blocked", True) is not False,
        "delay_lower_body_when_running_restricted": rules_source.get("delay_lower_body_when_running_restricted", True) is not False,
        "replace_rest_with_recovery_only_when_explicit": bool(rules_source.get("replace_rest_with_recovery_only_when_explicit", False)),
    }

    state_source = raw.get("rotation_state") if isinstance(raw.get("rotation_state"), dict) else {}
    valid_template_ids = [item["id"] for item in templates]
    processed_activity_ids = []
    for activity_id in state_source.get("processed_activity_ids", []) if isinstance(state_source.get("processed_activity_ids"), list) else []:
        cleaned = _clean_text(activity_id)
        if cleaned and cleaned not in processed_activity_ids:
            processed_activity_ids.append(cleaned)
    last_completed_template_id = _clean_text(state_source.get("last_completed_template_id"))
    if last_completed_template_id not in valid_template_ids:
        last_completed_template_id = None
    next_template_id = _clean_text(state_source.get("next_template_id"))
    if next_template_id not in valid_template_ids:
        next_template_id = _next_template_id(templates, last_completed_template_id)
    pending_template_id = _clean_text(state_source.get("pending_template_id")) or next_template_id
    if pending_template_id not in valid_template_ids:
        pending_template_id = next_template_id

    program = {
        "modality": "strength",
        "label": "Strength rotation",
        "enabled": raw.get("enabled", True) is not False,
        "templates": templates,
        "rules": rules,
        "rotation_state": {
            "last_completed_template_id": last_completed_template_id,
            "last_completed_template_label": _template_display_name(_template_by_id(templates, last_completed_template_id)),
            "last_completed_at": _clean_text(state_source.get("last_completed_at")),
            "last_completed_activity_id": _clean_text(state_source.get("last_completed_activity_id")),
            "next_template_id": next_template_id,
            "next_template_label": _template_display_name(_template_by_id(templates, next_template_id)),
            "pending_template_id": pending_template_id,
            "pending_template_label": _template_display_name(_template_by_id(templates, pending_template_id)),
            "processed_activity_ids": processed_activity_ids[-64:],
        },
    }
    program["summary"] = {
        "template_count": len(templates),
        "next_workout": program["rotation_state"]["next_template_label"] or "Not set",
        "last_completed": program["rotation_state"]["last_completed_template_label"],
        "skip_behavior": "Postpone missed sessions" if rules["skip_behavior"] == "postpone" else "Skip missed sessions",
        "rule_highlights": [
            "Continue rotation across weeks" if rules["continue_across_weeks"] else "Reset weekly",
            "Delay lower-body work when running is restricted" if rules["delay_lower_body_when_running_restricted"] else "No lower-body delay rule",
        ],
    }
    return program


def serialize_workout_template_settings_for_storage(settings: dict) -> dict:
    program = ((settings or {}).get("programs") or {}).get("strength") or {}
    return {
        "programs": {
            "strength": {
                "enabled": program.get("enabled", True),
                "templates": [
                    {
                        "id": item.get("id"),
                        "code": item.get("code"),
                        "label": item.get("label"),
                        "title": item.get("title"),
                        "summary": item.get("summary"),
                        "session_type": item.get("session_type"),
                        "workout_intent": item.get("workout_intent"),
                        "focus_area": item.get("focus_area"),
                    }
                    for item in program.get("templates", [])
                ],
                "rules": dict(program.get("rules") or {}),
                "rotation_state": {
                    "last_completed_template_id": (program.get("rotation_state") or {}).get("last_completed_template_id"),
                    "last_completed_at": (program.get("rotation_state") or {}).get("last_completed_at"),
                    "last_completed_activity_id": (program.get("rotation_state") or {}).get("last_completed_activity_id"),
                    "next_template_id": (program.get("rotation_state") or {}).get("next_template_id"),
                    "pending_template_id": (program.get("rotation_state") or {}).get("pending_template_id"),
                    "processed_activity_ids": (program.get("rotation_state") or {}).get("processed_activity_ids", []),
                },
            }
        }
    }


def normalize_workout_template_settings(raw_value: Optional[dict]) -> dict:
    raw = raw_value if isinstance(raw_value, dict) else {}
    programs = raw.get("programs") if isinstance(raw.get("programs"), dict) else {}
    strength_program = _normalize_strength_program(programs.get("strength"))
    return {
        "programs": {
            "strength": strength_program,
        }
    }


def _normalize_anchor(raw_anchor: Optional[dict], *, key: str, label: str, unit: str) -> dict:
    raw = raw_anchor if isinstance(raw_anchor, dict) else {}
    value = raw.get("value")
    try:
        numeric_value = float(value) if value not in {None, ""} else None
    except (TypeError, ValueError):
        numeric_value = None
    if numeric_value is not None and numeric_value <= 0:
        numeric_value = None
    return {
        "key": key,
        "label": label,
        "value": round(numeric_value, 1) if numeric_value is not None else None,
        "unit": unit,
        "is_set": numeric_value is not None,
    }


def _normalize_zone(raw_zone: Optional[dict], *, modality: str) -> dict:
    base = DEFAULT_PERFORMANCE_ZONES[modality]
    raw = raw_zone if isinstance(raw_zone, dict) else {}

    def pct_value(field: str) -> float:
        value = raw.get(field, base[field])
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = base[field]
        if numeric <= 0:
            numeric = base[field]
        return round(numeric, 2)

    lower = pct_value("zone2_lower_pct")
    upper = pct_value("zone2_upper_pct")
    if upper < lower:
        lower, upper = base["zone2_lower_pct"], base["zone2_upper_pct"]
    return {
        "modality": modality,
        "zone2_lower_pct": lower,
        "zone2_upper_pct": upper,
    }


def normalize_performance_settings(raw_value: Optional[dict]) -> dict:
    raw = raw_value if isinstance(raw_value, dict) else {}
    anchors_raw = raw.get("anchors") if isinstance(raw.get("anchors"), dict) else {}
    zones_raw = raw.get("zones") if isinstance(raw.get("zones"), dict) else {}
    anchors = {
        "run_threshold_pace": _normalize_anchor(
            anchors_raw.get("run_threshold_pace"),
            key="run_threshold_pace",
            label="Running threshold pace",
            unit="s/km",
        ),
        "ride_threshold_power": _normalize_anchor(
            anchors_raw.get("ride_threshold_power"),
            key="ride_threshold_power",
            label="Cycling threshold power",
            unit="W",
        ),
    }
    zones = {
        "run": _normalize_zone(zones_raw.get("run"), modality="run"),
        "ride": _normalize_zone(zones_raw.get("ride"), modality="ride"),
    }
    return _with_performance_summary({
        "anchors": anchors,
        "zones": zones,
        "ftp": normalize_ftp_choice(raw.get("ftp")),
    })


def _with_performance_summary(settings: dict) -> dict:
    anchors = settings["anchors"]
    anchors_set = sum(1 for item in anchors.values() if item["is_set"])
    return {
        **settings,
        "summary": {
            "anchors_set": anchors_set,
            "run_ready": anchors["run_threshold_pace"]["is_set"],
            "ride_ready": anchors["ride_threshold_power"]["is_set"],
            "headline": (
                "Performance anchors are ready for running and riding."
                if anchors_set == 2 else
                "One performance anchor is set."
                if anchors_set == 1 else
                "Performance anchors are still missing."
            ),
        },
    }


def serialize_performance_settings_for_storage(settings: dict) -> dict:
    return {
        "anchors": {
            key: {
                "value": item.get("value"),
                "unit": item.get("unit"),
            }
            for key, item in (settings.get("anchors") or {}).items()
        },
        "zones": {
            key: {
                "zone2_lower_pct": item.get("zone2_lower_pct"),
                "zone2_upper_pct": item.get("zone2_upper_pct"),
            }
            for key, item in (settings.get("zones") or {}).items()
        },
        "ftp": {
            key: (settings.get("ftp") or {}).get(key)
            for key in ("source", "manual_watts", "estimate_watts", "estimate_basis", "estimate_date", "effective_from")
        },
    }


def _with_derived_ride_anchor(conn: sqlite3.Connection, settings: dict) -> dict:
    """The cycling anchor is the chosen FTP, not a second number to keep in sync."""
    watts = ftp_on(conn)
    anchor = {
        **settings["anchors"]["ride_threshold_power"],
        "value": round(watts, 1) if watts else None,
        "is_set": bool(watts),
        "derived_from": "ftp",
    }
    return _with_performance_summary({**settings, "anchors": {**settings["anchors"], "ride_threshold_power": anchor}})


def _raw_performance_settings(conn: sqlite3.Connection) -> dict:
    raw_value = get_setting_value(conn, PERFORMANCE_SETTINGS_KEY)
    if not raw_value:
        return default_performance_settings()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_performance_settings()
    return normalize_performance_settings(parsed)


def get_performance_settings_for_conn(conn: sqlite3.Connection) -> dict:
    return _with_derived_ride_anchor(conn, _raw_performance_settings(conn))


def _current_ftp_estimate(conn: sqlite3.Connection, today: date) -> dict:
    try:
        from .personal_records import build_personal_records

        return build_personal_records(conn, today)["cycling_power"]["ftp_estimate"] or {}
    except (sqlite3.OperationalError, KeyError, TypeError):
        return {}


def _estimate_snapshot(estimate: dict, today: date) -> dict:
    if not (estimate.get("available") and estimate.get("watts")):
        return {"estimate_watts": None, "estimate_basis": None, "estimate_date": None}
    return {"estimate_watts": estimate["watts"], "estimate_basis": estimate.get("basis"), "estimate_date": today.isoformat()}


def _store_performance_settings(conn: sqlite3.Connection, settings: dict) -> None:
    set_setting_value(conn, PERFORMANCE_SETTINGS_KEY, json.dumps(serialize_performance_settings_for_storage(settings)))


def get_performance_settings_with_ftp(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """Settings plus the three FTP candidates for the Athlete page.

    When the athlete follows the training estimate, the stored snapshot moves
    with it here, so readers that cannot afford the estimate stay current.
    """
    today = today or date.today()
    settings = _raw_performance_settings(conn)
    estimate = _current_ftp_estimate(conn, today)
    choice = settings["ftp"]
    if choice["source"] == "estimate":
        snapshot = _estimate_snapshot(estimate, today)
        if snapshot["estimate_watts"] and snapshot["estimate_watts"] != choice["estimate_watts"]:
            settings = {**settings, "ftp": normalize_ftp_choice({**choice, **snapshot})}
            _store_performance_settings(conn, settings)
            conn.commit()
    return {
        **_with_derived_ride_anchor(conn, settings),
        "ftp_options": {
            "working": working_ftp(conn, today),
            "stored": stored_ftp(conn, today),
            "estimate": {key: estimate.get(key) for key in ("available", "watts", "basis", "note", "reason", "window_days")},
        },
    }


def get_performance_settings_data() -> dict:
    conn = get_db()
    try:
        return get_performance_settings_with_ftp(conn)
    finally:
        conn.close()


def set_performance_settings_for_conn(conn: sqlite3.Connection, payload: dict, today: Optional[date] = None) -> dict:
    today = today or date.today()
    existing = _raw_performance_settings(conn)["ftp"]
    requested = {key: value for key, value in ((payload or {}).get("ftp") or {}).items() if value is not None}
    legacy_ride_anchor = ((((payload or {}).get("anchors") or {}).get("ride_threshold_power")) or {}).get("value")
    if not requested and legacy_ride_anchor and legacy_ride_anchor != ftp_on(conn):
        # Older callers set the cycling anchor directly: treat it as a typed working FTP.
        requested = {"source": "manual", "manual_watts": legacy_ride_anchor}
    incoming = normalize_ftp_choice({**existing, **requested})
    changed = incoming["source"] != existing["source"] or (
        incoming["source"] == "manual" and incoming["manual_watts"] != existing["manual_watts"]
    )
    if incoming["source"] == "estimate":
        incoming = {**incoming, **_estimate_snapshot(_current_ftp_estimate(conn, today), today)}
    if changed:
        # A new source applies from today; earlier rides keep the FTP they were ridden with.
        incoming["effective_from"] = today.isoformat()
    normalized = normalize_performance_settings({**(payload or {}), "ftp": incoming})
    _store_performance_settings(conn, normalized)
    return _with_derived_ride_anchor(conn, normalized)


def set_performance_settings_data(payload: dict) -> dict:
    conn = get_db()
    try:
        set_performance_settings_for_conn(conn, payload)
        conn.commit()
        return get_performance_settings_with_ftp(conn)
    finally:
        conn.close()


def get_workout_template_settings_for_conn(conn: sqlite3.Connection) -> dict:
    raw_value = get_setting_value(conn, WORKOUT_TEMPLATE_SETTINGS_KEY)
    if not raw_value:
        return default_workout_template_settings()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_workout_template_settings()
    return normalize_workout_template_settings(parsed)


def get_workout_template_settings_data() -> dict:
    conn = get_db()
    try:
        from .activities import reconcile_workout_template_rotation_state

        reconcile_workout_template_rotation_state(conn)
        return get_workout_template_settings_for_conn(conn)
    finally:
        conn.close()


def set_workout_template_settings_for_conn(conn: sqlite3.Connection, payload: dict) -> dict:
    existing = get_workout_template_settings_for_conn(conn)
    existing_strength = ((existing.get("programs") or {}).get("strength")) or {}
    incoming_strength = (((payload or {}).get("programs") or {}).get("strength")) or {}
    merged = {
        "programs": {
            "strength": {
                **existing_strength,
                **incoming_strength,
                "rules": {
                    **(existing_strength.get("rules") or {}),
                    **(incoming_strength.get("rules") or {}),
                },
                "rotation_state": {
                    **(existing_strength.get("rotation_state") or {}),
                    **(incoming_strength.get("rotation_state") or {}),
                },
                "templates": incoming_strength.get("templates") or existing_strength.get("templates"),
            }
        }
    }
    normalized = normalize_workout_template_settings(merged)
    set_setting_value(
        conn,
        WORKOUT_TEMPLATE_SETTINGS_KEY,
        json.dumps(serialize_workout_template_settings_for_storage(normalized)),
    )
    return normalized


def set_workout_template_settings_data(payload: dict) -> dict:
    conn = get_db()
    try:
        normalized = set_workout_template_settings_for_conn(conn, payload)
        conn.commit()
        return normalized
    finally:
        conn.close()


def _positive_kg(value) -> Optional[float]:
    try:
        kg = float(value)
    except (TypeError, ValueError):
        return None
    return kg if 0 < kg <= 500 else None


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
    off_season_months = normalize_off_season_months(raw.get("off_season_months"))
    profile["off_season_months"] = off_season_months
    profile["off_season"] = {"months": off_season_months, "label": season_label(off_season_months)}
    profile["max_dumbbell_kg"] = _positive_kg(raw.get("max_dumbbell_kg"))
    reviewed_raw = raw.get("notes_reviewed_at") if isinstance(raw.get("notes_reviewed_at"), dict) else {}
    profile["notes_reviewed_at"] = {field: _iso_day(reviewed_raw.get(field)) for field in NOTE_FIELDS}
    profile["note_reviews"] = _note_reviews(profile)
    profile["athlete_brief"] = build_athlete_brief(profile)
    return profile


def _note_reviews(profile: dict, today: Optional[date] = None) -> dict:
    """How long since each free-text note was written or confirmed."""
    today = today or date.today()
    reviews = {}
    for field in NOTE_FIELDS:
        reviewed_at = profile["notes_reviewed_at"].get(field)
        age_days = (today - date.fromisoformat(reviewed_at)).days if reviewed_at else None
        has_text = bool(profile.get(field))
        reviews[field] = {
            "reviewed_at": reviewed_at,
            "age_days": age_days,
            "stale": has_text and (age_days is None or age_days > NOTE_STALE_AFTER_DAYS),
        }
    return reviews


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
        "off_season_months": profile.get("off_season_months"),
        "max_dumbbell_kg": profile.get("max_dumbbell_kg"),
        "notes_reviewed_at": profile.get("notes_reviewed_at") or {},
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
    if metric_type == "quality_sessions":
        return "ride"
    if metric_type == "zone2_hours":
        return normalize_modality(activity_type) or "run"
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

    body_areas = normalize_body_areas((raw_value or {}).get("body_areas") if isinstance(raw_value, dict) else None)
    if body_areas:
        protected = _format_list([item["summary_label"] for item in body_areas])
        headline = f"Protecting {protected}." if headline.startswith("All primary") else f"{headline} Protecting {protected}."

    payload["active"] = active
    payload["body_areas"] = body_areas
    payload["summary"] = {
        "active_count": len(active),
        "blocked_count": blocked_count,
        "limited_count": limited_count,
        "protected_count": len(body_areas),
        "headline": headline,
    }
    return payload


def _iso_day(value) -> Optional[str]:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat() if value else None
    except ValueError:
        return None


def normalize_body_areas(raw_items) -> list[dict]:
    items = []
    seen = set()
    for raw in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw, dict):
            continue
        area = _clean_text(raw.get("area"))
        area = area.lower().replace(" ", "_") if area else None
        if area not in BODY_AREAS:
            continue
        side = _clean_text(raw.get("side"))
        side = side.lower() if side and side.lower() in BODY_SIDES else None
        if (area, side) in seen:
            continue
        seen.add((area, side))
        label = BODY_AREAS[area]["label"]
        summary_label = f"{BODY_SIDES[side].lower()} {label.lower()}" if side in {"left", "right"} else label.lower()
        try:
            issue_id = int(raw.get("recovery_issue_id")) if raw.get("recovery_issue_id") not in {None, ""} else None
        except (TypeError, ValueError):
            issue_id = None
        items.append({
            "area": area,
            "label": label,
            "side": side,
            "summary_label": summary_label,
            "note": _clean_text(raw.get("note")),
            "since": _iso_day(raw.get("since")),
            "recovery_issue_id": issue_id,
        })
    return items


def _exercise_words(name: Optional[str]) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", re.sub(r"[-_–—]", " ", str(name or "").lower()))).strip()


def protected_area_for_exercise(name: Optional[str], body_areas: list[dict]) -> Optional[dict]:
    """The first protected area this exercise loads, if any."""
    words = _exercise_words(name)
    for item in body_areas or []:
        pattern = (BODY_AREAS.get(item.get("area")) or {}).get("avoid")
        if pattern and re.search(pattern, words):
            return item
    return None


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


def set_athlete_profile_data(payload: dict, today: Optional[date] = None) -> dict:
    today_iso = (today or date.today()).isoformat()
    conn = get_db()
    try:
        existing = get_athlete_profile_for_conn(conn)
        incoming = dict(payload or {})
        claimed = incoming.get("notes_reviewed_at") if isinstance(incoming.get("notes_reviewed_at"), dict) else {}
        reviewed = {}
        for field in NOTE_FIELDS:
            if _clean_text(incoming.get(field)) != existing.get(field):
                # Rewriting a note counts as reviewing it.
                reviewed[field] = today_iso
            else:
                # "Still accurate" sends today; otherwise keep the date already stored.
                dates = [day for day in (_iso_day(claimed.get(field)), existing["notes_reviewed_at"].get(field)) if day]
                reviewed[field] = min(max(dates), today_iso) if dates else None
        incoming["notes_reviewed_at"] = reviewed
        normalized = normalize_athlete_profile(incoming)
        set_setting_value(conn, ATHLETE_PROFILE_KEY, json.dumps(serialize_athlete_profile_for_storage(normalized)))
        conn.commit()
        return normalized
    finally:
        conn.close()
