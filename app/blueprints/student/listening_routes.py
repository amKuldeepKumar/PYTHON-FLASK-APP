from __future__ import annotations

from datetime import datetime
import re
from sqlalchemy import and_

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from . import bp
from ...extensions import db
from ...services.student_ai_intelligence import StudentAIIntelligenceService
from ...services.listening_audio_service import ListeningAudioService
from ...models.lms import Course, Enrollment, Lesson, LessonProgress, Question, QuestionAttempt, CourseProgress
from ...rbac import require_role




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


@bp.route('/listening', methods=['GET'])
@login_required
@require_role('STUDENT')
def listening_home_redirect():
    courses = _student_enrolled_track_courses('listening')
    if len(courses) == 1:
        return redirect(url_for('student.course_listening_home', course_id=courses[0].id))
    return render_template(
        'student/track_portal.html',
        track_label='Listening',
        track_key='listening',
        courses=[{'course': course} for course in courses],
        open_endpoint='student.course_listening_home',
        subtitle='The listening route now stays fully inside the themed student panel instead of showing a raw 404 page.',
        fallback_description='Train audio focus, replay control, and answer accuracy with guided listening lessons.',
        published_count=len(courses),
    )
def _student_enrolled_course(course_id: int) -> Course | None:
    enrollment = (
        Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
    )
    return enrollment.course if enrollment and enrollment.course else None


def _listening_lessons(course: Course) -> list[Lesson]:
    rows: list[Lesson] = []
    for level in sorted(course.levels, key=lambda row: ((row.sort_order or 0), row.id)):
        for lesson in sorted(level.lessons, key=lambda row: ((row.sort_order or 0), row.id)):
            if (lesson.lesson_type or '').strip().lower() != 'listening':
                continue
            if not getattr(lesson, 'is_published', True):
                continue
            workflow = (lesson.workflow_status or 'draft').strip().lower()
            if workflow not in {'approved', 'published', 'live'}:
                continue
            rows.append(lesson)
    return rows


def _recent_listening_cooldown_ids(course: Course, limit: int = 2) -> set[int]:
    lesson_ids = [lesson.id for lesson in _listening_lessons(course)]
    if not lesson_ids:
        return set()
    recent = (
        LessonProgress.query.filter(
            LessonProgress.student_id == current_user.id,
            LessonProgress.lesson_id.in_(lesson_ids),
            LessonProgress.completed_at.isnot(None),
        )
        .order_by(LessonProgress.completed_at.desc(), LessonProgress.id.desc())
        .limit(limit)
        .all()
    )
    return {row.lesson_id for row in recent}


def _listening_config(course: Course, lesson: Lesson):
    return ListeningAudioService.build_config(course, lesson)


def _listening_hidden_metrics(form) -> dict:
    def _to_int(value, default=0):
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default
    return {
        'time_spent': _to_int(form.get('listening_time_spent'), 0),
        'replay_count': _to_int(form.get('listening_replay_count'), 0),
        'play_count': _to_int(form.get('listening_play_count'), 0),
        'heard_audio': str(form.get('listening_started_audio') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
    }


def _listening_questions(lesson: Lesson) -> list[Question]:
    rows: list[Question] = []
    for chapter in sorted(lesson.chapters, key=lambda row: ((row.sort_order or 0), row.id)):
        for subsection in sorted(chapter.subsections, key=lambda row: ((row.sort_order or 0), row.id)):
            for question in sorted(subsection.questions, key=lambda row: ((row.sort_order or 0), row.id)):
                if getattr(question, 'is_active', True):
                    rows.append(question)
    return rows


def _normalized_text(value: str | None) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (value or '').strip().lower())
    return ' '.join(cleaned.split())


def _question_expected_answers(question: Question) -> list[str]:
    answers: list[str] = []
    for value in [question.model_answer, *question.answer_patterns_list]:
        norm = _normalized_text(value)
        if norm and norm not in answers:
            answers.append(norm)
    return answers


def _grade_answer(question: Question, answer_text: str) -> tuple[bool, float, str]:
    answer_norm = _normalized_text(answer_text)
    if not answer_norm:
        return False, 0.0, 'No answer submitted.'

    accepted = _question_expected_answers(question)
    if answer_norm and answer_norm in accepted:
        return True, 100.0, 'Exact answer match.'

    keywords = [_normalized_text(part) for part in (question.expected_keywords or '').split(',') if _normalized_text(part)]
    if keywords:
        matched = sum(1 for kw in keywords if kw in answer_norm)
        ratio = matched / len(keywords)
        if ratio >= 0.8:
            return True, round(70 + (ratio * 30), 1), 'Keyword match is strong.'
        if ratio >= 0.4:
            return False, round(35 + (ratio * 30), 1), 'Partial keyword match. Review the answer.'

    if accepted:
        best = max((len(set(answer_norm.split()) & set(candidate.split())) / max(1, len(set(candidate.split())))) for candidate in accepted)
        if best >= 0.75:
            return True, round(70 + (best * 20), 1), 'Close answer match.'
        if best >= 0.4:
            return False, round(30 + (best * 25), 1), 'Partially correct. Review the key words.'

    return False, 0.0, 'Answer does not match the expected response yet.'


