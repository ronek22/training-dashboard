from fastapi import APIRouter, Query

from ..db import get_db
from ..models.metrics import Metric
from ..services.metrics import create_metric_data, get_metric_history_data, get_performance_summary_data
from ..services.dashboard import (
    build_activity_heatmap,
    build_yearly_distance_series,
    build_yearly_duration_series,
    compute_activity_streak,
)
from ..services.health_data import get_health_summary
from ..services.heart_rate_zones import build_recent_heart_rate_zone_summary
from ..services.settings import get_performance_settings_for_conn

router = APIRouter()


@router.get("/metrics/health-summary")
def health_summary(days: int = 90):
    conn = get_db()
    try:
        return get_health_summary(conn, days=days)
    finally:
        conn.close()


@router.get("/metrics/training-history")
def training_history():
    conn = get_db()
    try:
        settings = get_performance_settings_for_conn(conn)
        return {
            "heart_rate_zone_summary": build_recent_heart_rate_zone_summary(conn, days=14, settings=settings),
            "activity_heatmap": build_activity_heatmap(conn),
            "ride_year_series": build_yearly_distance_series(conn, ("Ride", "VirtualRide")),
            "run_year_series": build_yearly_distance_series(conn, ("Run",)),
            "strength_year_series": build_yearly_duration_series(conn, ("WeightTraining",)),
        }
    finally:
        conn.close()


@router.post("/metrics", status_code=201)
def create_metric(metric: Metric):
    conn = get_db()
    try:
        return create_metric_data(conn, metric.date, metric.metric, metric.value, metric.unit, metric.notes)
    finally:
        conn.close()


@router.get("/metrics/performance-summary")
def get_performance_summary():
    conn = get_db()
    try:
        return get_performance_summary_data(conn)
    finally:
        conn.close()


@router.get("/metrics/session-comparisons")
def session_comparisons(days: int = Query(default=180, ge=30, le=365)):
    from ..services.session_comparisons import get_session_comparisons
    conn = get_db()
    try:
        return get_session_comparisons(conn, days)
    finally:
        conn.close()


@router.get("/metrics/{metric_name}")
def get_metric(metric_name: str, limit: int = 30):
    conn = get_db()
    try:
        return get_metric_history_data(
            conn,
            metric_name=metric_name,
            limit=limit,
            compute_activity_streak_fn=compute_activity_streak,
        )
    finally:
        conn.close()
