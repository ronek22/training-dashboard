"""Deterministic structured cycling workouts with Zwift .zwo export.

Steps are defined as FTP fractions. Exported .zwo files keep those fractions so
Zwift scales every target to the FTP configured in Zwift itself; watt targets
shown in the app use the latest stored FTP metric and say which one.
"""
import math
import sqlite3
from datetime import date, datetime
from typing import Optional
from xml.sax.saxutils import escape, quoteattr

FTP_STALE_AFTER_DAYS = 56
ZWO_AUTHOR = "Training Dashboard"


def _warmup(minutes, low, high):
    return {"kind": "warmup", "duration_s": minutes * 60, "power_low": low, "power_high": high}


def _cooldown(minutes, high, low):
    # Zwift reads Cooldown PowerLow as the starting power and PowerHigh as the end.
    return {"kind": "cooldown", "duration_s": minutes * 60, "power_low": high, "power_high": low}


def _steady(minutes, power, label=None):
    return {"kind": "steady", "duration_s": round(minutes * 60), "power": power, "label": label}


def _intervals(repeat, on_s, on_power, off_s, off_power, label=None):
    return {
        "kind": "intervals", "repeat": repeat, "on_duration_s": on_s, "on_power": on_power,
        "off_duration_s": off_s, "off_power": off_power, "label": label,
    }


# Weekday sessions fit the 60-90 minute window; long rides are for weekends.
CYCLING_WORKOUTS = (
    {
        "id": "recovery-spin-40", "name": "Recovery spin", "category": "Recovery", "workout_intent": "recovery",
        "description": "Very easy spinning to keep the legs moving without adding fatigue.",
        "purpose": "Active recovery that still counts as a day on the bike.",
        "steps": [_warmup(5, 0.40, 0.50), _steady(30, 0.50, "Easy spin"), _cooldown(5, 0.50, 0.40)],
    },
    {
        "id": "endurance-60", "name": "Endurance 60", "category": "Endurance", "workout_intent": "easy",
        "description": "Steady zone 2 riding with a gentle warm-up and cool-down.",
        "purpose": "Aerobic base with low fatigue cost.",
        "steps": [_warmup(10, 0.45, 0.65), _steady(45, 0.68, "Zone 2"), _cooldown(5, 0.60, 0.45)],
    },
    {
        "id": "endurance-long-120", "name": "Long endurance 2 h", "category": "Endurance", "workout_intent": "long",
        "description": "Two hours of zone 2 with three short tempo surges late in the ride.",
        "purpose": "Weekend aerobic volume and fatigue resistance.",
        "steps": [
            _warmup(10, 0.45, 0.65), _steady(60, 0.68, "Zone 2"),
            _intervals(3, 300, 0.80, 300, 0.65, "Tempo surges"), _steady(15, 0.65, "Zone 2"),
            _cooldown(5, 0.60, 0.45),
        ],
    },
    {
        "id": "tempo-3x12", "name": "Tempo 3 × 12 min", "category": "Tempo", "workout_intent": "tempo",
        "description": "Three 12-minute blocks at tempo with easy recoveries.",
        "purpose": "Raise sustainable power with moderate fatigue cost.",
        "steps": [
            _warmup(12, 0.45, 0.70), _intervals(3, 720, 0.80, 240, 0.55, "Tempo"), _steady(5, 0.60),
            _cooldown(8, 0.60, 0.45),
        ],
    },
    {
        "id": "sweet-spot-3x10", "name": "Sweet spot 3 × 10 min", "category": "Sweet spot", "workout_intent": "tempo",
        "description": "Three 10-minute sweet spot efforts; a good first step back into structure.",
        "purpose": "Build 15-30 minute power efficiently.",
        "steps": [
            _warmup(12, 0.45, 0.72), _intervals(3, 600, 0.89, 300, 0.55, "Sweet spot"), _steady(8, 0.60),
            _cooldown(5, 0.60, 0.45),
        ],
    },
    {
        "id": "sweet-spot-2x20", "name": "Sweet spot 2 × 20 min", "category": "Sweet spot", "workout_intent": "tempo",
        "description": "Two 20-minute sweet spot blocks.",
        "purpose": "Extend time near threshold for climbing-length efforts.",
        "steps": [
            _warmup(12, 0.45, 0.72), _intervals(2, 1200, 0.88, 300, 0.55, "Sweet spot"), _steady(8, 0.60),
            _cooldown(5, 0.60, 0.45),
        ],
    },
    {
        "id": "threshold-4x8", "name": "Threshold 4 × 8 min", "category": "Threshold", "workout_intent": "interval",
        "description": "Four 8-minute efforts at FTP with 4 minutes easy between.",
        "purpose": "Lift threshold power directly.",
        "steps": [
            _warmup(12, 0.45, 0.75), _steady(3, 0.90, "Opener"), _steady(3, 0.55),
            _intervals(4, 480, 1.00, 240, 0.55, "Threshold"), _cooldown(10, 0.60, 0.45),
        ],
    },
    {
        "id": "vo2-5x3", "name": "VO2 max 5 × 3 min", "category": "VO2 max", "workout_intent": "interval",
        "description": "Five 3-minute hard efforts with equal recovery.",
        "purpose": "Raise aerobic ceiling and 3-5 minute power.",
        "steps": [
            _warmup(12, 0.45, 0.75), _intervals(2, 60, 1.05, 60, 0.55, "Openers"), _steady(4, 0.55),
            _intervals(5, 180, 1.15, 180, 0.50, "VO2 max"), _cooldown(10, 0.60, 0.45),
        ],
    },
    {
        "id": "vo2-30-30", "name": "VO2 max 30/30 × 2 sets", "category": "VO2 max", "workout_intent": "interval",
        "description": "Two sets of ten 30-second hard / 30-second easy efforts.",
        "purpose": "Accumulate VO2 max time with short, manageable efforts.",
        "steps": [
            _warmup(12, 0.45, 0.75), _intervals(10, 30, 1.25, 30, 0.50, "Set 1"), _steady(6, 0.55),
            _intervals(10, 30, 1.25, 30, 0.50, "Set 2"), _cooldown(10, 0.60, 0.45),
        ],
    },
)

