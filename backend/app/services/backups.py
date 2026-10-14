"""Consistent snapshots of the training database, taken with SQLite's online backup API.

Snapshots land in data/backups/ as training-YYYYMMDD-HHMMSS-<kind>.db. Retention keeps the
newest copy of each of the last 7 days and of the 4 weeks before that, plus the last 2 startup
copies. Only files matching that name pattern are ever deleted, so hand-made copies stay.
"""
import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

NAME_RE = re.compile(r"^training-(\d{8}-\d{6})-(daily|startup|manual)\.db$")
STATUS_FILE = "backup-status.json"
DAILY_KEEP = 7
WEEKLY_KEEP = 4
STARTUP_KEEP = 2
# Uvicorn --reload restarts on every code edit; one pre-migration copy an hour is enough.
STARTUP_MIN_GAP = timedelta(hours=1)


def backup_dir(db_path: str) -> Path:
    configured = os.getenv("TRAINING_BACKUP_DIR", "").strip()
    return Path(configured) if configured else Path(db_path).resolve().parent / "backups"


def list_backups(directory: Path) -> list[dict]:
    items = []
    if directory.is_dir():
        for path in directory.iterdir():
            match = NAME_RE.match(path.name)
            if match and path.is_file():
                items.append({
                    "file": path.name,
                    "kind": match.group(2),
                    "created_at": datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").isoformat(),
                    "size_mb": round(path.stat().st_size / 1_048_576, 1),
                })
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


def _read_status(directory: Path) -> dict:
    try:
        return json.loads((directory / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(directory: Path, status: dict) -> None:
    tmp = directory / f"{STATUS_FILE}.tmp"
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(directory / STATUS_FILE)


def integrity_check(path: Path) -> str:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
    finally:
        conn.close()
    return "ok" if rows == ["ok"] else "; ".join(rows[:5])


def create_backup(db_path: str, kind: str = "daily", now: datetime | None = None) -> dict:
    """Snapshot db_path, verify it and apply retention. Returns the recorded status."""
    now = now or datetime.now()
    directory = backup_dir(db_path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"training-{now:%Y%m%d-%H%M%S}-{kind}.db"
    partial = target.with_name(target.name + ".partial")
    status = {"last_attempt_at": now.isoformat(timespec="seconds"), "kind": kind}
    try:
        partial.unlink(missing_ok=True)
        source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        result = integrity_check(partial)
        if result != "ok":
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"Integrity check failed: {result}")
        partial.replace(target)
        status.update(ok=True, file=target.name, message="Integrity check passed",
                      last_success_at=status["last_attempt_at"])
    except Exception as exc:
        partial.unlink(missing_ok=True)
        logger.exception("Database backup failed")
        previous = _read_status(directory)
        status.update(ok=False, file=None, message=str(exc) or exc.__class__.__name__,
                      last_success_at=previous.get("last_success_at"))
    _write_status(directory, status)
    if status["ok"]:
        status["deleted"] = prune(directory)
    return status


def prune(directory: Path) -> list[str]:
    """Delete backups outside retention; never touches files that do not match NAME_RE."""
    backups = list_backups(directory)
    keep = set([item["file"] for item in backups if item["kind"] == "startup"][:STARTUP_KEEP])
    days, weeks = set(), set()
    # Newest first, so the first file seen for a day or week is its newest copy.
    for item in (item for item in backups if item["kind"] != "startup"):
        created = datetime.fromisoformat(item["created_at"])
        if created.date() in days:
            continue
        if len(days) < DAILY_KEEP:
            days.add(created.date())
            keep.add(item["file"])
            continue
        week = created.isocalendar()[:2]
        if week not in weeks and len(weeks) < WEEKLY_KEEP:
            weeks.add(week)
            keep.add(item["file"])
    deleted = []
    for item in backups:
        if item["file"] not in keep:
            (directory / item["file"]).unlink(missing_ok=True)
            deleted.append(item["file"])
    return deleted


def daily_backup_due(db_path: str, now: datetime | None = None) -> bool:
    today = (now or datetime.now()).date().isoformat()
    return not any(item["kind"] != "startup" and item["created_at"].startswith(today)
                   for item in list_backups(backup_dir(db_path)))


def snapshot_before_migrations(db_path: str, now: datetime | None = None) -> dict | None:
    """Take a startup copy before init_db migrates, unless the database is new or a copy is recent."""
    now = now or datetime.now()
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        has_tables = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' LIMIT 1").fetchone()
    finally:
        conn.close()
    if not has_tables:
        return None
    latest = list_backups(backup_dir(db_path))
    if latest and now - datetime.fromisoformat(latest[0]["created_at"]) < STARTUP_MIN_GAP:
        return None
    # The first copy of the day doubles as the daily one, so a morning start does not copy twice.
    return create_backup(db_path, "daily" if daily_backup_due(db_path, now) else "startup", now)


def get_status(db_path: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    directory = backup_dir(db_path)
    status = _read_status(directory)
    last_success = status.get("last_success_at")
    stale = not last_success or now - datetime.fromisoformat(last_success) > timedelta(hours=36)
    return {
        "directory": str(directory),
        "last_attempt_at": status.get("last_attempt_at"),
        "last_success_at": last_success,
        "ok": status.get("ok"),
        "message": status.get("message"),
        "stale": stale,
        "retention": f"{DAILY_KEEP} daily, {WEEKLY_KEEP} weekly, {STARTUP_KEEP} before-startup",
        "backups": list_backups(directory),
    }


if __name__ == "__main__":
    # `just backup`: python -m app.services.backups (TRAINING_DB_PATH picks the database).
    logging.basicConfig(level=logging.INFO)
    from ..db import DB_PATH

    result = create_backup(DB_PATH, "manual")
    print(f"{'OK' if result['ok'] else 'FAILED'}: {result.get('file') or result['message']}")
    for name in result.get("deleted", []):
        print(f"Removed old backup {name}")
    sys.exit(0 if result["ok"] else 1)
