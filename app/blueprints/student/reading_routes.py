from __future__ import annotations

import json
import time
from typing import Any

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_, and_
from flask_login import current_user, login_required

from . import bp
from ...rbac import require_role
from ...models.reading_passage import ReadingPassage
from ...models.reading_question import ReadingQuestion
from ...models.reading_topic import ReadingTopic
from ...models.reading_session_log import ReadingSessionLog
from ...models.lms import Course, Enrollment
from ...extensions import db
from ...services.language_service import language_label, resolve_language_code
from ...i18n import get_translation_language_code, get_translation_language_name
from ...services.reading.translation_service import ReadingTranslationService
from ...services.student_ai_intelligence import StudentAIIntelligenceService
from ...services.reading.answer_evaluation_service import ReadingAnswerEvaluationService

READING_DRAFTS_SESSION_KEY = "student_reading_drafts"
READING_RESULTS_SESSION_KEY = "student_reading_results"
RECENT_READING_COOLDOWN_COUNT = 3


LEVEL_SEQUENCE = [ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED]
USER_LEVEL_LABELS = {
    ReadingTopic.LEVEL_BASIC: "Beginner",
    ReadingTopic.LEVEL_INTERMEDIATE: "Intermediate",
    ReadingTopic.LEVEL_ADVANCED: "Advanced",
}


def _level_index(level: str | None) -> int:
    normalized = _normalize_reading_level(level)
    try:
        return LEVEL_SEQUENCE.index(normalized)
    except ValueError:
        return 0


def _promote_level(level: str | None) -> str:
    idx = min(_level_index(level) + 1, len(LEVEL_SEQUENCE) - 1)
    return LEVEL_SEQUENCE[idx]


def _demote_level(level: str | None) -> str:
    idx = max(_level_index(level) - 1, 0)
    return LEVEL_SEQUENCE[idx]


def _user_level_label(level: str | None) -> str:
    return USER_LEVEL_LABELS.get(_normalize_reading_level(level), "Beginner")


def _student_recent_reading_logs(limit: int = 3, course_id: int | None = None) -> list[ReadingSessionLog]:
    query = ReadingSessionLog.query.filter_by(student_id=current_user.id)
    if course_id:
        query = query.filter_by(course_id=course_id)
    return query.order_by(ReadingSessionLog.submitted_at.desc(), ReadingSessionLog.id.desc()).limit(limit).all()


def _recently_used_passage_ids(course_id: int | None = None, limit: int = RECENT_READING_COOLDOWN_COUNT) -> list[int]:
    rows = _student_recent_reading_logs(limit=limit, course_id=course_id)
    seen: list[int] = []
    for row in rows:
        passage_id = int(row.passage_id or 0)
        if passage_id and passage_id not in seen:
            seen.append(passage_id)
    return seen


def _rotation_payload(passages: list[ReadingPassage], course_id: int | None = None) -> dict[str, Any]:
    recent_ids = _recently_used_passage_ids(course_id=course_id)
    fresh = [p for p in passages if p.id not in recent_ids]
    recent = [p for p in passages if p.id in recent_ids]
    ordered = fresh + recent
    return {
        'recent_ids': recent_ids,
        'fresh_ids': [p.id for p in fresh],
        'ordered_passages': ordered,
        'cooldown_count': RECENT_READING_COOLDOWN_COUNT,
        'fresh_count': len(fresh),
        'recent_count': len(recent),
    }


def _rotated_visible_reading_passages_for_student(course_id: int | None = None) -> tuple[list[ReadingPassage], dict[str, Any]]:
    passages = _visible_reading_passages_for_student(course_id)
    rotation = _rotation_payload(passages, course_id=course_id)
    ordered = rotation['ordered_passages']
    return ordered, rotation


