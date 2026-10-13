"""Fill detailed streams from a Strava bulk export instead of the API.

A Strava account export holds every activity's original file (FIT, TCX or GPX,
often gzipped) and an ``activities.csv`` mapping each Strava activity ID to its
file. Reading those locally takes minutes, where fetching the same streams
through the API takes days within Strava's rate limits.

Files are converted to the shape the Strava streams API returns (``time``,
``distance``, ``latlng``, ``altitude``, ``heartrate``, ``watts``, ``cadence``,
``velocity_smooth`` with ``data`` lists of equal length) and cached exactly
like the history backfill does, which then skips them. Activities that
already have streams are left alone. Files are treated as data: XML with a
DOCTYPE or entity declaration is refused, and nothing in the export is run.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import fitdecode

from .dashboard import estimate_thresholds, intensity_bucket_from_hr
from .strava import summarize_activity_streams, upsert_activity_detail_stream_cache, upsert_activity_stream_summary
from .strava_history_backfill import TYPES, ensure_schema

MAX_FILE_BYTES = 80 * 1024 * 1024  # Unzipped; a long ride is a few MB.
SEMICIRCLE = 180 / 2**31


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------


def _read(path: Path) -> bytes:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    else:
        data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("file too large")
    return data


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(data: bytes) -> ET.Element:
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in data.upper():
        raise ValueError("XML with DOCTYPE or entities is not read")
    return ET.fromstring(data.lstrip())


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def _number(element: Optional[ET.Element]) -> Optional[float]:
    try:
        return float(element.text) if element is not None and element.text else None
    except ValueError:
        return None


def _child(element: ET.Element, name: str) -> Optional[ET.Element]:
    return next((child for child in element.iter() if _local(child.tag) == name), None)


def _points_from_tcx(root: ET.Element) -> list[dict[str, Any]]:
    points = []
    for node in root.iter():
        if _local(node.tag) != "Trackpoint":
            continue
        stamp = _child(node, "Time")
        if stamp is None or not stamp.text:
            continue
        position = _child(node, "Position")
        lat = _number(_child(position, "LatitudeDegrees")) if position is not None else None
        lon = _number(_child(position, "LongitudeDegrees")) if position is not None else None
        hr_parent = _child(node, "HeartRateBpm")
        points.append({
            "time": _time(stamp.text), "lat": lat, "lon": lon,
            "altitude": _number(_child(node, "AltitudeMeters")), "distance": _number(_child(node, "DistanceMeters")),
            "heartrate": _number(_child(hr_parent, "Value")) if hr_parent is not None else None,
            "cadence": _number(_child(node, "Cadence")) or _number(_child(node, "RunCadence")),
            "watts": _number(_child(node, "Watts")), "speed": _number(_child(node, "Speed")),
        })
    return points


def _points_from_gpx(root: ET.Element) -> list[dict[str, Any]]:
    points = []
    for node in root.iter():
        if _local(node.tag) != "trkpt":
            continue
        stamp = _child(node, "time")
        if stamp is None or not stamp.text:
            continue
        try:
            lat, lon = float(node.get("lat")), float(node.get("lon"))
        except (TypeError, ValueError):
            lat = lon = None
        points.append({
            "time": _time(stamp.text), "lat": lat, "lon": lon, "altitude": _number(_child(node, "ele")), "distance": None,
            "heartrate": _number(_child(node, "hr")), "cadence": _number(_child(node, "cad")),
            "watts": _number(_child(node, "power")) or _number(_child(node, "PowerInWatts")), "speed": None,
        })
    return points


def _points_from_fit(data: bytes) -> list[dict[str, Any]]:
    points = []
    with fitdecode.FitReader(io.BytesIO(data)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage) or frame.name != "record":
                continue
            fields = {field.name: field.value for field in frame.fields}
            stamp = fields.get("timestamp")
            if not isinstance(stamp, datetime):
                continue
            lat, lon = fields.get("position_lat"), fields.get("position_long")
            points.append({
                "time": stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc),
                "lat": lat * SEMICIRCLE if isinstance(lat, (int, float)) else None,
                "lon": lon * SEMICIRCLE if isinstance(lon, (int, float)) else None,
                "altitude": fields.get("enhanced_altitude", fields.get("altitude")), "distance": fields.get("distance"),
                "heartrate": fields.get("heart_rate"), "cadence": fields.get("cadence"), "watts": fields.get("power"),
                "speed": fields.get("enhanced_speed", fields.get("speed")),
            })
    return points


def read_points(path: Path) -> list[dict[str, Any]]:
    name = path.name.lower()
    data = _read(path)
    if ".fit" in name:
        return _points_from_fit(data)
    if ".tcx" in name:
        return _points_from_tcx(_parse_xml(data))
    if ".gpx" in name:
        return _points_from_gpx(_parse_xml(data))
    raise ValueError(f"unknown file type: {path.name}")


# ---------------------------------------------------------------------------
# Points to Strava-shaped streams
# ---------------------------------------------------------------------------


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(min(1.0, h)))


def points_to_streams(points: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Equal-length streams like the Strava API; ``None`` when there is no time series."""
    points = sorted((point for point in points if point.get("time")), key=lambda point: point["time"])
    if len(points) < 2:
        return None
    start = points[0]["time"]
    streams: dict[str, Any] = {"time": {"data": [int(round((point["time"] - start).total_seconds())) for point in points]}}

    # Positions: carry the last known fix through short dropouts so the arrays stay aligned.
    first_fix = next(((point["lat"], point["lon"]) for point in points if point["lat"] is not None and point["lon"] is not None), None)
    if first_fix:
        last, latlng = first_fix, []
        for point in points:
            if point["lat"] is not None and point["lon"] is not None:
                last = (round(point["lat"], 7), round(point["lon"], 7))
            latlng.append([last[0], last[1]])
        streams["latlng"] = {"data": latlng}

    # Distance: the device's when every point has it, else measured along the track.
    if all(point["distance"] is not None for point in points):
        distance = [round(float(point["distance"]), 1) for point in points]
    elif "latlng" in streams:
        distance, total = [0.0], 0.0
        coords = streams["latlng"]["data"]
        for previous, current in zip(coords, coords[1:]):
            total += _haversine(tuple(previous), tuple(current))
            distance.append(round(total, 1))
    else:
        distance = None
    if distance and distance[-1] > 0:
        # Never let distance run backwards (device resets, GPS jitter).
        for index in range(1, len(distance)):
            distance[index] = max(distance[index], distance[index - 1])
        streams["distance"] = {"data": distance}

    for key, stream in (("altitude", "altitude"), ("heartrate", "heartrate"), ("watts", "watts"), ("cadence", "cadence"), ("speed", "velocity_smooth")):
        values = [point[key] for point in points]
        if any(value is not None for value in values):
            streams[stream] = {"data": [round(float(value), 1) if value is not None else None for value in values]}
    return streams


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _export_files(export_dir: Path) -> dict[str, Path]:
    with open(export_dir / "activities.csv", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        id_at, file_at = header.index("Activity ID"), header.index("Filename")
        files = {}
        for row in reader:
            if len(row) > file_at and row[file_at]:
                path = (export_dir / row[file_at]).resolve()
                if export_dir.resolve() in path.parents and path.is_file():  # Only files inside the export.
                    files[row[id_at].strip()] = path
    return files


def _targets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    kinds = ", ".join(f"'{kind}'" for kind in TYPES)
    return conn.execute(
        f"""
        SELECT a.id, a.type, a.date, a.duration_min, a.avg_hr, a.avg_watts, a.max_hr, a.distance_km,
               COALESCE(sr.external_id, a.id) AS strava_id
        FROM activities a
        LEFT JOIN activity_details d ON d.activity_id = a.id
        LEFT JOIN activity_source_refs sr ON sr.activity_id = a.id AND sr.source = 'strava'
        WHERE a.type IN ({kinds}) AND d.streams_json IS NULL
        ORDER BY a.date DESC
        """
    ).fetchall()


def import_export_streams(conn: sqlite3.Connection, export_dir: Path, *, dry_run: bool = False) -> dict[str, Any]:
    ensure_schema(conn)
    export_dir = Path(export_dir)
    if not (export_dir / "activities.csv").is_file():
        raise ValueError(f"No activities.csv in {export_dir}")
    files = _export_files(export_dir)
    thresholds = estimate_thresholds(conn)
    summary = {"candidates": 0, "imported": 0, "no_file": 0, "no_streams": 0, "unreadable": 0, "errors": []}
    for row in _targets(conn):
        summary["candidates"] += 1
        path = files.get(str(row["strava_id"]))
        if not path:
            summary["no_file"] += 1
            continue
        try:
            streams = points_to_streams(read_points(path))
        except (ValueError, ET.ParseError, OSError, EOFError, fitdecode.FitError) as error:
            summary["unreadable"] += 1
            if len(summary["errors"]) < 10:
                summary["errors"].append(f"{path.name}: {error}"[:200])
            continue
        if not streams:
            summary["no_streams"] += 1
            continue
        summary["imported"] += 1
        if dry_run:
            continue
        activity = dict(row)
        upsert_activity_detail_stream_cache(conn, activity["id"], streams)
        conn.execute("UPDATE activity_details SET source_status = 'strava_export' WHERE activity_id = ?", (activity["id"],))
        if (streams.get("heartrate") or {}).get("data") or (streams.get("watts") or {}).get("data"):
            stream_summary = summarize_activity_streams(activity, streams, thresholds, intensity_bucket_from_hr)
            if stream_summary:
                upsert_activity_stream_summary(conn, stream_summary)
        conn.execute(
            "INSERT INTO strava_history_backfill (activity_id, status, attempts, error, attempted_at) VALUES (?, 'fetched', 0, 'from export', ?) "
            "ON CONFLICT(activity_id) DO UPDATE SET status = 'fetched', error = 'from export', attempted_at = excluded.attempted_at",
            (activity["id"], datetime.now().isoformat()),
        )
        if summary["imported"] % 50 == 0:
            conn.commit()  # Keep write locks short while the app runs.
    conn.commit()
    return summary
