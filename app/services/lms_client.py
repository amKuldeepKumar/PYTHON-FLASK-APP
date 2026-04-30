from __future__ import annotations

from sqlalchemy import func

from ..models.lms import Course, Enrollment, Lesson, LessonProgress, Level, Question, QuestionAttempt
from ..models.user import User


def get_student_latest_course(admin_id: int | None, student_id: int):
    query = (
        Course.query.join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == student_id, Enrollment.status == "active")
    )

    if admin_id is not None:
        query = query.filter(Course.owner_admin_id == admin_id)

    return query.order_by(Enrollment.enrolled_at.desc(), Course.created_at.desc()).first()


def get_student_active_courses(student_id: int):
    return (
        Course.query.join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == student_id, Enrollment.status == "active")
        .order_by(Enrollment.enrolled_at.desc(), Course.title.asc())
        .all()
    )


def get_student_progress_summary(student_id: int) -> dict:
    attempts = QuestionAttempt.query.filter_by(student_id=student_id).all()
    scored_attempts = [a for a in attempts if a.attempt_kind == "final"]
    progress_rows = LessonProgress.query.filter_by(student_id=student_id).all()
    active_courses = Enrollment.query.filter_by(student_id=student_id, status="active").count()

    avg_accuracy = 0
    avg_grammar = 0
    avg_clarity = 0
    avg_confidence = 0

    if scored_attempts:
        def _avg(vals):
            vals = [v for v in vals if v is not None]
            return int(round(sum(vals) / len(vals))) if vals else 0

        avg_accuracy = _avg([a.accuracy_score for a in scored_attempts])
        avg_grammar = _avg([a.grammar_score for a in scored_attempts])
        avg_clarity = _avg([a.clarity_score for a in scored_attempts])
        avg_confidence = _avg([a.confidence_score for a in scored_attempts])

    completion_percent = 0
    completed_lessons = 0
    total_lessons = len(progress_rows)
    skipped_questions = 0
    retry_questions = 0
    support_tool_usage_count = 0
    support_tool_penalty_points = 0
    if progress_rows:
        completion_percent = int(round(sum(p.completion_percent for p in progress_rows) / len(progress_rows)))
        completed_lessons = sum(1 for p in progress_rows if (p.completion_percent or 0) >= 100 or p.completed_at)
        skipped_questions = sum(int(p.skipped_questions or 0) for p in progress_rows)
        retry_questions = sum(int(p.retry_questions or 0) for p in progress_rows)
        support_tool_usage_count = sum(int(p.support_tool_usage_count or 0) for p in progress_rows)
        support_tool_penalty_points = int(round(sum(float(p.support_tool_penalty_points or 0) for p in progress_rows)))

    question_count = Question.query.count()
    generated_answer_count = Question.query.filter(Question.answer_generation_status == "generated").count() if question_count else 0
    return {
        "active_courses": active_courses,
        "attempt_count": len(scored_attempts),
        "completed_questions": len({a.question_id for a in scored_attempts}),
        "avg_accuracy": avg_accuracy,
        "avg_grammar": avg_grammar,
        "avg_clarity": avg_clarity,
        "avg_confidence": avg_confidence,
        "completion_percent": completion_percent,
        "completed_lessons": completed_lessons,
        "total_lessons": total_lessons,
        "skipped_questions": skipped_questions,
        "retry_questions": retry_questions,
        "support_tool_usage_count": support_tool_usage_count,
        "support_tool_penalty_points": support_tool_penalty_points,
        "hint_usage_count": sum(1 for a in attempts if a.hint_used),
        "synonym_usage_count": sum(1 for a in attempts if a.synonym_used),
        "translation_usage_count": sum(1 for a in attempts if a.translation_used),
        "answer_generation_coverage": int(round((generated_answer_count / question_count) * 100)) if question_count else 0,
    }


def get_course_student_count(course_id: int) -> int:
    return Enrollment.query.filter_by(course_id=course_id, status="active").count()


def get_course_attempt_count(course_id: int) -> int:
    return (
        QuestionAttempt.query.join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course_id)
        .count()
    )


def get_course_accuracy(course_id: int) -> int:
    avg = db_avg_course_accuracy(course_id) or 0
    return int(round(float(avg)))


def db_avg_course_accuracy(course_id: int):
    return (
        QuestionAttempt.query
        .join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course_id, QuestionAttempt.attempt_kind == "final")
        .with_entities(func.avg(QuestionAttempt.accuracy_score))
        .scalar()
    )


def get_student_dashboard_cards(student: User) -> dict:
    latest_course = get_student_latest_course(student.admin_id, student.id)
    summary = get_student_progress_summary(student.id)

    return {
        "latest_course": latest_course,
        "summary": summary,
        "profile_completion": student.profile_completion_percent(),
        "learning_summary": student.latest_learning_summary(),
    }
