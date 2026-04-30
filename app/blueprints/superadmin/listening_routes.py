from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from . import bp
from ...extensions import db
from ...models.lms import Course, Level, Lesson, Chapter, Subsection, Question
from ...rbac import require_role
from ...services.listening_audio_service import ListeningAudioService
from ...services.listening_generation_service import ListeningGenerationService
from typing import Optional

LISTENING_TRACK_TYPES = ("listening",)
WORKFLOW_CHOICES = {"draft", "review", "published", "approved", "rejected", "pending", "live"}


def _safe_int(value, default=0, minimum: Optional[int] = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _question_generation_counts(form) -> dict:
    return {
        'short_answer_count': _safe_int(form.get('short_answer_count'), default=2, minimum=0),
        'fill_blank_count': _safe_int(form.get('fill_blank_count'), default=1, minimum=0),
        'true_false_count': _safe_int(form.get('true_false_count'), default=1, minimum=0),
    }


def _listening_course_rows():
    return (
        Course.query
        .filter(Course.status != "archived", Course.track_type.in_(LISTENING_TRACK_TYPES))
        .order_by(Course.title.asc())
        .all()
    )


def _ensure_listening_level(course: Course) -> Level:
    level = sorted(course.levels, key=lambda row: ((row.sort_order or 0), row.id))[0] if course.levels else None
    if level:
        return level
    level = Level(course_id=course.id, title="Level 1", description="Auto-created listening level", sort_order=1)
    db.session.add(level)
    db.session.flush()
    return level


def _ensure_listening_structure(lesson: Lesson) -> tuple[Chapter, Subsection]:
    chapter = sorted(lesson.chapters, key=lambda row: ((row.sort_order or 0), row.id))[0] if lesson.chapters else None
    if not chapter:
        chapter = Chapter(lesson_id=lesson.id, title="Listening Questions", description="Auto-created chapter", sort_order=1)
        db.session.add(chapter)
        db.session.flush()
    subsection = sorted(chapter.subsections, key=lambda row: ((row.sort_order or 0), row.id))[0] if chapter.subsections else None
    if not subsection:
        subsection = Subsection(chapter_id=chapter.id, title="Answer Set", sort_order=1)
        db.session.add(subsection)
        db.session.flush()
    return chapter, subsection


def _listening_lessons_query(selected_course_id: int = 0):
    query = (
        Lesson.query
        .join(Level, Level.id == Lesson.level_id)
        .join(Course, Course.id == Level.course_id)
        .filter(Course.track_type.in_(LISTENING_TRACK_TYPES), Lesson.lesson_type == 'listening')
        .order_by(Course.title.asc(), Level.sort_order.asc(), Lesson.sort_order.asc(), Lesson.id.desc())
    )
    if selected_course_id:
        query = query.filter(Course.id == selected_course_id)
    return query


@bp.get('/courses/<int:course_id>/listening')
@login_required
@require_role('SUPERADMIN')
def course_listening_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    if (course.track_type or '').strip().lower() not in LISTENING_TRACK_TYPES:
        flash('Please open this manager only for a listening course.', 'warning')
        return redirect(url_for('superadmin.course_detail', course_id=course.id))
    return redirect(url_for('superadmin.listening_topics', course_id=course.id))


@bp.get('/courses/<int:course_id>/listening/questions')
@login_required
@require_role('SUPERADMIN')
def course_listening_questions_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    if (course.track_type or '').strip().lower() not in LISTENING_TRACK_TYPES:
        flash('Please open this manager only for a listening course.', 'warning')
        return redirect(url_for('superadmin.course_detail', course_id=course.id))
    return redirect(url_for('superadmin.listening_questions', course_id=course.id))


@bp.get('/courses/<int:course_id>/listening/preview')
@login_required
@require_role('SUPERADMIN')
def course_listening_preview_manager(course_id: int):
    return redirect(url_for('superadmin.course_student_preview', course_id=course_id))


@bp.route('/listening/topics', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def listening_topics():
    selected_course_id = _safe_int(request.values.get('course_id'), default=0, minimum=0)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and (selected_course.track_type or '').strip().lower() not in LISTENING_TRACK_TYPES:
        flash('Please open listening topics from a listening course only.', 'warning')
        return redirect(url_for('superadmin.course_detail', course_id=selected_course.id))

    if request.method == 'POST':
        course_id = _safe_int(request.form.get('course_id'), default=0, minimum=0)
        course = Course.query.get(course_id) if course_id else None
        if not course or (course.track_type or '').strip().lower() not in LISTENING_TRACK_TYPES:
            flash('Select a valid listening course.', 'warning')
            return redirect(url_for('superadmin.courses'))
        title = (request.form.get('title') or '').strip()
        script = (request.form.get('script_text') or '').strip()
        estimated_minutes = _safe_int(request.form.get('estimated_minutes'), default=3, minimum=1)
        workflow_status = (request.form.get('workflow_status') or 'draft').strip().lower()
        if workflow_status not in WORKFLOW_CHOICES:
            workflow_status = 'draft'
        if not title:
            flash('Listening topic title is required.', 'warning')
            return redirect(url_for('superadmin.listening_topics', course_id=course.id))
        level = _ensure_listening_level(course)
        sort_order = len(level.lessons) + 1
        lesson = Lesson(
            level_id=level.id,
            title=title,
            slug='-'.join(title.lower().split())[:180] or None,
            lesson_type='listening',
            explanation_text=script,
            explanation_tts_text=script,
            estimated_minutes=estimated_minutes,
            is_published=(workflow_status in {'published', 'approved', 'live'}),
            workflow_status=workflow_status,
            sort_order=sort_order,
        )
        db.session.add(lesson)
        db.session.flush()
        _, subsection = _ensure_listening_structure(lesson)
        if not script:
            draft = ListeningGenerationService.build_script(course, lesson)
            lesson.explanation_text = draft.script_text
            lesson.explanation_tts_text = draft.script_text
            lesson.estimated_minutes = draft.estimated_minutes
        counts = _question_generation_counts(request.form)
        created_questions = ListeningGenerationService.sync_questions(lesson, subsection, replace_existing=False, **counts)
        db.session.commit()
        ListeningAudioService.ensure_audio(course, lesson)
        flash(f'Listening topic created. Script prepared and {created_questions} question(s) drafted.', 'success')
        return redirect(url_for('superadmin.listening_topic_edit', lesson_id=lesson.id))

    lessons = _listening_lessons_query(selected_course_id).all()
    lesson_rows = []
    for lesson in lessons:
        lesson.audio_ready = bool(ListeningAudioService.cached_exists(lesson.course, lesson))
        lesson_rows.append(lesson)
    return render_template('superadmin/listening_topics.html', lessons=lesson_rows, selected_course_id=selected_course_id, selected_course=selected_course, course_choices=_listening_course_rows(), duration_hint=ListeningGenerationService.target_minutes_for(selected_course, None) if selected_course else 3)


@bp.route('/listening/topics/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def listening_topic_edit(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course
    if not course or (course.track_type or '').strip().lower() not in LISTENING_TRACK_TYPES or (lesson.lesson_type or '').strip().lower() != 'listening':
        flash('Listening topic not found.', 'warning')
        return redirect(url_for('superadmin.courses'))
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        if not title:
            flash('Listening topic title is required.', 'warning')
            return redirect(url_for('superadmin.listening_topic_edit', lesson_id=lesson.id))
        lesson.title = title
        script = (request.form.get('script_text') or '').strip()
        lesson.estimated_minutes = _safe_int(request.form.get('estimated_minutes'), default=lesson.estimated_minutes or 3, minimum=1)
        if script:
            lesson.explanation_text = script
            lesson.explanation_tts_text = script
        workflow_status = (request.form.get('workflow_status') or 'draft').strip().lower()
        lesson.workflow_status = workflow_status if workflow_status in WORKFLOW_CHOICES else 'draft'
        lesson.is_published = lesson.workflow_status in {'published', 'approved', 'live'}
        db.session.commit()
        ListeningAudioService.ensure_audio(course, lesson)
        flash('Listening topic updated successfully.', 'success')
        return redirect(url_for('superadmin.listening_topics', course_id=course.id))
    return render_template('superadmin/listening_topic_edit.html', lesson=lesson, course=course)


@bp.post('/listening/topics/<int:lesson_id>/toggle')
@login_required
@require_role('SUPERADMIN')
def listening_topic_toggle(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.is_published = not bool(lesson.is_published)
    if lesson.is_published and (lesson.workflow_status or '').strip().lower() in {'draft', 'review', 'pending'}:
        lesson.workflow_status = 'published'
    db.session.commit()
    flash('Listening topic visibility updated.', 'success')
    return redirect(request.referrer or url_for('superadmin.listening_topics', course_id=lesson.course.id if lesson.course else None))


@bp.post('/listening/topics/<int:lesson_id>/submit-review')
@login_required
@require_role('SUPERADMIN')
def listening_topic_submit_review(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.workflow_status = 'review'
    lesson.is_published = False
    db.session.commit()
    flash('Listening topic moved to review.', 'success')
    return redirect(request.referrer or url_for('superadmin.listening_topics', course_id=lesson.course.id if lesson.course else None))


@bp.post('/listening/topics/<int:lesson_id>/publish')
@login_required
@require_role('SUPERADMIN')
def listening_topic_publish(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.workflow_status = 'published'
    lesson.is_published = True
    db.session.commit()
    flash('Listening topic published.', 'success')
    return redirect(request.referrer or url_for('superadmin.listening_topics', course_id=lesson.course.id if lesson.course else None))


@bp.post('/listening/topics/<int:lesson_id>/generate-script')
@login_required
@require_role('SUPERADMIN')
def listening_topic_generate_script(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    draft = ListeningGenerationService.build_script(lesson.course, lesson)
    lesson.explanation_text = draft.script_text
    lesson.explanation_tts_text = draft.script_text
    lesson.estimated_minutes = draft.estimated_minutes
    if (lesson.workflow_status or 'draft').strip().lower() == 'draft':
        lesson.workflow_status = 'review'
    db.session.commit()
    flash(f'AI script draft generated using {draft.provider_label}. Estimated duration: {draft.estimated_minutes} minute(s). Review and edit before publishing.', 'success')
    return redirect(request.referrer or url_for('superadmin.listening_topics', course_id=lesson.course.id if lesson.course else None))


@bp.post('/listening/topics/<int:lesson_id>/generate-draft')
@login_required
@require_role('SUPERADMIN')
def listening_topic_generate_draft(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    draft = ListeningGenerationService.build_script(lesson.course, lesson)
    lesson.explanation_text = draft.script_text
    lesson.explanation_tts_text = draft.script_text
    lesson.estimated_minutes = draft.estimated_minutes
    _, subsection = _ensure_listening_structure(lesson)
    counts = _question_generation_counts(request.form)
    created_questions = ListeningGenerationService.sync_questions(lesson, subsection, replace_existing=bool(request.form.get('replace_existing')), **counts)
    if (lesson.workflow_status or 'draft').strip().lower() == 'draft':
        lesson.workflow_status = 'review'
    db.session.commit()
    audio_path = ListeningAudioService.ensure_audio(lesson.course, lesson)
    audio_note = ' Audio draft created.' if audio_path else ' Audio generation skipped because server TTS is not available.'
    flash(f'Listening draft ready: script saved, {created_questions} written-answer questions generated.{audio_note}', 'success')
    return redirect(url_for('superadmin.listening_questions', course_id=lesson.course.id if lesson.course else 0, lesson_id=lesson.id))


@bp.post('/listening/topics/<int:lesson_id>/generate-audio')
@login_required
@require_role('SUPERADMIN')
def listening_topic_generate_audio(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    path = ListeningAudioService.ensure_audio(lesson.course, lesson)
    if path:
        flash('Listening audio generated and cached.', 'success')
    else:
        flash('Audio could not be generated because the script is empty or the server TTS engine failed.', 'warning')
    return redirect(request.referrer or url_for('superadmin.listening_topics', course_id=lesson.course.id if lesson.course else None))


@bp.post('/listening/topics/<int:lesson_id>/delete')
@login_required
@require_role('SUPERADMIN')
def listening_topic_delete(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.course.id if lesson.course else None
    db.session.delete(lesson)
    db.session.commit()
    flash('Listening topic deleted.', 'success')
    return redirect(url_for('superadmin.listening_topics', course_id=course_id))


@bp.route('/listening/questions', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def listening_questions():
    selected_course_id = _safe_int(request.values.get('course_id'), default=0, minimum=0)
    selected_lesson_id = _safe_int(request.values.get('lesson_id'), default=0, minimum=0)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None

    lesson_query = _listening_lessons_query(selected_course_id)
    lessons = lesson_query.all()
    selected_lesson = next((row for row in lessons if row.id == selected_lesson_id), None)
    if not selected_lesson and lessons:
        selected_lesson = lessons[0]
        selected_lesson_id = selected_lesson.id

    if request.method == 'POST':
        selected_lesson_id = _safe_int(request.form.get('lesson_id'), default=0, minimum=0)
        lesson = Lesson.query.get(selected_lesson_id) if selected_lesson_id else None
        if not lesson or (lesson.lesson_type or '').strip().lower() != 'listening':
            flash('Select a valid listening topic first.', 'warning')
            return redirect(url_for('superadmin.listening_questions', course_id=selected_course_id))
        _, subsection = _ensure_listening_structure(lesson)
        prompt = (request.form.get('prompt') or '').strip()
        answer = (request.form.get('model_answer') or '').strip()
        explanation = (request.form.get('explanation') or '').strip()
        if not prompt:
            flash('Question prompt is required.', 'warning')
            return redirect(url_for('superadmin.listening_questions', course_id=lesson.course.id, lesson_id=lesson.id))
        question = Question(
            subsection_id=subsection.id,
            prompt=prompt,
            prompt_type='listening',
            model_answer=answer,
            hint_text=explanation,
            expected_keywords=(request.form.get('expected_keywords') or '').strip() or None,
            answer_patterns_text='\n'.join([part for part in [answer, *(request.form.get('alt_answers') or '').splitlines()] if str(part).strip()]),
            evaluation_rubric='Listening answer check',
            answer_generation_status='done' if answer else 'pending',
            is_active=True,
            sort_order=len(subsection.questions) + 1,
        )
        db.session.add(question)
        db.session.commit()
        flash('Listening question created successfully.', 'success')
        return redirect(url_for('superadmin.listening_questions', course_id=lesson.course.id, lesson_id=lesson.id))

    question_rows = []
    if selected_lesson:
        for chapter in sorted(selected_lesson.chapters, key=lambda row: ((row.sort_order or 0), row.id)):
            for subsection in sorted(chapter.subsections, key=lambda row: ((row.sort_order or 0), row.id)):
                for question in sorted(subsection.questions, key=lambda row: ((row.sort_order or 0), row.id)):
                    question_rows.append(question)
    return render_template('superadmin/listening_questions.html', course_choices=_listening_course_rows(), selected_course_id=selected_course_id, selected_course=selected_course, lessons=lessons, selected_lesson=selected_lesson, question_rows=question_rows, generation_defaults={'short_answer_count': 2, 'fill_blank_count': 1, 'true_false_count': 1})


@bp.post('/listening/questions/generate/<int:lesson_id>')
@login_required
@require_role('SUPERADMIN')
def listening_questions_generate(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    _, subsection = _ensure_listening_structure(lesson)
    if not (lesson.explanation_tts_text or lesson.explanation_text or '').strip():
        draft = ListeningGenerationService.build_script(lesson.course, lesson)
        lesson.explanation_text = draft.script_text
        lesson.explanation_tts_text = draft.script_text
    counts = _question_generation_counts(request.form)
    created = ListeningGenerationService.sync_questions(lesson, subsection, replace_existing=bool(request.form.get('replace_existing')), **counts)
    if (lesson.workflow_status or 'draft').strip().lower() == 'draft':
        lesson.workflow_status = 'review'
    db.session.commit()
    flash(f'{created} listening questions generated from the current script.', 'success')
    return redirect(url_for('superadmin.listening_questions', course_id=lesson.course.id if lesson.course else 0, lesson_id=lesson.id))


@bp.route('/listening/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def listening_question_edit(question_id: int):
    question = Question.query.get_or_404(question_id)
    lesson = question.subsection.chapter.lesson if question.subsection and question.subsection.chapter else None
    if not lesson or (lesson.lesson_type or '').strip().lower() != 'listening':
        flash('Listening question not found.', 'warning')
        return redirect(url_for('superadmin.courses'))
    if request.method == 'POST':
        prompt = (request.form.get('prompt') or '').strip()
        if not prompt:
            flash('Question prompt is required.', 'warning')
            return redirect(url_for('superadmin.listening_question_edit', question_id=question.id))
        question.prompt = prompt
        question.model_answer = (request.form.get('model_answer') or '').strip() or None
        question.hint_text = (request.form.get('explanation') or '').strip() or None
        question.expected_keywords = (request.form.get('expected_keywords') or '').strip() or None
        question.answer_patterns_text = '\n'.join([part for part in [question.model_answer or '', *(request.form.get('alt_answers') or '').splitlines()] if str(part).strip()]) or None
        question.answer_generation_status = 'done' if question.model_answer else 'pending'
        db.session.commit()
        flash('Listening question updated successfully.', 'success')
        return redirect(url_for('superadmin.listening_questions', course_id=lesson.course.id if lesson.course else 0, lesson_id=lesson.id))
    return render_template('superadmin/listening_question_edit.html', question=question, lesson=lesson)


@bp.post('/listening/questions/<int:question_id>/toggle')
@login_required
@require_role('SUPERADMIN')
def listening_question_toggle(question_id: int):
    question = Question.query.get_or_404(question_id)
    question.is_active = not bool(question.is_active)
    db.session.commit()
    lesson = question.subsection.chapter.lesson
    return redirect(request.referrer or url_for('superadmin.listening_questions', course_id=lesson.course.id if lesson and lesson.course else 0, lesson_id=lesson.id if lesson else 0))


@bp.post('/listening/questions/<int:question_id>/delete')
@login_required
@require_role('SUPERADMIN')
def listening_question_delete(question_id: int):
    question = Question.query.get_or_404(question_id)
    lesson = question.subsection.chapter.lesson
    course_id = lesson.course.id if lesson and lesson.course else 0
    lesson_id = lesson.id if lesson else 0
    db.session.delete(question)
    db.session.commit()
    flash('Listening question deleted.', 'success')
    return redirect(url_for('superadmin.listening_questions', course_id=course_id, lesson_id=lesson_id))
