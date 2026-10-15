from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from ..db import get_db
from ..models.plans import WeeklyPlan, WeeklyPlanAdjustment, WeeklyPlanSwap
from ..services.plans import (
    adjust_weekly_plan_data,
    build_multi_week_execution_trend,
    list_weekly_plans_data,
    preview_weekly_plan_adjustment_data,
    swap_weekly_plan_days_data,
    upsert_weekly_plan_data,
)
from ..services.plan_follow_through import build_plan_follow_through
from ..services.minimum_week import apply_minimum_week, preview_minimum_week, restore_full_week
from ..services.today_options import apply_today_option, build_today_options, undo_today_option
from ..models.plans import TodayOptionApply, TodayOptionUndo, WinterArc, WinterArcAdjustment, WinterArcAdjustmentUndo
from ..services.arc_adjust import apply_arc_adjustment, undo_arc_adjustment, winter_arc_payload
from ..services.season_timeline import PREVIEW_MAX_WEEKS, build_season_timeline
from ..services.week_preview import PREVIEW_WEEKS, build_week_preview
from ..services.load_forecast import build_load_forecast
from ..services.winter_arc import clear_winter_arc, save_winter_arc

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


@router.post("/plans/weekly/swap")
def swap_weekly_plan_days(swap: WeeklyPlanSwap):
    conn = get_db()
    try:
        return swap_weekly_plan_days_data(conn, swap)
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


@router.get("/plans/follow-through")
def plan_follow_through(weeks: int = 12, day: Optional[date] = None):
    conn = get_db()
    try:
        return build_plan_follow_through(conn, weeks=weeks, today=day)
    finally:
        conn.close()


@router.post("/plans/weekly/{week_start}/minimum-week/preview")
def preview_minimum_viable_week(week_start: date):
    conn = get_db()
    try:
        return preview_minimum_week(conn, week_start.isoformat())
    finally:
        conn.close()


@router.post("/plans/weekly/{week_start}/minimum-week")
def apply_minimum_viable_week(week_start: date):
    conn = get_db()
    try:
        return apply_minimum_week(conn, week_start.isoformat())
    finally:
        conn.close()


@router.post("/plans/weekly/{week_start}/minimum-week/restore")
def restore_minimum_viable_week(week_start: date):
    conn = get_db()
    try:
        return restore_full_week(conn, week_start.isoformat())
    finally:
        conn.close()


@router.get("/plans/week-preview")
def get_week_preview(day: Optional[date] = None, weeks: int = Query(PREVIEW_WEEKS, ge=1, le=PREVIEW_MAX_WEEKS)):
    conn = get_db()
    try:
        return build_week_preview(conn, day, weeks)
    finally:
        conn.close()


@router.get("/plans/load-forecast")
def get_load_forecast(day: Optional[date] = None, weeks: int = Query(PREVIEW_WEEKS, ge=1, le=PREVIEW_MAX_WEEKS)):
    conn = get_db()
    try:
        return build_load_forecast(conn, day, weeks)
    finally:
        conn.close()


@router.get("/plans/season-timeline")
def get_season_timeline(day: Optional[date] = None):
    conn = get_db()
    try:
        return build_season_timeline(conn, day)
    finally:
        conn.close()


@router.get("/plans/winter-arc")
def get_winter_arc(day: Optional[date] = None):
    conn = get_db()
    try:
        return winter_arc_payload(conn, day)
    finally:
        conn.close()


@router.put("/plans/winter-arc")
def put_winter_arc(arc: WinterArc, day: Optional[date] = None):
    conn = get_db()
    try:
        save_winter_arc(conn, arc, day)
        return winter_arc_payload(conn, day)
    finally:
        conn.close()


@router.delete("/plans/winter-arc")
def delete_winter_arc(day: Optional[date] = None):
    conn = get_db()
    try:
        clear_winter_arc(conn, day)
        return winter_arc_payload(conn, day)
    finally:
        conn.close()


@router.post("/plans/winter-arc/adjustment")
def post_winter_arc_adjustment(adjustment: WinterArcAdjustment, day: Optional[date] = None):
    conn = get_db()
    try:
        return apply_arc_adjustment(conn, adjustment.action, adjustment.block_start.isoformat(), adjustment.weeks, day)
    finally:
        conn.close()


@router.post("/plans/winter-arc/adjustment/undo")
def post_winter_arc_adjustment_undo(undo: WinterArcAdjustmentUndo, day: Optional[date] = None):
    conn = get_db()
    try:
        return undo_arc_adjustment(conn, undo.id, day)
    finally:
        conn.close()


@router.get("/plans/today/options")
def today_options(reason: str, day: Optional[date] = None):
    # The browser sends its local date: the container clock is UTC, so around midnight "today" differs.
    conn = get_db()
    try:
        return build_today_options(conn, reason, day)
    finally:
        conn.close()


@router.post("/plans/today/options/apply")
def apply_today(request: TodayOptionApply):
    conn = get_db()
    try:
        return apply_today_option(conn, request.reason, request.key, request.day)
    finally:
        conn.close()


@router.post("/plans/today/options/undo")
def undo_today(request: TodayOptionUndo):
    conn = get_db()
    try:
        return undo_today_option(conn, request.undo, request.day)
    finally:
        conn.close()
