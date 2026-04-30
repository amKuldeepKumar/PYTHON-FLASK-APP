from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .provider_registry import AICentralProviderRegistry
from .prompt_builder import AIPromptBuilder
from .request_logger import AIRequestLogger
from .router import AIProviderRouter
from .rule_service import AIRuleService
from .runtime_control import AIRuntimeControl
from ..ai_rule_logger import AIRuleLogger
from ..translation_engine import translate_text
from ..speaking.ai_enhancement_service import SpeakingAIEnhancementService
from ..speaking.evaluation_service import EvaluationService
from ..reading.provider_registry_service import ReadingProviderRegistryService
from ..reading.passage_generation_service import ReadingPassageGenerationService
from ..reading.question_generation_service import ReadingQuestionGenerationService
from ..reading.translation_service import ReadingTranslationService
from ..reading.answer_evaluation_service import ReadingAnswerEvaluationService
from ..writing.evaluation_service import evaluate_writing_submission


@dataclass
class AIExecutionResult:
    ok: bool
    task_key: str
    provider: dict[str, Any]
    prompt: str
    output: dict[str, Any] = field(default_factory=dict)
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'ok': self.ok,
            'task_key': self.task_key,
            'provider': self.provider,
            'prompt': self.prompt,
            'output': self.output,
            'message': self.message,
        }


