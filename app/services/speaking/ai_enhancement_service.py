from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from ...models.speaking_provider import SpeakingProvider
from .provider_registry_service import SpeakingProviderRegistryService
from .deepgram_stt_service import DeepgramSTTService


class SpeakingAIEnhancementService:
    """Provider-aware AI enhancement layer for Phase 6G.

    This service keeps the app working even before live external APIs are wired.
    It uses registry-configured providers and produces deterministic mock outputs,
    while leaving one place to swap in real provider SDK calls later.
    """

    FILLER_WORDS = {
        'uh', 'um', 'er', 'ah', 'hmm', 'mmm', 'like', 'actually', 'basically', 'literally', 'so', 'well'
    }
    FILLER_PHRASES = ('you know', 'i mean', 'kind of', 'sort of')

    @staticmethod
    def _provider_meta(provider: SpeakingProvider | None) -> dict:
        if not provider:
            return {"id": None, "name": "No provider", "type": None, "kind": None}
        return {
            "id": provider.id,
            "name": provider.name,
            "type": provider.provider_type,
            "kind": provider.provider_kind,
            "label": provider.provider_label,
        }

    @staticmethod
    def _load_config(provider: SpeakingProvider | None) -> dict:
        if not provider or not provider.config_json:
            return {}
        try:
            raw = json.loads(provider.config_json)
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}
    @classmethod
    def transcribe_audio(cls, audio_meta: dict, fallback_transcript: str | None = None) -> dict:
        provider = SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_STT)

        if fallback_transcript and fallback_transcript.strip():
            return {
                "text": fallback_transcript.strip(),
                "source": "manual",
                "confidence": 1.0,
                "provider": cls._provider_meta(provider),
                "notes": ["Manual/browser transcript used."],
            }

        if provider and provider.is_enabled and provider.provider_type == SpeakingProvider.TYPE_DEEPGRAM:
            result = DeepgramSTTService.transcribe_audio_meta(provider, audio_meta or {})
            if result.get("ok"):
                return {
                    "text": result.get("text") or "",
                    "source": "deepgram",
                    "confidence": float(result.get("confidence") or 0.0),
                    "provider": cls._provider_meta(provider),
                    "notes": [result.get("message") or "Deepgram transcription completed."],
                }
            return {
                "text": "",
                "source": "deepgram_error",
                "confidence": 0.0,
                "provider": cls._provider_meta(provider),
                "notes": [result.get("message") or "Deepgram transcription failed."],
            }

        filename = (audio_meta.get("audio_original_name") or "student-audio").rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        generated = filename.strip() or "Student speaking response"
        if len(generated.split()) < 3:
            generated = f"{generated} practice response"

        notes = ["Mock STT transcript generated because no enabled Deepgram STT provider is set."]
        config = cls._load_config(provider)
        if config.get("mock_prefix"):
            generated = f"{config['mock_prefix']} {generated}".strip()

        return {
            "text": generated,
            "source": "stt_mock" if provider else "stt_unavailable",
            "confidence": 0.72 if provider and provider.is_enabled else 0.25,
            "provider": cls._provider_meta(provider),
            "notes": notes,
        }

    @staticmethod
    def _tokenize(text: str | None) -> list[str]:
        return re.findall(r"[a-zA-Z']+", (text or "").lower())

    @staticmethod
    def _sentence_parts(text: str | None) -> list[str]:
        return [part.strip() for part in re.split(r"[.!?]+", (text or '').strip()) if part.strip()]

    @classmethod
    def speaking_metrics(cls, *, transcript: str, duration_seconds: int | None = None) -> dict:
        tokens = cls._tokenize(transcript)
        word_count = len(tokens)
        sentence_parts = cls._sentence_parts(transcript)
        sentence_count = len(sentence_parts) or (1 if transcript.strip() else 0)
        avg_sentence_length = round(word_count / sentence_count, 1) if sentence_count else 0.0

        duration_seconds = max(0, int(duration_seconds or 0))
        wpm = round((word_count / duration_seconds) * 60, 1) if duration_seconds > 0 and word_count > 0 else 0.0

        filler_count = sum(1 for token in tokens if token in cls.FILLER_WORDS)
        normalized_text = f" {(transcript or '').lower()} "
        for phrase in cls.FILLER_PHRASES:
            filler_count += normalized_text.count(f" {phrase} ")
        filler_ratio = round((filler_count / word_count), 3) if word_count else 0.0

        pacing_band = 'unknown'
        pacing_score = 58
        if wpm <= 0:
            pacing_band = 'unknown'
            pacing_score = 58
        elif wpm < 70:
            pacing_band = 'too_slow'
            pacing_score = 40
        elif wpm < 95:
            pacing_band = 'slightly_slow'
            pacing_score = 62
        elif wpm <= 155:
            pacing_band = 'good'
            pacing_score = 86
        elif wpm <= 185:
            pacing_band = 'slightly_fast'
            pacing_score = 67
        else:
            pacing_band = 'too_fast'
            pacing_score = 44

        filler_score = 86
        if filler_ratio >= 0.18:
            filler_score = 34
        elif filler_ratio >= 0.10:
            filler_score = 52
        elif filler_ratio >= 0.05:
            filler_score = 69

        sentence_score = 82
        if avg_sentence_length <= 0:
            sentence_score = 28
        elif avg_sentence_length < 5:
            sentence_score = 48
        elif avg_sentence_length < 8:
            sentence_score = 66
        elif avg_sentence_length <= 22:
            sentence_score = 84
        elif avg_sentence_length <= 30:
            sentence_score = 68
        else:
            sentence_score = 45

        notes: list[str] = []
        if wpm > 0:
            if pacing_band == 'too_slow':
                notes.append('Try to speak a bit faster and keep your ideas moving.')
            elif pacing_band == 'slightly_slow':
                notes.append('Your pace is understandable, but it can be slightly more natural.')
            elif pacing_band == 'slightly_fast':
                notes.append('Slow down slightly so your speech sounds clearer.')
            elif pacing_band == 'too_fast':
                notes.append('You are speaking too fast. Add clearer pauses between ideas.')
        if filler_ratio >= 0.10:
            notes.append('Reduce filler words like uh or um for smoother fluency.')
        elif filler_ratio >= 0.05:
            notes.append('A few filler words are present. Try to pause silently instead.')
        if avg_sentence_length > 22:
            notes.append('Your sentences are getting long. Break ideas into shorter sentences.')
        elif 0 < avg_sentence_length < 6:
            notes.append('Try to connect your ideas into fuller sentences.')

        return {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'words_per_minute': wpm,
            'filler_count': filler_count,
            'filler_ratio': filler_ratio,
            'avg_sentence_length': avg_sentence_length,
            'pacing_band': pacing_band,
            'pacing_score': pacing_score,
            'filler_score': filler_score,
            'sentence_score': sentence_score,
            'notes': notes,
        }

    @classmethod
    def pronunciation_analysis(cls, *, transcript: str, prompt_text: str = '', duration_seconds: int | None = None) -> dict:
        provider = SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_PRONUNCIATION)
        tokens = cls._tokenize(transcript)
        prompt_tokens = cls._tokenize(prompt_text)
        word_count = len(tokens)
        avg_word_len = (sum(len(t) for t in tokens) / word_count) if word_count else 0
        variety = (len(set(tokens)) / word_count) if word_count else 0
        prompt_overlap = len(set(tokens).intersection(set(prompt_tokens))) if prompt_tokens else 0
        metrics = cls.speaking_metrics(transcript=transcript, duration_seconds=duration_seconds)

        pronunciation_score = max(0, min(100, round(
            34 + avg_word_len * 5 + variety * 16 + metrics['sentence_score'] * 0.18
        )))
        fluency_score = max(0, min(100, round(
            18
            + min(word_count, 80) * 0.45
            + variety * 12
            + metrics['pacing_score'] * 0.42
            + metrics['filler_score'] * 0.22
            + metrics['sentence_score'] * 0.16
        )))
        accent_confidence = max(0, min(100, round(
            42 + prompt_overlap * 5 + variety * 14 + metrics['sentence_score'] * 0.12
        )))

        notes: list[str] = []
        if word_count < 8:
            notes.append('Speech sample is short, so speaking confidence is limited.')
        if variety < 0.45:
            notes.append('Use more varied words for stronger fluency.')
        notes.extend(metrics.get('notes') or [])
        if not notes:
            notes.append('Speaking analysis completed successfully.')

        return {
            'provider': cls._provider_meta(provider),
            'pronunciation_score': pronunciation_score,
            'fluency_score': fluency_score,
            'accent_confidence': accent_confidence,
            'words_per_minute': metrics['words_per_minute'],
            'filler_count': metrics['filler_count'],
            'filler_ratio': metrics['filler_ratio'],
            'avg_sentence_length': metrics['avg_sentence_length'],
            'pacing_band': metrics['pacing_band'],
            'notes': notes,
        }

    @classmethod
    def ai_evaluation(cls, *, transcript: str, prompt_text: str, topic_title: str | None = None) -> dict:
        provider = SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_EVALUATION)
        tokens = cls._tokenize(transcript)
        prompt_tokens = cls._tokenize(' '.join(filter(None, [prompt_text, topic_title or ''])))
        ratio = SequenceMatcher(None, ' '.join(tokens), ' '.join(prompt_tokens)).ratio() if prompt_tokens else 0.0
        structure_score = min(100, max(0, round(30 + len(re.split(r"[.!?]+", transcript.strip())) * 12))) if transcript.strip() else 0
        relevance_score = min(100, max(0, round(ratio * 100 + len(set(tokens).intersection(set(prompt_tokens))) * 8)))
        idea_score = min(100, max(0, round(25 + min(len(tokens), 80) * 0.8)))

        notes: list[str] = []
        if relevance_score < 35:
            notes.append('Answer looks partly off-topic.')
        if idea_score < 45:
            notes.append('Add more detail and examples.')
        if structure_score < 45:
            notes.append('Use clearer sentence structure.')
        if not notes:
            notes.append('AI evaluation completed successfully.')

        return {
            'provider': cls._provider_meta(provider),
            'ai_relevance_score': relevance_score,
            'ai_structure_score': structure_score,
            'ai_idea_score': idea_score,
            'notes': notes,
        }

    @classmethod
    def recommendation_logic(cls, *, overall_score: float, relevance_score: float, pronunciation_score: float, fluency_score: float) -> dict:
        action = 'practice_more'
        recommendation = 'Practice again with more detail.'

        if relevance_score < 35:
            action = 'retry'
            recommendation = 'Stay closer to the prompt and answer the exact topic.'
        elif overall_score >= 8 and pronunciation_score >= 70 and fluency_score >= 70:
            action = 'next_prompt'
            recommendation = 'Move to the next prompt or a harder level.'
        elif overall_score >= 6:
            action = 'practice_more'
            recommendation = 'Good work. Practice one more answer on the same level.'
        elif pronunciation_score < 50:
            action = 'retry'
            recommendation = 'Retry and speak more clearly with better pacing.'

        return {
            'recommended_next_step': action,
            'recommendation_text': recommendation,
        }

    @classmethod
    def guardrail_off_topic_filter(cls, *, transcript: str, prompt_text: str, topic_title: str | None = None) -> dict:
        normalized = (transcript or '').strip().lower()
        tokens = cls._tokenize(normalized)
        prompt_tokens = set(cls._tokenize(' '.join(filter(None, [prompt_text, topic_title or '']))))
        token_set = set(tokens)
        overlap = token_set.intersection(prompt_tokens)

        repeated_char = bool(re.search(r"(.){5,}", normalized))
        repeated_word_ratio = 0.0
        if tokens:
            repeated_word_ratio = 1 - (len(token_set) / len(tokens))

        blocked = False
        reasons: list[str] = []
        if repeated_char:
            blocked = True
            reasons.append('Transcript looks noisy or repeated.')
        if len(tokens) >= 8 and len(overlap) == 0:
            blocked = True
            reasons.append('Answer appears off-topic.')
        if repeated_word_ratio > 0.72 and len(tokens) >= 10:
            blocked = True
            reasons.append('Too many repeated words.')

        return {
            'blocked': blocked,
            'reasons': reasons,
            'overlap_count': len(overlap),
            'repeated_word_ratio': round(repeated_word_ratio, 3),
        }

    @classmethod
    def build_enhanced_result(
        cls,
        *,
        transcript: str,
        prompt_text: str,
        topic_title: str | None = None,
        duration_seconds: int | None = None,
        base_evaluation: dict,
    ) -> dict:
        pronunciation = cls.pronunciation_analysis(
            transcript=transcript,
            prompt_text=prompt_text,
            duration_seconds=duration_seconds,
        )
        ai_eval = cls.ai_evaluation(transcript=transcript, prompt_text=prompt_text, topic_title=topic_title)
        recommendation = cls.recommendation_logic(
            overall_score=float(base_evaluation.get('score') or 0),
            relevance_score=float(base_evaluation.get('relevance_score') or 0),
            pronunciation_score=float(pronunciation.get('pronunciation_score') or 0),
            fluency_score=float(pronunciation.get('fluency_score') or 0),
        )
        guardrail = cls.guardrail_off_topic_filter(transcript=transcript, prompt_text=prompt_text, topic_title=topic_title)

        composite = (
            float(base_evaluation.get('score') or 0) * 10 * 0.46
            + float(pronunciation.get('pronunciation_score') or 0) * 0.18
            + float(pronunciation.get('fluency_score') or 0) * 0.18
            + float(ai_eval.get('ai_relevance_score') or 0) * 0.10
            + float(ai_eval.get('ai_structure_score') or 0) * 0.08
        ) / 10.0
        composite = round(max(0.0, min(10.0, composite)), 1)

        notes = []
        notes.extend(base_evaluation.get('feedback_items') or [])
        notes.extend(ai_eval.get('notes') or [])
        notes.extend(pronunciation.get('notes') or [])
        if guardrail.get('blocked'):
            notes.extend(guardrail.get('reasons') or [])
        notes.append(recommendation['recommendation_text'])

        enhanced = dict(base_evaluation)
        enhanced.update({
            'score': composite,
            'pronunciation_score': pronunciation.get('pronunciation_score'),
            'fluency_score': pronunciation.get('fluency_score'),
            'accent_confidence': pronunciation.get('accent_confidence'),
            'words_per_minute': pronunciation.get('words_per_minute'),
            'filler_count': pronunciation.get('filler_count'),
            'filler_ratio': pronunciation.get('filler_ratio'),
            'avg_sentence_length': pronunciation.get('avg_sentence_length'),
            'pacing_band': pronunciation.get('pacing_band'),
            'ai_relevance_score': ai_eval.get('ai_relevance_score'),
            'ai_structure_score': ai_eval.get('ai_structure_score'),
            'ai_idea_score': ai_eval.get('ai_idea_score'),
            'stt_provider': cls._provider_meta(SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_STT)),
            'evaluation_provider': ai_eval.get('provider'),
            'pronunciation_provider': pronunciation.get('provider'),
            'guardrail_blocked': guardrail.get('blocked'),
            'guardrail_reasons': guardrail.get('reasons'),
            'recommended_next_step': recommendation.get('recommended_next_step'),
            'recommendation_text': recommendation.get('recommendation_text'),
            'feedback_items': notes,
            'feedback_text': ' '.join(notes),
        })
        return enhanced
