from __future__ import annotations

from datetime import datetime

from ...extensions import db
from ...models.student_daily_activity import StudentDailyActivity
from ...models.student_reward_transaction import StudentRewardTransaction
from ...models.user import User
from ..economy_service import EconomyService
from ..student_activity_service import StudentActivityService


class MotivationService:
    @staticmethod
    def _effective_seconds(session, submitted_duration_seconds: int) -> int:
        effective = max(0, int(submitted_duration_seconds or 0))
        started_at = getattr(session, "started_at", None)
        if started_at:
            elapsed = int(max(0, (datetime.utcnow() - started_at).total_seconds()))
            effective = max(effective, elapsed)
        return effective

    @staticmethod
    def validate_submission_speed(session, *, transcript_text: str, duration_seconds: int, has_audio: bool = False) -> dict:
        words = len([part for part in (transcript_text or '').split() if part.strip()])
        effective_seconds = MotivationService._effective_seconds(session, duration_seconds)
        estimated_seconds = int(getattr(getattr(session, 'prompt', None), 'estimated_seconds', 0) or 0)
        min_seconds = max(8, min(30, int(round((estimated_seconds or 40) * 0.30))))

        if effective_seconds < 4:
            return {
                'allowed': False,
                'effective_seconds': effective_seconds,
                'min_seconds': min_seconds,
                'reason': 'Submission was too fast. Please speak for a little longer before submitting.',
            }

        if words >= 12 and effective_seconds < min_seconds:
            return {
                'allowed': False,
                'effective_seconds': effective_seconds,
                'min_seconds': min_seconds,
                'reason': f'Too fast to evaluate fairly. Please spend at least {min_seconds} seconds on this prompt before submitting.',
            }

        if words >= 25 and effective_seconds < max(10, min_seconds):
            return {
                'allowed': False,
                'effective_seconds': effective_seconds,
                'min_seconds': max(10, min_seconds),
                'reason': 'Your answer looks longer than the recorded speaking time. Please retry and speak naturally.',
            }

        if has_audio and effective_seconds >= 4:
            return {
                'allowed': True,
                'effective_seconds': effective_seconds,
                'min_seconds': min_seconds,
                'reason': None,
            }

        return {
            'allowed': True,
            'effective_seconds': effective_seconds,
            'min_seconds': min_seconds,
            'reason': None,
        }

    @staticmethod
    def award_for_completed_session(session) -> dict:
        if bool(getattr(session, 'completion_tracked', False)):
            return {
                'awarded': False,
                'coins_awarded': int(getattr(session, 'coins_awarded', 0) or 0),
                'streak': StudentActivityService.active_streak(session.student_id),
            }

        student = User.query.get(session.student_id)
        if not student:
            return {'awarded': False, 'coins_awarded': 0, 'streak': 0}

        day_row = StudentActivityService.get_or_create(session.student_id)
        day_row.speaking_completed_sessions = int(day_row.speaking_completed_sessions or 0) + 1
        day_row.speaking_attempts = int(day_row.speaking_attempts or 0) + 1
        session_minutes = max(1, round(int(getattr(session, 'duration_seconds', 0) or 0) / 60))
        day_row.practice_minutes = int(day_row.practice_minutes or 0) + session_minutes

        reward_plan = EconomyService.speaking_session_reward_plan(session)
        coins_awarded = int(reward_plan["coins_awarded"])
        notes = list(reward_plan["notes"])
        student.speaking_sessions_completed = int(student.speaking_sessions_completed or 0) + 1

        current_streak = StudentActivityService.active_streak(session.student_id)
        student.longest_learning_streak = max(int(student.longest_learning_streak or 0), int(current_streak or 0))

        EconomyService.award_coins(
            session.student_id,
            coins_awarded,
            reference_type="speaking_session",
            reference_id=session.id,
            title="Speaking session reward",
            description=" • ".join(notes),
            created_by="system",
            idempotency_key=f"speaking-session:{session.student_id}:{session.id}",
        )
        EconomyService.award_streak_milestone_if_eligible(session.student_id, current_streak)

        tx = StudentRewardTransaction(
            student_id=session.student_id,
            speaking_session_id=session.id,
            source_type='speaking_completion',
            coins=coins_awarded,
            title='Speaking session reward',
            description=' • '.join(notes),
        )
        db.session.add(tx)

        session.completion_tracked = True
        session.coins_awarded = coins_awarded
        db.session.flush()
        return {
            'awarded': True,
            'coins_awarded': coins_awarded,
            'streak': current_streak,
        }

    @staticmethod
    def track_fast_submit_flag(session, reason: str) -> None:
        session.is_fast_submit_flagged = True
        session.fast_submit_reason = (reason or '')[:255] or None
        student = User.query.get(session.student_id)
        if student:
            student.speaking_fast_submit_flags = int(student.speaking_fast_submit_flags or 0) + 1
        db.session.flush()

    @staticmethod
    def speaking_dashboard_stats(student_id: int) -> dict:
        student = User.query.get(student_id)
        latest_rewards = (
            StudentRewardTransaction.query.filter_by(student_id=student_id, source_type='speaking_completion')
            .order_by(StudentRewardTransaction.created_at.desc(), StudentRewardTransaction.id.desc())
            .limit(5)
            .all()
        )
        recent_days = (
            StudentDailyActivity.query.filter_by(student_id=student_id)
            .order_by(StudentDailyActivity.activity_date.desc())
            .limit(14)
            .all()
        )
        total_completed = sum(int(row.speaking_completed_sessions or 0) for row in recent_days)
        return {
            'coin_balance': int(getattr(student, 'coin_balance', 0) or 0),
            'lifetime_coins': int(getattr(student, 'lifetime_coins', 0) or 0),
            'streak': StudentActivityService.active_streak(student_id),
            'longest_streak': int(getattr(student, 'longest_learning_streak', 0) or 0),
            'speaking_sessions_completed': int(getattr(student, 'speaking_sessions_completed', 0) or 0),
            'completed_last_14_days': total_completed,
            'latest_rewards': latest_rewards,
        }
