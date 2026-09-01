import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from ..repositories.activities import list_activity_rows
from ..repositories.activity_analyses import (
    get_activity_analysis_request_row,
    get_activity_analysis_row,
    mark_activity_analysis_request_completed,
    mark_activity_analysis_request_failed,
    upsert_activity_analysis_request_row,
    upsert_activity_analysis_row,
)

SUPPORTED_ENDURANCE_TYPES = {"Run", "Ride", "VirtualRide", "Walk", "Hike"}


def _stats_by_key(detail_payload: dict) -> dict[str, dict]:
    return {item["key"]: item for item in detail_payload.get("stats", []) if item.get("key")}


def _format_decimal(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _recent_activity_hints(conn: sqlite3.Connection, activity_id: str, limit: int = 8) -> list[dict]:
    hints = []
    for row in list_activity_rows(conn, limit=12):
        if row["id"] == activity_id:
            continue
        hints.append(
            {
                "date": row["date"],
                "type": row["type"],
                "duration_min": _format_decimal(row["duration_min"]),
                "distance_km": _format_decimal(row["distance_km"]),
                "avg_hr": row["avg_hr"],
                "zone2": bool(row["zone2"]) if row["zone2"] is not None else None,
                "workout_intent": row["workout_intent"],
            }
        )
        if len(hints) >= limit:
            break
    return hints


def build_activity_analysis_context(conn: sqlite3.Connection, detail_payload: dict) -> dict:
    activity = detail_payload["activity"]
    stats = _stats_by_key(detail_payload)
    feedback = detail_payload.get("feedback") or {}
    hr_zones = detail_payload.get("heart_rate_zones") or {}
    strength_detail = detail_payload.get("strength_detail") or {}
    best_efforts = (detail_payload.get("best_efforts") or {}).get("efforts") or []
    limitations: list[str] = []

    if activity.get("type") == "WeightTraining":
        available = strength_detail.get("status") == "enriched"
        if not available:
            limitations.append(
                "Strength analysis needs linked exercise-level detail from TrainLog or Fitbod."
            )
    elif activity.get("type") in SUPPORTED_ENDURANCE_TYPES:
        available = bool(detail_payload.get("detail_available"))
        if not available:
            limitations.append("Detailed Strava workout data has not been cached for this activity yet.")
    else:
        available = False
        limitations.append(f"Activity type {activity.get('type')} is not supported by workout analysis yet.")

    if not hr_zones.get("available"):
        limitations.append("Heart-rate zone distribution is unavailable.")
    if not activity.get("linked_planned_session_id"):
        limitations.append("No explicit planned-session link is attached.")
    if not feedback:
        limitations.append("No post-workout subjective feedback is available.")
    if activity.get("type") != "WeightTraining" and not best_efforts:
        limitations.append("No best-effort segment summary is available from the cached streams.")

    strength_session = strength_detail.get("session") or {}
    strength_exercises = strength_session.get("exercises") or []
    top_exercises = [
        {
            "name": exercise.get("exercise_name"),
            "set_count": exercise.get("set_count"),
            "rep_count": exercise.get("rep_count"),
            "total_volume_kg": _format_decimal(exercise.get("total_volume_kg")),
        }
        for exercise in strength_exercises[:4]
    ]

    context = {
        "activity": {
            "id": activity.get("id"),
            "date": activity.get("date"),
            "type": activity.get("type"),
            "name": activity.get("name"),
            "workout_intent": activity.get("workout_intent"),
            "workout_intent_label": activity.get("workout_intent_label"),
            "linked_planned_session_id": activity.get("linked_planned_session_id"),
            "benchmark_label": activity.get("benchmark_label"),
        },
        "summary_stats": {
            "distance_km": _format_decimal(stats.get("distance_km", {}).get("value")),
            "moving_time_min": _format_decimal(stats.get("moving_time_min", {}).get("value")),
            "elapsed_time_min": _format_decimal(stats.get("elapsed_time_min", {}).get("value")),
            "avg_pace": stats.get("avg_pace", {}).get("value"),
            "avg_speed_kmh": _format_decimal(stats.get("avg_speed_kmh", {}).get("value")),
            "avg_hr": stats.get("avg_hr", {}).get("value"),
            "max_hr": stats.get("max_hr", {}).get("value"),
            "avg_watts": _format_decimal(stats.get("avg_watts", {}).get("value")),
            "normalized_power": _format_decimal(stats.get("normalized_power", {}).get("value")),
            "elevation_m": _format_decimal(stats.get("elevation_m", {}).get("value"), 0),
            "calories": _format_decimal(stats.get("calories", {}).get("value"), 0),
        },
        "heart_rate_zones": {
            "available": bool(hr_zones.get("available")),
            "summary": hr_zones.get("summary"),
            "zone2_minutes": _format_decimal(hr_zones.get("zone2_minutes")),
            "zone2_pct": hr_zones.get("zone2_pct"),
            "top_zones": [
                {
                    "key": zone.get("key"),
                    "label": zone.get("label"),
                    "minutes": _format_decimal(zone.get("minutes")),
                    "pct": zone.get("pct"),
                }
                for zone in (hr_zones.get("zones") or [])
                if zone.get("seconds", 0) > 0
            ][:3],
        },
        "best_efforts": [
            {
                "label": effort.get("label"),
                "duration_s": _format_decimal(effort.get("duration_s")),
                "metric_label": effort.get("metric_label"),
                "metric_unit": effort.get("metric_unit"),
                "metric_value": _format_decimal(effort.get("metric_value"), 2),
                "avg_hr": effort.get("avg_hr"),
                "elevation_gain_m": effort.get("elevation_gain_m"),
            }
            for effort in best_efforts[:3]
        ],
        "feedback": {
            "rpe": feedback.get("rpe"),
            "energy": feedback.get("energy"),
            "muscle_soreness": feedback.get("muscle_soreness"),
            "pain_level": feedback.get("pain_level"),
            "note": str(feedback.get("note") or "").strip() or None,
        } if feedback else None,
        "load_signals": {
            "hr_trimp": _format_decimal((detail_payload.get("source_stream_summary") or {}).get("hr_trimp")),
            "power_tss": _format_decimal((detail_payload.get("source_stream_summary") or {}).get("power_tss")),
            "normalized_power": _format_decimal((detail_payload.get("source_stream_summary") or {}).get("normalized_power")),
        },
        "strength_summary": {
            "status": strength_detail.get("status"),
            "set_count": strength_session.get("set_count"),
            "rep_count": strength_session.get("rep_count"),
            "total_volume_kg": _format_decimal(strength_session.get("total_volume_kg")),
            "exercise_count": len(strength_exercises),
            "top_exercises": top_exercises,
        },
        "recent_context": _recent_activity_hints(conn, activity.get("id")),
        "limitations": limitations,
        "available": available,
    }
    signature = hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "available": available,
        "limitations": limitations,
        "context": context,
        "context_signature": signature,
    }


