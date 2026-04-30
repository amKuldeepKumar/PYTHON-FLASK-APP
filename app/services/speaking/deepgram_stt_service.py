from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from ...models.speaking_provider import SpeakingProvider


class DeepgramSTTService:
    """Deepgram REST integration for Fluencify speaking STT.

    This avoids SDK version problems and lets the SuperAdmin API Registry become
    the single source for the Deepgram key, model, language, and extra options.
    """

    DEFAULT_BASE_URL = "https://api.deepgram.com"
    DEFAULT_MODEL = "nova-3"
    DEFAULT_LANGUAGE = "en"

    @staticmethod
    def _clean_base_url(provider: SpeakingProvider | None) -> str:
        raw = (getattr(provider, "api_base_url", None) or DeepgramSTTService.DEFAULT_BASE_URL).strip()
        return raw.rstrip("/") or DeepgramSTTService.DEFAULT_BASE_URL

    @staticmethod
    def _load_config(provider: SpeakingProvider | None) -> dict[str, Any]:
        raw = (getattr(provider, "config_json", None) or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _auth_headers(api_key: str, *, content_type: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Token {api_key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    @classmethod
    def _request_json(
        cls,
        *,
        url: str,
        api_key: str,
        method: str = "GET",
        data: bytes | None = None,
        content_type: str | None = None,
        timeout: int = 20,
    ) -> tuple[bool, dict[str, Any] | None, str]:
        req = Request(
            url,
            data=data,
            method=method,
            headers=cls._auth_headers(api_key, content_type=content_type),
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                payload = resp.read().decode("utf-8", errors="replace")
                if not payload.strip():
                    return True, {}, "OK"
                return True, json.loads(payload), "OK"
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            message = body or str(exc)
            return False, None, f"Deepgram HTTP {exc.code}: {message[:220]}"
        except URLError as exc:
            return False, None, f"Deepgram network error: {exc.reason}"
        except Exception as exc:
            return False, None, f"Deepgram error: {exc}"

    @classmethod
    def test_provider(cls, provider: SpeakingProvider) -> tuple[bool, str]:
        api_key = (getattr(provider, "api_key", None) or "").strip()
        if not api_key:
            return False, "Missing Deepgram API key."

        base_url = cls._clean_base_url(provider)
        timeout = int(getattr(provider, "timeout_seconds", None) or 20)
        ok, payload, message = cls._request_json(
            url=f"{base_url}/v1/projects",
            api_key=api_key,
            timeout=timeout,
        )
        if ok:
            project_count = len((payload or {}).get("projects") or []) if isinstance(payload, dict) else 0
            return True, f"Deepgram connected successfully. Projects visible: {project_count}."
        return False, message

    @classmethod
    def transcribe_bytes(
        cls,
        *,
        provider: SpeakingProvider,
        audio_bytes: bytes,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        api_key = (getattr(provider, "api_key", None) or "").strip()
        if not api_key:
            return {"ok": False, "text": "", "confidence": 0.0, "message": "Missing Deepgram API key."}
        if not audio_bytes:
            return {"ok": False, "text": "", "confidence": 0.0, "message": "Audio file is empty."}

        config = cls._load_config(provider)
        query = {
            "model": (getattr(provider, "model_name", None) or config.get("model") or cls.DEFAULT_MODEL),
            "language": config.get("language") or cls.DEFAULT_LANGUAGE,
            "smart_format": str(config.get("smart_format", True)).lower(),
            "punctuate": str(config.get("punctuate", True)).lower(),
        }
        for key in ("diarize", "utterances", "detect_language", "filler_words"):
            if key in config:
                query[key] = str(config[key]).lower()

        base_url = cls._clean_base_url(provider)
        url = f"{base_url}/v1/listen?{urlencode(query)}"
        timeout = int(getattr(provider, "timeout_seconds", None) or config.get("timeout", 45) or 45)
        ok, payload, message = cls._request_json(
            url=url,
            api_key=api_key,
            method="POST",
            data=audio_bytes,
            content_type=mime_type or "application/octet-stream",
            timeout=timeout,
        )
        if not ok:
            return {"ok": False, "text": "", "confidence": 0.0, "message": message}

        try:
            alt = payload["results"]["channels"][0]["alternatives"][0]
            transcript = (alt.get("transcript") or "").strip()
            confidence = float(alt.get("confidence") or 0.0)
        except Exception:
            transcript = ""
            confidence = 0.0

        if not transcript:
            return {"ok": False, "text": "", "confidence": confidence, "message": "Deepgram returned no transcript."}
        return {"ok": True, "text": transcript, "confidence": confidence, "message": "Deepgram transcription completed."}

    @classmethod
    def transcribe_audio_meta(cls, provider: SpeakingProvider, audio_meta: dict[str, Any]) -> dict[str, Any]:
        relative_path = (audio_meta or {}).get("audio_file_path")
        if not relative_path:
            return {"ok": False, "text": "", "confidence": 0.0, "message": "No audio file path found."}

        path = Path(current_app.instance_path) / str(relative_path)
        if not path.exists():
            return {"ok": False, "text": "", "confidence": 0.0, "message": f"Audio file not found: {relative_path}"}

        try:
            audio_bytes = path.read_bytes()
        except Exception as exc:
            return {"ok": False, "text": "", "confidence": 0.0, "message": f"Could not read audio file: {exc}"}

        return cls.transcribe_bytes(
            provider=provider,
            audio_bytes=audio_bytes,
            mime_type=(audio_meta or {}).get("audio_mime_type") or "application/octet-stream",
        )
