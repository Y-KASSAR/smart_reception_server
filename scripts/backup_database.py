"""
Database Backup & Restore
=========================
Creates timestamped SQLite backups of the smart_reception database
using sqlite3's online backup API (safe while server is running).
Also supports restore from any backup file and prunes old backups
based on `database.backup_retention_days` from config.yaml.

Usage:
    python scripts/backup_database.py backup
    python scripts/backup_database.py restore data/backups/smart_reception_20260424_120000.db
    python scripts/backup_database.py list
    python scripts/backup_database.py prune

Disaster recovery:
    1. Stop the server.
    2. Replace data/smart_reception.db with the backup file
       (or run: python scripts/backup_database.py restore <file>).
    3. Restart the server.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings  # noqa: E402
from config.logging_config import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)


def backup_dir() -> Path:
    d = PROJECT_ROOT / "data" / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return settings.database.full_path


def create_backup() -> Path:
    """Create a timestamped backup of the live database using sqlite3's online backup API."""
    src = db_path()
    if not src.exists():
        raise FileNotFoundError(f"Database not found: {src}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir() / f"smart_reception_{timestamp}.db"

    src_conn = sqlite3.connect(str(src))
    dest_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    size_kb = dest.stat().st_size / 1024
    logger.info(f"Backup created: {dest.name} ({size_kb:.1f} KB)")
    return dest


def list_backups() -> list[Path]:
    backups = sorted(backup_dir().glob("smart_reception_*.db"), reverse=True)
    return backups


def prune_old_backups(retention_days: int | None = None) -> int:
    if retention_days is None:
        retention_days = settings.database.backup_retention_days
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for f in list_backups():
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            removed += 1
            logger.info(f"Pruned old backup: {f.name}")
    return removed


def restore_backup(backup_file: Path) -> Path:
    """Restore a backup file over the live database. Creates a safety copy first."""
    backup_file = Path(backup_file)
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    target = db_path()
    if target.exists():
        safety = backup_dir() / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(target, safety)
        logger.info(f"Safety copy of current DB saved as: {safety.name}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, target)
    logger.info(f"Restored {backup_file.name} -> {target}")
    return target


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Smart Reception DB backup/restore tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup", help="Create a new timestamped backup")
    sub.add_parser("list", help="List existing backups")
    sub.add_parser("prune", help="Remove backups older than retention window")
    r = sub.add_parser("restore", help="Restore a backup file over the live database")
    r.add_argument("file", help="Path to backup .db file to restore")

    args = parser.parse_args()

    if args.cmd == "backup":
        path = create_backup()
        print(f"OK  backup -> {path}")
    elif args.cmd == "list":
        for f in list_backups():
            ts = datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")
            size_kb = f.stat().st_size / 1024
            print(f"{ts}  {size_kb:8.1f} KB  {f.name}")
    elif args.cmd == "prune":
        n = prune_old_backups()
        print(f"OK  pruned {n} backup(s)")
    elif args.cmd == "restore":
        path = restore_backup(Path(args.file))
        print(f"OK  restored -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
