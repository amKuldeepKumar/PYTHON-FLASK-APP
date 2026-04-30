from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from flask_login import current_user

from ...extensions import db
from ...models import AIUsageCounter, SecurityPolicy, UserPreferences


@dataclass
class AIQuotaDecision:
    allowed: bool
    reason: str | None = None
    counter: AIUsageCounter | None = None


class AIRuntimeControl:
    LEARNING_TASKS = {
        "translation", "speaking_stt", "speaking_evaluation", "speaking_pronunciation", "speaking_tts",
        "reading_passage", "reading_question", "reading_translation", "reading_evaluation",
        "writing_plagiarism", "writing_evaluation", "listening_review", "tutor_lesson_help",
    }

    @classmethod
    def actor_user_id(cls, context: dict | None = None) -> int | None:
        context = context or {}
        user_id = context.get("user_id") or context.get("actor_user_id")
        if user_id:
            return int(user_id)
        if getattr(current_user, "is_authenticated", False):
            return int(current_user.id)
        return None

    @classmethod
    def consent_for_user(cls, user_id: int | None) -> bool:
        if not user_id:
            return False
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        return bool(getattr(prefs, "allow_ml_training", False))

    @classmethod
    def enforce_learning_scope(cls, task_key: str, payload: dict | None = None) -> tuple[bool, str | None]:
        if task_key in cls.LEARNING_TASKS:
            return True, None
        text = " ".join(str(v) for v in (payload or {}).values() if isinstance(v, (str, int, float)))[:400].lower()
        forbidden = ["investment", "stock", "crypto", "medical diagnosis", "political campaign", "dating"]
        if any(term in text for term in forbidden):
            return False, "This AI layer is restricted to learning support and rejected an off-topic request."
        return True, None

    @classmethod
    def quota_check(cls, task_key: str, *, user_id: int | None, estimated_tokens: int = 0, tts_characters: int = 0, speech_seconds: int = 0) -> AIQuotaDecision:
        if not user_id:
            return AIQuotaDecision(True, None, None)
        policy = SecurityPolicy.singleton()
        counter = AIUsageCounter.query.filter_by(actor_user_id=user_id, usage_date=date.today()).first()
        if not counter:
            counter = AIUsageCounter(actor_user_id=user_id, usage_date=date.today())
            db.session.add(counter)
            db.session.flush()
        if counter.request_count >= int(policy.ai_daily_request_limit or 0):
            return AIQuotaDecision(False, "Daily AI request quota reached.", counter)
        if estimated_tokens and counter.token_count + estimated_tokens > int(policy.ai_daily_token_limit or 0):
            return AIQuotaDecision(False, "Daily AI token quota reached.", counter)
        if task_key == "translation" and counter.translation_count >= int(policy.translation_daily_limit or 0):
            return AIQuotaDecision(False, "Daily translation quota reached.", counter)
        if tts_characters and counter.tts_characters + tts_characters > int(policy.tts_daily_character_limit or 0):
            return AIQuotaDecision(False, "Daily TTS quota reached.", counter)
        if speech_seconds and counter.speech_seconds + speech_seconds > int(policy.speech_daily_seconds_limit or 0):
            return AIQuotaDecision(False, "Daily speech quota reached.", counter)
        return AIQuotaDecision(True, None, counter)

    @classmethod
    def consume_quota(cls, counter: AIUsageCounter | None, *, task_key: str, total_tokens: int = 0, tts_characters: int = 0, speech_seconds: int = 0) -> None:
        if not counter:
            return
        counter.request_count += 1
        counter.token_count += max(0, int(total_tokens or 0))
        if task_key == "translation":
            counter.translation_count += 1
        counter.tts_characters += max(0, int(tts_characters or 0))
        counter.speech_seconds += max(0, int(speech_seconds or 0))
        db.session.add(counter)
        db.session.commit()
