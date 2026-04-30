from __future__ import annotations

import hashlib
import json
import time
import uuid
from decimal import Decimal
from typing import Any

from ...extensions import db
from ...models import AIRequestLog, ApiCallLog, UserPreferences


class AIRequestLogger:
    @staticmethod
    def request_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _hash(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _redact(value: Any, limit: int = 1000) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        value = value.replace("\n", " ").strip()
        if len(value) > limit:
            value = value[:limit] + "…"
        return value

    @classmethod
    def start_timer(cls) -> float:
        return time.perf_counter()

    @classmethod
    def elapsed_ms(cls, started: float | None) -> int | None:
        if started is None:
            return None
        return int((time.perf_counter() - started) * 1000)

    @classmethod
    def log_request(
        cls,
        *,
        request_id: str,
        task_key: str,
        provider: dict[str, Any] | None,
        prompt: Any,
        response: Any,
        ok: bool,
        actor_user_id: int | None = None,
        course_id: int | None = None,
        lesson_id: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        estimated_cost: float | Decimal | None = None,
        cache_hit: bool = False,
        fallback_used: bool = False,
        error_code: str | None = None,
        error_message: str | None = None,
        status: str | None = None,
        consent_snapshot: bool | None = None,
        exportable_for_ml: bool | None = None,
    ) -> None:
        try:
            prefs = None
            if actor_user_id:
                prefs = UserPreferences.query.filter_by(user_id=actor_user_id).first()
            consent = bool(consent_snapshot if consent_snapshot is not None else getattr(prefs, "allow_ml_training", False))
            exportable = bool(exportable_for_ml if exportable_for_ml is not None else consent)
            provider = provider or {}
            row = AIRequestLog(
                request_id=request_id,
                actor_user_id=actor_user_id,
                course_id=course_id,
                lesson_id=lesson_id,
                task_key=task_key,
                provider_source=provider.get("source"),
                provider_id=provider.get("id") if isinstance(provider.get("id"), int) else None,
                provider_name=provider.get("name"),
                provider_type=provider.get("type"),
                model_name=provider.get("model_name"),
                prompt_hash=cls._hash(prompt),
                response_hash=cls._hash(response),
                redacted_prompt=cls._redact(prompt),
                redacted_response=cls._redact(response),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                cache_hit=bool(cache_hit),
                fallback_used=bool(fallback_used),
                circuit_state=provider.get("circuit_state"),
                status=status or ("success" if ok else "error"),
                error_code=error_code,
                error_message=(error_message or "")[:255] or None,
                consent_snapshot=consent,
                exportable_for_ml=exportable,
            )
            db.session.add(row)
            db.session.add(ApiCallLog(
                actor_user_id=actor_user_id,
                system=f"ai:{task_key}",
                endpoint=f"/ai/{task_key}",
                method="POST",
                ok=bool(ok),
                status_code=200 if ok else 500,
                provider_name=provider.get("name") or provider.get("source") or "System",
                message=((error_message or "Completed")[:255] if not ok else f"{task_key} completed")[:255],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

