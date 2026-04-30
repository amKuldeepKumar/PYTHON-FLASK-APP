from __future__ import annotations

from datetime import datetime
import json
import time

from ...extensions import db
from ...models.api_log import ApiCallLog
from ...models.reading_prompt_config import ReadingPromptConfig
from ...models.reading_provider import ReadingProvider


class ReadingProviderRegistryService:
    KIND_PASSAGE = ReadingProvider.KIND_PASSAGE
    KIND_QUESTION = ReadingProvider.KIND_QUESTION
    KIND_TRANSLATION = ReadingProvider.KIND_TRANSLATION
    KIND_EVALUATION = ReadingProvider.KIND_EVALUATION
    KIND_PLAGIARISM = ReadingProvider.KIND_PLAGIARISM

    DEFAULT_ROWS = (
        {"name": "Default Passage Provider", "provider_kind": ReadingProvider.KIND_PASSAGE, "usage_scope": ReadingProvider.USAGE_PASSAGE_GENERATION},
        {"name": "Default Question Provider", "provider_kind": ReadingProvider.KIND_QUESTION, "usage_scope": ReadingProvider.USAGE_QUESTION_GENERATION},
        {"name": "Default Translation Provider", "provider_kind": ReadingProvider.KIND_TRANSLATION, "usage_scope": ReadingProvider.USAGE_WORD_TRANSLATION},
        {"name": "Default Evaluation Provider", "provider_kind": ReadingProvider.KIND_EVALUATION, "usage_scope": ReadingProvider.USAGE_ANSWER_EVALUATION},
        {"name": "Default Plagiarism Provider", "provider_kind": ReadingProvider.KIND_PLAGIARISM, "usage_scope": ReadingProvider.USAGE_PLAGIARISM_CHECK},
    )

    DEFAULT_PROMPTS = {
        ReadingPromptConfig.TASK_PASSAGE: {
            "title": "Passage Generation Prompt",
            "prompt_text": "Generate one reading passage for the topic {{topic}} at {{level}} level. Keep the vocabulary suitable for the level, stay factual, and return clean paragraph text only.",
        },
        ReadingPromptConfig.TASK_QUESTION: {
            "title": "Question Generation Prompt",
            "prompt_text": "Using the passage below, generate MCQ, fill in the blanks, and true/false questions. Respect the requested counts and return structured JSON with answers.",
        },
        ReadingPromptConfig.TASK_TRANSLATION: {
            "title": "Translation / Synonym Prompt",
            "prompt_text": "Given a selected word from the reading passage, provide a simple meaning, one close synonym, and a learner-friendly translation in the requested language.",
        },
        ReadingPromptConfig.TASK_EVALUATION: {
            "title": "Answer Evaluation Prompt",
            "prompt_text": "Check the learner answer against the reading question and expected answer. Return correct/incorrect, a short reason, and a confidence score from 0 to 1.",
        },
        ReadingProvider.KIND_PLAGIARISM: {
            "title": "Plagiarism Check Prompt",
            "prompt_text": "Compare the learner submission with the reference material and flag likely copied spans, overlap percentage, and risk level in a short structured JSON response.",
        },
    }

    RECOMMENDED_APIS = {
        ReadingProvider.KIND_PASSAGE: [
            {"name": "OpenAI", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Passage generation", "placement": "Topic to level-based reading paragraph"},
            {"name": "Google Gemini API", "link": "https://ai.google.dev", "plan": "Usage-based / some free tier", "best_for": "Fast passage drafting", "placement": "Reading passage generation"},
            {"name": "Anthropic", "link": "https://www.anthropic.com/api", "plan": "Usage-based", "best_for": "Long-form controlled writing", "placement": "Passage generation"},
        ],
        ReadingProvider.KIND_QUESTION: [
            {"name": "OpenAI", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "MCQ + fill blanks + true/false", "placement": "Question generation from passage"},
            {"name": "Google Gemini API", "link": "https://ai.google.dev", "plan": "Usage-based / some free tier", "best_for": "Structured JSON output", "placement": "Question generation"},
            {"name": "Anthropic", "link": "https://www.anthropic.com/api", "plan": "Usage-based", "best_for": "Editorial style question sets", "placement": "Question generation"},
        ],
        ReadingProvider.KIND_TRANSLATION: [
            {"name": "Google Translate", "link": "https://cloud.google.com/translate", "plan": "Usage-based", "best_for": "Word translation", "placement": "Reading word support"},
            {"name": "OpenAI", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Meaning + synonym bundles", "placement": "Vocabulary helper"},
            {"name": "Azure AI Translator", "link": "https://azure.microsoft.com/products/ai-services/ai-translator", "plan": "Usage-based", "best_for": "Enterprise translation", "placement": "Translation / synonym support"},
        ],
        ReadingProvider.KIND_EVALUATION: [
            {"name": "OpenAI", "link": "https://platform.openai.com", "plan": "Usage-based", "best_for": "Short answer checking", "placement": "Reading answer evaluation"},
            {"name": "Google Gemini API", "link": "https://ai.google.dev", "plan": "Usage-based / some free tier", "best_for": "Reason-based checking", "placement": "Answer evaluation"},
            {"name": "Anthropic", "link": "https://www.anthropic.com/api", "plan": "Usage-based", "best_for": "Detailed wrong-answer explanation", "placement": "Evaluation and feedback"},
        ],
        ReadingProvider.KIND_PLAGIARISM: [
            {"name": "Copyleaks", "link": "https://copyleaks.com", "plan": "Usage-based / contact sales", "best_for": "Academic plagiarism checks", "placement": "Writing plagiarism review"},
            {"name": "Originality.ai", "link": "https://originality.ai", "plan": "Usage-based", "best_for": "Web and AI-assisted overlap checks", "placement": "Writing integrity checks"},
            {"name": "Turnitin", "link": "https://www.turnitin.com", "plan": "Institution contract", "best_for": "Institute plagiarism workflows", "placement": "Essay plagiarism review"},
        ],
    }

    @classmethod
    def ensure_defaults(cls) -> None:
        changed = False
        for row in cls.DEFAULT_ROWS:
            exists = ReadingProvider.query.filter_by(provider_kind=row["provider_kind"]).first()
            if not exists:
                db.session.add(ReadingProvider(
                    name=row["name"],
                    provider_kind=row["provider_kind"],
                    provider_type=ReadingProvider.TYPE_MOCK,
                    usage_scope=row.get("usage_scope"),
                    is_enabled=(row["provider_kind"] == ReadingProvider.KIND_PASSAGE),
                    is_default=True,
                    supports_test=True,
                    last_test_status="idle",
                    last_test_message="Ready for reading API configuration.",
                ))
                changed = True

        for task_type, payload in cls.DEFAULT_PROMPTS.items():
            prompt = ReadingPromptConfig.query.filter_by(task_type=task_type).first()
            if not prompt:
                db.session.add(ReadingPromptConfig(task_type=task_type, title=payload["title"], prompt_text=payload["prompt_text"], is_active=True))
                changed = True

        if changed:
            db.session.commit()

    @classmethod
    def grouped_registry(cls) -> dict[str, list[ReadingProvider]]:
        cls.ensure_defaults()
        rows = ReadingProvider.query.order_by(ReadingProvider.provider_kind.asc(), ReadingProvider.is_default.desc(), ReadingProvider.created_at.asc(), ReadingProvider.id.asc()).all()
        grouped = {cls.KIND_PASSAGE: [], cls.KIND_QUESTION: [], cls.KIND_TRANSLATION: [], cls.KIND_EVALUATION: [], cls.KIND_PLAGIARISM: []}
        for row in rows:
            grouped.setdefault(row.provider_kind, []).append(row)
        return grouped

    @classmethod
    def by_id(cls, provider_id: int) -> ReadingProvider | None:
        cls.ensure_defaults()
        return db.session.get(ReadingProvider, provider_id)

    @classmethod
    def default_provider(cls, provider_kind: str) -> ReadingProvider | None:
        cls.ensure_defaults()
        return ReadingProvider.query.filter_by(provider_kind=provider_kind, is_default=True).order_by(ReadingProvider.id.asc()).first()

    @classmethod
    def enabled_providers(cls, provider_kind: str) -> list[ReadingProvider]:
        cls.ensure_defaults()
        return ReadingProvider.query.filter_by(provider_kind=provider_kind, is_enabled=True).order_by(ReadingProvider.is_default.desc(), ReadingProvider.id.asc()).all()

    @classmethod
    def fallback_provider(cls, provider: ReadingProvider | None) -> ReadingProvider | None:
        if not provider or not provider.fallback_provider_id:
            return None
        fallback = cls.by_id(provider.fallback_provider_id)
        if not fallback or fallback.id == provider.id or fallback.provider_kind != provider.provider_kind:
            return None
        return fallback

    @classmethod
    def resolve_provider(cls, provider_kind: str) -> tuple[ReadingProvider | None, ReadingProvider | None]:
        primary = cls.default_provider(provider_kind)
        if primary and primary.is_enabled:
            return primary, cls.fallback_provider(primary)
        enabled = cls.enabled_providers(provider_kind)
        primary = enabled[0] if enabled else cls.default_provider(provider_kind)
        return primary, cls.fallback_provider(primary)

    @classmethod
    def choices_for_kind(cls, provider_kind: str, include_none: bool = True) -> list[tuple[int, str]]:
        rows = ReadingProvider.query.filter_by(provider_kind=provider_kind).order_by(ReadingProvider.is_default.desc(), ReadingProvider.name.asc()).all()
        choices = [(0, "No fallback")] if include_none else []
        choices.extend((row.id, row.name) for row in rows)
        return choices

    @classmethod
    def save_provider(cls, provider: ReadingProvider, payload: dict) -> ReadingProvider:
        cls.ensure_defaults()
        provider.name = payload.get("name") or provider.name
        provider.provider_kind = payload.get("provider_kind") or provider.provider_kind
        provider.provider_type = payload.get("provider_type") or provider.provider_type
        if payload.get("api_key"):
            provider.api_key = payload["api_key"]
        provider.official_website = payload.get("official_website")
        provider.api_base_url = payload.get("api_base_url")
        provider.model_name = payload.get("model_name")
        provider.usage_scope = payload.get("usage_scope")
        provider.pricing_note = payload.get("pricing_note")
        provider.notes = payload.get("notes")
        provider.config_json = cls._clean_json(payload.get("config_json"))
        provider.is_enabled = bool(payload.get("is_enabled"))
        provider.supports_test = bool(payload.get("supports_test", True))
        fallback_provider_id = int(payload.get("fallback_provider_id") or 0)
        provider.fallback_provider_id = fallback_provider_id or None
        provider.updated_at = datetime.utcnow()
        db.session.add(provider)
        db.session.commit()
        return provider

    @classmethod
    def set_default(cls, provider: ReadingProvider) -> None:
        ReadingProvider.query.filter_by(provider_kind=provider.provider_kind).update({"is_default": False})
        provider.is_default = True
        db.session.add(provider)
        db.session.commit()
        cls.log_event(provider, ok=True, message=f"{provider.name} set as default.", status_code=200, endpoint="/registry/default")

    @classmethod
    def toggle_enabled(cls, provider: ReadingProvider) -> None:
        provider.is_enabled = not provider.is_enabled
        provider.updated_at = datetime.utcnow()
        db.session.add(provider)
        db.session.commit()
        state = "enabled" if provider.is_enabled else "disabled"
        cls.log_event(provider, ok=True, message=f"{provider.name} {state}.", status_code=200, endpoint="/registry/toggle")

    @classmethod
    def create_provider(cls, provider_kind: str) -> ReadingProvider:
        count = ReadingProvider.query.filter_by(provider_kind=provider_kind).count() + 1
        usage_map = {
            cls.KIND_PASSAGE: ReadingProvider.USAGE_PASSAGE_GENERATION,
            cls.KIND_QUESTION: ReadingProvider.USAGE_QUESTION_GENERATION,
            cls.KIND_TRANSLATION: ReadingProvider.USAGE_WORD_TRANSLATION,
            cls.KIND_EVALUATION: ReadingProvider.USAGE_ANSWER_EVALUATION,
            cls.KIND_PLAGIARISM: ReadingProvider.USAGE_PLAGIARISM_CHECK,
        }
        row = ReadingProvider(
            name=f"{provider_kind.title()} Provider {count}",
            provider_kind=provider_kind,
            provider_type=ReadingProvider.TYPE_MOCK,
            usage_scope=usage_map.get(provider_kind),
            is_enabled=False,
            is_default=False,
            supports_test=True,
            last_test_status="idle",
            last_test_message="Created. Configure credentials before enabling.",
        )
        db.session.add(row)
        db.session.commit()
        return row

    @classmethod
    def active_prompt_map(cls) -> dict[str, ReadingPromptConfig]:
        cls.ensure_defaults()
        rows = ReadingPromptConfig.query.order_by(ReadingPromptConfig.task_type.asc()).all()
        return {row.task_type: row for row in rows}

    @classmethod
    def save_prompt(cls, task_type: str, title: str, prompt_text: str, is_active: bool = True) -> ReadingPromptConfig:
        cls.ensure_defaults()
        row = ReadingPromptConfig.query.filter_by(task_type=task_type).first()
        if not row:
            row = ReadingPromptConfig(task_type=task_type, title=title.strip(), prompt_text=prompt_text.strip(), is_active=is_active)
        else:
            row.title = title.strip()
            row.prompt_text = prompt_text.strip()
            row.is_active = bool(is_active)
        db.session.add(row)
        db.session.commit()
        return row

    @classmethod
    def test_provider(cls, provider: ReadingProvider) -> tuple[bool, str]:
        started = time.perf_counter()
        config = cls.load_config(provider)
        if provider.provider_type == ReadingProvider.TYPE_MOCK:
            ok, message = True, "Mock provider ready. No external API call needed."
        elif provider.provider_type in {ReadingProvider.TYPE_OPENAI_COMPATIBLE, ReadingProvider.TYPE_GOOGLE, ReadingProvider.TYPE_AZURE, ReadingProvider.TYPE_GEMINI, ReadingProvider.TYPE_ANTHROPIC, ReadingProvider.TYPE_CUSTOM}:
            missing = []
            if not provider.api_base_url:
                missing.append("base URL")
            if not provider.api_key:
                missing.append("API key")
            if missing:
                ok, message = False, f"Missing {' and '.join(missing)}."
            else:
                ok, message = True, f"Configuration looks valid. Test handshake simulated with timeout {config.get('timeout', 30)}s."
        else:
            ok, message = False, "Unsupported provider type."

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        provider.last_test_status = "success" if ok else "failed"
        provider.last_test_message = f"{message} ({elapsed_ms} ms)"
        provider.last_tested_at = datetime.utcnow()
        db.session.add(provider)
        db.session.commit()
        cls.log_event(provider, ok=ok, message=provider.last_test_message, status_code=200 if ok else 422, endpoint="/registry/test")
        return ok, provider.last_test_message

    @classmethod
    def execute_task(cls, provider_kind: str, payload: dict) -> dict:
        provider, fallback = cls.resolve_provider(provider_kind)
        if not provider:
            return {"ok": False, "message": "No reading provider configured.", "provider": None}
        result = cls._simulate_provider_call(provider, payload)
        if result.get("ok"):
            return result
        if fallback:
            return cls._simulate_provider_call(fallback, payload, used_as_fallback=True)
        return result

    @classmethod
    def _simulate_provider_call(cls, provider: ReadingProvider, payload: dict, used_as_fallback: bool = False) -> dict:
        task_label = payload.get("task") or provider.provider_kind
        config = cls.load_config(provider)
        message = f"{task_label.title()} request prepared for {provider.name} with timeout {config.get('timeout', 30)}s."
        cls.log_event(provider, ok=True, message=message, status_code=200, endpoint=f"/execute/{provider.provider_kind}")
        return {
            "ok": True,
            "provider": {"id": provider.id, "name": provider.name, "kind": provider.provider_kind, "type": provider.provider_type, "fallback": used_as_fallback},
            "message": message,
            "payload": payload,
        }

    @staticmethod
    def load_config(provider: ReadingProvider | None) -> dict:
        if not provider or not provider.config_json:
            return {}
        try:
            data = json.loads(provider.config_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _clean_json(raw_value: str | None) -> str | None:
        value = (raw_value or "").strip()
        if not value:
            return None
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except Exception:
            return value

    @staticmethod
    def _estimate_usage(provider: ReadingProvider | None, message: str) -> tuple[int, int, int, float]:
        input_tokens = max(1, len((message or "").split()))
        output_tokens = max(1, len((getattr(provider, "model_name", None) or getattr(provider, "name", None) or "").split()))
        total_tokens = input_tokens + output_tokens
        estimated_cost = round(total_tokens * 0.0001, 4)
        return input_tokens, output_tokens, total_tokens, estimated_cost

    @classmethod
    def log_event(cls, provider: ReadingProvider | None, ok: bool, message: str, status_code: int, endpoint: str) -> None:
        system = f"reading:{provider.provider_kind}" if provider else "reading:system"
        name = provider.name if provider else "Unknown provider"
        input_tokens, output_tokens, total_tokens, estimated_cost = cls._estimate_usage(provider, message)
        db.session.add(ApiCallLog(
            system=system,
            endpoint=endpoint,
            method="POST",
            ok=ok,
            status_code=status_code,
            provider_name=name,
            message=f"{name}: {message}"[:255],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        ))
        db.session.commit()