def _apply_reading_personalization(*, course: Course | None, passage: ReadingPassage, score: dict[str, Any]) -> dict[str, Any]:
    current_level = _normalize_reading_level(getattr(current_user, 'current_level', None))
    logs = _student_recent_reading_logs(limit=3, course_id=course.id if course else None)
    recent_accuracies = [float(row.accuracy or 0.0) for row in logs]
    avg_accuracy = round(sum(recent_accuracies) / len(recent_accuracies), 1) if recent_accuracies else float(score.get('accuracy') or 0.0)
    strong_count = sum(1 for value in recent_accuracies if value >= 80)
    weak_count = sum(1 for value in recent_accuracies if value < 45)

    new_level = current_level
    decision = 'stay'
    reason = 'Keep practicing at this level to build consistency.'

    if strong_count >= 2 and avg_accuracy >= 78:
        promoted = _promote_level(current_level)
        if promoted != current_level:
            new_level = promoted
            decision = 'promoted'
            reason = 'Strong recent accuracy unlocked the next reading level.'
        else:
            reason = 'You are already performing strongly at the highest level.'
    elif weak_count >= 2 and avg_accuracy < 45:
        demoted = _demote_level(current_level)
        if demoted != current_level:
            new_level = demoted
            decision = 'supported'
            reason = 'Recent low scores moved you to a simpler level for better recovery.'
        else:
            reason = 'You remain on the foundation level until accuracy improves.'
    elif float(score.get('accuracy') or 0.0) >= 80:
        reason = 'One more strong result will help unlock the next level.'
    elif float(score.get('accuracy') or 0.0) < 45:
        reason = 'A few guided retries will stabilize your current level.'

    if _normalize_reading_level(getattr(current_user, 'current_level', None)) != new_level:
        current_user.current_level = _user_level_label(new_level)
        db.session.commit()

    next_level = _promote_level(new_level) if _promote_level(new_level) != new_level else None
    return {
        'decision': decision,
        'reason': reason,
        'current_level': new_level,
        'current_level_label': _user_level_label(new_level),
        'next_level': next_level,
        'next_level_label': _user_level_label(next_level) if next_level else None,
        'avg_accuracy': avg_accuracy,
        'recent_logs': len(logs),
        'latest_accuracy': float(score.get('accuracy') or 0.0),
        'passage_level': _normalize_reading_level(getattr(passage, 'level', None)),
    }


def _reading_personalization_snapshot(course_id: int | None = None) -> dict[str, Any]:
    current_level = _normalize_reading_level(getattr(current_user, 'current_level', None))
    logs = _student_recent_reading_logs(limit=3, course_id=course_id)
    recent_accuracies = [float(row.accuracy or 0.0) for row in logs]
    avg_accuracy = round(sum(recent_accuracies) / len(recent_accuracies), 1) if recent_accuracies else 0.0
    strong_count = sum(1 for value in recent_accuracies if value >= 80)
    weak_count = sum(1 for value in recent_accuracies if value < 45)

    recommendation = current_level
    message = 'Keep going at your current level.'
    if strong_count >= 2 and avg_accuracy >= 78:
        recommendation = _promote_level(current_level)
        if recommendation != current_level:
            message = 'You are close to moving up based on recent reading accuracy.'
        else:
            message = 'You are already sustaining strong results at the top level.'
    elif weak_count >= 2 and avg_accuracy < 45:
        recommendation = _demote_level(current_level)
        if recommendation != current_level:
            message = 'A short step back can help rebuild confidence and accuracy.'
        else:
            message = 'Stay on the foundation level and focus on accuracy first.'

    return {
        'current_level': current_level,
        'current_level_label': _user_level_label(current_level),
        'recommended_level': recommendation,
        'recommended_level_label': _user_level_label(recommendation),
        'avg_accuracy': avg_accuracy,
        'recent_logs': len(logs),
        'message': message,
    }




def _reading_support_language_context() -> tuple[str, str, bool]:
    translation_language_code = resolve_language_code(get_translation_language_code(default="en"), default="en")
    if translation_language_code == "en":
        fallback_native_code = resolve_language_code(getattr(current_user, "native_language", None), default="")
        if fallback_native_code and fallback_native_code != "en":
            translation_language_code = fallback_native_code

    translation_language_name = get_translation_language_name(default="English")
    if translation_language_code != "en":
        translation_language_name = language_label(translation_language_code, fallback=translation_language_name)

    translation_support_enabled = bool(translation_language_code and translation_language_code != "en")
    return translation_language_code, translation_language_name, translation_support_enabled

