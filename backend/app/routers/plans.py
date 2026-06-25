from fastapi import APIRouter

from ..db import get_db
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment
from ..repositories.plans import upsert_weekly_plan_row
from ..services.plans import adjust_weekly_plan_data, list_weekly_plans_data

router = APIRouter()


@router.post("/plans/weekly", status_code=201)
def upsert_weekly_plan(plan: WeeklyPlan):
    conn = get_db()
    try:
        upsert_weekly_plan_row(conn, plan)
        conn.commit()
        return {"status": "ok", "week_start": plan.week_start}
    finally:
        conn.close()


@router.post("/plans/weekly/adjust")
def adjust_weekly_plan(adjustment: WeeklyPlanAdjustment):
    conn = get_db()
    try:
        return adjust_weekly_plan_data(conn, adjustment)
    finally:
        conn.close()


@router.get("/plans/weekly")
def list_weekly_plans(limit: int = 8):
    conn = get_db()
    try:
        return list_weekly_plans_data(conn, limit=limit)
    finally:
        conn.close()
