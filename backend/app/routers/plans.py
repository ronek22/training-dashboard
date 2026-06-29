from fastapi import APIRouter

from ..db import get_db
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment
from ..services.plans import (
    adjust_weekly_plan_data,
    build_multi_week_execution_trend,
    list_weekly_plans_data,
    preview_weekly_plan_adjustment_data,
    upsert_weekly_plan_data,
)

router = APIRouter()


@router.post("/plans/weekly", status_code=201)
def upsert_weekly_plan(plan: WeeklyPlan):
    conn = get_db()
    try:
        return upsert_weekly_plan_data(conn, plan)
    finally:
        conn.close()


@router.post("/plans/weekly/adjust")
def adjust_weekly_plan(adjustment: WeeklyPlanAdjustment):
    conn = get_db()
    try:
        return adjust_weekly_plan_data(conn, adjustment)
    finally:
        conn.close()


@router.post("/plans/weekly/adjust/preview")
def preview_weekly_plan_adjustment(adjustment: WeeklyPlanAdjustment):
    conn = get_db()
    try:
        return preview_weekly_plan_adjustment_data(conn, adjustment)
    finally:
        conn.close()


@router.get("/plans/weekly")
def list_weekly_plans(limit: int = 8):
    conn = get_db()
    try:
        return list_weekly_plans_data(conn, limit=limit)
    finally:
        conn.close()


@router.get("/plans/weekly/trends")
def weekly_plan_trends(weeks: int = 6):
    conn = get_db()
    try:
        return build_multi_week_execution_trend(conn, weeks=weeks)
    finally:
        conn.close()
