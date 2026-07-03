import csv
import hashlib
import io
import json
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from ..repositories.activities import get_activity_row
from ..repositories.fitbod_imports import (
    clear_fitbod_session_match_for_activity,
    count_fitbod_import_rows_by_kind,
    create_fitbod_import_batch,
    create_fitbod_import_row,
    delete_fitbod_workout_session_tree,
    create_fitbod_workout_exercise,
    create_fitbod_workout_session,
    create_fitbod_workout_set,
    delete_fitbod_session_decision,
    refresh_fitbod_import_batch_counts,
    get_fitbod_import_batch_by_hash,
    get_fitbod_session_decision,
    get_fitbod_session_by_activity_id,
    get_fitbod_workout_session,
    get_fitbod_workout_session_by_timestamp,
    get_latest_fitbod_import_batch,
    list_fitbod_workout_exercises_by_session,
    list_fitbod_workout_sessions_by_batch,
    list_fitbod_workout_sets_by_exercise,
    mark_fitbod_import_rows_ignored_for_session,
    update_fitbod_session_match,
    upsert_fitbod_session_decision,
)

PARSER_VERSION = "fitbod_csv_v1"
GROUPING_VERSION = "timestamp_group_v1"
NON_STRENGTH_EXERCISES = {
    "bike",
    "biking",
    "cycling",
    "elliptical",
    "hike",
    "hiking",
    "ride",
    "row",
    "rowing",
    "run",
    "running",
    "stairclimber",
    "stairmaster",
    "swim",
    "swimming",
    "walk",
    "walking",
    "yoga",
}
NON_STRENGTH_PREFIXES = tuple(sorted(NON_STRENGTH_EXERCISES, key=len, reverse=True))


@dataclass
class ParsedFitbodRow:
    row_index: int
    timestamp: datetime
    timestamp_text: str
    exercise_name: str
    reps: Optional[int]
    weight_kg: Optional[float]
    duration_seconds: Optional[float]
    distance_m: Optional[float]
    incline: Optional[float]
    resistance: Optional[float]
    is_warmup: bool
    note: Optional[str]
    multiplier: Optional[float]
    raw: dict


def _parse_datetime(value: str) -> datetime:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Missing Date")

    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
        raw.replace(" ", "T"),
    ]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is not None:
                return parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported Date format: {raw}")


def _parse_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _parse_int(value: object) -> Optional[int]:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _parse_bool(value: object) -> bool:
    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _looks_non_strength(exercise_name: str) -> bool:
    normalized = _normalize_name(exercise_name)
    if not normalized:
        return False
    if normalized in NON_STRENGTH_EXERCISES:
        return True
    return normalized.startswith(NON_STRENGTH_PREFIXES)


def _title_from_exercises(exercises: list[str]) -> str:
    unique = []
    seen = set()
    for exercise in exercises:
        if exercise not in seen:
            unique.append(exercise)
            seen.add(exercise)
    if not unique:
        return "Strength workout"
    if len(unique) == 1:
        return unique[0]
    if len(unique) == 2:
        return f"{unique[0]} + {unique[1]}"
    return f"{unique[0]} + {unique[1]} + {len(unique) - 2} more"


