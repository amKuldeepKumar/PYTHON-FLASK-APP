from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ...extensions import db
from ...models.reading_passage import ReadingPassage
from ...models.reading_prompt_config import ReadingPromptConfig
from ...models.reading_question import ReadingQuestion
from .provider_registry_service import ReadingProviderRegistryService


@dataclass
class QuestionGenerationResult:
    ok: bool
    message: str
    questions: list[ReadingQuestion]
    provider_name: str | None = None


class ReadingQuestionGenerationService:
    STOPWORDS = {
        "the", "and", "for", "that", "with", "from", "this", "they", "have", "their", "about", "into",
        "when", "what", "where", "which", "there", "because", "while", "these", "those", "been", "will",
        "are", "was", "were", "has", "had", "its", "than", "them", "also", "such", "into", "still",
        "today", "only", "more", "most", "some", "many", "very", "does", "did", "keep", "keeps", "make",
    }

    @classmethod
    def generate_and_store(
        cls,
        passage: ReadingPassage,
        level: str,
        mcq_count: int,
        fill_blank_count: int,
        true_false_count: int,
        replace_existing: bool = False,
    ) -> QuestionGenerationResult:
        prompt = ReadingPromptConfig.query.filter_by(task_type=ReadingPromptConfig.TASK_QUESTION, is_active=True).first()
        prompt_text = prompt.prompt_text if prompt else "Generate reading questions from the passage."
        prompt_snapshot = cls._render_prompt(
            prompt_text,
            passage=passage,
            level=level,
            mcq_count=mcq_count,
            fill_blank_count=fill_blank_count,
            true_false_count=true_false_count,
        )

        execution = ReadingProviderRegistryService.execute_task(
            provider_kind=ReadingProviderRegistryService.KIND_QUESTION,
            payload={
                "task": "question generation",
                "passage_id": passage.id,
                "topic": passage.topic_title_snapshot,
                "level": level,
                "counts": {
                    "mcq": mcq_count,
                    "fill_blank": fill_blank_count,
                    "true_false": true_false_count,
                },
                "prompt": prompt_snapshot,
            },
        )
        if not execution.get("ok"):
            return QuestionGenerationResult(ok=False, message=execution.get("message") or "Question generation failed.", questions=[])

        provider_meta = execution.get("provider") or {}
        provider = ReadingProviderRegistryService.by_id(provider_meta.get("id")) if provider_meta.get("id") else None

        if replace_existing:
            ReadingQuestion.query.filter_by(passage_id=passage.id).delete(synchronize_session=False)
            db.session.flush()

        sentences = cls._sentence_bank(passage.content)
        if not sentences:
            return QuestionGenerationResult(ok=False, message="Passage is too short to generate questions.", questions=[])

        generated: list[ReadingQuestion] = []
        order = 1
        for payload in cls._build_mcq(sentences, mcq_count, level):
            generated.append(cls._make_question(passage, ReadingQuestion.TYPE_MCQ, level, order, prompt_snapshot, payload, provider))
            order += 1
        for payload in cls._build_fill_blanks(sentences, fill_blank_count, level):
            generated.append(cls._make_question(passage, ReadingQuestion.TYPE_FILL_BLANK, level, order, prompt_snapshot, payload, provider))
            order += 1
        for payload in cls._build_true_false(sentences, true_false_count, level):
            generated.append(cls._make_question(passage, ReadingQuestion.TYPE_TRUE_FALSE, level, order, prompt_snapshot, payload, provider))
            order += 1

        if not generated:
            return QuestionGenerationResult(ok=False, message="No questions could be generated from this passage.", questions=[])

        db.session.add_all(generated)
        db.session.commit()
        return QuestionGenerationResult(
            ok=True,
            message=f"Generated {len(generated)} reading questions successfully.",
            questions=generated,
            provider_name=provider_meta.get("name"),
        )

    @classmethod
    def _render_prompt(cls, template: str, passage: ReadingPassage, level: str, mcq_count: int, fill_blank_count: int, true_false_count: int) -> str:
        rendered = template.replace("{{level}}", (level or passage.level or "basic").title())
        rendered += f"\n\nPassage title: {passage.title}"
        rendered += f"\nTopic: {passage.topic_title_snapshot}"
        rendered += f"\nCounts: MCQ={mcq_count}, FillBlank={fill_blank_count}, TrueFalse={true_false_count}"
        rendered += f"\n\nPassage:\n{passage.content}"
        return rendered

    @classmethod
    def _make_question(cls, passage: ReadingPassage, question_type: str, level: str, order: int, prompt_snapshot: str, payload: dict, provider) -> ReadingQuestion:
        return ReadingQuestion(
            passage_id=passage.id,
            topic_id=passage.topic_id,
            question_type=question_type,
            level=level,
            display_order=order,
            prompt_snapshot=prompt_snapshot,
            question_text=payload["question_text"],
            options_json=json.dumps(payload.get("options") or [], ensure_ascii=False),
            correct_answer=payload.get("correct_answer"),
            explanation=payload.get("explanation"),
            source_sentence=payload.get("source_sentence"),
            provider_id=provider.id if provider else None,
            provider_name_snapshot=provider.name if provider else None,
            status=ReadingQuestion.STATUS_DRAFT,
            is_active=True,
        )

    @classmethod
    def _sentence_bank(cls, content: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", content or "")
        cleaned = [re.sub(r"\s+", " ", part).strip() for part in parts]
        return [part for part in cleaned if len(part.split()) >= 6]

    @classmethod
    def _sentences_for_level(cls, sentences: list[str], level: str) -> list[str]:
        if level == 'advanced':
            ordered = sorted(sentences, key=lambda row: (-len(row.split()), row))
        elif level == 'intermediate':
            ordered = sorted(sentences, key=lambda row: (abs(len(row.split()) - 14), row))
        else:
            ordered = sorted(sentences, key=lambda row: (len(row.split()), row))
        return ordered

    @classmethod
    def _keywords(cls, sentence: str) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z\-']+", sentence)
        unique: list[str] = []
        seen: set[str] = set()
        for word in words:
            clean = word.strip(".,!?;:'\"()[]{}").lower()
            if len(clean) < 5 or clean in cls.STOPWORDS or clean in seen:
                continue
            seen.add(clean)
            unique.append(word.strip(".,!?;:'\"()[]{}"))
        return unique

    @classmethod
    def _build_mcq(cls, sentences: list[str], count: int, level: str) -> list[dict]:
        rows: list[dict] = []
        for sentence in cls._sentences_for_level(sentences, level):
            if len(rows) >= count:
                break
            keywords = cls._keywords(sentence)
            if not keywords:
                continue
            answer = keywords[0]
            distractors = [word for word in keywords[1:4] if word.lower() != answer.lower()]
            while len(distractors) < 3:
                distractors.append(f"Option {len(distractors) + 2}")
            rows.append({
                "question_text": f"According to the passage, which word best completes this idea? — {sentence.replace(answer, '_____', 1)}",
                "options": [answer] + distractors[:3],
                "correct_answer": answer,
                "explanation": f"Look back at the original sentence. The exact word used in the passage is '{answer}'.",
                "source_sentence": sentence,
            })
        return rows

    @classmethod
    def _build_fill_blanks(cls, sentences: list[str], count: int, level: str) -> list[dict]:
        rows: list[dict] = []
        for sentence in cls._sentences_for_level(sentences, level):
            if len(rows) >= count:
                break
            keywords = cls._keywords(sentence)
            if not keywords:
                continue
            answer = keywords[-1]
            question_text = sentence.replace(answer, "_____", 1)
            if question_text == sentence:
                continue
            rows.append({
                "question_text": question_text,
                "options": [],
                "correct_answer": answer,
                "explanation": f"Re-read the source sentence and restore the missing word '{answer}' from context.",
                "source_sentence": sentence,
            })
        return rows

    @classmethod
    def _build_true_false(cls, sentences: list[str], count: int, level: str) -> list[dict]:
        rows: list[dict] = []
        for index, sentence in enumerate(cls._sentences_for_level(sentences, level)):
            if len(rows) >= count:
                break
            if index % 2 == 0:
                question_text = sentence
                correct_answer = "True"
                explanation = "This statement matches the passage sentence exactly."
            else:
                words = sentence.split()
                if len(words) >= 6:
                    words[-2] = "not"
                question_text = " ".join(words)
                if question_text == sentence:
                    question_text = f"This statement is not supported by the passage: {sentence}"
                correct_answer = "False"
                explanation = "This statement changes a key detail from the original sentence, so it is false."
            rows.append({
                "question_text": question_text,
                "options": ["True", "False"],
                "correct_answer": correct_answer,
                "explanation": explanation,
                "source_sentence": sentence,
            })
        return rows
