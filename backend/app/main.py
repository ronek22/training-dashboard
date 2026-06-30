from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from .adapters.mcp import build_mcp_router_dependencies
from .db import get_db, init_db
from .routers.activities import router as activities_router
from .routers.activity_feedback import router as activity_feedback_router
from .routers.coaching import router as coaching_router
from .routers.dashboard import router as dashboard_router
from .routers.goals import router as goals_router
from .routers.integrations import router as integrations_router
from .routers.mcp import build_mcp_router
from .routers.metrics import router as metrics_router
from .routers.notes import router as notes_router
from .routers.planning_status import router as planning_status_router
from .routers.plans import router as plans_router
from .routers.settings import router as settings_router
from .routers.weekly_summary import router as weekly_summary_router

app = FastAPI(title="Training Dashboard API")

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
app.include_router(integrations_router)

init_db()
app.include_router(build_mcp_router(**build_mcp_router_dependencies()))

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
