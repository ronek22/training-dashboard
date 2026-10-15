"""A look back at each finished winter-arc block, and what it suggests for the next one.

Once a block's last Sunday is past, its recap reads what actually happened week by week: ride
hours against the block's target, key rides done against the rides the block asked for (each ride
classified from what was ridden, as on the ride-balance card), weeks lost to illness, trips or busy
days (``arc_adjust``), the longest run of on-target weeks, best 1/5/20-minute power against the six
weeks before the block, and the aerobic-decoupling trend over the block's steady rides.

It then makes at most two plain suggestions for the next block (hold or trim its hours, or ask for
one fewer quality ride a week). Suggestions only ever hold or ease the next block, never raise it,
and nothing changes until one is confirmed; each decision is stored so it is not offered again.
A block with fewer than ``MIN_RIDES`` rides says there is not enough data instead.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from . import winter_arc

SCHEMA = """
CREATE TABLE IF NOT EXISTS block_recap_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_start TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    action TEXT NOT NULL,
    suggestion_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

MIN_RIDES = 3  # fewer rides in the whole block: not enough to say how it went
ON_TARGET_HOURS = 0.8  # a week counts as on target at 80% of its hours and every key ride
HOURS_UNDER = 0.8  # below this share of the block's hours, the next block should not grow
HOURS_FAR_UNDER = 0.65  # below this, trim the next block towards what was really ridden
KEY_RIDES_UNDER = 0.6
POWER_DURATIONS = ((60, "1 min"), (300, "5 min"), (1200, "20 min"))
POWER_BEFORE_WEEKS = 6
ACTIONS = ("apply", "dismiss")


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _short(value: str) -> str:
    return date.fromisoformat(value).strftime("%-d %b")


def _half(value: float) -> float:
    return round(value * 2) / 2


def _find_block(conn: sqlite3.Connection, block_start: str) -> tuple[dict, Optional[dict]]:
    blocks = winter_arc.list_blocks(conn)
    for index, block in enumerate(blocks):
        if block["start_date"] == block_start:
            return block, blocks[index + 1] if index + 1 < len(blocks) else None
    raise HTTPException(status_code=404, detail="No arc block starts on this day.")


# --- What happened, week by week ----------------------------------------------------------------

def _classified_rides(conn: sqlite3.Connection, start: str, end: str, today: date) -> list[dict]:
    """Every ride of 20+ minutes in [start, end], typed from what was ridden (ride balance rules)."""
    from .ride_balance import MIN_RIDE_MINUTES, RIDE_TYPES, _hr_bands, _reference_ftp, classify_ride

    rows = conn.execute(
        f"""
        SELECT a.id, a.date, a.type, a.name, a.duration_min, a.avg_hr, a.workout_intent,
               d.detail_json, d.streams_json, d.source_status
        FROM activities AS a LEFT JOIN activity_details AS d ON d.activity_id = a.id
        WHERE a.type IN ({",".join("?" for _ in RIDE_TYPES)}) AND substr(a.date, 1, 10) BETWEEN ? AND ?
        ORDER BY a.date, a.id
        """,
        (*RIDE_TYPES, start, end),
    ).fetchall()
    ftp = _reference_ftp(conn, today)["watts"]
    bands = _hr_bands(conn)
    rides = []
    for row in rows:
        ride = dict(row)
        minutes = float(ride.get("duration_min") or 0)
        if minutes < MIN_RIDE_MINUTES:
            continue
        has_detail = row["streams_json"] is not None or row["detail_json"] is not None
        kind = classify_ride(ride, row if has_detail else None, ftp, bands)["type"]
        rides.append({"id": ride["id"], "date": str(ride["date"])[:10], "name": ride["name"], "minutes": round(minutes), "type": kind})
    return rides


