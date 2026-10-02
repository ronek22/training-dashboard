import sqlite3
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional

from .checkins import latest_daily_checkin
from .sick_mode import get_active_sick_period
from .health_data import get_health_metric_history
from .sleep_debt import BASELINE_NIGHTS, WINDOW_NIGHTS, build_sleep_debt

# Weekly load growth above this is the classic "too much, too soon" line.
RAMP_CAUTION_PCT = 10
RAMP_HIGH_PCT = 25
# A week this light is a poor base to compare against; ratios would be noise.
RAMP_MIN_PRIOR_LOAD = 40.0

BASELINE_DAYS = 28
MAX_SIGNAL_AGE_DAYS = 2
MIN_BASELINE_POINTS = 7


def build_ramp_rate(training_load_summary: Optional[dict]) -> dict:
    """Compare the last 7 days of load with the 7 days before them."""
    chart = (training_load_summary or {}).get("chart") or []
    if len(chart) < 14:
        return {"status": "insufficient_data", "available": False, "message": "Not enough load history for a ramp-rate check."}

    loads = [float(item.get("load") or 0) for item in chart]
    current_week = round(sum(loads[-7:]), 1)
    prior_week = round(sum(loads[-14:-7]), 1)
    base = {
        "current_week_load": current_week,
        "prior_week_load": prior_week,
        "caution_pct": RAMP_CAUTION_PCT,
        "high_pct": RAMP_HIGH_PCT,
    }
    if prior_week < RAMP_MIN_PRIOR_LOAD:
        return {
            **base,
            "status": "insufficient_data",
            "available": False,
            "change_pct": None,
            "message": "Last week was too light to judge the ramp rate.",
        }

    change_pct = round((current_week - prior_week) / prior_week * 100)
    if change_pct > RAMP_HIGH_PCT:
        status = "high"
        message = f"Load is up {change_pct}% on the previous 7 days. Hold or trim volume for a few days."
    elif change_pct > RAMP_CAUTION_PCT:
        status = "caution"
        message = f"Load is up {change_pct}% on the previous 7 days, above the ~{RAMP_CAUTION_PCT}% guideline."
    elif change_pct < -RAMP_CAUTION_PCT:
        status = "down"
        message = f"Load is down {abs(change_pct)}% on the previous 7 days."
    else:
        status = "ok"
        message = f"Load change of {change_pct:+d}% is within the ~{RAMP_CAUTION_PCT}% guideline."
    return {**base, **{"status": status, "available": True, "change_pct": change_pct, "message": message}}


def _fresh(entry_date: str, today) -> bool:
    return (today - datetime.strptime(entry_date, "%Y-%m-%d").date()).days <= MAX_SIGNAL_AGE_DAYS


def _baseline(history: list[dict], today, smooth_days: int = 1) -> Optional[tuple[float, float]]:
    """Return (recent value, mean of the readings before it).

    `smooth_days` averages that many latest readings, for noisy signals like HRV
    where one bad morning says little on its own.
    """
    if not history or not _fresh(history[0]["date"], today):
        return None
    cutoff = (today - timedelta(days=BASELINE_DAYS)).isoformat()
    recent = [float(item["value"]) for item in history[:smooth_days]]
    prior = [float(item["value"]) for item in history[smooth_days:] if item["date"] >= cutoff]
    if len(prior) < MIN_BASELINE_POINTS:
        return None
    return mean(recent), mean(prior)


def _factor(key: str, label: str, detail: str, tone: str, points: int) -> dict:
    return {"key": key, "label": label, "detail": detail, "tone": tone, "points": points}


def _physiology_factors(conn: sqlite3.Connection, today) -> list[dict]:
    factors: list[dict] = []

    hrv = _baseline(get_health_metric_history(conn, "hrv", BASELINE_DAYS + 7), today, smooth_days=3)
    if hrv:
        recent, base = hrv
        diff_pct = round((recent - base) / base * 100) if base else 0
        points = 2 if diff_pct <= -15 else 1 if diff_pct <= -8 else 0
        factors.append(_factor(
            "hrv", "HRV",
            f"{round(recent)} ms (3-day avg), {diff_pct:+d}% vs 4-week average",
            "risk" if points == 2 else "caution" if points else "steady", points,
        ))

    resting = _baseline(get_health_metric_history(conn, "resting_hr", BASELINE_DAYS + 7), today)
    if resting:
        recent, base = resting
        diff = round(recent - base)
        points = 2 if diff >= 5 else 1 if diff >= 3 else 0
        factors.append(_factor(
            "resting_hr", "Resting HR",
            f"{round(recent)} bpm, {diff:+d} vs 4-week average",
            "risk" if points == 2 else "caution" if points else "steady", points,
        ))

    sleep_history = get_health_metric_history(conn, "sleep", BASELINE_NIGHTS + WINDOW_NIGHTS + 2)
    sleep_points = 0
    if sleep_history and _fresh(sleep_history[0]["date"], today):
        hours = float(sleep_history[0]["value"])
        sleep_points = 2 if hours < 6 else 1 if hours < 7 else 0
        factors.append(_factor(
            "sleep", "Sleep", f"{hours:.1f} h last night",
            "risk" if sleep_points == 2 else "caution" if sleep_points else "steady", sleep_points,
        ))

    debt = build_sleep_debt(sleep_history, today, series_days=2)
    if debt["available"]:
        tone = {"risk": "risk", "caution": "caution"}.get(debt["status"], "steady")
        wanted = 2 if tone == "risk" else 1 if tone == "caution" else 0
        # Last night and the weekly debt describe the same sleep; together they count at most 2.
        points = max(0, min(wanted, 2 - sleep_points))
        factor = _factor(
            "sleep_debt", "Sleep debt",
            f"{debt['debt_hours']:.1f} h over {debt['nights']} nights vs your {debt['baseline_hours']:.1f} h median",
            tone, points,
        )
        factor["summary"] = {key: value for key, value in debt.items() if key != "history"}
        factors.append(factor)
    return factors