def _safe_round(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _get_strength_activity_date_range(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT MIN(date) AS earliest_date, MAX(date) AS latest_date, COUNT(*) AS activity_count
        FROM activities
        WHERE type = 'WeightTraining'
        """
    ).fetchone()
    return {
        "earliest_date": row["earliest_date"] if row else None,
        "latest_date": row["latest_date"] if row else None,
        "activity_count": int(row["activity_count"]) if row else 0,
    }


def _build_session_review_metadata(session_row: sqlite3.Row | dict, activity_range: dict) -> dict:
    workout_date = session_row["workout_date"]
    earliest_date = activity_range.get("earliest_date")
    latest_date = activity_range.get("latest_date")
    match_status = session_row["match_status"]

    if match_status == "rejected":
        return {
            "review_state": "rejected",
            "actionable": False,
            "range_reason": None,
        }

    if earliest_date and workout_date < earliest_date:
        return {
            "review_state": "outside_activity_range",
            "actionable": False,
            "range_reason": f"Session is older than the earliest imported strength activity ({earliest_date}).",
        }
    if latest_date and workout_date > latest_date:
        return {
            "review_state": "outside_activity_range",
            "actionable": False,
            "range_reason": f"Session is newer than the latest imported strength activity ({latest_date}).",
        }
    if match_status == "matched":
        return {
            "review_state": "matched",
            "actionable": False,
            "range_reason": None,
        }
    if match_status == "ambiguous":
        return {
            "review_state": "ambiguous",
            "actionable": True,
            "range_reason": None,
        }
    return {
        "review_state": "unmatched",
        "actionable": True,
        "range_reason": None,
    }


def _serialize_exercise_with_sets(conn: sqlite3.Connection, exercise_row: sqlite3.Row) -> dict:
    sets = []
    for set_row in list_fitbod_workout_sets_by_exercise(conn, int(exercise_row["id"])):
        sets.append(
            {
                "id": set_row["id"],
                "set_order": set_row["set_order"],
                "reps": set_row["reps"],
                "weight_kg": set_row["weight_kg"],
                "duration_seconds": set_row["duration_seconds"],
                "distance_m": set_row["distance_m"],
                "incline": set_row["incline"],
                "resistance": set_row["resistance"],
                "is_warmup": bool(set_row["is_warmup"]),
                "note": set_row["note"],
                "multiplier": set_row["multiplier"],
            }
        )
    return {
        "id": exercise_row["id"],
        "exercise_order": exercise_row["exercise_order"],
        "exercise_name": exercise_row["exercise_name"],
        "set_count": exercise_row["set_count"],
        "rep_count": exercise_row["rep_count"],
        "total_volume_kg": exercise_row["total_volume_kg"],
        "work_set_count": exercise_row["work_set_count"],
        "warmup_set_count": exercise_row["warmup_set_count"],
        "sets": sets,
    }


def _serialize_session(conn: sqlite3.Connection, session_row: sqlite3.Row, activity_range: Optional[dict] = None) -> dict:
    matched_activity = None
    if session_row["matched_activity_id"]:
        activity_row = get_activity_row(conn, session_row["matched_activity_id"])
        if activity_row:
            matched_activity = {
                "id": activity_row["id"],
                "date": activity_row["date"],
                "type": activity_row["type"],
                "name": activity_row["name"],
                "duration_min": activity_row["duration_min"],
            }
    exercises = [
        _serialize_exercise_with_sets(conn, exercise_row)
        for exercise_row in list_fitbod_workout_exercises_by_session(conn, int(session_row["id"]))
    ]
    return {
        "id": session_row["id"],
        "batch_id": session_row["batch_id"],
        "session_key": session_row["session_key"],
        "workout_timestamp": session_row["workout_timestamp"],
        "workout_date": session_row["workout_date"],
        "title": session_row["title"],
        "exercise_count": session_row["exercise_count"],
        "set_count": session_row["set_count"],
        "rep_count": session_row["rep_count"],
        "total_volume_kg": session_row["total_volume_kg"],
        "total_duration_seconds": session_row["total_duration_seconds"],
        "total_distance_m": session_row["total_distance_m"],
        "calories": session_row["calories"],
        "match_status": session_row["match_status"],
        "match_confidence": session_row["match_confidence"],
        "match_provenance": session_row["match_provenance"],
        "match_reason": session_row["match_reason"],
        "matched_activity": matched_activity,
        "exercises": exercises,
        **(_build_session_review_metadata(session_row, activity_range or {"earliest_date": None, "latest_date": None, "activity_count": 0})),
    }


def _serialize_batch(conn: sqlite3.Connection, batch_row: sqlite3.Row) -> dict:
    activity_range = _get_strength_activity_date_range(conn)
    sessions = []
    for session_row in list_fitbod_workout_sessions_by_batch(conn, int(batch_row["id"])):
        item = _serialize_session(conn, session_row, activity_range)
        item["candidate_activities"] = list_match_candidates_for_session(conn, int(session_row["id"]))
        sessions.append(item)
    matched_count = sum(1 for session in sessions if session["match_status"] == "matched")
    ambiguous_count = sum(1 for session in sessions if session["match_status"] == "ambiguous")
    unmatched_count = sum(1 for session in sessions if session["match_status"] == "unmatched")
    outside_activity_range_count = sum(1 for session in sessions if session["review_state"] == "outside_activity_range")
    actionable_count = sum(1 for session in sessions if session["actionable"])
    rejected_count = sum(1 for session in sessions if session["review_state"] == "rejected")
    return {
        "id": batch_row["id"],
        "file_name": batch_row["file_name"],
        "file_hash": batch_row["file_hash"],
        "parser_version": batch_row["parser_version"],
        "grouping_version": batch_row["grouping_version"],
        "imported_at": batch_row["imported_at"],
        "raw_row_count": batch_row["raw_row_count"],
        "strength_row_count": batch_row["strength_row_count"],
        "ignored_row_count": batch_row["ignored_row_count"],
        "rejected_row_count": batch_row["rejected_row_count"],
        "session_count": batch_row["session_count"],
        "matched_count": matched_count,
        "ambiguous_count": ambiguous_count,
        "unmatched_count": unmatched_count,
        "outside_activity_range_count": outside_activity_range_count,
        "actionable_count": actionable_count,
        "rejected_count": rejected_count,
        "activity_range": activity_range,
        "ignored_rows_reported": count_fitbod_import_rows_by_kind(conn, int(batch_row["id"]), "ignored"),
        "rejected_rows_reported": count_fitbod_import_rows_by_kind(conn, int(batch_row["id"]), "rejected"),
        "sessions": sessions,
    }


def _manual_match_resolution_from_decision(conn: sqlite3.Connection, decision_row: sqlite3.Row, session: dict) -> dict:
    activity_id = decision_row["activity_id"]
    activity_row = get_activity_row(conn, activity_id) if activity_id else None
    if not activity_row or activity_row["type"] != "WeightTraining":
        return {
            "match_status": "unmatched",
            "matched_activity_id": None,
            "match_confidence": None,
            "match_provenance": None,
            "match_reason": "Saved manual Fitbod link could not be restored because the linked activity is unavailable.",
        }
    return {
        "match_status": "matched",
        "matched_activity_id": activity_id,
        "match_confidence": 1.0,
        "match_provenance": "matched_manually",
        "match_reason": decision_row["reason"] or "Linked manually by the athlete.",
    }


def _match_score_for_activity(session: dict, activity_row: sqlite3.Row) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    if activity_row["type"] != "WeightTraining":
        return 0.0, ["Not a strength activity."]
    if activity_row["date"] != session["workout_date"]:
        return 0.0, ["Workout date does not match."]

    score += 0.55
    reasons.append("Same workout date.")

    duration_min = activity_row["duration_min"]
    session_minutes = (session["total_duration_seconds"] or 0) / 60 if session["total_duration_seconds"] else None
    if duration_min and session_minutes:
        delta = abs(float(duration_min) - float(session_minutes))
        if delta <= 15:
            score += 0.15
            reasons.append("Duration is close.")
        elif delta <= 30:
            score += 0.07
            reasons.append("Duration is plausible.")

    activity_name = _normalize_name(activity_row["name"])
    exercise_tokens = {_normalize_name(name) for name in session["exercise_names"]}
    exercise_tokens.discard("")
    if activity_name and exercise_tokens:
        overlaps = sum(1 for token in exercise_tokens if token and token in activity_name)
        if overlaps:
            ratio = min(overlaps / max(len(exercise_tokens), 1), 1.0)
            score += 0.20 * ratio
            reasons.append("Activity name overlaps grouped exercise names.")

    return min(score, 0.99), reasons


def _build_match_resolution(session: dict, candidates: list[sqlite3.Row]) -> dict:
    scored = []
    for candidate in candidates:
        score, reasons = _match_score_for_activity(session, candidate)
        if score <= 0:
            continue
        scored.append(
            {
                "activity_id": candidate["id"],
                "activity_name": candidate["name"],
                "activity_date": candidate["date"],
                "duration_min": candidate["duration_min"],
                "score": round(score, 2),
                "reason": " ".join(reasons),
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["activity_id"]))
    if not scored:
        return {
            "match_status": "unmatched",
            "matched_activity_id": None,
            "match_confidence": None,
            "match_provenance": None,
            "match_reason": "No same-day WeightTraining activities were available.",
        }

    top = scored[0]
    if len(scored) == 1 and top["score"] >= 0.55:
        return {
            "match_status": "matched",
            "matched_activity_id": top["activity_id"],
            "match_confidence": top["score"],
            "match_provenance": "matched_automatically",
            "match_reason": top["reason"],
        }

    if len(scored) > 1 and top["score"] >= 0.85 and (top["score"] - scored[1]["score"]) >= 0.15:
        return {
            "match_status": "matched",
            "matched_activity_id": top["activity_id"],
            "match_confidence": top["score"],
            "match_provenance": "matched_automatically",
            "match_reason": top["reason"],
        }

    return {
        "match_status": "ambiguous" if len(scored) > 1 else "unmatched",
        "matched_activity_id": None,
        "match_confidence": top["score"],
        "match_provenance": None,
        "match_reason": "Multiple plausible strength activities were found." if len(scored) > 1 else "No conservative automatic match was made.",
    }


def list_match_candidates_for_session(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    session_row = get_fitbod_workout_session(conn, session_id)
    if not session_row:
        return []
    exercise_names = [
        row["exercise_name"]
        for row in list_fitbod_workout_exercises_by_session(conn, session_id)
    ]
    session = {
        "workout_date": session_row["workout_date"],
        "total_duration_seconds": session_row["total_duration_seconds"],
        "exercise_names": exercise_names,
    }
    candidates = conn.execute(
        """
        SELECT id, date, type, name, duration_min
        FROM activities
        WHERE type = 'WeightTraining' AND date = ?
        ORDER BY created_at DESC, id DESC
        """,
        (session_row["workout_date"],),
    ).fetchall()
    output = []
    for candidate in candidates:
        score, reasons = _match_score_for_activity(session, candidate)
        output.append(
            {
                "id": candidate["id"],
                "date": candidate["date"],
                "name": candidate["name"],
                "duration_min": candidate["duration_min"],
                "score": round(score, 2) if score else 0,
                "reason": " ".join(reasons) if reasons else None,
            }
        )
    output.sort(key=lambda item: (-item["score"], item["id"]))
    return output


def import_fitbod_csv_data(conn: sqlite3.Connection, *, file_name: Optional[str], csv_text: str) -> dict:
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="Fitbod CSV payload is empty.")

    file_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    existing_batch = get_fitbod_import_batch_by_hash(conn, file_hash)
    if existing_batch:
        return _serialize_batch(conn, existing_batch)

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail=f"Could not read Fitbod CSV: {exc}") from exc

    if not reader.fieldnames or "Date" not in reader.fieldnames or "Exercise" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="Unsupported Fitbod CSV format. Expected Date and Exercise columns.")

    parsed_rows: list[ParsedFitbodRow] = []
    ignored_rows: list[dict] = []
    rejected_rows: list[dict] = []

    for row_index, raw_row in enumerate(reader, start=2):
        cleaned_row = {key: (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items()}
        exercise_name = (cleaned_row.get("Exercise") or "").strip()
        timestamp_text = (cleaned_row.get("Date") or "").strip()

        if _looks_non_strength(exercise_name):
            ignored_rows.append(
                {
                    "row_index": row_index,
                    "workout_timestamp": timestamp_text or None,
                    "exercise_name": exercise_name or None,
                    "ignore_reason": f"Filtered non-strength modality row: {exercise_name}.",
                    "raw": cleaned_row,
                }
            )
            continue

        try:
            timestamp = _parse_datetime(timestamp_text)
            if not exercise_name:
                raise ValueError("Missing Exercise")
            parsed_rows.append(
                ParsedFitbodRow(
                    row_index=row_index,
                    timestamp=timestamp,
                    timestamp_text=timestamp.isoformat(timespec="seconds"),
                    exercise_name=exercise_name,
                    reps=_parse_int(cleaned_row.get("Reps")),
                    weight_kg=_parse_float(cleaned_row.get("Weight(kg)")),
                    duration_seconds=_parse_float(cleaned_row.get("Duration(s)")),
                    distance_m=_parse_float(cleaned_row.get("Distance(m)")),
                    incline=_parse_float(cleaned_row.get("Incline")),
                    resistance=_parse_float(cleaned_row.get("Resistance")),
                    is_warmup=_parse_bool(cleaned_row.get("isWarmup")),
                    note=(cleaned_row.get("Note") or None),
                    multiplier=_parse_float(cleaned_row.get("multiplier")),
                    raw=cleaned_row,
                )
            )
        except (TypeError, ValueError) as exc:
            rejected_rows.append(
                {
                    "row_index": row_index,
                    "workout_timestamp": timestamp_text or None,
                    "exercise_name": exercise_name or None,
                    "ignore_reason": str(exc),
                    "raw": cleaned_row,
                }
            )

    session_groups: "OrderedDict[str, list[ParsedFitbodRow]]" = OrderedDict()
    for row in sorted(parsed_rows, key=lambda item: (item.timestamp, item.row_index)):
        session_groups.setdefault(row.timestamp_text, []).append(row)

    sessions_to_persist = []
    matched_count = 0
    ambiguous_count = 0
    unmatched_count = 0
    new_session_count = 0
    updated_session_count = 0
    preserved_manual_match_count = 0
    preserved_rejected_count = 0
    activity_range = _get_strength_activity_date_range(conn)
    affected_previous_batch_ids: set[int] = set()

    for session_key, rows in session_groups.items():
        exercises_map: "OrderedDict[str, list[ParsedFitbodRow]]" = OrderedDict()
        for row in rows:
            exercises_map.setdefault(row.exercise_name, []).append(row)

        exercise_names = list(exercises_map.keys())
        set_count = len(rows)
        rep_count = sum(row.reps or 0 for row in rows)
        total_volume = 0.0
        has_volume = False
        total_duration = 0.0
        has_duration = False
        total_distance = 0.0
        has_distance = False

        for row in rows:
            effective_multiplier = row.multiplier if row.multiplier not in (None, 0) else 1.0
            if row.weight_kg is not None and row.reps is not None:
                total_volume += float(row.weight_kg) * float(row.reps) * float(effective_multiplier)
                has_volume = True
            if row.duration_seconds is not None:
                total_duration += float(row.duration_seconds)
                has_duration = True
            if row.distance_m is not None:
                total_distance += float(row.distance_m)
                has_distance = True

        session_data = {
            "session_key": session_key,
            "workout_timestamp": session_key,
            "workout_date": rows[0].timestamp.date().isoformat(),
            "title": _title_from_exercises(exercise_names),
            "exercise_names": exercise_names,
            "exercise_count": len(exercise_names),
            "set_count": set_count,
            "rep_count": rep_count,
            "total_volume_kg": _safe_round(total_volume, 1) if has_volume else None,
            "total_duration_seconds": _safe_round(total_duration, 1) if has_duration else None,
            "total_distance_m": _safe_round(total_distance, 1) if has_distance else None,
            "calories": None,
            "rows": rows,
            "exercises_map": exercises_map,
        }

        existing_session = get_fitbod_workout_session_by_timestamp(conn, session_key)
        decision_row = get_fitbod_session_decision(conn, session_key)

        if decision_row and decision_row["decision_type"] == "rejected_manually":
            preserved_rejected_count += 1
            ignored_rows.extend(
                {
                    "row_index": row.row_index,
                    "workout_timestamp": row.timestamp_text,
                    "exercise_name": row.exercise_name,
                    "ignore_reason": decision_row["reason"] or "Rejected manually from the Fitbod review queue.",
                    "raw": row.raw,
                }
                for row in rows
            )
            continue

        if decision_row and decision_row["decision_type"] == "matched_manually":
            match = _manual_match_resolution_from_decision(conn, decision_row, session_data)
            preserved_manual_match_count += 1
        elif existing_session and existing_session["match_provenance"] == "matched_manually":
            match = {
                "match_status": existing_session["match_status"],
                "matched_activity_id": existing_session["matched_activity_id"],
                "match_confidence": existing_session["match_confidence"] or 1.0,
                "match_provenance": "matched_manually",
                "match_reason": existing_session["match_reason"] or "Linked manually by the athlete.",
            }
            preserved_manual_match_count += 1
        else:
            candidates = conn.execute(
                """
                SELECT id, date, type, name, duration_min
                FROM activities
                WHERE type = 'WeightTraining' AND date = ?
                ORDER BY created_at DESC, id DESC
                """,
                (session_data["workout_date"],),
            ).fetchall()
            match = _build_match_resolution(session_data, candidates)

        review_metadata = _build_session_review_metadata(
            {
                "workout_date": session_data["workout_date"],
                "match_status": match["match_status"],
            },
            activity_range,
        )
        if review_metadata["review_state"] == "outside_activity_range" and match["match_status"] == "unmatched":
            match["match_reason"] = review_metadata["range_reason"]
        session_data.update(match)
        session_data["existing_session_id"] = int(existing_session["id"]) if existing_session else None
        session_data["existing_batch_id"] = int(existing_session["batch_id"]) if existing_session else None
        if match["match_status"] == "matched":
            matched_count += 1
        elif match["match_status"] == "ambiguous":
            ambiguous_count += 1
        else:
            unmatched_count += 1
        if existing_session:
            updated_session_count += 1
        else:
            new_session_count += 1
        sessions_to_persist.append(session_data)

    imported_at = datetime.now().isoformat()
    batch_id = create_fitbod_import_batch(
        conn,
        file_name=file_name,
        file_hash=file_hash,
        parser_version=PARSER_VERSION,
        grouping_version=GROUPING_VERSION,
        imported_at=imported_at,
        raw_row_count=len(parsed_rows) + len(ignored_rows) + len(rejected_rows),
        strength_row_count=sum(len(session["rows"]) for session in sessions_to_persist),
        ignored_row_count=len(ignored_rows),
        rejected_row_count=len(rejected_rows),
        session_count=len(sessions_to_persist),
        matched_count=matched_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
    )

    for ignored in ignored_rows:
        create_fitbod_import_row(
            conn,
            batch_id=batch_id,
            row_index=ignored["row_index"],
            row_kind="ignored",
            workout_timestamp=ignored["workout_timestamp"],
            exercise_name=ignored["exercise_name"],
            ignore_reason=ignored["ignore_reason"],
            raw_json=json.dumps(ignored["raw"]),
        )

    for rejected in rejected_rows:
        create_fitbod_import_row(
            conn,
            batch_id=batch_id,
            row_index=rejected["row_index"],
            row_kind="rejected",
            workout_timestamp=rejected["workout_timestamp"],
            exercise_name=rejected["exercise_name"],
            ignore_reason=rejected["ignore_reason"],
            raw_json=json.dumps(rejected["raw"]),
        )

    for session in sessions_to_persist:
        if session["matched_activity_id"]:
            clear_fitbod_session_match_for_activity(conn, session["matched_activity_id"])

        existing_session_id = session["existing_session_id"]
        if existing_session_id:
            existing_batch_id = session["existing_batch_id"]
            if existing_batch_id and existing_batch_id != batch_id:
                affected_previous_batch_ids.add(existing_batch_id)
            delete_fitbod_workout_session_tree(conn, existing_session_id)
            session_id = create_fitbod_workout_session(
                conn,
                batch_id=batch_id,
                session_key=session["session_key"],
                workout_timestamp=session["workout_timestamp"],
                workout_date=session["workout_date"],
                title=session["title"],
                exercise_count=session["exercise_count"],
                set_count=session["set_count"],
                rep_count=session["rep_count"],
                total_volume_kg=session["total_volume_kg"],
                total_duration_seconds=session["total_duration_seconds"],
                total_distance_m=session["total_distance_m"],
                calories=session["calories"],
                match_status=session["match_status"],
                matched_activity_id=session["matched_activity_id"],
                match_confidence=session["match_confidence"],
                match_provenance=session["match_provenance"],
                match_reason=session["match_reason"],
            )
        else:
            session_id = create_fitbod_workout_session(
                conn,
                batch_id=batch_id,
                session_key=session["session_key"],
                workout_timestamp=session["workout_timestamp"],
                workout_date=session["workout_date"],
                title=session["title"],
                exercise_count=session["exercise_count"],
                set_count=session["set_count"],
                rep_count=session["rep_count"],
                total_volume_kg=session["total_volume_kg"],
                total_duration_seconds=session["total_duration_seconds"],
                total_distance_m=session["total_distance_m"],
                calories=session["calories"],
                match_status=session["match_status"],
                matched_activity_id=session["matched_activity_id"],
                match_confidence=session["match_confidence"],
                match_provenance=session["match_provenance"],
                match_reason=session["match_reason"],
            )

        for row in session["rows"]:
            create_fitbod_import_row(
                conn,
                batch_id=batch_id,
                row_index=row.row_index,
                row_kind="strength",
                workout_timestamp=row.timestamp_text,
                exercise_name=row.exercise_name,
                ignore_reason=None,
                raw_json=json.dumps(row.raw),
            )

        for exercise_order, (exercise_name, exercise_rows) in enumerate(session["exercises_map"].items(), start=1):
            exercise_volume = 0.0
            has_exercise_volume = False
            work_set_count = sum(1 for row in exercise_rows if not row.is_warmup)
            warmup_set_count = sum(1 for row in exercise_rows if row.is_warmup)
            rep_count = sum(row.reps or 0 for row in exercise_rows)

            for row in exercise_rows:
                effective_multiplier = row.multiplier if row.multiplier not in (None, 0) else 1.0
                if row.weight_kg is not None and row.reps is not None:
                    exercise_volume += float(row.weight_kg) * float(row.reps) * float(effective_multiplier)
                    has_exercise_volume = True

            exercise_id = create_fitbod_workout_exercise(
                conn,
                session_id=session_id,
                exercise_order=exercise_order,
                exercise_name=exercise_name,
                set_count=len(exercise_rows),
                rep_count=rep_count,
                total_volume_kg=_safe_round(exercise_volume, 1) if has_exercise_volume else None,
                work_set_count=work_set_count,
                warmup_set_count=warmup_set_count,
            )

            for set_order, row in enumerate(exercise_rows, start=1):
                create_fitbod_workout_set(
                    conn,
                    exercise_id=exercise_id,
                    set_order=set_order,
                    reps=row.reps,
                    weight_kg=row.weight_kg,
                    duration_seconds=row.duration_seconds,
                    distance_m=row.distance_m,
                    incline=row.incline,
                    resistance=row.resistance,
                    is_warmup=row.is_warmup,
                    note=row.note,
                    multiplier=row.multiplier,
                )

    for previous_batch_id in affected_previous_batch_ids:
        refresh_fitbod_import_batch_counts(conn, previous_batch_id)

    conn.commit()
    batch_row = get_fitbod_import_batch_by_hash(conn, file_hash)
    payload = _serialize_batch(conn, batch_row) if batch_row else {"status": "ok", "batch_id": batch_id}
    payload["new_session_count"] = new_session_count
    payload["updated_session_count"] = updated_session_count
    payload["preserved_manual_match_count"] = preserved_manual_match_count
    payload["preserved_rejected_count"] = preserved_rejected_count
    return payload


def get_latest_fitbod_import_data(conn: sqlite3.Connection) -> Optional[dict]:
    batch_row = get_latest_fitbod_import_batch(conn)
    if not batch_row:
        return None
    return _serialize_batch(conn, batch_row)


def link_fitbod_session_to_activity_data(conn: sqlite3.Connection, session_id: int, activity_id: Optional[str]) -> dict:
    session_row = get_fitbod_workout_session(conn, session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail=f"Fitbod workout session not found: {session_id}")

    if activity_id is not None:
        activity_row = get_activity_row(conn, activity_id)
        if not activity_row:
            raise HTTPException(status_code=404, detail=f"Activity not found: {activity_id}")
        if activity_row["type"] != "WeightTraining":
            raise HTTPException(status_code=400, detail="Fitbod strength detail can only link to WeightTraining activities.")
        clear_fitbod_session_match_for_activity(conn, activity_id)
        upsert_fitbod_session_decision(
            conn,
            workout_timestamp=session_row["workout_timestamp"],
            decision_type="matched_manually",
            activity_id=activity_id,
            reason="Linked manually by the athlete.",
        )
        update_fitbod_session_match(
            conn,
            session_id=session_id,
            matched_activity_id=activity_id,
            match_status="matched",
            match_confidence=1.0,
            match_provenance="matched_manually",
            match_reason="Linked manually by the athlete.",
        )
    else:
        delete_fitbod_session_decision(conn, session_row["workout_timestamp"])
        update_fitbod_session_match(
            conn,
            session_id=session_id,
            matched_activity_id=None,
            match_status="unmatched",
            match_confidence=None,
            match_provenance=None,
            match_reason="Link removed manually.",
        )

    conn.commit()
    updated = get_fitbod_workout_session(conn, session_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Could not reload Fitbod workout session after linking.")
    payload = _serialize_session(conn, updated, _get_strength_activity_date_range(conn))
    payload["candidate_activities"] = list_match_candidates_for_session(conn, session_id)
    return payload


def reject_fitbod_session_data(conn: sqlite3.Connection, session_id: int, reason: Optional[str]) -> dict:
    session_row = get_fitbod_workout_session(conn, session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail=f"Fitbod workout session not found: {session_id}")

    reject_reason = (reason or "").strip() or "Rejected manually from the Fitbod review queue."
    upsert_fitbod_session_decision(
        conn,
        workout_timestamp=session_row["workout_timestamp"],
        decision_type="rejected_manually",
        activity_id=None,
        reason=reject_reason,
    )
    mark_fitbod_import_rows_ignored_for_session(
        conn,
        batch_id=int(session_row["batch_id"]),
        workout_timestamp=session_row["workout_timestamp"],
        ignore_reason=reject_reason,
    )
    delete_fitbod_workout_session_tree(conn, session_id)
    refresh_fitbod_import_batch_counts(conn, int(session_row["batch_id"]))
    conn.commit()
    return {
        "status": "rejected",
        "session_id": session_id,
        "batch_id": int(session_row["batch_id"]),
        "reason": reject_reason,
    }


def get_fitbod_strength_detail_for_activity(conn: sqlite3.Connection, activity_id: str) -> Optional[dict]:
    session_row = get_fitbod_session_by_activity_id(conn, activity_id)
    if not session_row:
        return None
    payload = _serialize_session(conn, session_row, _get_strength_activity_date_range(conn))
    return {
        "status": "enriched",
        "session": payload,
    }
