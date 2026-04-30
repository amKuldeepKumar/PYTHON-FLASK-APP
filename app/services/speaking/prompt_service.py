from __future__ import annotations

from sqlalchemy import func, or_

from ...extensions import db
from ...models.speaking_prompt import SpeakingPrompt
from ...models.speaking_topic import SpeakingTopic


class PromptService:
    @staticmethod
    def _owner_topic_filter(owner_admin_id: int | None):
        if owner_admin_id is None:
            return SpeakingTopic.owner_admin_id.is_(None)
        return or_(
            SpeakingTopic.owner_admin_id == owner_admin_id,
            SpeakingTopic.owner_admin_id.is_(None),
        )

    @staticmethod
    def _owner_prompt_filter(owner_admin_id: int | None):
        if owner_admin_id is None:
            return SpeakingPrompt.owner_admin_id.is_(None)
        return or_(
            SpeakingPrompt.owner_admin_id == owner_admin_id,
            SpeakingPrompt.owner_admin_id.is_(None),
        )

    @staticmethod
    def list_topics(owner_admin_id: int | None, *, active_only: bool = False) -> list[SpeakingTopic]:
        query = SpeakingTopic.query.filter(PromptService._owner_topic_filter(owner_admin_id))
        if active_only:
            query = query.filter(
                SpeakingTopic.is_active.is_(True),
                SpeakingTopic.is_published.is_(True),
            )
        return query.order_by(
            SpeakingTopic.display_order.asc(),
            SpeakingTopic.title.asc(),
        ).all()

    @staticmethod
    def list_student_visible_topics(owner_admin_id: int | None, *, course_id: int | None = None) -> list[SpeakingTopic]:
        """
        Show active + published topics on the student dashboard even if prompts are not
        created yet, so the library is visible. Starting a topic still requires at least
        one active prompt.
        """
        query = (
            SpeakingTopic.query
            .filter(
                PromptService._owner_topic_filter(owner_admin_id),
                SpeakingTopic.is_active.is_(True),
                SpeakingTopic.is_published.is_(True),
            )
        )
        if course_id:
            query = query.filter(SpeakingTopic.course_id == course_id)
        return query.order_by(SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc()).all()

    @staticmethod
    def create_topic(
        *,
        owner_admin_id: int | None,
        code: str,
        title: str,
        description: str | None,
        level: str,
        display_order: int = 0,
        is_active: bool = True,
        is_published: bool = True,
    ) -> SpeakingTopic:
        normalized_code = (code or "").strip().lower().replace(" ", "-")
        title = (title or "").strip()

        if not normalized_code:
            raise ValueError("Topic code is required.")
        if not title:
            raise ValueError("Topic title is required.")

        query = SpeakingTopic.query.filter_by(code=normalized_code)
        if owner_admin_id is None:
            query = query.filter(SpeakingTopic.owner_admin_id.is_(None))
        else:
            query = query.filter_by(owner_admin_id=owner_admin_id)

        exists = query.first()
        if exists:
            raise ValueError("A speaking topic with this code already exists.")

        topic = SpeakingTopic(
            owner_admin_id=owner_admin_id,
            code=normalized_code,
            title=title,
            description=(description or "").strip() or None,
            level=(level or "basic").strip().lower(),
            display_order=max(0, int(display_order or 0)),
            is_active=bool(is_active),
            is_published=bool(is_published),
        )
        db.session.add(topic)
        db.session.commit()
        return topic

    @staticmethod
    def toggle_topic(topic: SpeakingTopic) -> SpeakingTopic:
        topic.is_active = not bool(topic.is_active)
        db.session.commit()
        return topic

    @staticmethod
    def list_prompts(
        owner_admin_id: int | None,
        *,
        topic_id: int | None = None,
        active_only: bool = False,
    ) -> list[SpeakingPrompt]:
        query = SpeakingPrompt.query.join(SpeakingTopic, SpeakingTopic.id == SpeakingPrompt.topic_id).filter(
            PromptService._owner_prompt_filter(owner_admin_id),
            PromptService._owner_topic_filter(owner_admin_id),
        )

        if topic_id:
            query = query.filter(SpeakingPrompt.topic_id == topic_id)

        if active_only:
            query = query.filter(
                SpeakingPrompt.is_active.is_(True),
                SpeakingTopic.is_active.is_(True),
                SpeakingTopic.is_published.is_(True),
            )

        return query.order_by(
            SpeakingTopic.display_order.asc(),
            SpeakingPrompt.display_order.asc(),
            SpeakingPrompt.title.asc(),
        ).all()

    @staticmethod
    def create_prompt(
        *,
        owner_admin_id: int | None,
        topic: SpeakingTopic,
        title: str,
        prompt_text: str,
        instruction_text: str | None,
        difficulty: str,
        estimated_seconds: int = 60,
        display_order: int = 0,
        is_active: bool = True,
    ) -> SpeakingPrompt:
        title = (title or "").strip()
        prompt_text = (prompt_text or "").strip()
        if not title:
            raise ValueError("Prompt title is required.")
        if not prompt_text:
            raise ValueError("Prompt text is required.")

        prompt = SpeakingPrompt(
            owner_admin_id=owner_admin_id,
            topic_id=topic.id,
            title=title,
            prompt_text=prompt_text,
            instruction_text=(instruction_text or "").strip() or None,
            difficulty=(difficulty or "basic").strip().lower(),
            estimated_seconds=max(15, int(estimated_seconds or 60)),
            display_order=max(0, int(display_order or 0)),
            is_active=bool(is_active),
        )
        db.session.add(prompt)
        db.session.commit()
        return prompt

    @staticmethod
    def toggle_prompt(prompt: SpeakingPrompt) -> SpeakingPrompt:
        prompt.is_active = not bool(prompt.is_active)
        db.session.commit()
        return prompt
