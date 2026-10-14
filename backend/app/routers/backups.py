from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from .. import db
from ..services import backups

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("")
def backup_status():
    return backups.get_status(db.DB_PATH)


@router.post("")
async def back_up_now():
    await run_in_threadpool(backups.create_backup, db.DB_PATH, "manual")
    return backups.get_status(db.DB_PATH)


@router.post("/drill")
async def run_restore_drill():
    await run_in_threadpool(backups.restore_drill, db.DB_PATH)
    return backups.get_status(db.DB_PATH)