class AIServiceLayer:
    @classmethod
    def execute(cls, task_key: str, payload: dict[str, Any] | None = None, *, context: dict[str, Any] | None = None) -> AIExecutionResult:
        payload = payload or {}
        context = context or {}
        merged = {**context, **payload}
        prompt = AIPromptBuilder.build(task_key, **merged)
        provider = AICentralProviderRegistry.default_provider_meta(task_key)
        track_key = AIRuleService.track_for_task(task_key)
        actor_user_id = AIRuntimeControl.actor_user_id(merged)
        request_id = AIRequestLogger.request_id()
        started = AIRequestLogger.start_timer()
        estimated_tokens = max(1, len(prompt.split()))
        guard_allowed, guard_reason = AIRuntimeControl.enforce_learning_scope(task_key, merged)
        if not guard_allowed:
            result = AIExecutionResult(False, task_key, provider, prompt, AIRuleService.apply_fallback_metadata({'decision': 'blocked'}, track_key, guard_reason), guard_reason)
            AIRequestLogger.log_request(request_id=request_id, task_key=task_key, provider=provider, prompt=prompt, response=result.output, ok=False, actor_user_id=actor_user_id, total_tokens=estimated_tokens, latency_ms=AIRequestLogger.elapsed_ms(started), error_code='guardrail_block', error_message=guard_reason, consent_snapshot=AIRuntimeControl.consent_for_user(actor_user_id))
            return result
        quota_decision = AIRuntimeControl.quota_check(task_key, user_id=actor_user_id, estimated_tokens=estimated_tokens, tts_characters=len((merged.get('text') or merged.get('prompt_text') or '')), speech_seconds=int(merged.get('duration_seconds') or 0))
        if not quota_decision.allowed:
            result = AIExecutionResult(False, task_key, provider, prompt, AIRuleService.apply_fallback_metadata({'decision': 'quota_block'}, track_key, quota_decision.reason), quota_decision.reason)
            AIRequestLogger.log_request(request_id=request_id, task_key=task_key, provider=provider, prompt=prompt, response=result.output, ok=False, actor_user_id=actor_user_id, total_tokens=estimated_tokens, latency_ms=AIRequestLogger.elapsed_ms(started), error_code='quota_block', error_message=quota_decision.reason, consent_snapshot=AIRuntimeControl.consent_for_user(actor_user_id))
            return result

        def _finalize(ok: bool, output: dict[str, Any] | None = None, message: str | None = None, *, provider_meta: dict[str, Any] | None = None) -> AIExecutionResult:
            final_output = AIRuleService.apply_fallback_metadata(output, track_key)
            selected_provider = provider_meta or provider
            AIRuleLogger.log({
                'task_key': task_key,
                'track_key': track_key,
                'ok': ok,
                'provider': selected_provider.get('label') if isinstance(selected_provider, dict) else selected_provider,
                'strictness': final_output.get('rule_metadata', {}).get('strictness'),
                'message': message,
            })
            total_tokens = max(1, len((prompt or '').split()) + len(str(final_output).split()))
            if ok:
                AIRuntimeControl.consume_quota(quota_decision.counter, task_key=task_key, total_tokens=total_tokens, tts_characters=len((merged.get('text') or merged.get('prompt_text') or '')), speech_seconds=int(merged.get('duration_seconds') or 0))
                if isinstance(selected_provider, dict):
                    AIProviderRouter.record_success(selected_provider.get('source'), selected_provider.get('id'))
            else:
                if isinstance(selected_provider, dict):
                    AIProviderRouter.record_failure(selected_provider.get('source'), selected_provider.get('id'), message)
            AIRequestLogger.log_request(request_id=request_id, task_key=task_key, provider=selected_provider, prompt=prompt, response=final_output, ok=ok, actor_user_id=actor_user_id, total_tokens=total_tokens, latency_ms=AIRequestLogger.elapsed_ms(started), estimated_cost=round(total_tokens * 0.0001, 6), cache_hit=bool(final_output.get('from_cache')), fallback_used=bool(selected_provider.get('fallback')) if isinstance(selected_provider, dict) else False, error_message=None if ok else message, consent_snapshot=AIRuntimeControl.consent_for_user(actor_user_id))
            return AIExecutionResult(ok, task_key, selected_provider, prompt, final_output, message)

        def _safe_call(fn):
            try:
                return fn()
            except Exception as exc:
                fallback_output = AIRuleService.apply_fallback_metadata({
                    'decision': 'fallback',
                    'reason': 'Safe fallback applied because the main AI flow failed.',
                }, track_key, str(exc))
                AIRuleLogger.log({
                    'task_key': task_key,
                    'track_key': track_key,
                    'ok': False,
                    'provider': provider.get('label') if isinstance(provider, dict) else provider,
                    'strictness': fallback_output.get('rule_metadata', {}).get('strictness'),
                    'message': str(exc),
                })
                return AIExecutionResult(False, task_key, provider, prompt, fallback_output, f'Safe fallback applied: {exc}')

        if task_key == 'translation':
            def _run_translation():
                from ..translation_engine import translate_text

                translated, from_cache = translate_text(
                    merged.get('source_text', ''),
                    merged.get('target_language_code', merged.get('target_language', 'en')),
                    source_lang=merged.get('source_language_code', 'en'),
                    context='ai_central',
                    actor_user_id=AIRuntimeControl.actor_user_id(merged),
                )
                return _finalize(True, {
                    'translated_text': translated,
                    'from_cache': from_cache,
                }, 'Central translation completed.')

            return _safe_call(_run_translation)

        if task_key == 'speaking_stt':
            return _safe_call(lambda: _finalize(True, SpeakingAIEnhancementService.transcribe_audio({'audio_original_name': merged.get('audio_name', 'sample.wav')}, merged.get('fallback_transcript')), 'Central speaking transcription completed.'))

        if task_key == 'speaking_pronunciation':
            return _safe_call(lambda: _finalize(True, SpeakingAIEnhancementService.pronunciation_analysis(
                transcript=(merged.get('transcript') or '').strip(),
                prompt_text=merged.get('prompt_text') or merged.get('topic') or '',
                duration_seconds=int(merged.get('duration_seconds') or 0),
            ), 'Central pronunciation analysis completed.'))

        if task_key == 'speaking_tts':
            def _run_tts():
                execution = ReadingProviderRegistryService.execute_task(
                    ReadingProviderRegistryService.KIND_TRANSLATION,
                    {'task': 'central tts preparation', 'prompt': prompt, **payload},
                )
                text = (merged.get('text') or merged.get('prompt_text') or 'Welcome to Fluencify.').strip()
                return _finalize(bool(execution.get('ok')), {
                    'voice_text': text,
                    'voice_hint': merged.get('voice_name') or 'Default voice',
                    'audio_status': 'ready_for_provider_generation',
                }, execution.get('message') or 'Central TTS preparation completed.', provider_meta=execution.get('provider') or provider)
            return _safe_call(_run_tts)

        if task_key == 'speaking_evaluation':
            def _run_speaking():
                transcript = (merged.get('transcript') or '').strip()
                duration_seconds = int(merged.get('duration_seconds') or 0)
                prompt_text = merged.get('prompt_text') or merged.get('topic') or ''
                quality = SpeakingAIEnhancementService.pronunciation_analysis(
                    transcript=transcript,
                    prompt_text=prompt_text,
                    duration_seconds=duration_seconds,
                )
                eval_row = EvaluationService.evaluate(transcript=transcript, prompt_text=prompt_text, duration_seconds=duration_seconds)
                return _finalize(True, {
                    'ai_metrics': quality,
                    'evaluation': eval_row,
                    'rule_track': 'speaking',
                }, 'Central speaking evaluation completed.')
            return _safe_call(_run_speaking)

        if task_key == 'reading_passage':
            def _run_reading_passage():
                topic_stub = type('TopicStub', (), {
                    'title': merged.get('topic', ''),
                    'description': merged.get('topic_description', ''),
                    'category': merged.get('topic_category', 'General'),
                    'level': merged.get('level', 'basic'),
                    'code': merged.get('topic_code', 'topic'),
                })()
                execution = ReadingProviderRegistryService.execute_task(ReadingProviderRegistryService.KIND_PASSAGE, {
                    'task': 'central passage generation',
                    'prompt': prompt,
                    **payload,
                })
                content = ReadingPassageGenerationService._build_mock_passage(
                    topic_stub,
                    merged.get('level', 'basic'),
                    merged.get('length_mode', merged.get('length', 'medium')),
                    merged.get('target_words'),
                )
                return _finalize(bool(execution.get('ok')), {
                    'title': ReadingPassageGenerationService._build_title(topic_stub.title, merged.get('level', 'basic'), merged.get('length_mode', merged.get('length', 'medium'))),
                    'content': content,
                }, execution.get('message'), provider_meta=execution.get('provider') or provider)
            return _safe_call(_run_reading_passage)

        if task_key == 'reading_question':
            def _run_reading_question():
                passage_text = merged.get('passage_content', '')
                sentences = ReadingQuestionGenerationService._sentence_bank(passage_text)
                output = {
                    'mcq': ReadingQuestionGenerationService._build_mcq(sentences, int(merged.get('mcq_count') or 0)),
                    'fill_blank': ReadingQuestionGenerationService._build_fill_blanks(sentences, int(merged.get('fill_blank_count') or 0)),
                    'true_false': ReadingQuestionGenerationService._build_true_false(sentences, int(merged.get('true_false_count') or 0)),
                }
                execution = ReadingProviderRegistryService.execute_task(ReadingProviderRegistryService.KIND_QUESTION, {'task': 'central question generation', 'prompt': prompt, **payload})
                return _finalize(bool(execution.get('ok')), output, execution.get('message'), provider_meta=execution.get('provider') or provider)
            return _safe_call(_run_reading_question)

        if task_key == 'reading_translation':
            def _run_reading_translation():
                result = ReadingTranslationService.translate_word(
                    merged.get('word', ''),
                    merged.get('sentence', ''),
                    merged.get('target_language', 'English'),
                    merged.get('target_language_code', 'en'),
                )
                return _finalize(result.ok, result.payload or {}, result.message)
            return _safe_call(_run_reading_translation)

        if task_key == 'reading_evaluation':
            def _run_reading_eval():
                result = ReadingAnswerEvaluationService.evaluate_answer(
                    merged.get('question_text', ''),
                    merged.get('student_answer', ''),
                    merged.get('correct_answer', ''),
                    merged.get('question_type', 'mcq'),
                )
                return _finalize(result.ok, {
                    'rule_track': 'reading',
                    'is_correct': result.is_correct,
                    'explanation': result.explanation,
                    'score': result.score,
                }, result.message)
            return _safe_call(_run_reading_eval)

        if task_key == 'writing_plagiarism':
            def _run_plagiarism():
                submission_text = (merged.get('submission_text') or '').strip()
                reference_text = (merged.get('reference_text') or '').strip()
                execution = ReadingProviderRegistryService.execute_task(
                    ReadingProviderRegistryService.KIND_PLAGIARISM,
                    {'task': 'central plagiarism detection', 'prompt': prompt, **payload},
                )
                overlap_seed = min(len(submission_text.split()), len(reference_text.split()))
                overlap_ratio = 0 if not submission_text or not reference_text else min(95, max(0, overlap_seed * 3))
                risk = 'high' if overlap_ratio >= 60 else ('medium' if overlap_ratio >= 25 else 'low')
                return _finalize(bool(execution.get('ok')), {
                    'overlap_percent': overlap_ratio,
                    'risk_level': risk,
                    'matched_spans': 0 if risk == 'low' else max(1, overlap_seed // 6),
                }, execution.get('message') or 'Central plagiarism review completed.', provider_meta=execution.get('provider') or provider)
            return _safe_call(_run_plagiarism)

        if task_key == 'writing_evaluation':
            def _run_writing():
                overall, feedback, summary, evaluation = evaluate_writing_submission(
                    merged.get('submission_text', ''),
                    merged.get('task'),
                    merged.get('topic'),
                )
                return _finalize(True, {
                    'rule_track': 'writing',
                    'overall_score': overall,
                    'feedback': feedback,
                    'summary': summary,
                    'evaluation': evaluation,
                }, 'Central writing evaluation completed.')
            return _safe_call(_run_writing)

        if task_key == 'listening_review':
            def _run_listening():
                caption_text = (merged.get('caption_text') or '').strip()
                prompt_text = (merged.get('prompt_text') or '').strip()
                decision = 'approved' if caption_text and prompt_text else 'pending'
                reason = 'Captions and prompt are both present.' if decision == 'approved' else 'Missing prompt or captions, keep in review.'
                return _finalize(True, {
                    'rule_track': 'listening',
                    'decision': decision,
                    'reason': reason,
                }, 'Central listening review completed.')
            return _safe_call(_run_listening)

        return _finalize(False, {}, 'Unsupported AI task key.')
