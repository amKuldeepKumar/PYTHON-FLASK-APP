from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from ...models import AIRequestLog


class AIMLExportService:
    @staticmethod
    def query_rows(start_date: datetime | None = None, end_date: datetime | None = None, exportable_only: bool = True):
        query = AIRequestLog.query.order_by(AIRequestLog.created_at.desc())
        if start_date:
            query = query.filter(AIRequestLog.created_at >= start_date)
        if end_date:
            query = query.filter(AIRequestLog.created_at <= end_date)
        if exportable_only:
            query = query.filter_by(exportable_for_ml=True)
        return query

    @classmethod
    def export_csv(cls, **kwargs) -> str:
        rows = cls.query_rows(**kwargs).all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["request_id", "task_key", "provider_name", "status", "total_tokens", "latency_ms", "estimated_cost", "prompt_hash", "response_hash", "created_at"])
        for row in rows:
            writer.writerow([row.request_id, row.task_key, row.provider_name, row.status, row.total_tokens, row.latency_ms, row.estimated_cost, row.prompt_hash, row.response_hash, row.created_at.isoformat() if row.created_at else ""])
        return buf.getvalue()

    @classmethod
    def export_jsonl(cls, **kwargs) -> str:
        lines = []
        for row in cls.query_rows(**kwargs).all():
            lines.append(json.dumps({
                "request_id": row.request_id,
                "task_key": row.task_key,
                "provider_name": row.provider_name,
                "status": row.status,
                "total_tokens": row.total_tokens,
                "latency_ms": row.latency_ms,
                "estimated_cost": float(row.estimated_cost or 0),
                "prompt_hash": row.prompt_hash,
                "response_hash": row.response_hash,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }, ensure_ascii=False))
        return "\n".join(lines)
