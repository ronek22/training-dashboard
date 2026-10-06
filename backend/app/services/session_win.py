"""The one encouraging thing to say about a finished session.

Wins come from facts the app already computes: the session read (power,
heart rate at the same power, pace at the same heart rate, lifts going up),
the all-time record wall, the streak and how the athlete went in. There is
always a win, because showing up counts. The win also writes the coach's
opening message for the chat about this session, so that chat never starts
from an empty box.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from .personal_records import STREAK_MILESTONES, _streak_section, build_activity_record_ranks

ORDINALS = {2: "2nd", 3: "3rd"}
STREAK_MIN_DAYS = 3
SPORT_NAMES = {"Ride": "ride", "VirtualRide": "indoor ride", "Run": "run", "WeightTraining": "lift", "Walk": "walk"}


RECORD_NOUNS = {"Bike power": "power", "Bike distance": "ride", "Indoor bike distance": "indoor ride", "Run": "run"}


def _record_name(item: dict) -> str:
    """'5 km run', '20 min power', 'longest ride', 'Back Squat'."""
    label = item["label"]
    if item["category"] == "Lift":
        return label
    if label[:1].isdigit():
        return f"{label} {RECORD_NOUNS.get(item['category'], item['category'].lower())}"
    return label[:1].lower() + label[1:]


def _record_wins(ranks: list[dict]) -> list[dict]:
    wins = []
    for item in ranks:
        name = _record_name(item)
        if item["rank"] == 1:
            wins.append({"score": 100, "kind": "record", "headline": f"All-time best {name}: {item['display']}",
                         "detail": "Top of your record wall. Nothing you've logged before beats it."})
        else:
            wins.append({"score": 72 - item["rank"], "kind": "record",
                         "headline": f"Your {ORDINALS.get(item['rank'], str(item['rank']))} best {name} ever",
                         "detail": f"{item['display']}, now on your record wall."})
    return wins


def _tough_day_win(detail_payload: dict, read: dict) -> Optional[dict]:
    going_in = next((signal for signal in read.get("signals") or [] if signal["key"] == "going_in"), None)
    if not going_in or going_in["tone"] != "warn":
        return None
    state = ", ".join(part for part in (going_in["value"].lower(), (going_in.get("detail") or "").replace(" · ", ", ")) if part)
    return {"score": 55, "kind": "consistency", "headline": "Showed up on a tough day",
            "detail": f"Going in: {state}. You still got it done."}


def _streak_win(conn: sqlite3.Connection, day: str) -> Optional[dict]:
    """A milestone day is a big win; any other streak day is a fallback that counts down to the next one."""
    streak = _streak_section(conn, date.today()).get("current")
    if not streak or not streak["start"] <= day <= streak["end"]:
        return None
    position = (date.fromisoformat(day) - date.fromisoformat(streak["start"])).days + 1
    if position < STREAK_MIN_DAYS:
        return None
    if position in STREAK_MILESTONES or position % 100 == 0:
        return {"score": 85, "kind": "consistency", "headline": f"{position} days in a row",
                "detail": "A streak milestone. Every single day counted to get here."}
    upcoming = next((days for days in STREAK_MILESTONES if days > position), (position // 100 + 1) * 100)
    return {"score": 20, "kind": "consistency", "headline": f"Day {position} of your streak",
            "detail": f"{upcoming - position} {'day' if upcoming - position == 1 else 'days'} to {upcoming} in a row."}


def _week_count_win(conn: sqlite3.Connection, activity: dict) -> dict:
    day = date.fromisoformat(str(activity["date"])[:10])
    monday = day - timedelta(days=day.weekday())
    count = conn.execute(
        "SELECT COUNT(*) FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ? AND date <= ?",
        (monday.isoformat(), day.isoformat(), activity["date"]),
    ).fetchone()[0]
    minutes = round(float(activity.get("duration_min") or 0))
    ordinal = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}.get(count, f"Number {count}")
    return {"score": 10, "kind": "consistency", "headline": f"{ordinal} session of the week in the bank",
            "detail": f"{minutes} min done. Consistency is what moves the needle." if minutes else "Consistency is what moves the needle."}


def _opener(activity: dict, win: dict, read: dict) -> str:
    sport = SPORT_NAMES.get(activity.get("type"), "session")
    lines = [f"{win['headline']}. {win['detail']}"]
    if read.get("next_time"):
        lines.append(f"Next time: {read['next_time']}")
    lines.append(f"Want to dig into this {sport}? Ask me why something happened, what to change next time, or how it fits your week.")
    return "\n\n".join(lines)


def build_session_win(
    conn: sqlite3.Connection,
    detail_payload: dict,
    session_read: Optional[dict] = None,
    record_ranks: Optional[dict[str, list[dict]]] = None,
) -> Optional[dict[str, Any]]:
    """``record_ranks`` lets a caller scoring many sessions compute the record wall once."""
    activity = detail_payload.get("activity") or {}
    if not activity.get("id"):
        return None
    day = str(activity["date"])[:10]
    read = session_read if session_read and session_read.get("available") else {}
    candidates: list[dict] = [{"kind": "progress", **win} for win in read.get("wins") or []]

    if detail_payload.get("sick_session"):
        candidates.append({"score": 60, "kind": "consistency", "headline": "Kept moving while sick",
                           "detail": "A gentle session that keeps the habit without digging a hole."})
    try:
        ranks = record_ranks if record_ranks is not None else build_activity_record_ranks(conn)
        candidates.extend(_record_wins(ranks.get(str(activity["id"]), [])))
    except (sqlite3.Error, KeyError, ValueError):
        pass
    tough = _tough_day_win(detail_payload, read)
    if tough:
        candidates.append(tough)
    quality = detail_payload.get("execution_quality") or {}
    if quality.get("status") == "matched":
        candidates.append({"score": 45, "kind": "plan", "headline": "Done exactly as planned",
                           "detail": "The plan only works when it gets done. This one did."})
    try:
        streak = _streak_win(conn, day)
    except (sqlite3.Error, ValueError):
        streak = None
    if streak:
        candidates.append(streak)
    candidates.append(_week_count_win(conn, activity))

    win = max(candidates, key=lambda item: item["score"])
    others = [item["headline"] for item in sorted(candidates, key=lambda item: -item["score"]) if item is not win and item["score"] >= 40][:2]
    return {
        "score": win["score"],
        "kind": win["kind"],
        "headline": win["headline"],
        "detail": win["detail"],
        "also": others,
        "opener": _opener(activity, win, read),
    }