def _serialize_analysis_snapshot(
    *,
    context_payload: dict,
    analysis_row: Optional[sqlite3.Row],
    request_row: Optional[sqlite3.Row],
) -> dict:
    available = context_payload["available"]
    payload = {
        "available": available,
        "reason": context_payload["limitations"][0] if (not available and context_payload["limitations"]) else None,
        "limitations": context_payload["limitations"][:4],
        "context": context_payload["context"],
        "requested_at": request_row["requested_at"] if request_row else None,
        "requested_via": request_row["requested_via"] if request_row else None,
        "generated_at": analysis_row["generated_at"] if analysis_row else None,
        "generator": analysis_row["generator"] if analysis_row else None,
        "model_name": analysis_row["model_name"] if analysis_row else None,
        "last_error": request_row["last_error"] if request_row else None,
        "stale": False,
    }

    if not available:
        payload["status"] = "unavailable"
        return payload

    if analysis_row:
        analysis = json.loads(analysis_row["analysis_json"])
        payload.update(analysis)
        stale = analysis_row["context_signature"] != context_payload["context_signature"]
        payload["stale"] = stale

    request_status = request_row["status"] if request_row else None
    if request_status == "pending":
        payload["status"] = "requested"
        return payload
    if request_status == "failed":
        payload["status"] = "failed"
        return payload
    if analysis_row:
        payload["status"] = "stale" if payload["stale"] else "ready"
        return payload
    payload["status"] = "not_requested"
    return payload


def get_activity_analysis_snapshot(conn: sqlite3.Connection, detail_payload: dict) -> dict:
    context_payload = build_activity_analysis_context(conn, detail_payload)
    analysis_row = get_activity_analysis_row(conn, detail_payload["activity"]["id"])
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    return _serialize_analysis_snapshot(
        context_payload=context_payload,
        analysis_row=analysis_row,
        request_row=request_row,
    )


def request_activity_analysis(conn: sqlite3.Connection, detail_payload: dict, *, force_refresh: bool = False, requested_via: str = "app") -> dict:
    snapshot = get_activity_analysis_snapshot(conn, detail_payload)
    if snapshot["status"] == "unavailable":
        return snapshot
    if snapshot["status"] == "requested" and not force_refresh:
        return snapshot
    if snapshot["status"] == "ready" and not force_refresh:
        return snapshot

    context_payload = build_activity_analysis_context(conn, detail_payload)
    requested_at = datetime.now().isoformat()
    upsert_activity_analysis_request_row(
        conn,
        activity_id=detail_payload["activity"]["id"],
        status="pending",
        requested_at=requested_at,
        requested_via=requested_via,
        context_signature=context_payload["context_signature"],
        last_error=None,
    )
    conn.commit()
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    analysis_row = get_activity_analysis_row(conn, detail_payload["activity"]["id"])
    return _serialize_analysis_snapshot(
        context_payload=context_payload,
        analysis_row=analysis_row,
        request_row=request_row,
    )