def _normalize_reading_level(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value.startswith("adv"):
        return ReadingTopic.LEVEL_ADVANCED
    if value.startswith("int") or value in {"b1", "b2"}:
        return ReadingTopic.LEVEL_INTERMEDIATE
    return ReadingTopic.LEVEL_BASIC


def _parse_question_options(raw: str | None) -> list[str]:
    text = (raw or "").strip()
    if not text or text == "[]":
        return []
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]
    except Exception:
        pass
    return [line.strip(" -•	") for line in text.splitlines() if line.strip()]




def _student_enrolled_track_courses(track_type: str) -> list[Course]:
    rows = (
        Enrollment.query
        .join(Course, Course.id == Enrollment.course_id)
        .filter(
            Enrollment.student_id == current_user.id,
            Enrollment.status == "active",
            Course.track_type == track_type,
            Course.is_published.is_(True),
        )
        .order_by(Enrollment.enrolled_at.desc(), Course.updated_at.desc(), Course.id.desc())
        .all()
    )
    seen: set[int] = set()
    courses: list[Course] = []
    for row in rows:
        course = getattr(row, 'course', None)
        if not course or course.id in seen:
            continue
        seen.add(course.id)
        courses.append(course)
    return courses

def _student_enrolled_course(course_id: int) -> Course | None:
    enrollment = (
        Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )
    return enrollment.course if enrollment and enrollment.course else None


def _student_course_enrollment(course_id: int) -> Enrollment | None:
    return (
        Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )


def _passage_level_allowed(enrollment: Enrollment | None, level_number: int | None) -> bool:
    if not enrollment:
        return False
    return enrollment.has_level_access(level_number)


