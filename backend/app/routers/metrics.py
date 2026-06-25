from fastapi import APIRouter

from ..db import get_db
from ..models.metrics import Metric
from ..services.metrics import create_metric_data, get_metric_history_data
from ..services.dashboard import compute_activity_streak

router = APIRouter()


@router.post("/metrics", status_code=201)
def create_metric(metric: Metric):
    conn = get_db()
    try:
        return create_metric_data(conn, metric.date, metric.metric, metric.value, metric.unit, metric.notes)
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