def _weeks(conn: sqlite3.Connection, block: dict, rides: list[dict]) -> list[dict]:
    from .arc_adjust import week_disruption

    weeks = []
    week = date.fromisoformat(block["start_date"])
    while week.isoformat() <= block["end_date"]:
        start, end = week.isoformat(), (week + timedelta(days=6)).isoformat()
        target = winter_arc.week_target(block, start)
        own = [ride for ride in rides if start <= ride["date"] <= end]
        done_hours = round(sum(ride["minutes"] for ride in own) / 60, 1)
        asked = {key: target["ride_mix"][key] for key in target["key_types"]}
        ridden = {key: sum(1 for ride in own if ride["type"] == key) for key in asked}
        key_planned = sum(asked.values())
        # Extra key rides in one week do not make up for a missed one in another.
        key_done = sum(min(asked[key], ridden[key]) for key in asked)
        lost = week_disruption(conn, start, target["ride_hours"], done_hours)
        weeks.append({
            "week_start": start,
            "week_number": target["week_number"],
            "lighter": target["lighter"],
            "ride_hours_target": target["ride_hours"],
            "ride_hours_done": done_hours,
            "key_rides_planned": key_planned,
            "key_rides_done": key_done,
            "key_types": target["key_types"],
            "key_by_type": {key: {"planned": asked[key], "done": min(asked[key], ridden[key])} for key in asked},
            "rides": len(own),
            "lost": bool(lost),
            "lost_reasons": lost["reasons"] if lost else [],
            "on_target": done_hours >= target["ride_hours"] * ON_TARGET_HOURS and key_done >= key_planned,
        })
        week += timedelta(weeks=1)
    return weeks


def _longest_streak(weeks: list[dict]) -> int:
    best = run = 0
    for week in weeks:
        run = run + 1 if week["on_target"] else 0
        best = max(best, run)
    return best


# --- Fitness change over the block --------------------------------------------------------------

def _power_change(conn: sqlite3.Connection, block: dict) -> dict:
    """Best 1/5/20-minute power in the block against the six weeks before it."""
    from .power_trends import get_cycling_power_trends_data

    before_start = (date.fromisoformat(block["start_date"]) - timedelta(weeks=POWER_BEFORE_WEEKS)).isoformat()
    efforts = get_cycling_power_trends_data(conn)["efforts"]
    durations = []
    for seconds, label in POWER_DURATIONS:
        own = [effort for effort in efforts if effort["duration_seconds"] == seconds]
        during = max((e["watts"] for e in own if block["start_date"] <= str(e["date"])[:10] <= block["end_date"]), default=None)
        before = max((e["watts"] for e in own if before_start <= str(e["date"])[:10] < block["start_date"]), default=None)
        durations.append({
            "seconds": seconds,
            "label": label,
            "during_watts": round(during) if during is not None else None,
            "before_watts": round(before) if before is not None else None,
            "change_watts": round(during - before) if during is not None and before is not None else None,
        })
    if not any(item["during_watts"] for item in durations):
        return {"status": "unavailable", "reason": "No rides with a power meter in this block.", "durations": durations}
    return {"status": "available", "before_weeks": POWER_BEFORE_WEEKS, "durations": durations}


def _decoupling_change(conn: sqlite3.Connection, block: dict) -> dict:
    """Heart-rate drift on the block's steady rides, for whichever setting had more of them."""
    from .aerobic_decoupling import build_aerobic_decoupling

    data = build_aerobic_decoupling(conn, weeks=block["weeks"], today=date.fromisoformat(block["end_date"]))
    rides = [ride for ride in data["rides"] if ride["date"] >= block["start_date"]]
    environments = sorted(
        data["environments"].items(),
        key=lambda item: (item[1]["status"] == "available", sum(ride["environment"] == item[0] for ride in rides)),
        reverse=True,
    )
    environment, trend = environments[0]
    if trend["status"] != "available":
        return {"status": "unavailable", "reason": f"Needs at least {data['thresholds']['min_trend_rides']} steady rides of 45+ min with power and heart rate; {len(rides)} in this block."}
    return {
        "status": "available",
        "environment": environment,
        "rides": [{key: ride[key] for key in ("date", "decoupling_pct", "efficiency")} for ride in rides if ride["environment"] == environment],
        "direction": trend["direction"],
        "hr_change_at_same_power_bpm": trend["hr_change_at_same_power_bpm"],
        "efficiency_change_pct": trend["efficiency_change_pct"],
        "median_decoupling_pct": trend["median_decoupling_pct"],
        "coupled_rides": trend["coupled_rides"],
        "coupled_threshold_pct": data["thresholds"]["coupled_decoupling_pct"],
    }


# --- Suggestions for the next block -------------------------------------------------------------

def _decisions(conn: sqlite3.Connection, block_start: str) -> dict[str, sqlite3.Row]:
    try:
        rows = conn.execute("SELECT * FROM block_recap_decisions WHERE block_start = ? ORDER BY id", (block_start,)).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row["suggestion"]: row for row in rows}


