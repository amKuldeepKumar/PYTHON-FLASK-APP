from __future__ import annotations

import json
from datetime import datetime
from urllib import error, request

from flask import current_app

from ..extensions import db
from ..models import ApiCallLog, SecurityPolicy, TranslationCache, TranslationProvider
from ..models.translation_cache import make_cache_key
from .ai.request_logger import AIRequestLogger
from .ai.router import AIProviderRouter
from .ai.runtime_control import AIRuntimeControl


DEFAULT_CONTEXT = "runtime"


def _estimate_translation_tokens(source_text: str | None, message: str | None = None) -> tuple[int, int, int]:
    input_tokens = max(1, len((source_text or "").split()))
    output_tokens = max(1, len((message or "").split())) if message else input_tokens
    total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _log_api_call(
    system: str,
    endpoint: str,
    method: str,
    ok: bool,
    status_code: int | None,
    message: str | None,
    *,
    provider_name: str | None = None,
    source_text: str | None = None,
) -> None:
    try:
        input_tokens, output_tokens, total_tokens = _estimate_translation_tokens(source_text, message)
        row = ApiCallLog(
            actor_user_id=None,
            system=system,
            endpoint=endpoint,
            method=method,
            ok=bool(ok),
            status_code=status_code,
            provider_name=provider_name,
            message=(message or "")[:255] or None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=round(total_tokens * 0.0001, 4),
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_primary_provider() -> TranslationProvider:
    return TranslationProvider.primary()


def cached_translation(source_text: str, target_lang: str, *, source_lang: str = "en", context: str = DEFAULT_CONTEXT, version: str | None = None) -> str | None:
    key = make_cache_key(source_text, source_lang, target_lang, context, version)
    row = TranslationCache.query.filter_by(cache_key=key).first()
    if not row:
        return None
    if row.is_expired():
        return None
    return row.translated_text


def _cache_translation(source_text: str, translated_text: str, target_lang: str, *, source_lang: str = "en", context: str = DEFAULT_CONTEXT, version: str | None = None, ttl_seconds: int | None = None) -> TranslationCache:
    key = make_cache_key(source_text, source_lang, target_lang, context, version)
    row = TranslationCache.query.filter_by(cache_key=key).first()
    if not row:
        row = TranslationCache(cache_key=key)
        db.session.add(row)
    row.src_lang = source_lang
    row.target_lang = target_lang
    row.context = context
    row.version = version
    row.source_text = source_text
    row.translated_text = translated_text
    row.expires_at = TranslationCache.compute_expiry(ttl_seconds or SecurityPolicy.singleton().translation_cache_ttl_seconds)
    db.session.commit()
    return row


def _mock_translate(text: str, target_lang: str) -> str:
    return f"[{target_lang}] {text}"


def _call_openai_compatible(provider: TranslationProvider, source_text: str, target_lang: str, source_lang: str) -> str:
    base_url = (provider.api_base_url or "").rstrip("/")
    api_key = (provider.api_key or "").strip()
    model = (provider.model_name or "").strip()
    if not base_url or not api_key or not model:
        raise RuntimeError("Provider is missing API base URL, API key, or model name.")

    endpoint = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": f"You are a translation engine. Translate from {source_lang} to {target_lang}. Return only the translated text.",
            },
            {"role": "user", "content": source_text},
        ],
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with request.urlopen(req, timeout=int(provider.timeout_seconds or 30)) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            translated = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not translated:
                raise RuntimeError("Provider returned an empty translation response.")
            _log_api_call("translation", endpoint, "POST", True, getattr(resp, "status", 200), f"Translated to {target_lang}", provider_name=provider.name, source_text=source_text)
            return translated
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
        _log_api_call("translation", endpoint, "POST", False, getattr(exc, "code", None), detail[:200], provider_name=provider.name, source_text=source_text)
        raise RuntimeError(f"Translation provider error: {detail[:200]}")
    except Exception as exc:
        _log_api_call("translation", endpoint, "POST", False, None, str(exc)[:200], provider_name=provider.name, source_text=source_text)
        raise


def _estimate_cost(provider: TranslationProvider, input_tokens: int, output_tokens: int) -> float:
    base = float(provider.per_request_cost or 0)
    token_cost = ((input_tokens / 1000.0) * float(provider.cost_per_1k_input or 0)) + ((output_tokens / 1000.0) * float(provider.cost_per_1k_output or 0))
    return round(base + token_cost, 6)