def _checkin_factor(latest_feedback: Optional[dict], today) -> Optional[dict]:
    if not latest_feedback:
        return None
    feedback_date = latest_feedback.get("activity_date")
    if not feedback_date or (today - datetime.strptime(feedback_date, "%Y-%m-%d").date()).days > 3:
        return None
    energy = int(latest_feedback.get("energy") or 0)
    soreness = int(latest_feedback.get("muscle_soreness") or 0)
    pain = int(latest_feedback.get("pain_level") or 0)
    points = 2 if pain >= 4 or energy == 1 else 1 if energy == 2 or soreness >= 4 else 0
    return _factor(
        "check_in", "Check-in",
        f"energy {energy}/5, soreness {soreness}/5, pain {pain}/10",
        "risk" if points == 2 else "caution" if points else "steady", points,
    )


def _daily_checkin_factor(checkin: Optional[dict], today) -> Optional[dict]:
    """The morning check-in, when it is from today or yesterday."""
    if not checkin:
        return None
    age = (today - datetime.strptime(checkin["date"], "%Y-%m-%d").date()).days
    if age < 0 or age > 1:
        return None
    energy, soreness = int(checkin["energy"]), int(checkin["muscle_soreness"])
    stress, sleep_quality = int(checkin["stress"]), int(checkin["sleep_quality"])
    pain = int(checkin.get("pain_level") or 0)
    flags = [
        energy <= 2 and f"low energy {energy}/5",
        soreness >= 4 and f"soreness {soreness}/5",
        stress >= 4 and f"stress {stress}/5",
        sleep_quality <= 2 and f"poor sleep {sleep_quality}/5",
        pain >= 4 and f"pain {pain}/10",
    ]
    flags = [flag for flag in flags if flag]
    points = 2 if pain >= 4 or energy == 1 else min(2, len(flags))
    detail = ", ".join(flags) if flags else f"energy {energy}/5, stress {stress}/5, soreness {soreness}/5"
    return _factor(
        "check_in", "Morning check-in", detail,
        "risk" if points == 2 else "caution" if points else "steady", points,
    )


LEVEL_LABELS = {"green": "Green", "amber": "Amber", "red": "Red", "unknown": "No read"}
LEVEL_ADVICE = {
    "green": "Signals are aligned. Train as planned.",
    "amber": "Some signals are off. Keep hard sessions honest or swap for something easier.",
    "red": "Several signals point to poor recovery. Swap today's hard session for recovery or rest.",
    "unknown": "Not enough recent data for a readiness score.",
}


def build_readiness_score(
    conn: sqlite3.Connection,
    *,
    state: str,
    latest_feedback: Optional[dict],
    training_load_summary: Optional[dict],
    ramp: Optional[dict] = None,
    daily_checkin: Optional[dict] = None,
) -> dict:
    """Blend load state, sleep/HRV/resting HR, the latest check-in and ramp rate into green/amber/red."""
    today = datetime.now().date()
    ramp = ramp if ramp is not None else build_ramp_rate(training_load_summary)

    try:
        factors = _physiology_factors(conn, today)
    except sqlite3.OperationalError:
        factors = []
    checkin = _daily_checkin_factor(daily_checkin if daily_checkin is not None else latest_daily_checkin(conn), today)
    checkin = checkin or _checkin_factor(latest_feedback, today)
    if checkin:
        factors.append(checkin)
    sick = get_active_sick_period(conn)
    if sick:
        below_neck = sick["severity"] == "below_neck"
        factors.insert(0, _factor(
            "sick", "Sick mode", "fever or chest symptoms" if below_neck else "head cold",
            "risk", 4 if below_neck else 2,
        ))

    ratio_status = ((training_load_summary or {}).get("ratio") or {}).get("status")
    form = float(((training_load_summary or {}).get("current") or {}).get("form") or 0)
    load_points = 2 if state == "strained" else 1 if state == "watch" else 0
    load_detail = f"training form {round(form)}, load ratio {ratio_status or 'n/a'}"
    factors.append(_factor(
        "load", "Training load", load_detail,
        "risk" if load_points == 2 else "caution" if load_points else "steady", load_points,
    ))

    ramp_points = 2 if ramp.get("status") == "high" else 1 if ramp.get("status") == "caution" else 0
    if ramp.get("available"):
        factors.append(_factor(
            "ramp", "Weekly ramp", f"{ramp['change_pct']:+d}% vs previous 7 days",
            "risk" if ramp_points == 2 else "caution" if ramp_points else "steady", ramp_points,
        ))

    has_evidence = state != "insufficient_data" or len(factors) > 1
    points = sum(item["points"] for item in factors)
    if not has_evidence:
        level = "unknown"
    elif points >= 4:
        level = "red"
    elif points >= 2:
        level = "amber"
    else:
        level = "green"

    drivers = [item for item in factors if item["points"] > 0]
    return {
        "level": level,
        "label": LEVEL_LABELS[level],
        "points": points,
        "advice": LEVEL_ADVICE[level],
        "suggests_swap": level in {"amber", "red"},
        "factors": factors,
        "drivers": [f"{item['label']}: {item['detail']}" for item in drivers[:3]],
        "physiology_available": any(item["key"] in {"hrv", "resting_hr", "sleep", "sleep_debt"} for item in factors),
        "sleep_debt": next((item["summary"] for item in factors if item["key"] == "sleep_debt"), None),
    }