def get_activity_analysis_context_payload(conn: sqlite3.Connection, detail_payload: dict) -> dict:
    context_payload = build_activity_analysis_context(conn, detail_payload)
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    snapshot = get_activity_analysis_snapshot(conn, detail_payload)
    return {
        "activity_id": detail_payload["activity"]["id"],
        "status": snapshot["status"],
        "requested_at": request_row["requested_at"] if request_row else None,
        "requested_via": request_row["requested_via"] if request_row else None,
        "context_signature": context_payload["context_signature"],
        "available": context_payload["available"],
        "limitations": context_payload["limitations"],
        "context": context_payload["context"],
        "instructions": {
            "task": "Act as a thoughtful endurance and strength coach. Explain what this workout means within the athlete's recent training trajectory, rather than recapping fields already visible on the activity page.",
            "output_schema": {
                "headline": "short coaching conclusion, not an activity label or metric recap",
                "summary": "3-5 sentences covering the session's training value, how it fits recent work, any meaningful concern, and the practical implication for recovery or upcoming training",
                "key_observations": "list of 2-4 interpreted coaching signals; include what went well and any issue worth watching, not raw-stat restatements",
                "limitations": "list of 0-4 evidence gaps that materially limit the coaching interpretation",
                "confidence_note": "single sentence distinguishing direct evidence from inference",
            },
            "rules": [
                "Lead with interpretation: adaptation value, execution quality, fatigue or recovery signal, consistency, progression, or mismatch with intended effort.",
                "Use duration, distance, pace, heart rate, zones, power, and other visible metrics only as evidence for a coaching judgment or comparison; do not repeat them merely to summarize the workout.",
                "Compare with recent_context when it supports a real pattern such as accumulating load, repeated intensity, consistency, recovery spacing, or a modality imbalance. Do not claim a trend from one data point.",
                "Identify at least one positive signal when supported. Flag only meaningful concerns; if no concern is supported, say that plainly instead of inventing one.",
                "Treat the athlete's feedback note as first-class coaching evidence. Use it to interpret pain, soreness, perceived difficulty, conditions, or session character when relevant, while distinguishing the athlete's report from measured data.",
                "End the summary with a practical implication for the next 24-72 hours or the next similar session, without rewriting the weekly plan.",
                "Do not invent facts that are not supported by the provided context.",
                "Do not give medical advice or injury diagnosis.",
            ],
        },
    }


def save_activity_analysis(
    conn: sqlite3.Connection,
    detail_payload: dict,
    *,
    headline: str,
    summary: str,
    key_observations: list[str],
    limitations: list[str],
    confidence_note: str,
    generator: str,
    model_name: Optional[str],
    requested_via: Optional[str] = "mcp",
) -> dict:
    context_payload = build_activity_analysis_context(conn, detail_payload)
    if not context_payload["available"]:
        raise HTTPException(status_code=400, detail="Analysis context is unavailable for this activity.")

    analysis = {
        "headline": headline.strip(),
        "summary": summary.strip(),
        "key_observations": [item.strip() for item in key_observations if str(item).strip()][:4],
        "limitations": [item.strip() for item in limitations if str(item).strip()][:4],
        "confidence_note": confidence_note.strip(),
    }
    generated_at = datetime.now().isoformat()
    upsert_activity_analysis_row(
        conn,
        activity_id=detail_payload["activity"]["id"],
        context_signature=context_payload["context_signature"],
        context_json=json.dumps(context_payload["context"], sort_keys=True),
        analysis_json=json.dumps(analysis, sort_keys=True),
        generated_at=generated_at,
        generator=generator,
        model_name=model_name,
        requested_via=requested_via,
    )
    mark_activity_analysis_request_completed(conn, detail_payload["activity"]["id"])
    conn.commit()
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    analysis_row = get_activity_analysis_row(conn, detail_payload["activity"]["id"])
    return _serialize_analysis_snapshot(
        context_payload=context_payload,
        analysis_row=analysis_row,
        request_row=request_row,
    )


def fail_activity_analysis(conn: sqlite3.Connection, detail_payload: dict, *, error_message: str) -> dict:
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    if not request_row:
        raise HTTPException(status_code=404, detail="No pending analysis request exists for this activity.")
    mark_activity_analysis_request_failed(conn, detail_payload["activity"]["id"], error_message.strip())
    conn.commit()
    return get_activity_analysis_snapshot(conn, detail_payload)
