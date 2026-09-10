"""Source-backed general self-care exercise catalogue. No claim of clinical approval."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator


class ReviewedExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    version: int = Field(ge=1)
    source_publisher: str = Field(min_length=1)
    source_checked_on: date
    hold_seconds: int = Field(default=0, ge=0, le=30)
    scope: Literal["general_soreness"]
    locations: list[str] = Field(min_length=1)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    equipment: str = Field(min_length=1)
    stop_conditions: str = Field(min_length=1)
    source_url: HttpUrl
    repetitions_min: int = Field(ge=1, le=30)
    repetitions_max: int = Field(ge=1, le=30)
    sets_min: int = Field(ge=1, le=3)
    sets_max: int = Field(ge=1, le=3)

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.repetitions_min > self.repetitions_max or self.sets_min > self.sets_max:
            raise ValueError("Invalid prescription bounds.")
        if self.source_url.scheme != "https":
            raise ValueError("Exercise sources must use HTTPS.")
        if any(not location.strip() or location != location.strip().lower() for location in self.locations):
            raise ValueError("Locations must be normalized, explicit names.")
        return self

STOP = "Stop if pain increases, movement hurts, or new symptoms appear. Do not force the range. If symptoms remain worse afterwards or the next morning, pause and seek advice."
KNEE_SOURCE = "https://www.merseycare.nhs.uk/download_file/view/487/738"
SITTING_SOURCE = "https://www.nhs.uk/live-well/exercise/sitting-exercises/"


def entry(id, locations, name, purpose, instructions, source, reps, hold=0, sets=1):
    return dict(id=id, version=1, scope="general_soreness", locations=locations,
                name=name, purpose=purpose, instructions=instructions,
                source_url=source, source_publisher="Mersey Care NHS Foundation Trust" if source == KNEE_SOURCE else "NHS",
                source_checked_on="2026-09-08", hold_seconds=hold,
                frequency="Start with one short session; repeat only if symptoms stay settled. Build gradually within the source guidance.",
                equipment="Stable chair or exercise mat", stop_conditions=STOP,
                repetitions_min=reps, repetitions_max=reps, sets_min=sets, sets_max=sets)


# Public general self-care guidance, not an independently clinically validated protocol.
# Initial volumes below the source targets are deliberate conservative starting doses.
EXERCISES = (
    entry("knee-comfortable-movement", ["knee"], "Gentle knee bend and straighten",
          "Maintain comfortable knee movement.",
          "Sit on a stable chair. Slowly bend and straighten the affected knee within a painless range. Avoid the deep bend if it reproduces your symptoms.", KNEE_SOURCE, 5),
    entry("knee-thigh-contraction", ["knee", "quads"], "Static thigh contraction",
          "Activate the front thigh without repeatedly bending the knee.",
          "Sit or lie with your leg supported straight. Tighten the front thigh, gently pressing the back of the knee towards the supporting surface. Hold, then relax for three seconds. Skip if uncomfortable.", KNEE_SOURCE, 5, 10),
    entry("ankle-mobility", ["calves", "ankle"], "Seated ankle stretch",
          "Move the ankle gently.",
          "Sit upright holding the chair. Extend one leg with the foot lifted. Slowly point your toes away, then back towards you. Repeat on each side.", SITTING_SOURCE, 5, sets=2),
    entry("hip-marching", ["hip"], "Seated hip marching",
          "Gentle hip and thigh movement.",
          "Sit upright and hold the chair. Lift one bent knee only as far as comfortable. Lower slowly. Alternate sides; repetitions are per side.", SITTING_SOURCE, 5),
    entry("neck-rotation", ["neck"], "Comfortable neck rotation",
          "Maintain neck mobility.",
          "Sit tall with relaxed shoulders. Turn your head gently to one side, hold, then return to centre. Repeat each side without forcing the turn.", SITTING_SOURCE, 3, 5),
)


def reviewed_library():
    """Validate source-backed entries; the legacy function name is internal only."""
    entries, seen = [], set()
    for entry in EXERCISES:
        try:
            validated = ReviewedExercise.model_validate(entry).model_dump(mode="json")
        except ValidationError:
            continue
        if validated["id"] in seen:
            return []
        seen.add(validated["id"])
        entries.append(validated)
    return entries


def matches_location(entry, location):
    import re
    words = set(re.findall(r"[a-z]+", location.lower()))
    aliases = {"knee": {"knee", "knees"}, "quads": {"quad", "quads", "quadriceps", "thigh", "thighs"},
               "calves": {"calf", "calves"}, "ankle": {"ankle", "ankles"},
               "hip": {"hip", "hips"}, "neck": {"neck"}}
    return any(words & aliases.get(area, {area}) for area in entry["locations"])
