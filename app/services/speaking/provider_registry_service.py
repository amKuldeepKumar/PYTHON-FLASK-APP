from __future__ import annotations

from datetime import datetime
import json

from ...extensions import db
from ...models.api_log import ApiCallLog
from ...models.speaking_provider import SpeakingProvider
from .deepgram_stt_service import DeepgramSTTService


class SpeakingProviderRegistryService:
    KIND_STT = SpeakingProvider.KIND_STT
    KIND_EVALUATION = SpeakingProvider.KIND_EVALUATION
    KIND_PRONUNCIATION = SpeakingProvider.KIND_PRONUNCIATION
    KIND_TTS = SpeakingProvider.KIND_TTS

    DEFAULT_ROWS = (
        {
            "name": "Default STT Provider",
            "provider_kind": SpeakingProvider.KIND_STT,
            "usage_scope": SpeakingProvider.USAGE_STT_MIC,
        },
        {
            "name": "Default Evaluation Provider",
            "provider_kind": SpeakingProvider.KIND_EVALUATION,
            "usage_scope": SpeakingProvider.USAGE_EVAL_SPEAKING,
        },
        {
            "name": "Default Pronunciation Provider",
            "provider_kind": SpeakingProvider.KIND_PRONUNCIATION,
            "usage_scope": SpeakingProvider.USAGE_PRONUNCIATION_SCORING,
        },
        {
            "name": "Default TTS Provider",
            "provider_kind": SpeakingProvider.KIND_TTS,
            "usage_scope": SpeakingProvider.USAGE_TTS_LESSON,
        },
    )

    RECOMMENDED_APIS = {
        SpeakingProvider.KIND_STT: [
            {"name": "Deepgram", "link": "https://deepgram.com", "plan": "Usage-based / trial", "best_for": "Realtime STT", "placement": "Mic to text"},
            {"name": "Google Cloud Speech-to-Text", "link": "https://cloud.google.com/speech-to-text", "plan": "Usage-based", "best_for": "Wide language support", "placement": "Mic to text / uploads"},
            {"name": "Azure AI Speech", "link": "https://azure.microsoft.com/products/ai-services/ai-speech", "plan": "Usage-based", "best_for": "Enterprise speech stack", "placement": "Mic to text / uploads"},
            {"name": "OpenAI Whisper API", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Simple high-quality transcription", "placement": "Audio upload to text"},
        ],
        SpeakingProvider.KIND_EVALUATION: [
            {"name": "OpenAI", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Rubric scoring and feedback", "placement": "Speaking score / AI feedback"},
            {"name": "Azure OpenAI", "link": "https://azure.microsoft.com/products/ai-services/openai-service", "plan": "Enterprise contract / usage", "best_for": "Managed enterprise evaluation", "placement": "Speaking score / AI feedback"},
            {"name": "Anthropic", "link": "https://www.anthropic.com/api", "plan": "Usage-based", "best_for": "Long feedback generation", "placement": "AI feedback"},
            {"name": "Google Gemini API", "link": "https://ai.google.dev", "plan": "Usage-based / free tier on some plans", "best_for": "Flexible text evaluation", "placement": "Speaking score / AI feedback"},
        ],
        SpeakingProvider.KIND_PRONUNCIATION: [
            {"name": "Azure AI Speech Pronunciation Assessment", "link": "https://azure.microsoft.com/products/ai-services/ai-speech", "plan": "Usage-based", "best_for": "Pronunciation and phoneme detail", "placement": "Pronunciation score"},
            {"name": "Google Cloud Speech", "link": "https://cloud.google.com/speech-to-text", "plan": "Usage-based", "best_for": "Speech confidence support", "placement": "Pronunciation score / accent check"},
            {"name": "Speechace", "link": "https://www.speechace.com", "plan": "Contact sales / usage", "best_for": "English learning pronunciation", "placement": "Pronunciation score / accent check"},
            {"name": "ELSA / dedicated pronunciation vendors", "link": "https://elsaspeak.com/en/elsa-api", "plan": "Custom pricing", "best_for": "English speaking products", "placement": "Pronunciation score"},
        ],
        SpeakingProvider.KIND_TTS: [
            {"name": "ElevenLabs", "link": "https://elevenlabs.io", "plan": "Usage-based", "best_for": "Natural premium voices", "placement": "Lesson playback / AI voice"},
            {"name": "Azure AI Speech", "link": "https://azure.microsoft.com/products/ai-services/ai-speech", "plan": "Usage-based", "best_for": "Enterprise TTS", "placement": "Dashboard voice / lesson narration"},
            {"name": "Google Cloud Text-to-Speech", "link": "https://cloud.google.com/text-to-speech", "plan": "Usage-based", "best_for": "Multilingual narration", "placement": "Lesson playback / multilingual voice"},
            {"name": "OpenAI audio", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Unified model family", "placement": "Generated spoken responses / TTS"},
        ],
    }

    @classmethod
    def ensure_defaults(cls) -> None:
        changed = False
        for row in cls.DEFAULT_ROWS:
            exists = SpeakingProvider.query.filter_by(provider_kind=row["provider_kind"]).first()
            if not exists:
                db.session.add(SpeakingProvider(
                    name=row["name"],
                    provider_kind=row["provider_kind"],
                    provider_type=SpeakingProvider.TYPE_MOCK,
                    usage_scope=row.get("usage_scope"),
                    is_enabled=(row["provider_kind"] == SpeakingProvider.KIND_EVALUATION),
                    is_default=True,
                    supports_test=True,
                    last_test_status="idle",
                    last_test_message="Ready for future API configuration.",
                ))
                changed = True
        if changed:
            db.session.commit()

    @classmethod
    def grouped_registry(cls) -> dict[str, list[SpeakingProvider]]:
        cls.ensure_defaults()
        rows = SpeakingProvider.query.order_by(
            SpeakingProvider.provider_kind.asc(),
            SpeakingProvider.is_default.desc(),
            SpeakingProvider.created_at.asc(),
            SpeakingProvider.id.asc(),
        ).all()
        grouped = {cls.KIND_STT: [], cls.KIND_EVALUATION: [], cls.KIND_PRONUNCIATION: [], cls.KIND_TTS: []}
        for row in rows:
            grouped.setdefault(row.provider_kind, []).append(row)
        return grouped

    @classmethod
    def by_id(cls, provider_id: int) -> SpeakingProvider | None:
        cls.ensure_defaults()
        return db.session.get(SpeakingProvider, provider_id)

    @classmethod
    def default_provider(cls, provider_kind: str) -> SpeakingProvider | None:
        cls.ensure_defaults()
        return SpeakingProvider.query.filter_by(provider_kind=provider_kind, is_default=True).order_by(SpeakingProvider.id.asc()).first()

    @classmethod
    def enabled_providers(cls, provider_kind: str) -> list[SpeakingProvider]:
        cls.ensure_defaults()
        return SpeakingProvider.query.filter_by(provider_kind=provider_kind, is_enabled=True).order_by(SpeakingProvider.is_default.desc(), SpeakingProvider.id.asc()).all()

    @classmethod
    def fallback_provider(cls, provider: SpeakingProvider | None) -> SpeakingProvider | None:
        if not provider or not provider.fallback_provider_id:
            return None
        fallback = cls.by_id(provider.fallback_provider_id)
        if not fallback or fallback.id == provider.id or fallback.provider_kind != provider.provider_kind:
            return None
        return fallback

    @classmethod
    def resolve_provider(cls, provider_kind: str) -> tuple[SpeakingProvider | None, SpeakingProvider | None]:
        primary = cls.default_provider(provider_kind)
        fallback = cls.fallback_provider(primary)
        return primary, fallback

    @classmethod
    def provider_runtime_settings(cls, provider_kind: str) -> dict:
        provider, fallback = cls.resolve_provider(provider_kind)
        if not provider:
            return {"provider": None, "fallback_provider": None, "config": {}}
        try:
            config = json.loads(provider.config_json) if provider.config_json else {}
            if not isinstance(config, dict):
                config = {}
        except Exception:
            config = {}
        return {"provider": provider, "fallback_provider": fallback, "config": config}

    @classmethod
    def fallback_choices(cls, provider_kind: str, current_provider_id: int | None = None) -> list[tuple[int, str]]:
        rows = SpeakingProvider.query.filter_by(provider_kind=provider_kind).order_by(SpeakingProvider.is_default.desc(), SpeakingProvider.name.asc()).all()
        choices = [(0, "No fallback")]
        for row in rows:
            if current_provider_id and row.id == current_provider_id:
                continue
            choices.append((row.id, f"{row.name} ({row.provider_label})"))
        return choices

    @classmethod
    def save_provider(cls, provider: SpeakingProvider, payload: dict) -> SpeakingProvider:
        provider.name = payload["name"]
        provider.provider_kind = payload["provider_kind"]
        provider.provider_type = payload["provider_type"]
        incoming_key = payload.get("api_key")
        if incoming_key:
            provider.api_key = incoming_key
        provider.api_base_url = payload.get("api_base_url")
        provider.official_website = payload.get("official_website")
        provider.model_name = payload.get("model_name")
        provider.config_json = payload.get("config_json")
        provider.usage_scope = payload.get("usage_scope") or None
        provider.pricing_note = payload.get("pricing_note") or None
        provider.notes = payload.get("notes") or None
        fallback_provider_id = payload.get("fallback_provider_id")
        provider.fallback_provider_id = fallback_provider_id or None
        provider.is_enabled = bool(payload.get("is_enabled"))
        provider.supports_test = bool(payload.get("supports_test", True))
        db.session.add(provider)
        db.session.commit()
        return provider

    @classmethod
    def set_default(cls, provider: SpeakingProvider) -> None:
        cls.ensure_defaults()
        SpeakingProvider.query.filter_by(provider_kind=provider.provider_kind).update({"is_default": False})
        provider.is_default = True
        provider.is_enabled = True
        db.session.add(provider)
        db.session.commit()
        cls.log_test(provider, True, "Default provider updated by superadmin.")

    @classmethod
    def toggle_enabled(cls, provider: SpeakingProvider) -> None:
        provider.is_enabled = not bool(provider.is_enabled)
        if provider.is_default and not provider.is_enabled:
            provider.is_enabled = True
            provider.last_test_status = "warning"
            provider.last_test_message = "Default provider stays enabled. Choose another default before disabling."
        db.session.add(provider)
        db.session.commit()

    @classmethod
    def create_provider(cls, provider_kind: str) -> SpeakingProvider:
        count = SpeakingProvider.query.filter_by(provider_kind=provider_kind).count() + 1
        default_usage = {
            cls.KIND_STT: SpeakingProvider.USAGE_STT_MIC,
            cls.KIND_EVALUATION: SpeakingProvider.USAGE_EVAL_SPEAKING,
            cls.KIND_PRONUNCIATION: SpeakingProvider.USAGE_PRONUNCIATION_SCORING,
            cls.KIND_TTS: SpeakingProvider.USAGE_TTS_LESSON,
        }.get(provider_kind)
        row = SpeakingProvider(
            name=f"{provider_kind.title()} Provider {count}",
            provider_kind=provider_kind,
            provider_type=SpeakingProvider.TYPE_MOCK,
            usage_scope=default_usage,
            is_enabled=False,
            is_default=False,
            supports_test=True,
            last_test_status="idle",
            last_test_message="Not tested yet.",
        )
        db.session.add(row)
        db.session.commit()
        return row
    @classmethod
    def test_provider(cls, provider: SpeakingProvider) -> tuple[bool, str]:
        if provider.provider_type == SpeakingProvider.TYPE_MOCK:
            ok = True
            message = f"{provider.kind_label} mock provider is reachable and ready."
        elif provider.provider_type == SpeakingProvider.TYPE_DEEPGRAM:
            ok, message = DeepgramSTTService.test_provider(provider)
        elif provider.provider_type == SpeakingProvider.TYPE_OPENAI_COMPATIBLE:
            missing = []
            if not provider.api_key:
                missing.append("API key")
            if not provider.api_base_url:
                missing.append("base URL")
            if not provider.model_name:
                missing.append("model name")
            ok = not missing
            message = "Configuration looks valid." if ok else f"Missing {', '.join(missing)}."
        else:
            missing = []
            if not provider.api_key:
                missing.append("API key")
            if provider.provider_type in {SpeakingProvider.TYPE_GOOGLE, SpeakingProvider.TYPE_AZURE, SpeakingProvider.TYPE_CUSTOM} and not provider.api_base_url:
                missing.append("base URL")
            ok = not missing
            message = "Configuration looks valid." if ok else f"Missing {', '.join(missing)}."

        provider.last_test_status = "ok" if ok else "error"
        provider.last_test_message = (message or "")[:255]
        provider.last_tested_at = datetime.utcnow()
        db.session.add(provider)
        db.session.commit()
        cls.log_test(provider, ok, message)
        return ok, message

    @classmethod
    def recommended_market_options(cls, provider_kind: str) -> list[dict]:
        return cls.RECOMMENDED_APIS.get(provider_kind, [])

    @staticmethod
    def _estimate_usage(provider: SpeakingProvider, message: str) -> tuple[int, int, int, float]:
        input_tokens = max(1, len((message or "").split()))
        output_tokens = max(1, len((provider.model_name or provider.name or "").split()))
        total_tokens = input_tokens + output_tokens
        estimated_cost = round(total_tokens * 0.0001, 4)
        return input_tokens, output_tokens, total_tokens, estimated_cost

    @classmethod
    def log_test(cls, provider: SpeakingProvider, ok: bool, message: str) -> None:
        input_tokens, output_tokens, total_tokens, estimated_cost = cls._estimate_usage(provider, message)
        db.session.add(ApiCallLog(
            system=f"speaking:{provider.provider_kind}",
            endpoint=provider.api_base_url or provider.provider_label,
            method="TEST",
            status_code=200 if ok else 400,
            ok=ok,
            provider_name=provider.name,
            message=message[:255],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        ))
        db.session.commit()
