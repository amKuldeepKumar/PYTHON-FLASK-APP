from __future__ import annotations

import json
import os
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

IST = timezone(timedelta(hours=5, minutes=30))
WEEKDAY_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


@dataclass(frozen=True)
class BackupSchedule:
    weekday: int = 1
    hour: int = 0
    minute: int = 0
    timezone_name: str = 'Asia/Kolkata'


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backup_root() -> Path:
    root = _project_root() / 'instance' / 'backups'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    skip_names = {'__pycache__', '.git', '.pytest_cache', 'node_modules', 'instance/backups'}
    if '__pycache__' in parts or '.git' in parts or '.pytest_cache' in parts or 'node_modules' in parts:
        return True
    if path.name.endswith('.pyc'):
        return True
    return False


def _iter_project_files() -> Iterable[Path]:
    root = _project_root()
    excluded_dirs = {
        root / 'instance' / 'backups',
        root / 'venv',
        root / '.venv',
    }
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)
        dirs[:] = [d for d in dirs if (current_path / d) not in excluded_dirs and d not in {'__pycache__', '.git', '.pytest_cache', 'node_modules'}]
        for filename in files:
            file_path = current_path / filename
            if _should_skip(file_path):
                continue
            yield file_path


def create_backup(reason: str = 'manual') -> Path:
    root = _project_root()
    backup_root = _backup_root()
    stamp = datetime.now(IST).strftime('%Y%m%d_%H%M%S')
    archive_path = backup_root / f'fluencify_backup_{stamp}.zip'

    manifest = {
        'created_at_ist': datetime.now(IST).isoformat(),
        'reason': reason,
        'project_root': str(root),
        'includes': ['application files', 'instance database', 'uploads', 'migrations', 'env files'],
    }

    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in _iter_project_files():
            arcname = file_path.relative_to(root)
            zf.write(file_path, arcname.as_posix())
        zf.writestr('backup_manifest.json', json.dumps(manifest, indent=2))

    return archive_path


def list_backups(limit: int = 12) -> list[dict]:
    items = []
    for path in sorted(_backup_root().glob('fluencify_backup_*.zip'), reverse=True)[:limit]:
        stat = path.stat()
        items.append({
            'name': path.name,
            'path': str(path),
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'created_at': datetime.fromtimestamp(stat.st_mtime, IST),
        })
    return items


def prune_backups(keep_last: int = 8) -> int:
    removed = 0
    backups = sorted(_backup_root().glob('fluencify_backup_*.zip'), reverse=True)
    for path in backups[keep_last:]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def compute_next_run(schedule: BackupSchedule | None = None, now: datetime | None = None) -> datetime:
    schedule = schedule or BackupSchedule()
    now = now.astimezone(IST) if now else datetime.now(IST)
    target = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
    delta = (schedule.weekday - target.weekday()) % 7
    if delta == 0 and target <= now:
        delta = 7
    if delta:
        target = target + timedelta(days=delta)
    return target


_scheduler_lock = threading.Lock()
_scheduler_started = False


def start_backup_scheduler(app) -> None:
    global _scheduler_started
    if not app.config.get('BACKUP_SCHEDULER_ENABLED', True):
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    def _runner():
        with app.app_context():
            while True:
                try:
                    schedule = BackupSchedule(
                        weekday=int(app.config.get('BACKUP_WEEKDAY', 1)),
                        hour=int(app.config.get('BACKUP_HOUR', 0)),
                        minute=int(app.config.get('BACKUP_MINUTE', 0)),
                        timezone_name=str(app.config.get('BACKUP_TIMEZONE', 'Asia/Kolkata')),
                    )
                    now = datetime.now(IST)
                    next_run = compute_next_run(schedule, now)
                    sleep_seconds = max(20, int((next_run - now).total_seconds()))
                    time.sleep(min(sleep_seconds, 60))
                    current = datetime.now(IST)
                    if current.weekday() == schedule.weekday and current.hour == schedule.hour and current.minute == schedule.minute:
                        create_backup(reason='scheduled')
                        prune_backups(int(app.config.get('BACKUP_RETENTION_COUNT', 8)))
                        time.sleep(65)
                except Exception:
                    time.sleep(60)

    thread = threading.Thread(target=_runner, name='fluencify-backup-scheduler', daemon=True)
    thread.start()
