import os
import sqlite3
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "runtime" / "giveaway-bot.sqlite3"
BACKUP_DIR = BASE_DIR / "runtime" / "backups"
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))


def create_backup() -> Path:
    if not DATABASE.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destination = BACKUP_DIR / f"giveaway-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
    with sqlite3.connect(DATABASE, timeout=30) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {integrity}")
    destination.chmod(0o600)
    return destination


def prune_backups() -> int:
    cutoff = time.time() - RETENTION_DAYS * 24 * 60 * 60
    deleted = 0
    for path in BACKUP_DIR.glob("giveaway-*.sqlite3"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            deleted += 1
    return deleted


if __name__ == "__main__":
    backup = create_backup()
    deleted = prune_backups()
    print(f"Backup created: {backup.name}; old backups deleted: {deleted}")