def _lesson_progress_row(student_id: int, lesson: Lesson) -> LessonProgress:
    row = LessonProgress.query.filter_by(student_id=student_id, lesson_id=lesson.id).first()
    if row:
        return row
    row = LessonProgress(student_id=student_id, lesson_id=lesson.id)
    db.session.add(row)
    return row


def _course_progress_row(student_id: int, course: Course) -> CourseProgress:
    row = CourseProgress.query.filter_by(student_id=student_id, course_id=course.id).first()
    if row:
        return row
    row = CourseProgress(student_id=student_id, course_id=course.id)
    db.session.add(row)
    return row


def _update_progress(course: Course, lesson: Lesson, correct: int, total: int) -> None:
    lesson_row = _lesson_progress_row(current_user.id, lesson)
    lesson_row.total_questions = total
    lesson_row.completed_questions = correct
    lesson_row.completion_percent = int(round((correct / max(1, total)) * 100)) if total else 0
    lesson_row.last_activity_at = datetime.utcnow()
    lesson_row.completed_at = datetime.utcnow()

    course_row = _course_progress_row(current_user.id, course)
    lesson_ids = [item.id for level in course.levels for item in level.lessons]
    progress_rows = LessonProgress.query.filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id.in_(lesson_ids) if lesson_ids else False,
    ).all() if lesson_ids else []
    course_row.total_lessons = len(lesson_ids)
    course_row.completed_lessons = sum(1 for row in progress_rows if (row.completion_percent or 0) >= 100)
    course_row.total_questions = sum(int(row.total_questions or 0) for row in progress_rows)
    course_row.completed_questions = sum(int(row.completed_questions or 0) for row in progress_rows)
    accuracy = 0.0
    if progress_rows:
        accuracy = sum(float(row.completion_percent or 0) for row in progress_rows) / len(progress_rows)
    course_row.average_accuracy = round(accuracy, 1)
    course_row.completion_percent = int(round((course_row.completed_lessons / max(1, course_row.total_lessons)) * 100)) if course_row.total_lessons else 0
    course_row.last_activity_at = datetime.utcnow()


def _listening_result_payload(lesson: Lesson) -> dict | None:
    attempts = (
        QuestionAttempt.query.filter_by(student_id=current_user.id, lesson_id=lesson.id, attempt_kind='final')
        .order_by(QuestionAttempt.attempted_at.desc(), QuestionAttempt.id.desc())
        .limit(max(1, lesson.question_count or 1))
        .all()
    )
    if not attempts:
        return None
    attempts_by_question = {}
    for attempt in attempts:
        attempts_by_question.setdefault(attempt.question_id, attempt)
    rows = []
    correct = 0
    for question in _listening_questions(lesson):
        attempt = attempts_by_question.get(question.id)
        if not attempt:
            continue
        is_correct = bool(attempt.is_correctish)
        if is_correct:
            correct += 1
        rows.append({
            'question': question,
            'your_answer': attempt.response_text or '',
            'correct_answer': (question.model_answer or (question.answer_patterns_list[0] if question.answer_patterns_list else '—')),
            'feedback': attempt.ai_feedback or '',
            'is_correct': is_correct,
        })
    if not rows:
        return None
    total = len(rows)
    return {
        'correct': correct,
        'total': total,
        'accuracy': int(round((correct / max(1, total)) * 100)),
        'rows': rows,
        'show_answers_allowed': True,
    }


