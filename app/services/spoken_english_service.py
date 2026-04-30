from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..extensions import db
from ..models.lms import Course, Enrollment
from ..models.speaking_prompt import SpeakingPrompt
from ..models.speaking_session import SpeakingSession
from ..models.speaking_topic import SpeakingTopic
from ..models.student_daily_activity import StudentDailyActivity
from .course_pathway_seed import ensure_special_english_pathways
from .speaking.speaking_session_service import SpeakingSessionService


@dataclass
class SpokenEnglishHomePayload:
    course: Course
    topics: list[SpeakingTopic]
    daily_prompt: SpeakingPrompt | None
    daily_topic: SpeakingTopic | None
    active_prompt_count: int
    completed_today: int
    total_completed: int
    streak_days: int
    average_score: int
    recent_sessions: list[SpeakingSession]
    category_cards: list[dict]
    free_topic_count: int
    premium_topic_count: int


class SpokenEnglishService:
    @staticmethod
    def sync_special_pathways(owner_admin_id: int | None, created_by_id: int | None):
        return ensure_special_english_pathways(owner_admin_id, created_by_id)

    @staticmethod
    def ensure_special_courses(owner_admin_id: int | None, created_by_id: int | None) -> None:
        try:
            SpokenEnglishService.sync_special_pathways(owner_admin_id, created_by_id)
        except Exception:
            db.session.rollback()

    @staticmethod
    def is_spoken_english_course(course: Course | None) -> bool:
        if not course:
            return False
        title = (getattr(course, 'title', '') or '').strip().lower()
        slug = (getattr(course, 'slug', '') or '').strip().lower()
        return title == 'spoken english' or slug == 'spoken-english'

    @staticmethod
    def visible_topics(course: Course) -> list[SpeakingTopic]:
        topics = [
            topic for topic in (getattr(course, 'speaking_topics', []) or [])
            if bool(getattr(topic, 'is_active', False))
            and bool(getattr(topic, 'is_published', False))
            and int(getattr(topic, 'active_prompt_count', 0) or 0) > 0
        ]
        return sorted(topics, key=lambda row: ((getattr(row, 'display_order', 0) or 0), (getattr(row, 'title', '') or '').lower(), getattr(row, 'id', 0) or 0))

    @staticmethod
    def category_cards(course: Course) -> list[dict]:
        cards: list[dict] = []
        for topic in SpokenEnglishService.visible_topics(course):
            title = (getattr(topic, 'title', '') or '').strip()
            text = title.lower()
            if 'functional' in text or 'q&a' in text or 'qa' in text:
                label = 'Quick Q&A'
                desc = 'Short answer practice for real daily situations.'
            else:
                label = 'Daily Conversation'
                desc = 'Longer guided answers for confidence and fluency.'
            cards.append({
                'topic': topic,
                'label': label,
                'description': desc,
                'prompt_count': int(getattr(topic, 'active_prompt_count', 0) or 0),
            })
        return cards

    @staticmethod
    def daily_prompt(course: Course, student_id: int) -> tuple[SpeakingTopic | None, SpeakingPrompt | None]:
        topics = SpokenEnglishService.visible_topics(course)
        prompts: list[tuple[SpeakingTopic, SpeakingPrompt]] = []
        for topic in topics:
            rows = topic.prompts.filter_by(is_active=True).order_by(SpeakingPrompt.display_order.asc(), SpeakingPrompt.id.asc()).all()
            for prompt in rows:
                prompts.append((topic, prompt))
        if not prompts:
            return None, None
        offset = int(date.today().strftime('%Y%m%d')) + int(student_id or 0)
        topic, prompt = prompts[offset % len(prompts)]
        resumable = SpeakingSessionService.get_resumable_session(student_id, topic_id=topic.id, course_id=course.id)
        if resumable and getattr(resumable, 'prompt', None):
            return topic, resumable.prompt
        return topic, prompt

    @staticmethod
    def model_answer_for_prompt(prompt: SpeakingPrompt | None) -> str:
        if not prompt:
            return ''
        title = (getattr(prompt, 'title', '') or '').strip()
        prompt_text = (getattr(prompt, 'prompt_text', '') or '').strip()
        instruction = (getattr(prompt, 'instruction_text', '') or '').strip()
        opening = 'A strong answer can start like this: '
        text = f"{prompt_text}"
        low = f"{title} {prompt_text} {instruction}".lower()
        if 'morning routine' in low:
            text = 'I usually wake up early, get ready, have breakfast, and start my day with a simple plan. This keeps me active and organized.'
        elif 'market' in low:
            text = 'Hello, how much are these vegetables? I would like one kilo, please. Can you also give me some fresh tomatoes? Thank you.'
        elif 'new friend' in low or 'introduce yourself' in low:
            text = 'Hi, my name is Rahul. I am from Punjab, and I enjoy learning English and meeting new people. What do you like to do in your free time?'
        elif 'directions' in low:
            text = 'Excuse me, could you please tell me how to get to the railway station? Is it far from here, and should I take a bus or walk?'
        elif 'phone call' in low:
            text = 'Hello, I am calling to ask about the class timing. Could you please tell me when the next English class starts? Thank you for your help.'
        return opening + text

    @staticmethod
    def _streak_days(student_id: int) -> int:
        days = {
            row.activity_date
            for row in StudentDailyActivity.query.filter_by(student_id=student_id).all()
            if int(getattr(row, 'speaking_attempts', 0) or 0) > 0 or int(getattr(row, 'speaking_completed_sessions', 0) or 0) > 0
        }
        if not days:
            return 0
        streak = 0
        cursor = date.today()
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @staticmethod
    def enrollment(course_id: int, student_id: int) -> Enrollment | None:
        return (
            Enrollment.query.filter_by(student_id=student_id, course_id=course_id, status='active')
            .order_by(Enrollment.enrolled_at.desc())
            .first()
        )

    @staticmethod
    def build_home(course: Course, student_id: int) -> SpokenEnglishHomePayload:
        topics = SpokenEnglishService.visible_topics(course)
        daily_topic, daily_prompt = SpokenEnglishService.daily_prompt(course, student_id)
        recent_sessions = SpeakingSessionService.recent_sessions_for_student(student_id, limit=6, course_id=course.id)
        completed_today = (
            SpeakingSession.query.filter(
                SpeakingSession.student_id == student_id,
                SpeakingSession.course_id == course.id,
                SpeakingSession.status == SpeakingSession.STATUS_COMPLETED,
                db.func.date(SpeakingSession.updated_at) == date.today(),
            ).count()
        )
        total_completed = (
            SpeakingSession.query.filter_by(student_id=student_id, course_id=course.id, status=SpeakingSession.STATUS_COMPLETED).count()
        )
        score_rows = (
            db.session.query(SpeakingSession.evaluation_score)
            .filter(
                SpeakingSession.student_id == student_id,
                SpeakingSession.course_id == course.id,
                SpeakingSession.evaluation_score.isnot(None),
            )
            .all()
        )
        score_values = [float(row[0]) for row in score_rows if row and row[0] is not None]
        average_score = int(round(sum(score_values) / len(score_values))) if score_values else 0
        return SpokenEnglishHomePayload(
            course=course,
            topics=topics,
            daily_prompt=daily_prompt,
            daily_topic=daily_topic,
            active_prompt_count=sum(int(getattr(topic, 'active_prompt_count', 0) or 0) for topic in topics),
            completed_today=completed_today,
            total_completed=total_completed,
            streak_days=SpokenEnglishService._streak_days(student_id),
            average_score=average_score,
            recent_sessions=recent_sessions,
            category_cards=SpokenEnglishService.category_cards(course),
            free_topic_count=len(topics),
            premium_topic_count=0,
        )
