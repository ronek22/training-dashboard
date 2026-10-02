"""Carbs and bottles to bring on a planned ride.

Bands follow common sports-nutrition guidance: 30–60 g/h keeps endurance
rides going, 60–90 g/h supports sweet spot and harder work. Short or recovery
rides need no plan beyond water.
"""
import math
from typing import Optional

from .cycling_workouts import get_cycling_workout, render_cycling_workout

RIDE_TYPES = {"ride", "virtualride", "cycling", "bike"}
HARD_INTENTS = {"tempo", "interval", "race_specific"}
ENDURANCE_INTENTS = {"easy", "long"}

ENDURANCE_MIN_MINUTES = 90
HARD_MIN_MINUTES = 60
BOTTLE_ML = 600
FLUID_ML_PER_H = 500
HOT_FLUID_ML_PER_H = 750


def _target_g_per_h(intent: str, minutes: int) -> int:
    if intent in HARD_INTENTS:
        return 75 if minutes >= 90 else 60
    return 60 if minutes >= 180 else 50 if minutes >= 120 else 40


def _bottles(minutes: int, ml_per_h: int) -> int:
    # Round half up: 2.5 bottles means bring 3.
    return max(1, math.floor(minutes / 60 * ml_per_h / BOTTLE_ML + 0.5))


def build_fuel_plan(day: dict) -> Optional[dict]:
    """Return a fuel plan for a ride long or hard enough to need one, else None."""
    if str(day.get("session_type") or "").strip().lower() not in RIDE_TYPES:
        return None
    workout = get_cycling_workout(day.get("cycling_workout_id"))
    intent = str(day.get("workout_intent") or (workout or {}).get("workout_intent") or "easy").lower()
    minutes = day.get("target_duration_min") or (render_cycling_workout(workout)["duration_min"] if workout else None)
    if not minutes or intent == "recovery":
        return None
    minutes = int(minutes)

    hard = intent in HARD_INTENTS
    if minutes < (HARD_MIN_MINUTES if hard else ENDURANCE_MIN_MINUTES):
        return None

    low, high = (60, 90) if hard else (30, 60)
    target = _target_g_per_h(intent, minutes)
    total = int(math.ceil(target * minutes / 60 / 10) * 10)
    bottles = _bottles(minutes, FLUID_ML_PER_H)
    hot_bottles = _bottles(minutes, HOT_FLUID_ML_PER_H)
    return {
        "intent": intent,
        "duration_min": minutes,
        "carbs_g_per_h": {"low": low, "high": high, "target": target},
        "total_carbs_g": total,
        "bottles": bottles,
        "hot_bottles": hot_bottles,
        "bottle_ml": BOTTLE_ML,
        "summary": f"~{target} g carbs/h · {total} g total · {bottles} bottle{'s' if bottles != 1 else ''}"
        + (f" ({hot_bottles} if hot)" if hot_bottles != bottles else ""),
        "tip": (
            "Start eating in the first 20 minutes and keep going every 20–30 minutes; drink mix counts toward carbs."
            if hard else
            "Eat little and often from the first half hour, before you feel hungry."
        ),
    }
