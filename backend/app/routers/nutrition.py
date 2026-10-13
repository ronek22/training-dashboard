from typing import Optional

from fastapi import APIRouter, Query

from ..db import get_db
from ..models.nutrition import DinnerPlanInput, FoodEntryInput, ProductInput, RecipeInput, FoodItemInput, NutritionProfileInput, ProteinTickInput, WeeklyBodyCheckinInput
from ..services import dinner_plan, food_log, meal_ideas, products, recipes
from ..services.protein import build_protein_status, set_protein_tick
from ..services.weekly_body_checkin import build_weekly_body_checkin, save_weekly_body_checkin

router = APIRouter()


@router.get("/nutrition/protein")
def get_protein_status():
    conn = get_db()
    try:
        return build_protein_status(conn)
    finally:
        conn.close()


@router.put("/nutrition/protein/{day}")
def put_protein_tick(day: str, payload: ProteinTickInput):
    conn = get_db()
    try:
        return set_protein_tick(conn, day, payload.hit)
    finally:
        conn.close()


@router.get("/nutrition/weekly-checkin")
def get_weekly_body_checkin():
    conn = get_db()
    try:
        return build_weekly_body_checkin(conn)
    finally:
        conn.close()


@router.put("/nutrition/weekly-checkin")
def put_weekly_body_checkin(payload: WeeklyBodyCheckinInput):
    conn = get_db()
    try:
        return save_weekly_body_checkin(conn, payload.protein_most_days, payload.weight_kg, payload.skipped)
    finally:
        conn.close()


@router.get("/nutrition/food")
def get_food_day(date: str):
    conn = get_db()
    try:
        return food_log.build_food_day(conn, date)
    finally:
        conn.close()


@router.get("/nutrition/food/ideas")
def get_meal_ideas(date: str, hour: Optional[int] = Query(None, ge=0, le=23)):
    conn = get_db()
    try:
        return meal_ideas.build_meal_ideas(conn, date, hour)
    finally:
        conn.close()


@router.post("/nutrition/food/entries")
def post_food_entry(payload: FoodEntryInput):
    conn = get_db()
    try:
        return food_log.create_food_entry(conn, payload.model_dump())
    finally:
        conn.close()


@router.put("/nutrition/food/entries/{entry_id}")
def put_food_entry(entry_id: int, payload: FoodEntryInput):
    conn = get_db()
    try:
        return food_log.update_food_entry(conn, entry_id, payload.model_dump())
    finally:
        conn.close()


@router.delete("/nutrition/food/entries/{entry_id}")
def delete_food_entry(entry_id: int):
    conn = get_db()
    try:
        return food_log.delete_food_entry(conn, entry_id)
    finally:
        conn.close()


@router.get("/nutrition/food/saved")
def get_saved_foods():
    conn = get_db()
    try:
        return food_log.list_saved_foods(conn)
    finally:
        conn.close()


@router.post("/nutrition/food/saved")
def post_saved_food(payload: FoodItemInput):
    conn = get_db()
    try:
        return food_log.save_food(conn, payload.model_dump())
    finally:
        conn.close()


@router.post("/nutrition/food/saved/{food_id}/use")
def post_saved_food_use(food_id: int):
    conn = get_db()
    try:
        food_log.use_saved_food(conn, food_id)
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/nutrition/food/saved/{food_id}")
def delete_saved_food(food_id: int):
    conn = get_db()
    try:
        return food_log.delete_saved_food(conn, food_id)
    finally:
        conn.close()


@router.get("/nutrition/dinners")
def get_dinner_week(week_start: str):
    conn = get_db()
    try:
        return dinner_plan.build_dinner_week(conn, week_start)
    finally:
        conn.close()


@router.put("/nutrition/dinners/{day}")
def put_dinner(day: str, payload: DinnerPlanInput):
    conn = get_db()
    try:
        return dinner_plan.set_dinner(conn, day, payload.model_dump())
    finally:
        conn.close()


@router.get("/nutrition/dinners/shopping-list")
def get_dinner_shopping_list(dates: str = ""):
    conn = get_db()
    try:
        return dinner_plan.shopping_list(conn, [value.strip() for value in dates.split(",")])
    finally:
        conn.close()


@router.get("/nutrition/dinners/{day}/log-items")
def get_dinner_log_items(day: str):
    conn = get_db()
    try:
        return dinner_plan.dinner_log_items(conn, day)
    finally:
        conn.close()


@router.get("/nutrition/products")
def get_products(q: str = ""):
    conn = get_db()
    try:
        return products.list_products(conn, q)
    finally:
        conn.close()


@router.get("/nutrition/products/search")
def search_products(q: str):
    return products.search_off(q)


@router.get("/nutrition/products/hint")
def get_products_hint():
    conn = get_db()
    try:
        return products.products_hint(conn)
    finally:
        conn.close()


@router.post("/nutrition/products")
def post_product(payload: ProductInput):
    conn = get_db()
    try:
        return products.save_product(conn, payload.model_dump())
    finally:
        conn.close()


@router.put("/nutrition/products/{product_id}")
def put_product(product_id: int, payload: ProductInput):
    conn = get_db()
    try:
        return products.update_product(conn, product_id, payload.model_dump())
    finally:
        conn.close()


@router.delete("/nutrition/products/{product_id}")
def delete_product(product_id: int):
    conn = get_db()
    try:
        return products.delete_product(conn, product_id)
    finally:
        conn.close()


@router.post("/nutrition/products/{product_id}/use")
def post_product_use(product_id: int):
    conn = get_db()
    try:
        products.use_product(conn, product_id)
        return {"ok": True}
    finally:
        conn.close()


@router.get("/nutrition/recipes")
def get_recipes(q: str = ""):
    conn = get_db()
    try:
        return recipes.list_recipes(conn, q)
    finally:
        conn.close()


@router.post("/nutrition/recipes")
def post_recipe(payload: RecipeInput):
    conn = get_db()
    try:
        return recipes.create_recipe(conn, payload.model_dump())
    finally:
        conn.close()


@router.get("/nutrition/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    conn = get_db()
    try:
        return recipes.get_recipe(conn, recipe_id)
    finally:
        conn.close()


@router.put("/nutrition/recipes/{recipe_id}")
def put_recipe(recipe_id: int, payload: RecipeInput):
    conn = get_db()
    try:
        return recipes.update_recipe(conn, recipe_id, payload.model_dump())
    finally:
        conn.close()


@router.delete("/nutrition/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    conn = get_db()
    try:
        return recipes.delete_recipe(conn, recipe_id)
    finally:
        conn.close()


@router.post("/nutrition/dinners/copy-previous")
def post_copy_previous_dinners(week_start: str):
    conn = get_db()
    try:
        return dinner_plan.copy_previous_week(conn, week_start)
    finally:
        conn.close()


@router.get("/nutrition/profile")
def get_nutrition_profile():
    conn = get_db()
    try:
        return food_log.get_nutrition_profile(conn)
    finally:
        conn.close()


@router.put("/nutrition/profile")
def put_nutrition_profile(payload: NutritionProfileInput):
    conn = get_db()
    try:
        return food_log.save_nutrition_profile(conn, payload.model_dump())
    finally:
        conn.close()


@router.get("/nutrition/context")
def get_nutrition_context():
    conn = get_db()
    try:
        return food_log.build_nutrition_context(conn)
    finally:
        conn.close()
