"""Evidence rules for cycling distance records."""

import math
from typing import Any


def _stream(streams: Any, key: str) -> list[Any]:
    if not isinstance(streams, dict):
        return []
    value = streams.get(key)
    if isinstance(value, dict):
        value = value.get("data")
    return list(value) if isinstance(value, (list, tuple)) else []


def has_gps_coordinates(streams: Any) -> bool:
    matches = 0
    for point in _stream(streams, "latlng"):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            lat, lon = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            matches += 1
            if matches >= 2:
                return True
    return False


def has_power_chart_data(streams: Any) -> bool:
    matches = 0
    for value in _stream(streams, "watts"):
        try:
            watts = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(watts) and watts > 0:
            matches += 1
            if matches >= 2:
                return True
    return False


def ride_has_record_evidence(streams: Any) -> bool:
    """Count rides toward distance records only with a GPS track or recorded power."""
    return has_gps_coordinates(streams) or has_power_chart_data(streams)


def cleaned_distance_stream(streams: Any, max_speed_kmh: float = 70.0) -> list[float]:
    """Remove impossible increments from a cumulative distance stream."""
    distances = _stream(streams, "distance")
    times = _stream(streams, "time")
    cleaned: list[float] = []
    previous: tuple[float, float] | None = None
    total = 0.0
    for raw_distance, raw_time in zip(distances, times):
        try:
            distance, timestamp = float(raw_distance), float(raw_time)
        except (TypeError, ValueError):
            cleaned.append(total)
            continue
        if not math.isfinite(distance) or not math.isfinite(timestamp):
            cleaned.append(total)
            continue
        if previous is not None:
            previous_distance, previous_time = previous
            elapsed = timestamp - previous_time
            gained = distance - previous_distance
            if elapsed > 0 and gained >= 0 and gained / elapsed * 3.6 <= max_speed_kmh:
                total += gained
        cleaned.append(total)
        previous = (distance, timestamp)
    return cleaned