@bp.route('/courses/<int:course_id>/listening', methods=['GET'])
@login_required
@require_role('STUDENT')
def course_listening_home(course_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash('You are not enrolled in this course.', 'warning')
        return redirect(url_for('student.my_courses'))

    if (getattr(course, 'track_type', '') or '').strip().lower() != 'listening':
        flash('This course is not configured as a listening track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))

    cooldown_ids = _recent_listening_cooldown_ids(course)
    lesson_rows: list[dict] = []
    for lesson in _listening_lessons(course):
        questions = _listening_questions(lesson)
        if not questions:
            continue
        script = (lesson.explanation_tts_text or lesson.explanation_text or '').strip()
        config = _listening_config(course, lesson)
        lesson_rows.append({
            'review_status': (lesson.workflow_status or 'draft').title(),
            'cooldown': lesson.id in cooldown_ids,
            'lesson': lesson,
            'level_number': getattr(getattr(lesson, 'level', None), 'sort_order', 1) or 1,
            'script': script,
            'question_count': len(questions),
            'replay_limit': config.replay_limit,
            'estimated_seconds': max(45, min(1200, (len(script.split()) or 40) * 2)),
            'has_ready_audio': bool(ListeningAudioService.audio_url(course, lesson)),
            'topic_label': lesson.title,
        })

    return render_template(
        'student/listening_home.html',
        course=course,
        lesson_rows=lesson_rows,
        total_lessons=len(lesson_rows),
        intelligence_track=StudentAIIntelligenceService.for_track(current_user.id, 'listening'),
    )


@bp.get('/courses/<int:course_id>/listening/lesson/<int:lesson_id>/audio')
@login_required
@require_role('STUDENT')
def course_listening_audio(course_id: int, lesson_id: int):
    course = _student_enrolled_course(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    if not course or lesson.level.course_id != course.id:
        abort(404)
    audio_path = ListeningAudioService.ensure_audio(course, lesson)
    if not audio_path:
        abort(404)
    return send_file(audio_path, mimetype='audio/wav', max_age=3600)


@bp.route('/courses/<int:course_id>/listening/lesson/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
@require_role('STUDENT')
def course_listening_session(course_id: int, lesson_id: int):
    course = _student_enrolled_course(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    if course and (getattr(course, 'track_type', '') or '').strip().lower() != 'listening':
        flash('This course is not configured as a listening track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if not course or lesson.level.course_id != course.id:
        flash('Listening lesson not found.', 'warning')
        return redirect(url_for('student.my_courses'))

    questions = _listening_questions(lesson)
    script_text = (lesson.explanation_tts_text or lesson.explanation_text or '').strip()
    script_segments = [segment.strip() for segment in script_text.splitlines() if segment.strip()]
    estimated_seconds = max(45, min(1200, (len(script_text.split()) or 40) * 2))
    
    playback_config = _listening_config(course, lesson)
    if request.method == 'GET':
        ListeningAudioService.ensure_audio(course, lesson)

    audio_ready = bool(ListeningAudioService.audio_url(course, lesson))
    audio_url = url_for('student.course_listening_audio', course_id=course.id, lesson_id=lesson.id) if audio_ready else None
    result = None

    show_answers = str(request.values.get('show_answers') or '').strip().lower() in {'1', 'true', 'yes', 'on'}

    if request.method == 'POST':
        metrics = _listening_hidden_metrics(request.form)
        if not metrics['heard_audio'] and audio_url:
            flash('Play the listening audio at least once before submitting.', 'warning')
            result = _listening_result_payload(lesson)
        else:
            correct = 0
            total = len(questions)
            for question in questions:
                answer = (request.form.get(f'answer_{question.id}') or '').strip()
                is_correct, score, feedback = _grade_answer(question, answer)
                if is_correct:
                    correct += 1
                db.session.add(QuestionAttempt(
                    student_id=current_user.id,
                    question_id=question.id,
                    lesson_id=lesson.id,
                    chapter_id=question.subsection.chapter_id if question.subsection else None,
                    subsection_id=question.subsection_id,
                    response_text=answer,
                    response_mode='typed',
                    attempt_kind='final',
                    accuracy_score=score,
                    ai_feedback=feedback,
                    is_correctish=is_correct,
                    duration_seconds=metrics['time_spent'],
                    support_tools_json=str({
                        'listening': {
                            'replay_count': metrics['replay_count'],
                            'play_count': metrics['play_count'],
                            'heard_audio': metrics['heard_audio'],
                        }
                    }),
                ))
            _update_progress(course, lesson, correct, len(questions))
            lesson_row = _lesson_progress_row(current_user.id, lesson)
            lesson_row.support_tool_usage_count = metrics['replay_count']
            lesson_row.retry_questions = max(0, metrics['play_count'] - 1)
            lesson_row.last_activity_at = datetime.utcnow()
            db.session.commit()
            result = _listening_result_payload(lesson)
            flash('Listening answers submitted successfully.', 'success')
    else:
        result = _listening_result_payload(lesson)

    answer_map = {}
    for row in (result or {}).get('rows', []):
        answer_map[row['question'].id] = row['your_answer']

    return render_template(
        'student/listening_session.html',
        course=course,
        lesson=lesson,
        script_text=script_text,
        script_segments=script_segments,
        estimated_seconds=estimated_seconds,
        questions=questions,
        answer_map=answer_map,
        replay_limit=playback_config.replay_limit,
        listening_audio_url=audio_url,
        allowed_speeds=playback_config.allowed_speeds,
        caption_default=playback_config.caption_default,
        caption_locked=playback_config.caption_locked,
        listening_result=result,
        show_answers=show_answers,
    )
