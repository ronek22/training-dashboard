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
    # Set for a recipe dish: macros are for this many portions, and grams usually stay empty.
    portions: Optional[float] = None


class FoodEntryInput(BaseModel):
    date: str
    meal: str = "snack"
    source: str = "manual"
    raw_text: Optional[str] = None
    items: list[FoodItemInput]


class MealPhotoInput(BaseModel):
    media_type: str
    data: str  # base64


class MealEstimateInput(BaseModel):
    text: str = ""
    image: Optional[MealPhotoInput] = None


class DinnerPlanInput(BaseModel):
    # An empty dish clears the day.
    dish: Optional[str] = None
    notes: Optional[str] = None
    kcal: Optional[float] = None
    protein_g: Optional[float] = None
    # Planning a saved recipe sets the dish and numbers from it.
    recipe_id: Optional[int] = None
    servings: Optional[float] = None


class RecipeIngredientInput(BaseModel):
    name: str
    amount: Optional[str] = None
    grams: Optional[float] = None
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    # Set when the ingredient is a saved product, so grams rescale real label values.
    product_id: Optional[int] = None
    per_100g: Optional[dict] = None


class ProductInput(BaseModel):
    name: str
    brand: Optional[str] = None
    barcode: Optional[str] = None
    per_100g: dict
    serving_g: Optional[float] = None
    package_g: Optional[float] = None
    source: str = "manual"


class RecipeInput(BaseModel):
    title: str
    servings: float = 2
    minutes: Optional[int] = None
    source: str = "manual"
    source_url: Optional[str] = None
    ingredients: list[RecipeIngredientInput] = []
    steps: list[str] = []
    tags: list[str] = []
    notes: Optional[str] = None
    per_serving: Optional[dict] = None


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