def _fresh_suggestions(block: dict, following: Optional[dict], weeks: list[dict]) -> list[dict]:
    """Hold or ease the next block when this one fell short. Never raises it."""
    if not following:
        return []
    counted = [week for week in weeks if not week["lost"]]  # Lost weeks already had their own card.
    if not counted:
        return []
    suggestions = []
    target = sum(week["ride_hours_target"] for week in counted)
    done = sum(week["ride_hours_done"] for week in counted)
    share = done / target if target else 1
    under = round((1 - share) * 100)
    normal = [week["ride_hours_done"] for week in counted if not week["lighter"]] or [week["ride_hours_done"] for week in counted]
    usual = max(1.0, _half(sum(normal) / len(normal)))
    hours_to = None
    if share < HOURS_FAR_UNDER and usual < following["weekly_hours"]:
        hours_to = usual
        reason = f"you rode about {usual:g} h in a normal week"
    elif share < HOURS_UNDER and following["weekly_hours"] > block["weekly_hours"]:
        hours_to = block["weekly_hours"]
        reason = f"keep it at {block['label']}'s {block['weekly_hours']:g} h until those hours come easily"
    if hours_to is not None:
        suggestions.append({
            "id": "hours",
            "message": f"Hours were {under}% under. Set {following['label']} to {hours_to:g} h a week instead of {following['weekly_hours']:g} h: {reason}.",
            "change": {"block_start": following["start_date"], "block_label": following["label"], "field": "weekly_hours", "from": following["weekly_hours"], "to": hours_to},
        })

    planned = sum(week["key_rides_planned"] for week in counted)
    hit = sum(week["key_rides_done"] for week in counted)
    quality = {key: following["ride_mix"][key] for key in winter_arc.QUALITY_TYPES if following["ride_mix"][key]}
    if planned and hit / planned < KEY_RIDES_UNDER and sum(quality.values()) >= 2:
        kind = max(quality, key=lambda key: (quality[key], key == "sweet_spot"))
        name = winter_arc.MIX_LABELS[kind].lower()
        suggestions.append({
            "id": "key_rides",
            "message": f"{hit} of {planned} key rides happened. Ask {following['label']} for one fewer {name} ride a week ({quality[kind]} → {quality[kind] - 1}) so the ones left land.",
            "change": {"block_start": following["start_date"], "block_label": following["label"], "field": f"ride_mix.{kind}", "from": quality[kind], "to": quality[kind] - 1},
        })
    return suggestions


def _suggestions(conn: sqlite3.Connection, block: dict, following: Optional[dict], weeks: list[dict]) -> list[dict]:
    decided = _decisions(conn, block["start_date"])
    result = []
    for suggestion in _fresh_suggestions(block, following, weeks):
        if suggestion["id"] not in decided:
            result.append({**suggestion, "decision": None})
    # Decided ones stay on the page as they were confirmed, with what was chosen.
    for key, row in decided.items():
        result.append({**json.loads(row["suggestion_json"]), "decision": row["action"], "decided_at": row["created_at"]})
    order = {"hours": 0, "key_rides": 1}
    return sorted(result, key=lambda item: order.get(item["id"], 9))


def _headline(block: dict, totals: dict, status: str) -> str:
    if status == "thin":
        return f"{block['label']} left too little riding to read."
    hours, keys = totals["hours_pct"], totals["key_rides"]
    key_share = keys["done"] / keys["planned"] if keys["planned"] else 1
    if hours >= 90 and key_share >= 0.9:
        return f"{block['label']} delivered."
    if hours >= 90 and key_share < KEY_RIDES_UNDER:
        return f"{block['label']} had the hours, not the key rides."
    if hours < 75 and key_share >= 0.9:
        return f"{block['label']} landed its key rides on fewer hours."
    if hours >= 75 and key_share >= KEY_RIDES_UNDER:
        return f"{block['label']} mostly delivered."
    return f"{block['label']} came up short, and that is useful to know."


# --- Public -------------------------------------------------------------------------------------