_WORKOUTS_BY_ID = {workout["id"]: workout for workout in CYCLING_WORKOUTS}
CYCLING_WORKOUT_IDS = frozenset(_WORKOUTS_BY_ID)


def get_cycling_workout(workout_id: Optional[str]) -> Optional[dict]:
    return _WORKOUTS_BY_ID.get(workout_id or "")


def _step_duration(step: dict) -> int:
    if step["kind"] == "intervals":
        return step["repeat"] * (step["on_duration_s"] + step["off_duration_s"])
    return step["duration_s"]


def _power_samples(steps: list[dict]):
    """Yield (seconds, ftp_fraction) segments; ramps are split per minute."""
    for step in steps:
        if step["kind"] == "intervals":
            for _ in range(step["repeat"]):
                yield step["on_duration_s"], step["on_power"]
                yield step["off_duration_s"], step["off_power"]
        elif step["kind"] == "steady":
            yield step["duration_s"], step["power"]
        else:
            minutes = max(1, step["duration_s"] // 60)
            chunk = step["duration_s"] / minutes
            for index in range(minutes):
                share = (index + 0.5) / minutes
                yield chunk, step["power_low"] + (step["power_high"] - step["power_low"]) * share


def _intensity_summary(steps: list[dict]) -> dict:
    total = weighted4 = 0.0
    for seconds, fraction in _power_samples(steps):
        total += seconds
        weighted4 += seconds * fraction ** 4
    intensity_factor = (weighted4 / total) ** 0.25 if total else 0.0
    return {
        "intensity_factor": round(intensity_factor, 2),
        "estimated_tss": round(total / 3600 * intensity_factor ** 2 * 100),
    }


def _watts(ftp: Optional[float], fraction: float) -> Optional[int]:
    return round(ftp * fraction) if ftp else None


def _render_step(step: dict, ftp: Optional[float]) -> dict:
    rendered = {**step, "duration_s": _step_duration(step)}
    if step["kind"] == "intervals":
        rendered["on_watts"] = _watts(ftp, step["on_power"])
        rendered["off_watts"] = _watts(ftp, step["off_power"])
    elif step["kind"] == "steady":
        rendered["watts"] = _watts(ftp, step["power"])
    else:
        rendered["watts_low"] = _watts(ftp, step["power_low"])
        rendered["watts_high"] = _watts(ftp, step["power_high"])
    return rendered


def render_cycling_workout(workout: dict, ftp: Optional[float] = None) -> dict:
    duration_s = sum(_step_duration(step) for step in workout["steps"])
    return {
        **workout,
        "steps": [_render_step(step, ftp) for step in workout["steps"]],
        "duration_min": round(duration_s / 60),
        **_intensity_summary(workout["steps"]),
    }


def latest_ftp(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    row = conn.execute(
        "SELECT value, date FROM metrics WHERE metric = 'ftp' ORDER BY date DESC, id DESC LIMIT 1"
    ).fetchone()
    try:
        watts = float(row["value"]) if row else None
    except (TypeError, ValueError):
        watts = None
    if watts is None or not math.isfinite(watts) or watts <= 0:
        return {"available": False, "watts": None, "date": None, "age_days": None, "stale": False}
    today = today or date.today()
    try:
        age_days = (today - datetime.strptime(row["date"], "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        age_days = None
    return {
        "available": True, "watts": watts, "date": row["date"], "age_days": age_days,
        "stale": age_days is not None and age_days > FTP_STALE_AFTER_DAYS,
    }


def build_cycling_workout_library(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    ftp = latest_ftp(conn, today)
    return {
        "ftp": ftp,
        "ftp_stale_after_days": FTP_STALE_AFTER_DAYS,
        "export_note": "Exported .zwo targets are FTP percentages, so Zwift scales them to the FTP set in Zwift.",
        "workouts": [render_cycling_workout(workout, ftp["watts"]) for workout in CYCLING_WORKOUTS],
    }


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def _zwo_step(step: dict) -> str:
    kind = step["kind"]
    if kind == "warmup":
        return (f'<Warmup Duration="{step["duration_s"]}" PowerLow="{_fmt(step["power_low"])}" '
                f'PowerHigh="{_fmt(step["power_high"])}"/>')
    if kind == "cooldown":
        return (f'<Cooldown Duration="{step["duration_s"]}" PowerLow="{_fmt(step["power_low"])}" '
                f'PowerHigh="{_fmt(step["power_high"])}"/>')
    if kind == "steady":
        return f'<SteadyState Duration="{step["duration_s"]}" Power="{_fmt(step["power"])}"/>'
    return (f'<IntervalsT Repeat="{step["repeat"]}" OnDuration="{step["on_duration_s"]}" '
            f'OffDuration="{step["off_duration_s"]}" OnPower="{_fmt(step["on_power"])}" '
            f'OffPower="{_fmt(step["off_power"])}"/>')


def build_zwo(workout: dict) -> str:
    steps = "\n".join(f"        {_zwo_step(step)}" for step in workout["steps"])
    return (
        "<workout_file>\n"
        f"    <author>{escape(ZWO_AUTHOR)}</author>\n"
        f"    <name>{escape(workout['name'])}</name>\n"
        f"    <description>{escape(workout['description'] + ' ' + workout['purpose'])}</description>\n"
        "    <sportType>bike</sportType>\n"
        f"    <tags>\n        <tag name={quoteattr(workout['category'])}/>\n    </tags>\n"
        f"    <workout>\n{steps}\n    </workout>\n"
        "</workout_file>\n"
    )
