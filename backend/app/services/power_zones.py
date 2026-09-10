import json
import math
import sqlite3
from typing import Optional


# Upper FTP fractions are inclusive; the final zone is open-ended.
POWER_ZONE_LIMITS = (0.55, 0.75, 0.90, 1.05, 1.20, 1.50)


def build_activity_power_zone_summary(
    conn: sqlite3.Connection, activity: dict, detail_row: Optional[sqlite3.Row]
) -> dict:
    def unavailable(reason):
        return {"available": False, "state": "unavailable", "reason": reason}

    if activity.get("type") not in {"Ride", "VirtualRide", "EBikeRide"}:
        return unavailable("unsupported_activity_type")
    if not detail_row or not detail_row["streams_json"]:
        return unavailable("missing_streams")
    streams = json.loads(detail_row["streams_json"])
    times = (streams.get("time") or {}).get("data") or []
    watts = (streams.get("watts") or {}).get("data") or []
    if len(times) < 2:
        return unavailable("missing_time_stream")
    if len(watts) < 2:
        return unavailable("missing_power_stream")
    ftp_row = conn.execute(
        "SELECT value FROM metrics WHERE metric = 'ftp' AND date <= ? ORDER BY date DESC, id DESC LIMIT 1",
        (activity.get("date"),),
    ).fetchone()
    try:
        ftp = float(ftp_row["value"]) if ftp_row else 0
    except (TypeError, ValueError):
        ftp = 0
    if not math.isfinite(ftp) or ftp <= 0:
        return unavailable("missing_ftp")

    limits = [ftp * fraction for fraction in POWER_ZONE_LIMITS]
    totals = [0.0] * 7
    for index in range(1, min(len(times), len(watts))):
        try:
            previous, current, power = float(times[index - 1]), float(times[index]), float(watts[index])
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (previous, current, power)):
            continue
        if current <= previous or power < 0:
            continue
        # Zero watts is valid coasting time in zone 1.
        zone_index = next((i for i, limit in enumerate(limits) if power <= limit), 6)
        totals[zone_index] += current - previous
    total = sum(totals)
    if total <= 0:
        return unavailable("empty_zone_samples")

    zones = []
    for index, seconds in enumerate(totals):
        lower = limits[index - 1] if index else 0
        upper = limits[index] if index < 6 else None
        watt_range = (
            f"0–{upper:g} W" if index == 0 else
            f"> {lower:g} W" if upper is None else
            f"> {lower:g}–{upper:g} W"
        )
        zones.append({
            "key": f"zone{index + 1}", "label": f"Zone {index + 1}",
            "seconds": seconds, "minutes": round(seconds / 60, 1),
            "pct": round(seconds / total * 100), "highlight": index == 1,
            "watt_range": watt_range,
        })
    return {
        "available": True, "state": "available", "reason": None,
        "ftp_watts": ftp, "summary": "Power zone 2 time",
        "total_minutes": round(total / 60, 1),
        "zone2_minutes": zones[1]["minutes"], "zone2_pct": zones[1]["pct"],
        "dominant_zone_key": zones[totals.index(max(totals))]["key"], "zones": zones,
    }
