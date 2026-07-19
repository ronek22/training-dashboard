import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import fitdecode
from fastapi import HTTPException

from ..repositories.activities import get_latest_activity_date, upsert_activity_row
from .activity_sources import find_activity_match, upsert_source_ref


HEALTHFIT_SOURCE = "healthfit"
FILENAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-([^-]+)\.fit$", re.IGNORECASE)


SPORT_TYPES = {
    "running": "Run", "cycling": "Ride", "walking": "Walk", "hiking": "Hike",
    "strength_training": "WeightTraining", "training": "WeightTraining",
    "swimming": "Swim", "yoga": "Yoga", "basketball": "Basketball",
}


def healthfit_directory() -> Path:
    return Path(os.getenv("HEALTHFIT_DIR", "/healthfit"))


def _fields(message) -> dict:
    return {field.name: field.value for field in message.fields}


def _iso(value) -> Optional[str]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_healthfit_file(path: Path, include_streams: bool = False) -> dict:
    session = {}
    file_id = {}
    records = []
    try:
        with fitdecode.FitReader(path) as fit:
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "file_id":
                    file_id = _fields(frame)
                elif frame.name == "session" and not session:
                    session = _fields(frame)
                elif include_streams and frame.name == "record":
                    records.append(_fields(frame))
    except (OSError, fitdecode.FitError) as exc:
        raise ValueError(f"Could not decode {path.name}: {exc}") from exc
    if not session:
        raise ValueError(f"No FIT session found in {path.name}")

    name_match = FILENAME_PATTERN.match(path.name)
    local_date = name_match.group(1) if name_match else None
    title = name_match.group(3) if name_match else path.stem
    sport = str(session.get("sport") or "").lower()
    activity_type = SPORT_TYPES.get(sport)
    if activity_type is None:
        normalized_title = title.lower()
        if "strength" in normalized_title:
            activity_type = "WeightTraining"
        elif "run" in normalized_title:
            activity_type = "Run"
        elif "cycl" in normalized_title:
            activity_type = "Ride"
        elif "walk" in normalized_title:
            activity_type = "Walk"
        else:
            activity_type = sport.title().replace("_", "") or "Workout"

    started_at = _iso(session.get("start_time") or file_id.get("time_created"))
    date = local_date or (started_at[:10] if started_at else None)
    if not date:
        raise ValueError(f"No workout date found in {path.name}")
    distance_m = session.get("total_distance")
    duration_s = session.get("total_timer_time") or session.get("total_elapsed_time")
    avg_hr = session.get("avg_heart_rate")
    avg_speed = session.get("enhanced_avg_speed") or session.get("avg_speed")
    pace = None
    if activity_type == "Run" and avg_speed:
        pace_seconds = round(1000 / float(avg_speed))
        pace = f"{pace_seconds // 60}:{pace_seconds % 60:02d}"
    file_hash = _file_hash(path)
    activity = {
        "id": f"healthfit:{file_hash[:24]}", "date": date, "type": activity_type,
        "name": title, "distance_km": round(float(distance_m) / 1000, 2) if distance_m is not None else None,
        "duration_min": round(float(duration_s) / 60, 1) if duration_s is not None else None,
        "avg_hr": round(float(avg_hr)) if avg_hr is not None else None,
        "max_hr": round(float(session["max_heart_rate"])) if session.get("max_heart_rate") is not None else None,
        "avg_pace": pace,
        "avg_watts": round(float(session["avg_power"]), 1) if session.get("avg_power") is not None else None,
        "elevation_m": round(float(session["total_ascent"])) if session.get("total_ascent") is not None else None,
        "calories": round(float(session["total_calories"])) if session.get("total_calories") is not None else None,
        "zone2": False, "notes": None,
    }
    streams = None
    if include_streams and records:
        start = session.get("start_time")
        streams = {}
        mapping = {
            "heart_rate": "heartrate", "power": "watts", "cadence": "cadence",
            "distance": "distance", "enhanced_altitude": "altitude", "enhanced_speed": "velocity_smooth",
        }
        if start:
            streams["time"] = {"data": [max(0, int((row["timestamp"] - start).total_seconds())) for row in records if row.get("timestamp")]}
        for fit_key, stream_key in mapping.items():
            values = [row.get(fit_key) for row in records]
            if any(value is not None for value in values):
                streams[stream_key] = {"data": values}
        latlng = [
            [row.get("position_lat") * (180 / 2**31), row.get("position_long") * (180 / 2**31)]
            for row in records if row.get("position_lat") is not None and row.get("position_long") is not None
        ]
        if latlng:
            streams["latlng"] = {"data": latlng}
    return {"file_hash": file_hash, "file_name": path.name, "started_at": started_at, "activity": activity, "streams": streams}


def _existing_ref(conn: sqlite3.Connection, file_hash: str):
    return conn.execute(
        "SELECT * FROM activity_source_refs WHERE source = ? AND external_id = ?",
        (HEALTHFIT_SOURCE, file_hash),
    ).fetchone()


def _existing_file_ref(conn: sqlite3.Connection, file_name: str):
    return conn.execute(
        "SELECT * FROM activity_source_refs WHERE source = ? AND (file_name = ? OR external_id = ?)",
        (HEALTHFIT_SOURCE, file_name, f"filename:{file_name}"),
    ).fetchone()