def _visible_reading_passages_for_student(course_id: int | None = None) -> list[ReadingPassage]:
    student_level = _normalize_reading_level(getattr(current_user, "current_level", None))
    base_query = (
        ReadingPassage.query
        .join(ReadingTopic, ReadingTopic.id == ReadingPassage.topic_id)
        .join(ReadingQuestion, ReadingQuestion.passage_id == ReadingPassage.id)
        .filter(
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ReadingTopic.is_active.is_(True),
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .distinct()
        .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
    )

    if course_id:
        base_query = base_query.filter(
            or_(
                ReadingPassage.course_id == course_id,
                and_(ReadingPassage.course_id.is_(None), ReadingTopic.course_id == course_id),
            )
        )

    preferred = base_query.filter(ReadingPassage.level == student_level).all()
    if preferred:
        return preferred
    return base_query.all()


def _approved_questions_for_passage(passage_id: int) -> list[ReadingQuestion]:
    return (
        ReadingQuestion.query
        .filter(
            ReadingQuestion.passage_id == passage_id,
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .order_by(ReadingQuestion.display_order.asc(), ReadingQuestion.id.asc())
        .all()
    )


def _session_drafts() -> dict[str, Any]:
    payload = session.get(READING_DRAFTS_SESSION_KEY, {}) or {}
    return payload if isinstance(payload, dict) else {}


def _store_session_drafts(payload: dict[str, Any]) -> None:
    session[READING_DRAFTS_SESSION_KEY] = payload
    session.modified = True


def _session_results() -> dict[str, Any]:
    payload = session.get(READING_RESULTS_SESSION_KEY, {}) or {}
    return payload if isinstance(payload, dict) else {}


def _store_session_results(payload: dict[str, Any]) -> None:
    session[READING_RESULTS_SESSION_KEY] = payload
    session.modified = True


def _draft_key(passage_id: int) -> str:
    return f"{current_user.id}:{passage_id}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _reading_speed_wpm(word_count: int | None, elapsed_seconds: int | None) -> float:
    words = max(_safe_int(word_count, 0), 0)
    seconds = max(_safe_int(elapsed_seconds, 0), 0)
    if not words or not seconds:
        return 0.0
    return round((words / seconds) * 60.0, 1)


def _reading_metrics_from_result(passage: ReadingPassage, elapsed_seconds: int, score: dict[str, Any]) -> dict[str, Any]:
    speed = _reading_speed_wpm(getattr(passage, 'word_count', 0), elapsed_seconds)
    return {
        'accuracy': float(score.get('accuracy') or 0.0),
        'correct': _safe_int(score.get('correct')),
        'incorrect': _safe_int(score.get('incorrect')),
        'errors': _safe_int(score.get('incorrect')),
        'total': _safe_int(score.get('total')),
        'elapsed_seconds': max(elapsed_seconds, 0),
        'reading_speed_wpm': speed,
        'word_count': max(_safe_int(getattr(passage, 'word_count', 0)), 0),
    }


def _latest_session_log(passage_id: int) -> ReadingSessionLog | None:
    return (
        ReadingSessionLog.query
        .filter_by(student_id=current_user.id, passage_id=passage_id)
        .order_by(ReadingSessionLog.submitted_at.desc(), ReadingSessionLog.id.desc())
        .first()
    )


def _course_reading_analytics(course_id: int) -> dict[str, Any]:
    rows = (
        ReadingSessionLog.query
        .filter_by(student_id=current_user.id, course_id=course_id)
        .order_by(ReadingSessionLog.submitted_at.desc(), ReadingSessionLog.id.desc())
        .all()
    )
    if not rows:
        return {
            'sessions': 0,
            'avg_accuracy': 0.0,
            'avg_speed_wpm': 0.0,
            'total_errors': 0,
            'total_time_seconds': 0,
            'best_accuracy': 0.0,
            'recent_logs': [],
        }

    sessions = len(rows)
    total_time = sum(max(int(r.elapsed_seconds or 0), 0) for r in rows)
    total_errors = sum(max(int(r.errors_count or 0), 0) for r in rows)
    avg_accuracy = round(sum(float(r.accuracy or 0.0) for r in rows) / sessions, 1)
    avg_speed = round(sum(float(r.reading_speed_wpm or 0.0) for r in rows) / sessions, 1)
    best_accuracy = round(max(float(r.accuracy or 0.0) for r in rows), 1)
    recent_logs = []
    for row in rows[:5]:
        recent_logs.append({
            'passage_title': row.passage.title if row.passage else 'Reading passage',
            'submitted_at': row.submitted_at,
            'accuracy': float(row.accuracy or 0.0),
            'elapsed_seconds': int(row.elapsed_seconds or 0),
            'reading_speed_wpm': float(row.reading_speed_wpm or 0.0),
            'errors_count': int(row.errors_count or 0),
        })
    return {
        'sessions': sessions,
        'avg_accuracy': avg_accuracy,
        'avg_speed_wpm': avg_speed,
        'total_errors': total_errors,
        'total_time_seconds': total_time,
        'best_accuracy': best_accuracy,
        'recent_logs': recent_logs,
    }


def _persist_reading_session_log(*, course: Course | None, passage: ReadingPassage, elapsed_seconds: int, submitted_answers: dict[str, str], score: dict[str, Any]) -> ReadingSessionLog:
    metrics = _reading_metrics_from_result(passage, elapsed_seconds, score)
    row = ReadingSessionLog(
        student_id=current_user.id,
        course_id=course.id if course else getattr(passage, 'course_id', None),
        passage_id=passage.id,
        topic_id=passage.topic_id,
        accuracy=metrics['accuracy'],
        correct_count=metrics['correct'],
        incorrect_count=metrics['incorrect'],
        total_questions=metrics['total'],
        errors_count=metrics['errors'],
        elapsed_seconds=metrics['elapsed_seconds'],
        reading_speed_wpm=metrics['reading_speed_wpm'],
        progress_percent=100,
        answers_json=json.dumps(submitted_answers, ensure_ascii=False),
        checked_rows_json=json.dumps(score.get('checked_rows') or [], ensure_ascii=False),
    )
    db.session.add(row)
    db.session.commit()
    return row


def _normalized_answer_text(value: str | None) -> str:
    text = " ".join((value or "").strip().lower().split())
    text = text.replace(".", " ").replace(",", " ").replace(";", " ").replace(":", " ")
    words = [word for word in text.split() if word not in {"a", "an", "the"}]
    return " ".join(words)


def _answer_overlap_ratio(answer: str, expected: str) -> float:
    answer_tokens = set(_normalized_answer_text(answer).split())
    expected_tokens = set(_normalized_answer_text(expected).split())
    if not answer_tokens or not expected_tokens:
        return 0.0
    return len(answer_tokens & expected_tokens) / max(1, len(expected_tokens))


def _evaluate_reading_answer(question: ReadingQuestion, answer: str, passage_text: str) -> tuple[bool, str]:
    expected = (question.correct_answer or '').strip()
    normalized_answer = _normalized_answer_text(answer)
    normalized_expected = _normalized_answer_text(expected)

    if question.question_type == ReadingQuestion.TYPE_TRUE_FALSE:
        return (normalized_answer == normalized_expected, question.explanation or 'Check whether the statement matches the passage exactly.')

    if question.question_type == ReadingQuestion.TYPE_MCQ:
        return (normalized_answer == normalized_expected, question.explanation or 'Review the line in the passage that supports the correct option.')

    if normalized_answer and normalized_answer == normalized_expected:
        return True, question.explanation or 'Your answer matches the key answer.'

    overlap = _answer_overlap_ratio(answer, expected)
    if overlap >= 0.7:
        return True, question.explanation or 'Your answer captures the main expected idea from the passage.'

    ai_result = ReadingAnswerEvaluationService.evaluate_answer(
        question_text=question.question_text or '',
        expected_answer=expected,
        learner_answer=answer,
        passage_text=passage_text or '',
    )
    if ai_result.ok and ai_result.is_correct is not None:
        return bool(ai_result.is_correct), ai_result.reason or question.explanation or 'Answer evaluated from the passage context.'

    return False, question.explanation or 'Review the passage and match your answer to the key detail more closely.'


def _build_question_view_models(questions: list[ReadingQuestion], saved_answers: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    saved_answers = saved_answers or {}
    rows: list[dict[str, Any]] = []
    for q in questions:
        rows.append({
            "id": q.id,
            "display_order": q.display_order,
            "type": q.question_type,
            "type_label": q.type_label,
            "text": q.question_text,
            "options": _parse_question_options(q.options_json),
            "answer": str(saved_answers.get(str(q.id), "")),
            "correct_answer": (q.correct_answer or "").strip(),
            "explanation": (q.explanation or "").strip(),
        })
    return rows


def _score_submission(questions: list[ReadingQuestion], submitted_answers: dict[str, str], passage_text: str = "") -> dict[str, Any]:
    total = len(questions)
    correct = 0
    checked_rows: list[dict[str, Any]] = []
    for q in questions:
        answer = (submitted_answers.get(str(q.id)) or "").strip()
        expected = (q.correct_answer or "").strip()
        is_correct, explanation = _evaluate_reading_answer(q, answer, passage_text)
        if is_correct:
            correct += 1
        checked_rows.append({
            "question_id": q.id,
            "your_answer": answer,
            "correct_answer": expected,
            "is_correct": is_correct,
            "explanation": (explanation or q.explanation or "Review the supporting sentence in the passage.").strip(),
        })

    accuracy = round((correct / total) * 100, 1) if total else 0.0
    return {
        "total": total,
        "correct": correct,
        "incorrect": max(total - correct, 0),
        "accuracy": accuracy,
        "checked_rows": checked_rows,
    }


@bp.route('/reading', methods=['GET'])
@login_required
@require_role('STUDENT')
def reading_home():
    courses = _student_enrolled_track_courses('reading')
    if len(courses) == 1:
        return redirect(url_for('student.course_reading_home', course_id=courses[0].id))
    return render_template(
        'student/track_portal.html',
        track_label='Reading',
        track_key='reading',
        courses=[{'course': course} for course in courses],
        open_endpoint='student.course_reading_home',
        subtitle='Open reading practice from a themed launcher instead of getting pushed back to My Courses.',
        fallback_description='Build speed, accuracy, and understanding with guided reading sets.',
        published_count=len(courses),
    )


@bp.route('/courses/<int:course_id>/reading', methods=['GET'])
@login_required
@require_role('STUDENT')
def course_reading_home(course_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash('You are not enrolled in this course.', 'warning')
        return redirect(url_for('student.my_courses'))

    if (getattr(course, 'track_type', '') or '').strip().lower() != 'reading':
        flash('This course is not configured as a reading track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))

    passages, rotation = _rotated_visible_reading_passages_for_student(course.id)
    student_level = _normalize_reading_level(getattr(current_user, 'current_level', None))
    rows = []
    for passage in passages:
        approved_questions = _approved_questions_for_passage(passage.id)
        if not approved_questions:
            continue
        rows.append({
            'passage': passage,
            'question_count': len(approved_questions),
            'mcq_count': sum(1 for q in approved_questions if q.question_type == ReadingQuestion.TYPE_MCQ),
            'fill_blank_count': sum(1 for q in approved_questions if q.question_type == ReadingQuestion.TYPE_FILL_BLANK),
            'true_false_count': sum(1 for q in approved_questions if q.question_type == ReadingQuestion.TYPE_TRUE_FALSE),
            'is_recently_used': passage.id in rotation['recent_ids'],
            'rotation_state': 'fresh' if passage.id in rotation['fresh_ids'] else 'cooldown',
        })

    analytics = _course_reading_analytics(course.id)
    return render_template(
        'student/reading_home.html',
        rows=rows,
        student_level=student_level,
        total_passages=len(rows),
        course=course,
        analytics=analytics,
        personalization=_reading_personalization_snapshot(course.id),
        rotation=rotation,
        intelligence_track=StudentAIIntelligenceService.for_track(current_user.id, 'reading'),
    )


@bp.route('/courses/<int:course_id>/reading/session/<int:passage_id>', methods=['GET'])
@login_required
@require_role('STUDENT')
def course_reading_session(course_id: int, passage_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash('You are not enrolled in this course.', 'warning')
        return redirect(url_for('student.my_courses'))
    passage = ReadingPassage.query.get_or_404(passage_id)
    if (getattr(course, 'track_type', '') or '').strip().lower() != 'reading':
        flash('This course is not configured as a reading track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if passage.course_id != course.id:
        flash('This reading passage does not belong to the selected course.', 'warning')
        return redirect(url_for('student.course_reading_home', course_id=course.id))
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        flash('This reading session is not available for students yet.', 'warning')
        return redirect(url_for('student.course_reading_home', course_id=course.id))

    return _render_reading_session_page(passage=passage, course=course)


@bp.route('/reading/session/<int:passage_id>', methods=['GET'])
@login_required
@require_role('STUDENT')
def reading_session(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        flash('This reading session is not available for students yet.', 'warning')
        return redirect(url_for('student.my_courses'))

    course = _student_enrolled_course(getattr(passage, 'course_id', None)) if getattr(passage, 'course_id', None) else None
    return _render_reading_session_page(passage=passage, course=course)


def _redirect_for_reading_context(passage: ReadingPassage, course=None):
    if course is not None:
        return redirect(url_for('student.course_reading_session', course_id=course.id, passage_id=passage.id))
    if getattr(passage, 'course_id', None):
        return redirect(url_for('student.course_reading_session', course_id=passage.course_id, passage_id=passage.id))
    return redirect(url_for('student.reading_session', passage_id=passage.id))


def _reading_session_result_payload(passage: ReadingPassage):
    result = _session_results().get(_draft_key(passage.id))
    latest_log = _latest_session_log(passage.id)
    if latest_log:
        result = {
            'submitted_at': int(latest_log.submitted_at.timestamp()) if latest_log.submitted_at else 0,
            'elapsed_seconds': int(latest_log.elapsed_seconds or 0),
            'score': {
                'total': int(latest_log.total_questions or 0),
                'correct': int(latest_log.correct_count or 0),
                'incorrect': int(latest_log.incorrect_count or 0),
                'accuracy': float(latest_log.accuracy or 0.0),
                'checked_rows': json.loads(latest_log.checked_rows_json or '[]') if latest_log.checked_rows_json else [],
            },
            'answers': json.loads(latest_log.answers_json or '{}') if latest_log.answers_json else {},
            'reading_speed_wpm': float(latest_log.reading_speed_wpm or 0.0),
            'errors_count': int(latest_log.errors_count or 0),
        }
    return result


def _reading_timer_seconds(passage: ReadingPassage) -> int:
    base_time = int((passage.word_count or 120) * 1.2)
    passage_level = (getattr(passage, "level", "") or "").strip().lower()

    if passage_level == "basic":
        timer_seconds = base_time
    elif passage_level == "intermediate":
        timer_seconds = int(base_time * 0.8)
    elif passage_level == "advanced":
        timer_seconds = int(base_time * 0.6)
    else:
        timer_seconds = base_time

    return max(180, min(1800, timer_seconds))


def _render_reading_session_page(passage: ReadingPassage, course=None):
    questions = _approved_questions_for_passage(passage.id)
    if not questions:
        flash('Questions are not published for this passage yet.', 'warning')
        if course is not None:
            return redirect(url_for('student.course_reading_home', course_id=course.id))
        return redirect(url_for('student.my_courses'))

    rotated_passages, rotation = _rotated_visible_reading_passages_for_student(getattr(course, 'id', None) or getattr(passage, 'course_id', None))
    if passage.id in rotation['recent_ids'] and rotation['fresh_count'] > 0:
        replacement = next((row for row in rotated_passages if row.id != passage.id and row.id not in rotation['recent_ids']), None)
        if replacement is not None:
            flash('This passage was used recently, so a fresher reading set was opened for better variety.', 'info')
            return _redirect_for_reading_context(replacement, course=course)

    draft = _session_drafts().get(_draft_key(passage.id), {}) or {}

    return render_template(
        'student/reading_session.html',
        passage=passage,
        question_rows=_build_question_view_models(questions, draft.get('answers', {})),
        saved_answers=draft.get('answers', {}),
        saved_progress=draft.get('progress', 0),
        saved_elapsed=draft.get('elapsed_seconds', 0),
        timer_seconds=_reading_timer_seconds(passage),
        reading_result=_reading_session_result_payload(passage),
        course=course,
        reading_support_language=_reading_support_language_context(),
    )


def _submit_reading_session(passage: ReadingPassage, course=None):
    questions = _approved_questions_for_passage(passage.id)
    if not questions:
        flash('No approved questions are available for this passage.', 'warning')
        if course is not None:
            return redirect(url_for('student.course_reading_home', course_id=course.id))
        return redirect(url_for('student.my_courses'))

    submitted_answers = {str(q.id): (request.form.get(f'answer_{q.id}') or '').strip() for q in questions}
    elapsed_seconds = int(request.form.get('elapsed_seconds') or 0)
    score = _score_submission(questions, submitted_answers, passage.content)
    metrics = _reading_metrics_from_result(passage, elapsed_seconds, score)
    _persist_reading_session_log(course=course, passage=passage, elapsed_seconds=elapsed_seconds, submitted_answers=submitted_answers, score=score)
    personalization = _apply_reading_personalization(course=course, passage=passage, score=score)
    results = _session_results()
    results[_draft_key(passage.id)] = {
        'submitted_at': int(time.time()),
        'elapsed_seconds': elapsed_seconds,
        'score': score,
        'answers': submitted_answers,
        'reading_speed_wpm': metrics['reading_speed_wpm'],
        'errors_count': metrics['errors'],
    }
    _store_session_results(results)

    drafts = _session_drafts()
    drafts[_draft_key(passage.id)] = {
        'answers': submitted_answers,
        'progress': 100,
        'elapsed_seconds': elapsed_seconds,
        'updated_at': int(time.time()),
    }
    _store_session_drafts(drafts)

    if personalization['decision'] == 'promoted':
        flash(f"Great work! Your reading level moved to {personalization['current_level_label']}.", 'success')
    elif personalization['decision'] == 'supported':
        flash(f"Reading path adjusted to {personalization['current_level_label']} for better support.", 'warning')
    else:
        flash(f"Reading session submitted successfully. {personalization['reason']}", 'success')
    return _redirect_for_reading_context(passage, course=course)


def _reading_autosave_response(passage_id: int, course_id: int | None = None):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if course_id is not None and passage.course_id != course_id:
        return jsonify({'ok': False, 'message': 'Passage does not belong to the selected course.'}), 404
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        return jsonify({'ok': False, 'message': 'Passage unavailable.'}), 404

    payload = request.get_json(silent=True) or {}
    answers = payload.get('answers') or {}
    clean_answers = {str(key): str(value) for key, value in answers.items()}
    progress = int(payload.get('progress') or 0)
    elapsed_seconds = int(payload.get('elapsed_seconds') or 0)
    drafts = _session_drafts()
    drafts[_draft_key(passage_id)] = {
        'answers': clean_answers,
        'progress': progress,
        'elapsed_seconds': elapsed_seconds,
        'updated_at': int(time.time()),
    }
    _store_session_drafts(drafts)
    return jsonify({'ok': True, 'saved_at': drafts[_draft_key(passage_id)]['updated_at']})


@bp.route('/courses/<int:course_id>/reading/session/<int:passage_id>/autosave', methods=['POST'])
@login_required
@require_role('STUDENT')
def course_reading_autosave(course_id: int, passage_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        return jsonify({'ok': False, 'message': 'Course unavailable.'}), 404
    return _reading_autosave_response(passage_id, course.id)


@bp.route('/reading/session/<int:passage_id>/autosave', methods=['POST'])
@login_required
@require_role('STUDENT')
def reading_autosave(passage_id: int):
    return _reading_autosave_response(passage_id)



@bp.route('/courses/<int:course_id>/reading/session/<int:passage_id>/submit', methods=['POST'])
@login_required
@require_role('STUDENT')
def course_reading_submit(course_id: int, passage_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash('You are not enrolled in this course.', 'warning')
        return redirect(url_for('student.my_courses'))
    passage = ReadingPassage.query.get_or_404(passage_id)
    if (getattr(course, 'track_type', '') or '').strip().lower() != 'reading':
        flash('This course is not configured as a reading track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if passage.course_id != course.id:
        flash('This reading passage does not belong to the selected course.', 'warning')
        return redirect(url_for('student.course_reading_home', course_id=course.id))
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        flash('This reading passage is not available for submission.', 'warning')
        return redirect(url_for('student.course_reading_home', course_id=course.id))

    return _submit_reading_session(passage=passage, course=course)


@bp.route('/reading/session/<int:passage_id>/submit', methods=['POST'])
@login_required
@require_role('STUDENT')
def reading_submit(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        flash('This reading passage is not available for submission.', 'warning')
        return redirect(url_for('student.my_courses'))
    course = _student_enrolled_course(getattr(passage, 'course_id', None)) if getattr(passage, 'course_id', None) else None
    return _submit_reading_session(passage=passage, course=course)


@bp.route('/reading/session/<int:passage_id>/word-support', methods=['POST'])
@login_required
@require_role('STUDENT')
def reading_word_support(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if not (passage.is_active and passage.is_published and passage.status == ReadingPassage.STATUS_APPROVED):
        return jsonify({'ok': False, 'message': 'Passage unavailable.'}), 404

    payload = request.get_json(silent=True) or {}
    word = str(payload.get('word') or '').strip()
    sentence = str(payload.get('sentence') or '').strip()
    if not word:
        return jsonify({'ok': False, 'message': 'Select a word first.'}), 400

    translation_language_code, translation_language_name, translation_support_enabled = _reading_support_language_context()
    target_language = translation_language_name if translation_support_enabled else 'English'

    result = ReadingTranslationService.translate_word(
        word=word,
        sentence=sentence,
        target_language=target_language,
        target_language_code=translation_language_code,
    )

    response_payload = ReadingTranslationService.enrich_payload(
        result.payload,
        word=word,
        sentence=sentence,
        target_language_code=translation_language_code,
    )
    meaning = str(response_payload.get('meaning') or '').strip() or (sentence or f'A simple explanation for {word}.')
    synonym = str(response_payload.get('synonym') or '').strip() or 'Not available yet'
    translation = str(response_payload.get('translation') or '').strip()
    if not translation:
        translation = word if translation_language_code == 'en' else f'[{translation_language_code}] {word}'

    return jsonify({
        'ok': bool(result.ok),
        'word': word,
        'meaning': meaning,
        'synonym': synonym,
        'translation': translation,
        'provider_name': result.provider_name or 'Reading vocabulary helper',
        'target_language_code': translation_language_code,
        'target_language_label': target_language,
        'notebook_status': 'Vocabulary notebook save can be added next.',
        'message': result.message,
    })
