from __future__ import annotations

import json

from datetime import datetime

from sqlalchemy import case, func

from ...extensions import db
from ...models.speaking_prompt import SpeakingPrompt
from ...models.speaking_session import SpeakingSession
from ...models.speaking_topic import SpeakingTopic
from .attempt_service import AttemptService
from .ai_enhancement_service import SpeakingAIEnhancementService
from .evaluation_service import EvaluationService
from .guardrail_service import GuardrailService
from .motivation_service import MotivationService
from ..interview.interview_evaluation_service import InterviewEvaluationService


class SpeakingSessionService:
    NO_REPEAT_RECENT_COUNT = 5

    @staticmethod
    def _is_interview_prompt(prompt: SpeakingPrompt | None) -> bool:
        if not prompt:
            return False
        if bool(getattr(prompt, 'is_interview_prompt', False)):
            return True
        topic = getattr(prompt, 'topic', None)
        course = getattr(topic, 'course', None) if topic else None
        track = (getattr(course, 'track_type', '') or '').strip().lower()
        return track == 'interview'

    @staticmethod
    def select_prompt(
        owner_admin_id: int | None,
        *,
        topic_id: int | None = None,
        student_id: int | None = None,
        course_id: int | None = None,
    ) -> SpeakingPrompt | None:
        query = SpeakingPrompt.query.join(
            SpeakingTopic,
            SpeakingTopic.id == SpeakingPrompt.topic_id,
        ).filter(
            SpeakingPrompt.is_active.is_(True),
            SpeakingTopic.is_active.is_(True),
            SpeakingTopic.is_published.is_(True),
        )

        if owner_admin_id is None:
            query = query.filter(
                SpeakingPrompt.owner_admin_id.is_(None),
                SpeakingTopic.owner_admin_id.is_(None),
            )
        else:
            query = query.filter(
                (SpeakingPrompt.owner_admin_id == owner_admin_id) | (SpeakingPrompt.owner_admin_id.is_(None)),
                (SpeakingTopic.owner_admin_id == owner_admin_id) | (SpeakingTopic.owner_admin_id.is_(None)),
            )

        if topic_id:
            query = query.filter(SpeakingPrompt.topic_id == topic_id)
            query = query.filter(SpeakingPrompt.is_active.is_(True))
        if course_id is not None:
            query = query.filter(SpeakingTopic.course_id == course_id)

        excluded_prompt_ids: list[int] = []
        if student_id is not None:
            recent_query = (
                db.session.query(SpeakingSession.prompt_id)
                .filter(
                    SpeakingSession.student_id == student_id,
                    SpeakingSession.status == SpeakingSession.STATUS_COMPLETED,
                )
            )
            if course_id is not None:
                recent_query = recent_query.filter(SpeakingSession.course_id == course_id)
            excluded_prompt_ids = [
                row[0]
                for row in (
                    recent_query
                    .order_by(
                        case((SpeakingSession.last_submitted_at.is_(None), 1), else_=0).asc(),
                        SpeakingSession.last_submitted_at.desc(),
                        SpeakingSession.id.desc(),
                    )
                    .limit(SpeakingSessionService.NO_REPEAT_RECENT_COUNT)
                    .all()
                )
                if row[0]
            ]

        if excluded_prompt_ids:
            candidate = query.filter(~SpeakingPrompt.id.in_(excluded_prompt_ids)).order_by(func.random()).first()
            if candidate:
                return candidate

        return query.order_by(func.random()).first()


    @staticmethod
    def ensure_prompt_for_topic(topic: SpeakingTopic, owner_admin_id: int | None = None) -> SpeakingPrompt:
        existing = (
            topic.prompts
            .filter_by(is_active=True)
            .order_by(SpeakingPrompt.display_order.asc(), SpeakingPrompt.id.asc())
            .first()
        )
        if existing:
            return existing

        title = (getattr(topic, "title", None) or "Speaking Practice").strip()
        prompt = SpeakingPrompt(
            owner_admin_id=owner_admin_id if owner_admin_id is not None else getattr(topic, 'owner_admin_id', None),
            topic_id=topic.id,
            title=f"{title} speaking prompt",
            prompt_text=(
                f"Speak about {title}. Share your ideas in a clear introduction, "
                "2 to 3 supporting points, one example, and a short conclusion."
            ),
            instruction_text=(
                "Stay on topic, speak naturally, and explain your ideas clearly. "
                "The system will capture your voice, convert it to text, and then evaluate your answer."
            ),
            difficulty=(getattr(topic, 'level', None) or 'basic'),
            estimated_seconds=60,
            target_duration_seconds=60,
            min_duration_seconds=30,
            max_duration_seconds=90,
            display_order=0,
            is_active=True,
        )
        db.session.add(prompt)
        db.session.commit()
        return prompt

    @staticmethod
    def start_session(*, student_id: int, owner_admin_id: int | None, prompt: SpeakingPrompt) -> SpeakingSession:
        session = SpeakingSession(
            owner_admin_id=owner_admin_id,
            student_id=student_id,
            topic_id=prompt.topic_id,
            prompt_id=prompt.id,
            course_id=getattr(prompt.topic, 'course_id', None),
            status=SpeakingSession.STATUS_IN_PROGRESS,
            duration_seconds=0,
            started_at=datetime.utcnow(),
            submitted_from='web',
            max_retry_count=2,
        )
        db.session.add(session)
        db.session.commit()
        return session


    @staticmethod
    def get_resumable_session(student_id: int, *, topic_id: int | None = None, course_id: int | None = None) -> SpeakingSession | None:
        query = SpeakingSession.query.filter(
            SpeakingSession.student_id == student_id,
            SpeakingSession.status.in_([SpeakingSession.STATUS_READY, SpeakingSession.STATUS_IN_PROGRESS]),
        )
        if topic_id is not None:
            query = query.filter(SpeakingSession.topic_id == topic_id)
        if course_id is not None:
            query = query.filter(SpeakingSession.course_id == course_id)
        return query.order_by(SpeakingSession.updated_at.desc(), SpeakingSession.id.desc()).first()

    @staticmethod
    def get_student_session(student_id: int, session_id: int) -> SpeakingSession | None:
        return SpeakingSession.query.filter_by(id=session_id, student_id=student_id).first()

    @staticmethod
    def recent_sessions_for_student(student_id: int, *, limit: int = 5, course_id: int | None = None) -> list[SpeakingSession]:
        query = SpeakingSession.query.filter_by(student_id=student_id)
        if course_id is not None:
            query = query.filter(SpeakingSession.course_id == course_id)
        return (
            query
            .order_by(SpeakingSession.created_at.desc(), SpeakingSession.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def attempts_for_session(session: SpeakingSession):
        return session.attempts.all()

    @staticmethod
    def submit_session(
        session: SpeakingSession,
        *,
        transcript_text: str,
        duration_seconds: int,
        audio_file=None,
        submitted_from: str = 'web',
        browser_stt_used: bool = False,
    ) -> dict:
        normalized = GuardrailService.normalize_transcript(transcript_text)
        audio_meta = AttemptService.save_audio(audio_file)

        if not normalized and audio_meta.get('audio_file_path'):
            stt_result = SpeakingAIEnhancementService.transcribe_audio(audio_meta, fallback_transcript=None)
            normalized = GuardrailService.normalize_transcript(stt_result.get('text'))
        else:
            stt_result = SpeakingAIEnhancementService.transcribe_audio(audio_meta, fallback_transcript=normalized)

        transcript_source = stt_result.get('source') or 'manual'
        if browser_stt_used and normalized:
            transcript_source = 'browser_stt'
        elif normalized and audio_meta.get('audio_file_path') and transcript_source == 'manual':
            transcript_source = 'manual_plus_audio'

        allowed, validation_message = GuardrailService.validate_transcript(normalized)
        if not allowed:
            raise ValueError(validation_message or 'Please enter a longer transcript before submitting.')

        duration_seconds = max(0, int(duration_seconds or 0))
        min_allowed = int(getattr(session.prompt, 'effective_min_duration', 0) or 0)
        max_allowed = int(getattr(session.prompt, 'effective_max_duration', 0) or 0)
        target_allowed = int(getattr(session.prompt, 'effective_target_duration', 0) or 0)
        if min_allowed and duration_seconds < min_allowed:
            raise ValueError(f'Speak for at least {min_allowed} seconds before submitting this prompt.')
        if max_allowed and duration_seconds > max_allowed:
            raise ValueError(f'This prompt allows up to {max_allowed} seconds. Please keep your answer within the speaking limit.')

        speed_check = MotivationService.validate_submission_speed(
            session,
            transcript_text=normalized,
            duration_seconds=duration_seconds,
            has_audio=bool(audio_meta.get('audio_file_path')),
        )
        if not speed_check.get('allowed'):
            MotivationService.track_fast_submit_flag(session, speed_check.get('reason') or 'Fast submit blocked')
            db.session.commit()
            raise ValueError(speed_check.get('reason') or 'Submission was too fast.')

        retries_left = max(0, int(session.max_retry_count or 0) - int(session.retry_count or 0))
        evaluation = EvaluationService.evaluate(
            transcript=normalized,
            prompt_text=session.prompt.prompt_text,
            instruction_text=getattr(session.prompt, 'instruction_text', None),
            topic_title=getattr(session.topic, 'title', None),
            estimated_seconds=session.prompt.estimated_seconds,
            retries_left=retries_left,
            duration_seconds=duration_seconds,
        )
        evaluation = SpeakingAIEnhancementService.build_enhanced_result(
            transcript=normalized,
            prompt_text=session.prompt.prompt_text,
            topic_title=getattr(session.topic, 'title', None),
            duration_seconds=duration_seconds,
            base_evaluation=evaluation,
        )
        if evaluation.get('guardrail_blocked'):
            raise ValueError(' '.join(evaluation.get('guardrail_reasons') or ['Answer blocked by speaking guardrail.']))
        attempt = AttemptService.create_attempt(
            session=session,
            transcript_text=normalized,
            duration_seconds=duration_seconds,
            evaluation=evaluation,
            audio_meta=audio_meta,
            transcript_source=transcript_source,
        )

        session.duration_seconds = max(0, int(duration_seconds or 0))
        session.submitted_from = submitted_from or 'web'
        session.transcript_text = normalized
        session.transcript_source = transcript_source
        session.audio_file_path = audio_meta.get('audio_file_path') or session.audio_file_path
        session.audio_original_name = audio_meta.get('audio_original_name') or session.audio_original_name
        session.latest_word_count = int(evaluation.get('word_count') or 0)
        session.latest_char_count = int(evaluation.get('char_count') or 0)
        session.submit_count = int(session.submit_count or 0) + 1
        session.result_summary = evaluation.get('feedback_text')
        session.last_submitted_at = datetime.utcnow()
        session.ended_at = datetime.utcnow()
        session.status = SpeakingSession.STATUS_COMPLETED
        session.evaluation_score = float(evaluation.get('score') or 0)
        session.relevance_score = float(evaluation.get('relevance_score') or 0)
        session.is_relevant = bool(evaluation.get('is_relevant'))
        session.feedback_text = evaluation.get('feedback_text')
        session.evaluation_json = json.dumps(evaluation, ensure_ascii=False)
        session.recommended_next_step = evaluation.get('recommended_next_step')
        if session.submit_count > 1:
            session.retry_count = int(session.submit_count - 1)
        motivation = MotivationService.award_for_completed_session(session)
        db.session.commit()
        return {
            'session': session,
            'attempt': attempt,
            'evaluation': evaluation,
            'motivation': motivation,
            'retries_left_after_submit': max(0, int(session.max_retry_count or 0) - int(session.retry_count or 0)),
        }

    @staticmethod
    def reopen_for_retry(session: SpeakingSession) -> SpeakingSession:
        if not session.can_retry:
            raise ValueError('Retry limit reached for this speaking session.')
        session.status = SpeakingSession.STATUS_IN_PROGRESS
        session.recommended_next_step = 'retry'
        session.ended_at = None
        db.session.commit()
        return session