def preview_healthfit_import(conn: sqlite3.Connection) -> dict:
    directory = healthfit_directory()
    initialized = bool(conn.execute(
        "SELECT 1 FROM activity_source_refs WHERE source = ? LIMIT 1",
        (HEALTHFIT_SOURCE,),
    ).fetchone())
    if not directory.is_dir():
        return {
            "configured": False, "initialized": initialized, "directory": str(directory),
            "cutoff_date": get_latest_activity_date(conn), "items": [], "counts": {},
        }
    cutoff = get_latest_activity_date(conn)
    items = []
    for path in sorted(directory.glob("*.fit")):
        name_match = FILENAME_PATTERN.match(path.name)
        file_date = name_match.group(1) if name_match else None
        existing_file = _existing_file_ref(conn, path.name)
        if existing_file:
            items.append({
                "file_name": path.name, "file_hash": existing_file["file_hash"],
                "date": file_date, "type": None, "name": name_match.group(3) if name_match else path.stem,
                "action": "already_processed", "reason": existing_file["match_reason"] or f"Previously {existing_file['status']}.",
                "activity_id": existing_file["activity_id"],
            })
            continue
        if not initialized and cutoff and file_date and file_date < cutoff:
            items.append({
                "file_name": path.name, "file_hash": None, "date": file_date, "type": None,
                "name": name_match.group(3), "action": "baseline",
                "reason": "Historical file before the existing activity cutoff; contents will not be opened and no activity will be created.",
                "activity_id": None,
            })
            continue
        try:
            parsed = parse_healthfit_file(path)
        except ValueError as exc:
            items.append({"file_name": path.name, "action": "error", "reason": str(exc)})
            continue
        existing = _existing_ref(conn, parsed["file_hash"])
        if existing:
            action = "already_processed"
            reason = existing["match_reason"] or f"Previously {existing['status']}."
            activity_id = existing["activity_id"]
        else:
            match = find_activity_match(conn, parsed["activity"])
            if match["status"] == "matched":
                action, reason, activity_id = "link_existing", match["reason"], match["activity"]["id"]
            elif match["status"] == "ambiguous":
                action, reason, activity_id = "ambiguous", match["reason"], None
            elif not initialized and cutoff and parsed["activity"]["date"] <= cutoff:
                action, reason, activity_id = "baseline", "Historical file at or before the existing activity cutoff; no activity will be created.", None
            else:
                action, activity_id = "create", None
                reason = (
                    "Previously unseen HealthFit file after initialization; workout date does not suppress late-arriving files."
                    if initialized
                    else "Workout is newer than the existing activity cutoff and has no match."
                )
        items.append({
            "file_name": parsed["file_name"], "file_hash": parsed["file_hash"],
            "date": parsed["activity"]["date"], "type": parsed["activity"]["type"],
            "name": parsed["activity"]["name"], "action": action, "reason": reason, "activity_id": activity_id,
        })
    counts = {}
    for item in items:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    return {
        "configured": True, "initialized": initialized, "directory": str(directory),
        "cutoff_date": cutoff, "items": items, "counts": counts,
    }


def apply_healthfit_import(conn: sqlite3.Connection) -> dict:
    preview = preview_healthfit_import(conn)
    if not preview["configured"]:
        raise HTTPException(status_code=400, detail=f"HealthFit directory is unavailable: {preview['directory']}")
    directory = healthfit_directory()
    applied = {"created": 0, "linked": 0, "baselined": 0, "skipped": 0}
    for item in preview["items"]:
        action = item["action"]
        if action in {"already_processed", "ambiguous", "error"}:
            applied["skipped"] += 1
            continue
        if action == "baseline" and not item.get("file_hash"):
            upsert_source_ref(
                conn, source=HEALTHFIT_SOURCE, external_id=f"filename:{item['file_name']}", activity_id=None,
                started_at=None, status="baseline", file_name=item["file_name"], file_hash=None,
                match_reason=item["reason"], metadata={"date": item.get("date")},
            )
            applied["baselined"] += 1
            continue
        parsed = parse_healthfit_file(directory / item["file_name"], include_streams=action == "create")
        activity_id = item.get("activity_id")
        status = action
        if action == "create":
            upsert_activity_row(conn, parsed["activity"], preserve_annotations=True)
            activity_id = parsed["activity"]["id"]
            streams = parsed.get("streams")
            if streams:
                import json
                conn.execute(
                    """INSERT INTO activity_details (activity_id, fetched_at, source_status, streams_json)
                       VALUES (?, ?, 'healthfit_fit', ?)
                       ON CONFLICT(activity_id) DO UPDATE SET fetched_at=excluded.fetched_at,
                       source_status=excluded.source_status, streams_json=excluded.streams_json, updated_at=CURRENT_TIMESTAMP""",
                    (activity_id, datetime.now().isoformat(), json.dumps(streams)),
                )
            applied["created"] += 1
        elif action == "link_existing":
            applied["linked"] += 1
        else:
            applied["baselined"] += 1
        upsert_source_ref(
            conn, source=HEALTHFIT_SOURCE, external_id=parsed["file_hash"], activity_id=activity_id,
            started_at=parsed["started_at"], status=status, file_name=parsed["file_name"],
            file_hash=parsed["file_hash"], match_reason=item["reason"], metadata={"activity": parsed["activity"]},
        )
    conn.commit()
    return {**preview, "applied": applied}
