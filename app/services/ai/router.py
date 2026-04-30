from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ...extensions import db
from ...models import ReadingProvider, SecurityPolicy, SpeakingProvider, TranslationProvider


class AIProviderRouter:
    @staticmethod
    def _circuit_open(row) -> bool:
        if not row:
            return False
        if (row.circuit_state or "closed") != "open":
            return False
        until = getattr(row, "circuit_open_until", None)
        if until and until > datetime.utcnow():
            return True
        row.circuit_state = "half_open"
        db.session.add(row)
        db.session.commit()
        return False

    @classmethod
    def _sort_rows(cls, rows):
        return sorted(rows, key=lambda r: (getattr(r, "priority", 100), 0 if getattr(r, "is_default", False) else 1, getattr(r, "id", 0)))

    @classmethod
    def provider_candidates(cls, task_key: str) -> list[dict[str, Any]]:
        rows: list[Any] = []
        if task_key == "translation":
            rows = TranslationProvider.query.filter_by(is_enabled=True).all() or [TranslationProvider.primary()]
            return [cls._descriptor("translation", row, task_key) for row in cls._sort_rows(rows) if not cls._circuit_open(row)]
        if task_key.startswith("speaking_"):
            kind = {
                "speaking_stt": SpeakingProvider.KIND_STT,
                "speaking_evaluation": SpeakingProvider.KIND_EVALUATION,
                "speaking_pronunciation": SpeakingProvider.KIND_PRONUNCIATION,
                "speaking_tts": SpeakingProvider.KIND_TTS,
            }.get(task_key)
            rows = SpeakingProvider.query.filter_by(provider_kind=kind, is_enabled=True).all()
            return [cls._descriptor("speaking", row, task_key) for row in cls._sort_rows(rows) if not cls._circuit_open(row)]
        if task_key.startswith("reading_") or task_key == "writing_plagiarism":
            kind = {
                "reading_passage": ReadingProvider.KIND_PASSAGE,
                "reading_question": ReadingProvider.KIND_QUESTION,
                "reading_translation": ReadingProvider.KIND_TRANSLATION,
                "reading_evaluation": ReadingProvider.KIND_EVALUATION,
                "writing_plagiarism": ReadingProvider.KIND_PLAGIARISM,
            }.get(task_key)
            rows = ReadingProvider.query.filter_by(provider_kind=kind, is_enabled=True).all()
            return [cls._descriptor("reading", row, task_key) for row in cls._sort_rows(rows) if not cls._circuit_open(row)]
        return []

    @staticmethod
    def _descriptor(source: str, row, task_key: str) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "kind": getattr(row, "provider_kind", task_key),
            "type": row.provider_type,
            "source": source,
            "model_name": getattr(row, "model_name", None),
            "priority": getattr(row, "priority", 100),
            "timeout_seconds": getattr(row, "timeout_seconds", 30),
            "circuit_state": getattr(row, "circuit_state", "closed"),
        }

    @classmethod
    def record_success(cls, source: str, provider_id: int | None) -> None:
        row = cls._load(source, provider_id)
        if not row:
            return
        row.total_requests = int(getattr(row, "total_requests", 0) or 0) + 1
        row.consecutive_failures = 0
        row.last_success_at = datetime.utcnow()
        row.circuit_state = "closed"
        row.circuit_open_until = None
        db.session.add(row)
        db.session.commit()

    @classmethod
    def record_failure(cls, source: str, provider_id: int | None, error_message: str | None = None) -> None:
        row = cls._load(source, provider_id)
        if not row:
            return
        policy = SecurityPolicy.singleton()
        row.total_requests = int(getattr(row, "total_requests", 0) or 0) + 1
        row.total_failures = int(getattr(row, "total_failures", 0) or 0) + 1
        row.consecutive_failures = int(getattr(row, "consecutive_failures", 0) or 0) + 1
        row.last_failure_at = datetime.utcnow()
        if hasattr(row, "last_error"):
            row.last_error = (error_message or "Provider failed")[:255]
        if row.consecutive_failures >= int(policy.ai_circuit_breaker_threshold or 3):
            row.circuit_state = "open"
            row.circuit_open_until = datetime.utcnow() + timedelta(minutes=int(policy.ai_circuit_breaker_minutes or 10))
        db.session.add(row)
        db.session.commit()

    @staticmethod
    def _load(source: str, provider_id: int | None):
        if not provider_id:
            return None
        model = {
            "translation": TranslationProvider,
            "speaking": SpeakingProvider,
            "reading": ReadingProvider,
        }.get(source)
        return db.session.get(model, provider_id) if model else None
