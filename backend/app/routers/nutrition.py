from fastapi import APIRouter

from ..db import get_db
from ..models.nutrition import FoodEntryInput, FoodItemInput, NutritionProfileInput, ProteinTickInput, WeeklyBodyCheckinInput
from ..services import food_log
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