def provider_translate(source_text: str, target_lang: str, *, source_lang: str = "en", actor_user_id: int | None = None) -> tuple[str, dict]:
    providers = AIProviderRouter.provider_candidates("translation")
    if not providers:
        provider = get_primary_provider()
        providers = [{"id": provider.id, "name": provider.name, "type": provider.provider_type, "source": "translation", "model_name": provider.model_name}]

    last_error = None
    for idx, descriptor in enumerate(providers):
        provider = db.session.get(TranslationProvider, descriptor.get("id")) if descriptor.get("id") else get_primary_provider()
        if provider is None:
            continue
        provider.last_error = None
        try:
            if not provider.is_enabled or provider.provider_type == "mock":
                translated = _mock_translate(source_text, target_lang)
            elif provider.provider_type == "openai_compatible":
                translated = _call_openai_compatible(provider, source_text, target_lang, source_lang)
            else:
                raise RuntimeError("Unsupported translation provider type.")

            provider.consume_credit()
            provider.last_credit_sync_at = datetime.utcnow()
            db.session.commit()
            AIProviderRouter.record_success("translation", provider.id)
            input_tokens, output_tokens, total_tokens = _estimate_translation_tokens(source_text, translated)
            return translated, {
                "provider": descriptor,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": _estimate_cost(provider, input_tokens, output_tokens),
                "fallback_used": idx > 0,
                "cache_hit": False,
            }
        except Exception as exc:
            last_error = str(exc)
            provider.last_error = str(exc)[:255]
            db.session.commit()
            AIProviderRouter.record_failure("translation", provider.id, str(exc))
            current_app.logger.exception("Translation provider failed: %s", exc)
            continue
    raise RuntimeError(last_error or "Translation failed.")


def translate_text(source_text: str, target_lang: str, *, source_lang: str = "en", context: str = DEFAULT_CONTEXT, version: str | None = None, ttl_seconds: int | None = None, actor_user_id: int | None = None) -> tuple[str, bool]:
    if not source_text:
        return "", False
    if target_lang == source_lang:
        return source_text, False

    request_id = AIRequestLogger.request_id()
    started = AIRequestLogger.start_timer()
    input_tokens, output_tokens, total_tokens = _estimate_translation_tokens(source_text, target_lang)
    decision = AIRuntimeControl.quota_check("translation", user_id=actor_user_id, estimated_tokens=total_tokens)
    if not decision.allowed:
        AIRequestLogger.log_request(
            request_id=request_id,
            task_key="translation",
            provider={"source": "translation", "name": "quota-guard", "type": "internal_guard"},
            prompt=source_text,
            response=decision.reason,
            ok=False,
            actor_user_id=actor_user_id,
            input_tokens=input_tokens,
            output_tokens=0,
            total_tokens=input_tokens,
            latency_ms=AIRequestLogger.elapsed_ms(started),
            error_code="quota_block",
            error_message=decision.reason,
        )
        raise RuntimeError(decision.reason or "Translation quota reached.")

    cached = cached_translation(source_text, target_lang, source_lang=source_lang, context=context, version=version)
    if cached is not None:
        in_t, out_t, total_t = _estimate_translation_tokens(source_text, cached)
        AIRuntimeControl.consume_quota(decision.counter, task_key="translation", total_tokens=total_t)
        AIRequestLogger.log_request(
            request_id=request_id,
            task_key="translation",
            provider={"source": "translation", "name": "cache", "type": "cache"},
            prompt=source_text,
            response=cached,
            ok=True,
            actor_user_id=actor_user_id,
            input_tokens=in_t,
            output_tokens=out_t,
            total_tokens=total_t,
            latency_ms=AIRequestLogger.elapsed_ms(started),
            estimated_cost=0,
            cache_hit=True,
            status="success",
            consent_snapshot=AIRuntimeControl.consent_for_user(actor_user_id),
        )
        return cached, True

    translated, meta = provider_translate(source_text, target_lang, source_lang=source_lang, actor_user_id=actor_user_id)
    _cache_translation(
        source_text,
        translated,
        target_lang,
        source_lang=source_lang,
        context=context,
        version=version,
        ttl_seconds=ttl_seconds,
    )
    AIRuntimeControl.consume_quota(decision.counter, task_key="translation", total_tokens=meta.get("total_tokens", 0))
    AIRequestLogger.log_request(
        request_id=request_id,
        task_key="translation",
        provider=meta.get("provider"),
        prompt=source_text,
        response=translated,
        ok=True,
        actor_user_id=actor_user_id,
        input_tokens=meta.get("input_tokens"),
        output_tokens=meta.get("output_tokens"),
        total_tokens=meta.get("total_tokens"),
        latency_ms=AIRequestLogger.elapsed_ms(started),
        estimated_cost=meta.get("estimated_cost"),
        cache_hit=False,
        fallback_used=meta.get("fallback_used", False),
        status="success",
        consent_snapshot=AIRuntimeControl.consent_for_user(actor_user_id),
    )
    return translated, False
