import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

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
from .session_read import build_session_read

SUPPORTED_ENDURANCE_TYPES = {"Run", "Ride", "VirtualRide", "Walk", "Hike"}
MAX_QUESTION_LENGTH = 500


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
    session_read = build_session_read(conn, detail_payload)

    sick_session = detail_payload.get("sick_session")
    if sick_session:
        # A guided sick-mode session: the exercise list comes from TrainLog, effort from the watch.
        available = bool(detail_payload.get("detail_available") or stats.get("avg_hr", {}).get("value"))
        if not available:
            limitations.append("No heart-rate data from the watch is available for this sick-mode session.")
    elif activity.get("type") == "WeightTraining":
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
    if activity.get("type") != "WeightTraining" and not sick_session and not best_efforts:
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
            "fuelling": feedback.get("fuelling"),
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
        "sick_session": {
            "title": sick_session.get("title"),
            "planned_steps": sick_session.get("steps"),
            "added_live": sick_session.get("extras"),
            "guided_min": sick_session.get("guided_min"),
            "guidance": "The athlete was sick (sick mode) and did this gentle home session to keep a daily streak. "
                        "Judge whether effort stayed easy enough for someone who is ill (heart rate, duration), "
                        "not training stimulus; never suggest pushing harder while symptoms last.",
        } if sick_session else None,
        "recent_context": _recent_activity_hints(conn, activity.get("id")),
        "session_read": _session_read_for_context(session_read),
        "limitations": limitations,
        "available": available,
    }
    signature = hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "available": available,
        "limitations": limitations,
        "context": context,
        "context_signature": signature,
        "session_read": session_read,
    }


def _session_read_for_context(session_read: dict) -> Optional[dict]:
    """The deterministic read without chart series, for the LLM context."""
    if not session_read.get("available"):
        return None
    return {
        "verdict": session_read["verdict"],
        "signals": [{key: signal[key] for key in ("label", "value", "detail", "tone")} for signal in session_read["signals"]],
        "next_time": session_read.get("next_time"),
        "watch": session_read.get("watch"),
        "method": session_read.get("method"),
    }


def _clean_question(question: Optional[str]) -> Optional[str]:
    text = " ".join(str(question or "").split())
    return text[:MAX_QUESTION_LENGTH] or None


def _request_question(request_row: Optional[sqlite3.Row]) -> Optional[str]:
    return request_row["question"] if request_row and "question" in request_row.keys() else None


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
        "pending_question": _request_question(request_row) if request_row and request_row["status"] == "pending" else None,
        "session_read": context_payload["session_read"],
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


_KEEP_QUESTION = object()


def request_activity_analysis(
    conn: sqlite3.Connection,
    detail_payload: dict,
    *,
    force_refresh: bool = False,
    requested_via: str = "app",
    question: Any = _KEEP_QUESTION,
) -> dict:
    """Queue an LLM read. ``question`` replaces the athlete's question; leaving it out keeps a pending one.

    The app saves the question first and then starts the coach CLI, which calls this again
    through MCP without a question, so a pending question must survive that call.
    """
    snapshot = get_activity_analysis_snapshot(conn, detail_payload)
    if snapshot["status"] == "unavailable":
        return snapshot
    if snapshot["status"] == "requested" and not force_refresh:
        return snapshot
    if snapshot["status"] == "ready" and not force_refresh:
        return snapshot

    context_payload = build_activity_analysis_context(conn, detail_payload)
    requested_at = datetime.now().isoformat()
    if question is _KEEP_QUESTION:
        existing = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
        question = _request_question(existing) if existing and existing["status"] == "pending" else None
    upsert_activity_analysis_request_row(
        conn,
        activity_id=detail_payload["activity"]["id"],
        status="pending",
        requested_at=requested_at,
        requested_via=requested_via,
        context_signature=context_payload["context_signature"],
        last_error=None,
        question=_clean_question(question),
    )
    conn.commit()
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    analysis_row = get_activity_analysis_row(conn, detail_payload["activity"]["id"])
    return _serialize_analysis_snapshot(
        context_payload=context_payload,
        analysis_row=analysis_row,
        request_row=request_row,
    )


ANALYSIS_RULES = [
    "The athlete already sees context.session_read on the page: its verdict, comparison signals, next-time instruction and watch item. Never restate them; build on them, explain them, or disagree with evidence.",
    "Use metrics only as evidence for a judgment or comparison; do not recap the workout.",
    "Compare with recent_context only when it supports a real pattern such as accumulating load, repeated intensity, recovery spacing or a modality imbalance. Do not claim a trend from one data point.",
    "Treat the athlete's feedback note as first-class evidence, while distinguishing their report from measured data.",
    "If feedback.fuelling is 'bonked', weigh under-fuelling as a likely cause of a late fade in power, pace or heart rate before blaming fitness. 'overate' points to GI discomfort rather than fitness.",
    "If the evidence cannot answer the question, say so plainly and name the data that would.",
    "Do not invent facts that are not supported by the provided context.",
    "Do not give medical advice or injury diagnosis.",
]


def _analysis_instructions(question: Optional[str]) -> dict:
    if question:
        task = (
            "Act as the athlete's endurance and strength coach and answer their question about this session: "
            f"\"{question}\". Answer it directly, using this session's data, session_read and recent_context as evidence."
        )
        schema = {
            "headline": "the direct answer in one short sentence",
            "summary": "2-4 sentences explaining the answer and what to do about it",
            "key_observations": "0-3 pieces of evidence behind the answer that the page does not already show",
            "limitations": "0-3 evidence gaps that limit the answer",
            "confidence_note": "single sentence distinguishing direct evidence from inference",
        }
    else:
        task = (
            "Act as the athlete's endurance and strength coach. The page already shows a rule-based read of this session "
            "(context.session_read). Connect the dots it cannot: why the session went the way it did, how it fits the recent "
            "training trajectory, and whether you agree with its next-time instruction."
        )
        schema = {
            "headline": "one short coaching conclusion that adds to the session_read verdict, not a repeat of it",
            "summary": "2-4 sentences: the likely why, how it fits recent work, and the practical implication for the next 24-72 hours",
            "key_observations": "0-3 interpreted signals the page does not already show",
            "limitations": "0-3 evidence gaps that materially limit the interpretation",
            "confidence_note": "single sentence distinguishing direct evidence from inference",
        }
    return {"task": task, "output_schema": schema, "rules": ANALYSIS_RULES}


def get_activity_analysis_context_payload(conn: sqlite3.Connection, detail_payload: dict) -> dict:
    context_payload = build_activity_analysis_context(conn, detail_payload)
    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    question = _request_question(request_row) if request_row and request_row["status"] == "pending" else None
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
        "question": question,
        "instructions": _analysis_instructions(question),
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

    request_row = get_activity_analysis_request_row(conn, detail_payload["activity"]["id"])
    analysis = {
        "question": _request_question(request_row) if request_row and request_row["status"] == "pending" else None,
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
