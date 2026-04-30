from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class AIRuleLogger:
    """Lightweight JSONL logger for AI rule usage without requiring schema changes."""

    LOG_DIR = Path(__file__).resolve().parents[2] / 'logs'
    LOG_FILE = LOG_DIR / 'ai_rule_usage.jsonl'

    @classmethod
    def log(cls, payload: dict[str, Any]) -> None:
        try:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                **payload,
            }
            with cls.LOG_FILE.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception:
            return None

    @classmethod
    def tail(cls, limit: int = 12) -> list[dict[str, Any]]:
        try:
            if not cls.LOG_FILE.exists():
                return []
            lines = cls.LOG_FILE.read_text(encoding='utf-8').splitlines()[-max(1, int(limit)): ]
            rows = []
            for line in reversed(lines):
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
            return rows
        except Exception:
            return []
