from __future__ import annotations

from dataclasses import dataclass

from ...models.reading_prompt_config import ReadingPromptConfig
from .provider_adapter_service import ReadingProviderAdapterService
from .provider_registry_service import ReadingProviderRegistryService


@dataclass
class ReadingAnswerEvaluationResult:
    ok: bool
    message: str
    is_correct: bool | None = None
    reason: str | None = None
    confidence: float | None = None
    provider_name: str | None = None
    payload: dict | None = None


class ReadingAnswerEvaluationService:
    @classmethod
    def evaluate_answer(cls, question_text: str, expected_answer: str, learner_answer: str, passage_text: str = "") -> ReadingAnswerEvaluationResult:
        prompt = ReadingPromptConfig.query.filter_by(task_type=ReadingPromptConfig.TASK_EVALUATION, is_active=True).first()
        prompt_text = prompt.prompt_text if prompt else "Evaluate learner answer."
        prompt_snapshot = (
            prompt_text
            + f"\n\nQuestion: {question_text.strip()}"
            + f"\nExpected answer: {expected_answer.strip()}"
            + f"\nLearner answer: {learner_answer.strip()}"
            + (f"\nPassage: {passage_text.strip()}" if passage_text.strip() else "")
            + "\nReturn JSON with keys: is_correct, reason, confidence."
        )
        execution = ReadingProviderRegistryService.execute_task(
            provider_kind=ReadingProviderRegistryService.KIND_EVALUATION,
            payload={
                "task": "answer evaluation",
                "question_text": question_text,
                "expected_answer": expected_answer,
                "learner_answer": learner_answer,
                "passage_text": passage_text,
                "prompt": prompt_snapshot,
            },
        )
        if not execution.get("ok"):
            return ReadingAnswerEvaluationResult(ok=False, message=execution.get("message") or "Evaluation failed.")
        provider = execution.get("provider") or {}
        text = ((execution.get("response") or {}).get("text") or "").strip()
        parsed = ReadingProviderAdapterService.parse_text_or_json(text)
        if isinstance(parsed, dict):
            is_correct = parsed.get("is_correct")
            if isinstance(is_correct, str):
                is_correct = is_correct.strip().lower() in {"true", "yes", "1", "correct"}
            confidence = parsed.get("confidence")
            try:
                confidence = float(confidence) if confidence is not None else None
            except Exception:
                confidence = None
            return ReadingAnswerEvaluationResult(
                ok=True,
                message=execution.get("message") or "Evaluation completed.",
                is_correct=is_correct if isinstance(is_correct, bool) else None,
                reason=(parsed.get("reason") or "").strip() or None,
                confidence=confidence,
                provider_name=provider.get("name"),
                payload=parsed,
            )
        return ReadingAnswerEvaluationResult(ok=True, message=execution.get("message") or "Evaluation completed.", provider_name=provider.get("name"), payload={"raw": text})
