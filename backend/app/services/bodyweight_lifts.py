"""Bodyweight lifts: plan days with no gym kit (travel kit, a coach-written bodyweight session at the
parents' or in a hotel), run on the phone as a one-time strength session.

The exercises come from, in order: the day's structured ``exercises`` (the coach fills these), its
written ``steps`` parsed as "Name, 3 sets x 8-12 reps" or "Plank, 3 sets x 30-45 sec", and last a
stock list picked by the words in the title. Holds carry ``seconds`` instead of ``reps``.
"""
import re
from typing import Optional

NO_EQUIPMENT_LIFT_RE = re.compile(r"travel kit|body\s?weight|no[- ]equipment", re.IGNORECASE)
DEFAULT_REST_SECONDS = 60


def is_no_equipment_lift(day: dict) -> bool:
    """These never take a saved A/B/C/D workout or loaded accessories."""
    return bool(NO_EQUIPMENT_LIFT_RE.search(str(day.get("title") or "")))


def _lift(name: str, sets: int, reps: Optional[int], rest_seconds: int, notes: Optional[str], seconds: Optional[int] = None) -> dict:
    return {"name": name, "sets": sets, "reps": reps, "seconds": seconds, "weight_kg": None, "rest_seconds": rest_seconds, "notes": notes}


STOCK_BLOCKS = {
    "upper": [
        _lift("Push Up", 4, 12, 90, "Hands on a table or sofa edge if 12 is too many; feet raised once it's easy."),
        _lift("Pike Push Up", 3, 8, 90, "Hips high, lower the head between the hands. Shoulders, not chest."),
        _lift("Chair Dip", 3, 10, 90, "Sturdy chair, elbows straight back, shoulders down."),
        _lift("Backpack Row", 3, 12, 60, "Pack filled with water bottles, hinge forward, pull to the hip. Reps per arm."),
    ],
    "lower": [
        _lift("Air Squat", 3, 15, 60, "Sit between the heels, chest up, 2 s down."),
        _lift("Reverse Lunge", 3, 10, 60, "Step back, back knee hovers over the floor. Reps per leg."),
        _lift("Glute Bridge", 3, 15, 60, "Squeeze at the top for a second."),
    ],
    "core": [
        _lift("Plank", 3, None, 45, "Squeeze glutes, ribs down, breathe.", seconds=40),
        _lift("Dead Bug", 3, 10, 45, "Lower back pressed into the floor, slow opposite arm and leg. Reps per side."),
        _lift("Reverse Crunch", 3, 12, 45, "Curl the hips off the floor, lower slowly."),
    ],
}

# "Push-ups, 4 sets x 8-15 reps at 2 RIR", "Plank, 3 sets x 30-45 sec", "Dead bug, 3 x 10 per side".
_STEP_RE = re.compile(
    r"^(?P<name>[^,:;]+?),\s*(?P<sets>\d{1,2})\s*(?:sets?\s*)?[x×]\s*(?P<low>\d{1,3})(?:\s*[-–]\s*(?P<high>\d{1,3}))?"
    r"\s*(?P<unit>reps?\b|sec(?:onds?|s)?\b|s\b|min(?:utes?|s)?\b)?(?P<rest>.*)$",
    re.IGNORECASE,
)


def parse_step(step: str) -> Optional[dict]:
    match = _STEP_RE.match(step.strip())
    if not match:
        return None
    low, high = int(match["low"]), int(match["high"] or match["low"])
    unit = (match["unit"] or "").lower()
    value = (low + high) / 2
    name = match["name"].strip()
    notes = match["rest"].strip(" ,.;") or None
    if notes:
        notes = notes[0].upper() + notes[1:]
    seconds = None
    reps: Optional[int] = None
    if unit.startswith("min"):
        seconds = int(round(value * 60))
    elif unit.startswith("s"):
        seconds = int(5 * round(value / 5))
    else:
        reps = int(round(value))
    return _lift(name[0].upper() + name[1:], int(match["sets"]), reps, DEFAULT_REST_SECONDS, notes, seconds=seconds)


def _from_structured(items: list) -> list[dict]:
    return [
        _lift(item["name"], item["sets"], item.get("reps"), item.get("rest_seconds") or DEFAULT_REST_SECONDS, item.get("notes"), seconds=item.get("seconds"))
        | {"weight_kg": item.get("weight_kg")}
        for item in items
        if item.get("name") and item.get("sets") and (item.get("reps") or item.get("seconds"))
    ]


def _stock(title: str) -> list[dict]:
    title = title.lower()
    blocks = [key for key in ("upper", "lower", "core") if re.search(rf"\b{key}\b", title)]
    if re.search(r"\b(?:legs|full body|full-body)\b", title):
        blocks = [key for key in ("upper", "lower") if key not in blocks] + blocks
    if not [key for key in blocks if key != "core"]:
        blocks.insert(0, "upper")
    return [dict(item) for key in blocks for item in STOCK_BLOCKS[key]]


def lift_exercises(day: dict) -> list[dict]:
    """The exercises a no-equipment lift day runs as, in the coach's order."""
    structured = _from_structured(day.get("exercises") or [])
    if structured:
        return structured
    parsed = [item for item in (parse_step(step) for step in day.get("steps") or []) if item]
    return parsed or _stock(str(day.get("title") or ""))
