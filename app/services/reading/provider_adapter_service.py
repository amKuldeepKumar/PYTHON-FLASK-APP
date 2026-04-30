from __future__ import annotations

import json
import re
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...models.reading_provider import ReadingProvider


@dataclass
class ProviderExecutionResult:
    ok: bool
    status_code: int | None
    message: str
    provider_payload: dict[str, Any] | None = None
    raw_response: Any = None
    latency_ms: int | None = None


class ReadingProviderAdapterService:
    """Real provider execution layer for Phase 7A.

    Supports:
    - mock
    - openai_compatible
    - azure
    - gemini/google
    - anthropic
    - custom (template-driven)
    """

    @classmethod
    def execute(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        started = time.perf_counter()
        try:
            provider_type = (provider.provider_type or ReadingProvider.TYPE_MOCK).strip().lower()
            if provider_type == ReadingProvider.TYPE_MOCK:
                result = ProviderExecutionResult(
                    ok=True,
                    status_code=200,
                    message=f"{(payload.get('task') or provider.provider_kind).title()} request prepared for {provider.name} in mock mode.",
                    provider_payload={"mode": "mock"},
                    raw_response={"mock": True, "echo": payload},
                )
            elif provider_type == ReadingProvider.TYPE_OPENAI_COMPATIBLE:
                result = cls._call_openai_compatible(provider, payload, config)
            elif provider_type == ReadingProvider.TYPE_AZURE:
                result = cls._call_azure_openai(provider, payload, config)
            elif provider_type in {ReadingProvider.TYPE_GEMINI, ReadingProvider.TYPE_GOOGLE}:
                result = cls._call_gemini(provider, payload, config)
            elif provider_type == ReadingProvider.TYPE_ANTHROPIC:
                result = cls._call_anthropic(provider, payload, config)
            elif provider_type == ReadingProvider.TYPE_CUSTOM:
                result = cls._call_custom(provider, payload, config)
            else:
                result = ProviderExecutionResult(ok=False, status_code=422, message=f"Unsupported provider type: {provider.provider_type}")
        except Exception as exc:
            result = ProviderExecutionResult(ok=False, status_code=500, message=f"Provider execution failed: {exc}")
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    @classmethod
    def test_connection(cls, provider: ReadingProvider, config: dict[str, Any]) -> ProviderExecutionResult:
        payload = {
            "task": "connection test",
            "prompt": config.get("test_prompt") or "Reply with exactly: READY",
            "expect_text": "READY",
            "test_mode": True,
        }
        return cls.execute(provider, payload, config)

    @classmethod
    def _call_openai_compatible(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        endpoint = cls._join_url(provider.api_base_url or config.get("api_base_url"), config.get("endpoint_path") or "/chat/completions")
        if not endpoint:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing base URL for OpenAI-compatible provider.")
        if not provider.api_key:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing API key for OpenAI-compatible provider.")
        if not (provider.model_name or config.get("model")):
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing model name for OpenAI-compatible provider.")

        request_body = {
            "model": provider.model_name or config.get("model"),
            "messages": cls._messages_from_payload(payload),
            "temperature": config.get("temperature", 0.3),
            "max_tokens": config.get("max_tokens", 1400),
        }
        if isinstance(config.get("extra_body"), dict):
            request_body.update(config["extra_body"])
        headers = cls._build_headers(provider, config, {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        })
        raw = cls._post_json(endpoint, request_body, headers, config)
        text = cls._extract_openai_text(raw)
        return ProviderExecutionResult(ok=True, status_code=200, message="OpenAI-compatible provider executed successfully.", provider_payload={"text": text}, raw_response=raw)

    @classmethod
    def _call_azure_openai(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        base = provider.api_base_url or config.get("api_base_url")
        deployment = config.get("deployment_name") or provider.model_name
        api_version = config.get("api_version") or "2024-02-15-preview"
        if not base:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing Azure base URL.")
        if not provider.api_key:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing Azure API key.")
        if not deployment:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing Azure deployment/model name.")
        endpoint = cls._join_url(base, f"/openai/deployments/{deployment}/chat/completions?api-version={api_version}")
        request_body = {
            "messages": cls._messages_from_payload(payload),
            "temperature": config.get("temperature", 0.3),
            "max_tokens": config.get("max_tokens", 1400),
        }
        if isinstance(config.get("extra_body"), dict):
            request_body.update(config["extra_body"])
        headers = cls._build_headers(provider, config, {
            "api-key": provider.api_key,
            "Content-Type": "application/json",
        })
        raw = cls._post_json(endpoint, request_body, headers, config)
        text = cls._extract_openai_text(raw)
        return ProviderExecutionResult(ok=True, status_code=200, message="Azure OpenAI provider executed successfully.", provider_payload={"text": text}, raw_response=raw)

    @classmethod
    def _call_gemini(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        model = provider.model_name or config.get("model") or "gemini-1.5-flash"
        base = provider.api_base_url or config.get("api_base_url") or "https://generativelanguage.googleapis.com"
        if not provider.api_key:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing Gemini API key.")
        endpoint_path = config.get("endpoint_path") or f"/v1beta/models/{model}:generateContent?key={provider.api_key}"
        endpoint = cls._join_url(base, endpoint_path)
        request_body = {
            "contents": [{"parts": [{"text": cls._prompt_from_payload(payload)}]}],
            "generationConfig": {
                "temperature": config.get("temperature", 0.3),
                "maxOutputTokens": config.get("max_output_tokens", config.get("max_tokens", 1400)),
            },
        }
        if isinstance(config.get("extra_body"), dict):
            request_body.update(config["extra_body"])
        headers = cls._build_headers(provider, config, {"Content-Type": "application/json"})
        raw = cls._post_json(endpoint, request_body, headers, config)
        text = cls._extract_gemini_text(raw)
        return ProviderExecutionResult(ok=True, status_code=200, message="Gemini provider executed successfully.", provider_payload={"text": text}, raw_response=raw)

    @classmethod
    def _call_anthropic(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        endpoint = cls._join_url(provider.api_base_url or config.get("api_base_url") or "https://api.anthropic.com", config.get("endpoint_path") or "/v1/messages")
        if not provider.api_key:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing Anthropic API key.")
        model = provider.model_name or config.get("model") or "claude-3-5-sonnet-latest"
        request_body = {
            "model": model,
            "max_tokens": config.get("max_tokens", 1400),
            "temperature": config.get("temperature", 0.3),
            "messages": [{"role": "user", "content": cls._prompt_from_payload(payload)}],
        }
        if isinstance(config.get("system_prompt"), str) and config["system_prompt"].strip():
            request_body["system"] = config["system_prompt"].strip()
        if isinstance(config.get("extra_body"), dict):
            request_body.update(config["extra_body"])
        headers = cls._build_headers(provider, config, {
            "x-api-key": provider.api_key,
            "anthropic-version": config.get("anthropic_version") or "2023-06-01",
            "Content-Type": "application/json",
        })
        raw = cls._post_json(endpoint, request_body, headers, config)
        text = cls._extract_anthropic_text(raw)
        return ProviderExecutionResult(ok=True, status_code=200, message="Anthropic provider executed successfully.", provider_payload={"text": text}, raw_response=raw)

    @classmethod
    def _call_custom(cls, provider: ReadingProvider, payload: dict[str, Any], config: dict[str, Any]) -> ProviderExecutionResult:
        endpoint = cls._join_url(provider.api_base_url or config.get("api_base_url"), config.get("endpoint_path") or "")
        if not endpoint:
            return ProviderExecutionResult(ok=False, status_code=422, message="Missing base URL for custom provider.")
        method = (config.get("method") or "POST").upper()
        body_template = config.get("request_template")
        if isinstance(body_template, str) and body_template.strip():
            try:
                body = json.loads(cls._string_template(body_template, payload, provider))
            except Exception as exc:
                return ProviderExecutionResult(ok=False, status_code=422, message=f"Invalid custom request template: {exc}")
        else:
            body = payload
        headers = cls._build_headers(provider, config, {"Content-Type": "application/json"})
        if provider.api_key and config.get("auth_header"):
            headers[config["auth_header"]] = provider.api_key
        elif provider.api_key and config.get("bearer_auth", True):
            headers.setdefault("Authorization", f"Bearer {provider.api_key}")
        raw = cls._post_json(endpoint, body, headers, config, method=method)
        extracted = cls._extract_by_path(raw, config.get("response_path"))
        if isinstance(extracted, (dict, list)):
            text = json.dumps(extracted, ensure_ascii=False)
        else:
            text = str(extracted or "")
        return ProviderExecutionResult(ok=True, status_code=200, message="Custom provider executed successfully.", provider_payload={"text": text}, raw_response=raw)

    @staticmethod
    def _messages_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
        system = payload.get("system_prompt") or "You are a precise reading-learning assistant. Follow the prompt exactly and return structured, clean output only."
        return [
            {"role": "system", "content": str(system)},
            {"role": "user", "content": ReadingProviderAdapterService._prompt_from_payload(payload)},
        ]

    @staticmethod
    def _prompt_from_payload(payload: dict[str, Any]) -> str:
        prompt = (payload.get("prompt") or "").strip()
        if prompt:
            return prompt
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _build_headers(provider: ReadingProvider, config: dict[str, Any], defaults: dict[str, str]) -> dict[str, str]:
        headers = dict(defaults)
        extra = config.get("headers")
        if isinstance(extra, dict):
            for key, value in extra.items():
                if value is not None:
                    headers[str(key)] = str(value)
        return headers

    @staticmethod
    def _post_json(url: str, body: Any, headers: dict[str, str], config: dict[str, Any], method: str = "POST") -> Any:
        timeout = max(5, min(int(config.get("timeout", 30)), 180))
        verify_ssl = bool(config.get("verify_ssl", True))
        context = None if verify_ssl else ssl._create_unverified_context()
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout, context=context) as response:
                raw = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type.lower() or raw[:1] in {"{", "["}:
                    return json.loads(raw)
                return {"text": raw}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            detail = raw[:500]
            raise RuntimeError(f"HTTP {exc.code}: {detail}")
        except URLError as exc:
            raise RuntimeError(f"Network error: {exc.reason}")

    @staticmethod
    def _extract_openai_text(raw: Any) -> str:
        choices = raw.get("choices") if isinstance(raw, dict) else None
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    texts.append(str(item.get("text") or item.get("content") or ""))
            return "\n".join(t for t in texts if t).strip()
        return str(content or "").strip()

    @staticmethod
    def _extract_gemini_text(raw: Any) -> str:
        candidates = raw.get("candidates") if isinstance(raw, dict) else None
        if not candidates:
            return ""
        parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
        texts = []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
        return "\n".join(texts).strip()

    @staticmethod
    def _extract_anthropic_text(raw: Any) -> str:
        content = raw.get("content") if isinstance(raw, dict) else None
        if not content:
            return ""
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text") or ""))
        return "\n".join(texts).strip()

    @staticmethod
    def parse_text_or_json(text: str) -> Any:
        clean = (text or "").strip()
        if not clean:
            return None
        fenced = re.match(r"```(?:json)?\s*(.*?)\s*```", clean, flags=re.S | re.I)
        if fenced:
            clean = fenced.group(1).strip()
        try:
            return json.loads(clean)
        except Exception:
            return clean

    @staticmethod
    def _extract_by_path(payload: Any, path: str | None) -> Any:
        if not path:
            return payload
        current = payload
        for chunk in str(path).split('.'):
            key = chunk.strip()
            if not key:
                continue
            if isinstance(current, list):
                try:
                    current = current[int(key)]
                    continue
                except Exception:
                    return None
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    @staticmethod
    def _join_url(base: str | None, path: str | None) -> str:
        left = (base or "").strip().rstrip('/')
        right = (path or "").strip()
        if not left and not right:
            return ""
        if not right:
            return left
        if right.startswith("http://") or right.startswith("https://"):
            return right
        if right.startswith("?"):
            return f"{left}{right}"
        return f"{left}/{right.lstrip('/')}"

    @staticmethod
    def _string_template(template: str, payload: dict[str, Any], provider: ReadingProvider) -> str:
        values = {
            "api_key": provider.api_key or "",
            "model": provider.model_name or "",
            "prompt": payload.get("prompt") or "",
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "topic": payload.get("topic") or payload.get("topic_code") or "",
            "task": payload.get("task") or "",
        }
        result = template
        for key, value in values.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result
