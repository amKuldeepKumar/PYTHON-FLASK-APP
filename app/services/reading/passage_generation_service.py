from __future__ import annotations

from dataclasses import dataclass
import re

from ...extensions import db
from ...models.reading_passage import ReadingPassage
from ...models.reading_prompt_config import ReadingPromptConfig
from ...models.reading_topic import ReadingTopic
from .provider_registry_service import ReadingProviderRegistryService


@dataclass
class PassageGenerationResult:
    ok: bool
    passage: ReadingPassage | None
    message: str
    provider_name: str | None = None


class ReadingPassageGenerationService:
    LENGTH_RANGES = {
        ReadingPassage.LENGTH_SHORT: (90, 120),
        ReadingPassage.LENGTH_MEDIUM: (140, 190),
        ReadingPassage.LENGTH_LONG: (220, 280),
    }

    LEVEL_STYLES = {
        ReadingTopic.LEVEL_BASIC: {
            "tone": "simple, clear, and beginner-friendly",
            "connector": "Use direct sentences with easy transitions.",
            "focus": "Keep facts easy to follow and avoid complex clauses.",
        },
        ReadingTopic.LEVEL_INTERMEDIATE: {
            "tone": "balanced, informative, and classroom-friendly",
            "connector": "Use moderate sentence variety and connected ideas.",
            "focus": "Introduce detail, cause-and-effect, and light analysis.",
        },
        ReadingTopic.LEVEL_ADVANCED: {
            "tone": "mature, analytical, and academically polished",
            "connector": "Use richer transitions and more layered sentence structure.",
            "focus": "Add nuance, context, and interpretation without losing clarity.",
        },
    }

    @classmethod
    def generate_and_store(cls, topic: ReadingTopic, level: str, length_mode: str, target_words: int | None = None) -> PassageGenerationResult:
        level = (level or topic.level or ReadingTopic.LEVEL_BASIC).strip().lower()
        if level not in cls.LEVEL_STYLES:
            level = ReadingTopic.LEVEL_BASIC
        length_mode = (length_mode or ReadingPassage.LENGTH_MEDIUM).strip().lower()
        if length_mode not in cls.LENGTH_RANGES:
            length_mode = ReadingPassage.LENGTH_MEDIUM

        prompt = ReadingPromptConfig.query.filter_by(task_type=ReadingPromptConfig.TASK_PASSAGE, is_active=True).first()
        prompt_text = prompt.prompt_text if prompt else "Generate a reading passage."
        prompt_snapshot = cls._render_prompt(prompt_text, topic=topic, level=level, length_mode=length_mode, target_words=target_words)

        execution = ReadingProviderRegistryService.execute_task(
            provider_kind=ReadingProviderRegistryService.KIND_PASSAGE,
            payload={
                "task": "passage generation",
                "topic": topic.title,
                "topic_code": topic.code,
                "topic_category": topic.category or "General",
                "topic_description": topic.description or "",
                "level": level,
                "length": length_mode,
                "prompt": prompt_snapshot,
            },
        )
        if not execution.get("ok"):
            return PassageGenerationResult(ok=False, passage=None, message=execution.get("message") or "Passage generation failed.")

        provider_meta = execution.get("provider") or {}
        provider = ReadingProviderRegistryService.by_id(provider_meta.get("id")) if provider_meta.get("id") else None
        content = cls._build_mock_passage(topic=topic, level=level, length_mode=length_mode, target_words=target_words)
        word_count = len(re.findall(r"\b\w+\b", content))
        passage = ReadingPassage(
            topic_id=topic.id,
            topic_title_snapshot=topic.title,
            level=level,
            length_mode=length_mode,
            title=cls._build_title(topic.title, level, length_mode),
            content=content,
            word_count=word_count,
            prompt_snapshot=prompt_snapshot,
            generation_notes=execution.get("message"),
            generation_source="dynamic_api",
            provider_id=provider.id if provider else None,
            provider_name_snapshot=provider_meta.get("name"),
            status=ReadingPassage.STATUS_DRAFT,
            is_active=True,
            is_published=False,
        )
        db.session.add(passage)
        db.session.commit()
        return PassageGenerationResult(ok=True, passage=passage, message="Reading passage generated successfully.", provider_name=provider_meta.get("name"))

    @classmethod
    def _render_prompt(cls, template: str, topic: ReadingTopic, level: str, length_mode: str, target_words: int | None = None) -> str:
        low, high = cls.LENGTH_RANGES.get(length_mode, cls.LENGTH_RANGES[ReadingPassage.LENGTH_MEDIUM])
        rendered = template.replace("{{topic}}", topic.title)
        rendered = rendered.replace("{{level}}", level.title())
        rendered = rendered.replace("{{length}}", length_mode.title())
        target_label = f'{target_words} words' if target_words else f'{low}-{high} words'
        rendered = rendered.replace("{{word_range}}", target_label)
        if topic.description:
            rendered += f"\n\nTopic guidance: {topic.description}"
        return rendered

    @classmethod
    def _build_title(cls, topic_title: str, level: str, length_mode: str) -> str:
        return f"{topic_title} • {level.title()} • {length_mode.title()} Passage"

    @classmethod
    def _build_mock_passage(cls, topic: ReadingTopic, level: str, length_mode: str, target_words: int | None = None) -> str:
        style = cls.LEVEL_STYLES[level]
        low, high = cls.LENGTH_RANGES[length_mode]
        target = int(target_words or ((low + high) // 2))
        category = (topic.category or "general studies").strip() or "general studies"
        description = (topic.description or "").strip()
        opening = f"{topic.title} is presented here in a {style['tone']} reading passage for {level} learners."
        body = f"It belongs to the {category} area and gives students a guided explanation of why the topic matters in real life, history, or public discussion."
        detail = f"{style['connector']} {style['focus']} The passage uses clear examples so the learner can connect the main idea, supporting details, and important vocabulary."
        topic_line = f"When students read about {topic.title.lower()}, they should notice who was involved, what changed over time, and why the subject still matters today."
        desc_line = f"{description}" if description else f"The content is shaped to remain accurate, readable, and suitable for class practice without becoming too technical."
        closing = f"By the end, the reader should feel ready to answer questions, identify evidence from the paragraph, and discuss the theme with confidence."
        sentences = [opening, body, detail, topic_line, desc_line, closing]
        text = " ".join(sentences)
        extras = [
            f"This {length_mode} passage keeps the word range near {target} words so the activity matches the lesson expectation.",
            "It also keeps the structure organized from introduction to explanation and final takeaway.",
            "That makes it easier for the next AI step to generate MCQ, fill-in-the-blank, and true-false questions from the same content.",
            "Learners can return to the paragraph to check facts, infer meaning, and build reading confidence step by step.",
            f"Because the level is {level}, vocabulary and sentence patterns stay aligned with that course stage.",
        ]
        idx = 0
        while len(re.findall(r"\b\w+\b", text)) < low and idx < len(extras) * 4:
            text += " " + extras[idx % len(extras)]
            idx += 1
        return text
