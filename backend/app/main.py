import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .adapters.mcp import build_mcp_router_dependencies
from .db import get_db, init_db
from .routers.activities import router as activities_router
from .routers.activity_feedback import router as activity_feedback_router
from .routers.coaching import router as coaching_router
from .routers.dashboard import router as dashboard_router
from .routers.goals import router as goals_router
from .routers.integrations import router as integrations_router
from .routers.mcp import build_mcp_app
from .routers.metrics import router as metrics_router
from .routers.notes import router as notes_router
from .routers.planning_status import router as planning_status_router
from .routers.plans import router as plans_router
from .routers.settings import router as settings_router
from .routers.strength import router as strength_router
from .routers.strength_workouts import router as strength_workouts_router
from .routers.weekly_summary import router as weekly_summary_router
from .routers.weekly_reviews import router as weekly_reviews_router
from .routers.weather import router as weather_router
from .services.health_data import apply_health_data_import

mcp_app = build_mcp_app(**build_mcp_router_dependencies())
logger = logging.getLogger(__name__)


def _import_health_data_once() -> None:
    conn = get_db()
    try:
        apply_health_data_import(conn)
    except Exception:
        logger.exception("Automatic Health Data Export import failed")
    finally:
        conn.close()


async def _health_data_import_loop() -> None:
    interval = max(60, int(os.getenv("HEALTH_DATA_IMPORT_INTERVAL_SECONDS", "900")))
    while True:
        await asyncio.to_thread(_import_health_data_once)
        await asyncio.sleep(interval)


@asynccontextmanager
async def app_lifespan(app_instance: FastAPI):
    async with mcp_app.router.lifespan_context(app_instance):
        task = None
        if os.getenv("HEALTH_DATA_AUTO_IMPORT", "false").lower() in {"1", "true", "yes", "on"}:
            task = asyncio.create_task(_health_data_import_loop())
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


app = FastAPI(title="Training Dashboard API", lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(plans_router)
app.include_router(activities_router)
app.include_router(activity_feedback_router)
app.include_router(coaching_router)
app.include_router(notes_router)
app.include_router(planning_status_router)
app.include_router(settings_router)
app.include_router(metrics_router)
app.include_router(goals_router)
app.include_router(weekly_summary_router)
app.include_router(dashboard_router)
app.include_router(strength_router)
app.include_router(strength_workouts_router)
app.include_router(integrations_router)
app.include_router(weather_router)
app.include_router(weekly_reviews_router)

init_db()
app.mount("/mcp", mcp_app)

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
