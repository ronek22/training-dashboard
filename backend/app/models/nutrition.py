from typing import Optional

from pydantic import BaseModel, Field


class ProteinTickInput(BaseModel):
    # None clears the tick.
    hit: Optional[bool] = None


class FoodItemInput(BaseModel):
    name: str
    grams: Optional[float] = None
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    confidence: Optional[str] = None


class FoodEntryInput(BaseModel):
    date: str
    meal: str = "snack"
    source: str = "manual"
    raw_text: Optional[str] = None
    items: list[FoodItemInput]


class NutritionProfileInput(BaseModel):
    sex: Optional[str] = None
    birth_year: Optional[int] = Field(default=None, ge=1920, le=2015)
    height_cm: Optional[float] = Field(default=None, ge=120, le=230)
    daily_life: Optional[str] = None
    goal: Optional[str] = None


class WeeklyBodyCheckinInput(BaseModel):
    protein_most_days: Optional[bool] = None
    weight_kg: Optional[float] = None
    skipped: bool = False
