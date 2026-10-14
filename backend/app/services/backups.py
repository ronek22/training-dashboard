"""Consistent snapshots of the training database, taken with SQLite's online backup API.

Snapshots land in data/backups/ as training-YYYYMMDD-HHMMSS-<kind>.db. Retention keeps the
newest copy of each of the last 7 days and of the 4 weeks before that, plus the last 2 startup
copies. Only files matching that name pattern are ever deleted, so hand-made copies stay.

The restore drill (weekly, or `just restore-drill`) proves the newest copy restores: it copies it to a
temporary file next to the backups, runs the app's migrations on that copy in a child process (so the live DB_PATH is never
swapped) and runs smoke queries. The result lands in restore-drill.json; the copy is always deleted.
"""
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

NAME_RE = re.compile(r"^training-(\d{8}-\d{6})-(daily|startup|manual)\.db$")
STATUS_FILE = "backup-status.json"
DRILL_FILE = "restore-drill.json"
DRILL_EVERY = timedelta(days=7)
DRILL_TIMEOUT_S = 900
DRILL_SCRATCH_PREFIX = "restore-drill-"
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


def _read_status(directory: Path, name: str = STATUS_FILE) -> dict:
    try:
        return json.loads((directory / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(directory: Path, status: dict, name: str = STATUS_FILE) -> None:
    tmp = directory / f"{name}.tmp"
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(directory / name)


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


def smoke_check(path: Path) -> dict:
    """Queries a restored app depends on; raises when the copy could not serve the training history."""
    conn = sqlite3.connect(path)
    try:
        activities, latest = conn.execute("SELECT COUNT(*), MAX(date) FROM activities").fetchone()
        plan_weeks = conn.execute("SELECT COUNT(*) FROM weekly_plans").fetchone()[0]
    finally:
        conn.close()
    if not activities:
        raise RuntimeError("Smoke query failed: no activities in the restored copy")
    return {"activities": activities, "latest_activity": latest, "plan_weeks": plan_weeks}


def _migrate_copy(path: Path) -> None:
    """Run init_db against path in a child process, so this process's db.DB_PATH stays on the live file."""
    parts = __package__.split(".")  # "app.services" in the container, "backend.app.services" in tests
    cwd = Path(__file__).resolve().parents[len(parts)]
    package = ".".join(parts[:-1])
    code = f"from {package} import db; db.init_db(snapshot=False)"
    result = subprocess.run([sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True,
                            timeout=DRILL_TIMEOUT_S, env={**os.environ, "TRAINING_DB_PATH": str(path)})
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(f"Migrations failed: {lines[-1] if lines else f'exit code {result.returncode}'}")


def restore_drill(db_path: str, now: datetime | None = None) -> dict:
    """Restore the newest backup into a temporary file, migrate it, smoke-test it and record the result."""
    now = now or datetime.now()
    directory = backup_dir(db_path)
    directory.mkdir(parents=True, exist_ok=True)
    status = {"ran_at": now.isoformat(timespec="seconds"), "ok": False, "file": None}
    try:
        newest = list_backups(directory)
        if not newest:
            raise RuntimeError("No backup to restore")
        status["file"] = newest[0]["file"]
        # A drill killed mid-copy (a --reload restart) cannot clean up after itself; the next one does.
        for stale in directory.glob(f"{DRILL_SCRATCH_PREFIX}*"):
            shutil.rmtree(stale, ignore_errors=True)
        with tempfile.TemporaryDirectory(prefix=DRILL_SCRATCH_PREFIX, dir=directory) as scratch:
            copy = Path(scratch) / "training.db"
            shutil.copyfile(directory / status["file"], copy)
            _migrate_copy(copy)
            result = integrity_check(copy)
            if result != "ok":
                raise RuntimeError(f"Integrity check after migrations failed: {result}")
            status.update(ok=True, message="Restored, migrated and queried", **smoke_check(copy))
    except Exception as exc:
        logger.exception("Restore drill failed")
        status["message"] = str(exc) or exc.__class__.__name__
    _write_status(directory, status, DRILL_FILE)
    return status


def restore_drill_due(db_path: str, now: datetime | None = None) -> bool:
    ran_at = _read_status(backup_dir(db_path), DRILL_FILE).get("ran_at")
    return not ran_at or (now or datetime.now()) - datetime.fromisoformat(ran_at) >= DRILL_EVERY


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
        "restore_drill": _read_status(directory, DRILL_FILE) or None,
    }


if __name__ == "__main__":
    # `just backup`: python -m app.services.backups (TRAINING_DB_PATH picks the database).
    # `just restore-drill`: python -m app.services.backups drill
    logging.basicConfig(level=logging.INFO)
    from ..db import DB_PATH

    if sys.argv[1:] == ["drill"]:
        drill = restore_drill(DB_PATH)
        detail = (f"{drill['file']}: {drill['activities']} activities, latest {drill['latest_activity']}, "
                  f"{drill['plan_weeks']} plan weeks" if drill["ok"] else f"{drill['file'] or '-'}: {drill['message']}")
        print(f"{'OK' if drill['ok'] else 'FAILED'}: {detail}")
        sys.exit(0 if drill["ok"] else 1)
    result = create_backup(DB_PATH, "manual")
    print(f"{'OK' if result['ok'] else 'FAILED'}: {result.get('file') or result['message']}")
    for name in result.get("deleted", []):
        print(f"Removed old backup {name}")
    sys.exit(0 if result["ok"] else 1)
