"""Sleep payback plan: when sleep debt is at risk and stress has been high on 2+ recent days.

Recovery from the cause instead of only skipping sessions: a target bedtime for the next three
nights (your median wake time minus your median sleep plus an extra hour), a finish-by time for
the sessions left this week, and a 60-minute cap on them until the projected debt is back to ok.
Sessions are only shortened or moved, never removed, so lifts and key rides stay in the week.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from statistics import median
from typing import Optional

from .downshift import STRESS_LEVEL, STRESS_TAGS
from .health_data import get_sleep_history
from .life_load import get_life_load_days
from .sleep_debt import BASELINE_NIGHTS, CAUTION_HOURS, WINDOW_NIGHTS, _debt_on, build_sleep_debt

STRESS_WINDOW_DAYS = 3
MIN_STRESS_DAYS = 2
EXTRA_SLEEP_HOURS = 1.0
FALL_ASLEEP_MINUTES = 15
BEDTIME_NIGHTS = 3
PROJECTION_NIGHTS = 7
SESSION_CAP_MIN = 60
WIND_DOWN_HOURS = 3
WAKE_LOOKBACK_DAYS = 28
MIN_WAKE_NIGHTS = 5
# Later "wake times" are naps, not the night's end.
LATEST_WAKE_MINUTES = 14 * 60
SKIP_SESSION_TYPES = {"rest", "recovery"}


def _clock(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _project(nights: dict[date, float], as_of: date, target_hours: float) -> list[dict]:
    """Debt each morning if every coming night lands on the target, until it is back to ok."""
    projected = dict(nights)
    points = []
    for offset in range(1, PROJECTION_NIGHTS + 1):
        day = as_of + timedelta(days=offset)
        projected[day] = target_hours
        point = _debt_on(projected, day)
        if not point:
            break
        points.append({"date": day.isoformat(), "debt_hours": point["value"], "projected": True})
        if point["value"] < CAUTION_HOURS:
            break
    return points


def _session_advice(day: dict, finish_by: Optional[str], capped: bool) -> dict:
    planned = day.get("target_duration_min")
    planned = int(planned) if planned else None
    is_lift = str(day.get("session_type") or "").lower() == "strength"
    shorten_to = SESSION_CAP_MIN if capped and (planned is None or planned > SESSION_CAP_MIN) else None
    if shorten_to and is_lift:
        action = f"Keep it under {SESSION_CAP_MIN} min: main lifts first, drop the add-ons."
    elif shorten_to:
        action = f"Keep it under {SESSION_CAP_MIN} min: hold the main set, trim warm-up and extras."
    else:
        action = "Keep it as planned."
    slot = f"Morning or early evening, done by {finish_by}." if finish_by else "Morning or early evening, done 3 h before bed."
    return {
        "date": day["date"],
        "title": day.get("title") or day.get("session_type") or "Session",
        "session_type": day.get("session_type"),
        "planned_min": planned,
        "shorten_to_min": shorten_to,
        "slot": slot,
        "action": action,
    }


def build_sleep_payback_plan(
    sleep_history: list[dict],
    stress_days: list[str],
    plan_days: list[dict],
    wake_minutes: list[int],
    today: date,
) -> dict:
    """Pure core. `stress_days` are ISO dates in the last few days with high stress."""
    debt = build_sleep_debt(sleep_history, today, series_days=STRESS_WINDOW_DAYS)
    if not debt["available"] or debt["status"] != "risk":
        return {"active": False}
    window_start = (today - timedelta(days=STRESS_WINDOW_DAYS - 1)).isoformat()
    stressed = sorted({day for day in stress_days if window_start <= day <= today.isoformat()})
    if len(stressed) < MIN_STRESS_DAYS:
        return {"active": False}

    baseline = debt["baseline_hours"]
    target_hours = round(baseline + EXTRA_SLEEP_HOURS, 2)
    nights = {datetime.strptime(item["date"], "%Y-%m-%d").date(): float(item["value"]) for item in sleep_history if item.get("value")}
    as_of = datetime.strptime(debt["as_of"], "%Y-%m-%d").date()
    projection = _project(nights, as_of, target_hours)
    clears_on = projection[-1]["date"] if projection and projection[-1]["debt_hours"] < CAUTION_HOURS else None

    wake = round(median(wake_minutes)) if len(wake_minutes) >= MIN_WAKE_NIGHTS else None
    bedtime_minutes = wake - round(target_hours * 60) - FALL_ASLEEP_MINUTES if wake is not None else None
    if bedtime_minutes is not None:
        bedtime_minutes -= bedtime_minutes % 15
    bedtime = _clock(bedtime_minutes) if bedtime_minutes is not None else None
    finish_by = _clock(bedtime_minutes - WIND_DOWN_HOURS * 60) if bedtime_minutes is not None else None

    bedtimes = []
    for offset in range(BEDTIME_NIGHTS):
        # The night before a wake date; the first one is tonight unless last night hasn't synced yet.
        wake_day = as_of + timedelta(days=offset + 1)
        if wake_day <= today:
            continue
        bedtimes.append({"night_of": (wake_day - timedelta(days=1)).isoformat(), "bedtime": bedtime, "sleep_hours": target_hours})

    cap_until = clears_on or (projection[-1]["date"] if projection else today.isoformat())
    sessions = [
        _session_advice(day, finish_by, day["date"] <= cap_until)
        for day in plan_days
        if str(day.get("session_type") or "").lower() not in SKIP_SESSION_TYPES
    ]

    recent = [
        {"date": point["date"], "debt_hours": point["value"], "projected": False}
        for point in reversed(debt["history"])
    ]
    return {
        "active": True,
        "debt_hours": debt["debt_hours"],
        "baseline_hours": baseline,
        "target_sleep_hours": target_hours,
        "stress_days": stressed,
        "wake_time": _clock(wake) if wake is not None else None,
        "bedtime": bedtime,
        "finish_by": finish_by,
        "bedtimes": bedtimes,
        "session_cap_min": SESSION_CAP_MIN,
        "sessions": sessions,
        "progress": recent + projection,
        "clears_on": clears_on,
        "headline": f"Pay back {debt['debt_hours']:.0f} h of sleep debt",
        "message": (
            f"Stress has been high on {len(stressed)} of the last {STRESS_WINDOW_DAYS} days and you are "
            f"{debt['debt_hours']:.1f} h short of your usual {baseline:.1f} h a night. "
            + (f"Bed by {bedtime} for {target_hours:.1f} h " if bedtime else f"Aim for {target_hours:.1f} h ")
            + "the next three nights; sessions stay in the week but move earlier and stay under "
            + f"{SESSION_CAP_MIN} min until the debt clears."
        ),
    }


def _stress_days(conn: sqlite3.Connection, today: date) -> list[str]:
    start = (today - timedelta(days=STRESS_WINDOW_DAYS - 1)).isoformat()
    end = today.isoformat()
    try:
        rows = conn.execute("SELECT date FROM daily_checkins WHERE date BETWEEN ? AND ? AND stress >= ?", (start, end, STRESS_LEVEL)).fetchall()
        days = {row["date"] for row in rows}
        days |= {day for day, item in get_life_load_days(conn, start, end).items() if set(item.get("tags", [])) & set(STRESS_TAGS)}
    except sqlite3.OperationalError:
        return []
    return sorted(days)


def _wake_minutes(conn: sqlite3.Connection, today: date) -> list[int]:
    """Local wake time (minutes after midnight) of each recent night, from the last asleep sample."""
    try:
        rows = conn.execute(
            """
            SELECT date, MAX(end_timestamp) AS woke FROM health_metric_samples
            WHERE metric = 'sleep' AND end_timestamp IS NOT NULL AND category_label != 'awake' AND date >= ?
            GROUP BY date
            """,
            ((today - timedelta(days=WAKE_LOOKBACK_DAYS)).isoformat(),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    minutes = []
    for row in rows:
        try:
            woke = datetime.fromisoformat(str(row["woke"]).replace("Z", "+00:00")).astimezone()
        except ValueError:
            continue
        if woke.hour * 60 + woke.minute < LATEST_WAKE_MINUTES:
            minutes.append(woke.hour * 60 + woke.minute)
    return minutes


def _remaining_plan_days(conn: sqlite3.Connection, today: date) -> list[dict]:
    """This week's planned days from today on; today drops out once something is recorded."""
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    try:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
        done_today = conn.execute("SELECT 1 FROM activities WHERE substr(date, 1, 10) = ? LIMIT 1", (today.isoformat(),)).fetchone()
    except sqlite3.OperationalError:
        return []
    days = json.loads(row["days_json"]) if row else []
    return [
        day for day in days
        if day.get("date") and (day["date"] > today.isoformat() or (day["date"] == today.isoformat() and not done_today))
    ]


def build_sleep_payback(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    try:
        history = get_sleep_history(conn, BASELINE_NIGHTS + WINDOW_NIGHTS + STRESS_WINDOW_DAYS)
    except sqlite3.OperationalError:
        return {"active": False}
    stress = _stress_days(conn, today)
    if len(stress) < MIN_STRESS_DAYS:
        return {"active": False}
    return build_sleep_payback_plan(history, stress, _remaining_plan_days(conn, today), _wake_minutes(conn, today), today)


def sleep_payback_coaching_context(conn: sqlite3.Connection) -> Optional[dict]:
    plan = build_sleep_payback(conn)
    if not plan["active"]:
        return None
    return {
        "debt_hours": plan["debt_hours"],
        "stress_days": plan["stress_days"],
        "bedtime": plan["bedtime"],
        "finish_by": plan["finish_by"],
        "clears_on": plan["clears_on"],
        "guidance": (
            f"Sleep payback: keep remaining sessions under {SESSION_CAP_MIN} min and in morning or early-evening slots"
            + (f" (done by {plan['finish_by']})" if plan["finish_by"] else "")
            + " until the debt clears. Never remove lift sessions; shorten or move them."
        ),
    }
