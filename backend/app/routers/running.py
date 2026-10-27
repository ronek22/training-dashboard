from fastapi import APIRouter

from ..db import get_db
from ..services.run_dynamics import scan_run_dynamics
from ..services.running_fitness import build_running_fitness

router = APIRouter(prefix="/running", tags=["running"])


@router.get("/fitness")
def running_fitness():
    conn = get_db()
    try:
        return build_running_fitness(conn)
    finally:
        conn.close()


@router.post("/dynamics/scan")
def scan_dynamics():
    """Read new HealthFit running files now instead of waiting for the background sync."""
    conn = get_db()
    try:
        return scan_run_dynamics(conn)
    finally:
        conn.close()