def build_block_recap(conn: sqlite3.Connection, block_start: str, today: Optional[date] = None) -> dict:
    today = today or date.today()
    block, following = _find_block(conn, block_start)
    if block["end_date"] >= today.isoformat():
        opens = (date.fromisoformat(block["end_date"]) + timedelta(days=1)).isoformat()
        raise HTTPException(status_code=409, detail=f"{block['label']} is still running; its recap opens on {_short(opens)}.")

    rides = _classified_rides(conn, block["start_date"], block["end_date"], today)
    weeks = _weeks(conn, block, rides)
    status = "thin" if len(rides) < MIN_RIDES else "ok"
    hours_target = round(sum(week["ride_hours_target"] for week in weeks), 1)
    hours_done = round(sum(ride["minutes"] for ride in rides) / 60, 1)
    by_type = {
        key: {
            "label": winter_arc.MIX_LABELS[key],
            "planned": sum(week["key_by_type"].get(key, {}).get("planned", 0) for week in weeks),
            "done": sum(week["key_by_type"].get(key, {}).get("done", 0) for week in weeks),
        }
        for key in block["key_types"]
    }
    totals = {
        "ride_hours_target": hours_target,
        "ride_hours_done": hours_done,
        "hours_pct": round(hours_done / hours_target * 100) if hours_target else 0,
        "key_rides": {
            "planned": sum(week["key_rides_planned"] for week in weeks),
            "done": sum(week["key_rides_done"] for week in weeks),
            "by_type": by_type,
        },
        "rides": len(rides),
        "ride_days": len({ride["date"] for ride in rides}),
        "on_target_weeks": sum(week["on_target"] for week in weeks),
        "longest_streak": _longest_streak(weeks),
        "lost_weeks": sum(week["lost"] for week in weeks),
    }
    return {
        "block": {key: block[key] for key in ("id", "label", "focus", "focus_label", "start_date", "end_date", "weeks", "weekly_hours", "ride_mix", "key_types")},
        "next_block": {key: following[key] for key in ("label", "focus_label", "start_date", "end_date", "weekly_hours", "ride_mix")} if following else None,
        "status": status,
        "min_rides": MIN_RIDES,
        "headline": _headline(block, totals, status),
        "totals": totals,
        "weeks": weeks,
        "power": _power_change(conn, block) if status == "ok" else None,
        "decoupling": _decoupling_change(conn, block) if status == "ok" else None,
        "suggestions": _suggestions(conn, block, following, weeks) if status == "ok" else [],
    }


def decide_block_suggestion(
    conn: sqlite3.Connection, block_start: str, suggestion_id: str, action: str, to: Optional[float] = None, today: Optional[date] = None,
) -> dict:
    """Apply or dismiss one suggestion. It must still match the recap, so a stale page cannot edit the arc."""
    if action not in ACTIONS:
        raise HTTPException(status_code=422, detail=f"Unknown action: {action}")
    today = today or date.today()
    recap = build_block_recap(conn, block_start, today)
    suggestion = next((item for item in recap["suggestions"] if item["id"] == suggestion_id and item["decision"] is None), None)
    if not suggestion or (action == "apply" and to != suggestion["change"]["to"]):
        raise HTTPException(status_code=409, detail="The arc changed since this suggestion; reload the recap.")
    ensure_table(conn)
    if action == "apply":
        change = suggestion["change"]
        row = conn.execute("SELECT * FROM winter_arc_blocks WHERE start_date = ?", (change["block_start"],)).fetchone()
        if change["field"] == "weekly_hours":
            conn.execute("UPDATE winter_arc_blocks SET weekly_hours = ? WHERE id = ?", (change["to"], row["id"]))
        else:
            mix = json.loads(row["ride_mix_json"])
            mix[change["field"].split(".", 1)[1]] = int(change["to"])
            conn.execute("UPDATE winter_arc_blocks SET ride_mix_json = ? WHERE id = ?", (json.dumps(mix), row["id"]))
    stored = {key: value for key, value in suggestion.items() if key != "decision"}
    conn.execute(
        "INSERT INTO block_recap_decisions (block_start, suggestion, action, suggestion_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (block_start, suggestion_id, "applied" if action == "apply" else "dismissed", json.dumps(stored),
         datetime.combine(today, datetime.now().time()).isoformat(timespec="seconds")),
    )
    conn.commit()
    return build_block_recap(conn, block_start, today)


def clear_decisions(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("DELETE FROM block_recap_decisions")
    except sqlite3.OperationalError:
        pass
