from __future__ import annotations

from datetime import datetime
from sqlalchemy import func

from ..extensions import db
from ..models.lms import Course, Level, Lesson
from ..models.reading_passage import ReadingPassage
from ..models.reading_question import ReadingQuestion
from ..models.reading_topic import ReadingTopic
from ..models.speaking_prompt import SpeakingPrompt
from ..models.speaking_topic import SpeakingTopic


def _normalize_level(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {"basic", "beginner", "a1", "a2"}:
        return "basic"
    if value in {"intermediate", "b1", "b2"}:
        return "intermediate"
    if value in {"advanced", "c1", "c2"}:
        return "advanced"
    return "basic"


def _ensure_course_level(course: Course) -> Level:
    if course.levels:
        return sorted(course.levels, key=lambda row: (row.sort_order, row.id))[0]

    level = Level(
        course_id=course.id,
        title=(course.difficulty or "Basic").title(),
        description="Auto-created level to connect generated module content to the course workspace.",
        sort_order=1,
    )
    db.session.add(level)
    db.session.flush()
    return level


def _course_has_skill_lesson(course: Course, skill: str) -> bool:
    skill = (skill or "").strip().lower()
    for level in course.levels:
        for lesson in level.lessons:
            lesson_type = (getattr(lesson, "lesson_type", None) or "").strip().lower()
            if lesson_type == skill:
                return True
    return False


def _course_has_visible_speaking(course: Course) -> bool:
    target_language = (course.language_code or "en").strip().lower()
    target_level = _normalize_level(course.difficulty)

    base = (
        db.session.query(SpeakingTopic.id)
        .join(SpeakingPrompt, SpeakingPrompt.topic_id == SpeakingTopic.id)
        .filter(
            SpeakingTopic.is_active.is_(True),
            SpeakingTopic.is_published.is_(True),
            SpeakingPrompt.is_active.is_(True),
            func.lower(func.coalesce(SpeakingTopic.language_code, "en")) == target_language,
        )
        .distinct()
    )

    exact = base.filter(
        func.lower(func.coalesce(SpeakingTopic.level, "basic")) == target_level
    ).count()

    return bool(exact or base.count())


def _course_has_visible_reading(course: Course) -> bool:
    target_level = _normalize_level(course.difficulty)

    rows = (
        db.session.query(ReadingPassage.id)
        .join(ReadingTopic, ReadingTopic.id == ReadingPassage.topic_id)
        .filter(
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ReadingTopic.is_active.is_(True),
        )
        .all()
    )
    if not rows:
        return False

    exact = (
        db.session.query(ReadingPassage.id)
        .join(ReadingTopic, ReadingTopic.id == ReadingPassage.topic_id)
        .join(ReadingQuestion, ReadingQuestion.passage_id == ReadingPassage.id)
        .filter(
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ReadingTopic.is_active.is_(True),
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
            func.lower(func.coalesce(ReadingPassage.level, "basic")) == target_level,
        )
        .distinct()
        .count()
    )

    fallback = (
        db.session.query(ReadingPassage.id)
        .join(ReadingQuestion, ReadingQuestion.passage_id == ReadingPassage.id)
        .filter(
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .distinct()
        .count()
    )

    return bool(exact or fallback)


def ensure_course_module_lessons() -> None:
    changed = False
    now = datetime.utcnow()

    for course in Course.query.order_by(Course.id.asc()).all():
        level = _ensure_course_level(course)

        next_sort_order = max([lesson.sort_order for lesson in level.lessons] + [0]) + 1

        if _course_has_visible_speaking(course) and not _course_has_skill_lesson(course, "speaking"):
            db.session.add(
                Lesson(
                    level_id=level.id,
                    title="Speaking Practice",
                    slug=f"course-{course.id}-speaking-practice",
                    lesson_type="speaking",
                    explanation_text="Auto-created speaking practice lesson to connect published speaking topics to this course.",
                    explanation_tts_text="Auto-created speaking practice lesson to connect published speaking topics to this course.",
                    estimated_minutes=10,
                    is_published=True,
                    sort_order=next_sort_order,
                    workflow_status="published",
                    created_at=now,
                    updated_at=now,
                )
            )
            changed = True
            next_sort_order += 1

        if _course_has_visible_reading(course) and not _course_has_skill_lesson(course, "reading"):
            db.session.add(
                Lesson(
                    level_id=level.id,
                    title="Reading Practice",
                    slug=f"course-{course.id}-reading-practice",
                    lesson_type="reading",
                    explanation_text="Auto-created reading practice lesson to connect approved published passages to this course.",
                    explanation_tts_text="Auto-created reading practice lesson to connect approved published passages to this course.",
                    estimated_minutes=12,
                    is_published=True,
                    sort_order=next_sort_order,
                    workflow_status="published",
                    created_at=now,
                    updated_at=now,
                )
            )
            changed = True

    if changed:
        db.session.commit()
    else:
        db.session.rollback()