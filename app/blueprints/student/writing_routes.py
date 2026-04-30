from __future__ import annotations

import json

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from ...extensions import db
from ...models.lms import Course, Enrollment
from ...models.writing_submission import WritingSubmission
from ...services.student_ai_intelligence import StudentAIIntelligenceService
from ...models.writing_task import WritingTask
from ...models.writing_topic import WritingTopic
from ...rbac import require_role
from ...services.writing import evaluate_writing_submission




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


@bp.route('/writing', methods=['GET'])
@login_required
@require_role('STUDENT')
def writing_home_redirect():
    courses = _student_enrolled_track_courses('writing')
    if len(courses) == 1:
        return redirect(url_for('student.course_writing_home', course_id=courses[0].id))
    return render_template(
        'student/track_portal.html',
        track_label='Writing',
        track_key='writing',
        courses=[{'course': course} for course in courses],
        open_endpoint='student.course_writing_home',
        subtitle='Your writing route now opens inside the student theme with direct access to enrolled writing courses.',
        fallback_description='Practice structured answers, tasks, and topic writing inside one guided flow.',
        published_count=len(courses),
    )
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


def _level_allowed(enrollment: Enrollment | None, level_number: int | None) -> bool:
    if not enrollment:
        return False
    return enrollment.has_level_access(level_number)


def _evaluate_writing(text: str, task: WritingTask | None, topic: WritingTopic | None = None) -> tuple[float, str, str, dict]:
    return evaluate_writing_submission(text=text, task=task, topic=topic)


def _normalized_submission_text(value: str) -> str:
    import re
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", (value or "").strip().lower()).split())


def _recent_duplicate_submission(course_id: int, task_id: int | None, topic_id: int | None, normalized_text: str) -> WritingSubmission | None:
    if not normalized_text:
        return None
    rows = (
        WritingSubmission.query
        .filter_by(student_id=current_user.id, course_id=course_id, task_id=task_id, topic_id=topic_id)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .limit(5)
        .all()
    )
    for row in rows:
        if _normalized_submission_text(row.submission_text) == normalized_text:
            return row
    return None


def _integrity_payload(form) -> dict:
    def _to_int(name: str) -> int:
        try:
            return max(0, int(form.get(name) or 0))
        except Exception:
            return 0
    return {
        'paste_count': _to_int('paste_count'),
        'largest_paste_chars': _to_int('largest_paste_chars'),
        'focus_loss_count': _to_int('focus_loss_count'),
        'draft_seconds': _to_int('draft_seconds'),
    }


def _resume_writing_target(course: Course, tasks: list[WritingTask], topics: list[WritingTopic]):
    latest = (
        WritingSubmission.query
        .filter_by(student_id=current_user.id, course_id=course.id)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .first()
    )
    if latest and latest.task_id:
        task = next((item for item in tasks if item.id == latest.task_id), None)
        if task:
            return url_for("student.course_writing_task", course_id=course.id, task_id=task.id)
    if latest and latest.topic_id:
        topic = next((item for item in topics if item.id == latest.topic_id), None)
        if topic:
            return url_for("student.course_writing_topic_workspace", course_id=course.id, topic_id=topic.id)
    if tasks:
        return url_for("student.course_writing_task", course_id=course.id, task_id=tasks[0].id)
    if topics:
        return url_for("student.course_writing_topic_workspace", course_id=course.id, topic_id=topics[0].id)
    return None


@bp.route("/courses/<int:course_id>/writing", methods=["GET"])
@login_required
@require_role("STUDENT")
def course_writing_home(course_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash("You are not enrolled in this course.", "warning")
        return redirect(url_for("student.my_courses"))

    if (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))

    enrollment = _student_course_enrollment(course.id)

    topics = [
        topic for topic in (getattr(course, 'writing_topics', []) or [])
        if bool(getattr(topic, 'is_active', False))
        and bool(getattr(topic, 'is_published', False))
        and _level_allowed(enrollment, getattr(topic, 'course_level_number', None))
    ]

    tasks = [
        task for task in (getattr(course, 'writing_tasks', []) or [])
        if bool(getattr(task, 'is_active', False))
        and bool(getattr(task, 'is_published', False))
        and bool(getattr(getattr(task, 'topic', None), 'is_active', False))
        and bool(getattr(getattr(task, 'topic', None), 'is_published', False))
        and bool((getattr(task, 'instructions', '') or '').strip())
        and _level_allowed(enrollment, getattr(task, 'course_level_number', None))
    ]

    resume_url = _resume_writing_target(course, tasks, topics)
    if resume_url:
        return redirect(resume_url)

    recent_submissions = (
        WritingSubmission.query
        .filter_by(student_id=current_user.id, course_id=course.id)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "student/writing_home.html",
        course=course,
        topics=topics,
        tasks=tasks,
        recent_submissions=recent_submissions,
        intelligence_track=StudentAIIntelligenceService.for_track(current_user.id, 'writing'),
    )

@bp.route("/courses/<int:course_id>/writing/topic/<int:topic_id>", methods=["GET"])
@login_required
@require_role("STUDENT")
def course_writing_topic_workspace(course_id: int, topic_id: int):
    course = _student_enrolled_course(course_id)
    topic = WritingTopic.query.get_or_404(topic_id)

    if not course:
        flash("You are not enrolled in this course.", "warning")
        return redirect(url_for("student.my_courses"))

    if (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))

    if topic.course_id != course.id:
        flash("Writing topic not found.", "warning")
        return redirect(url_for("student.course_writing_home", course_id=course.id))

    enrollment = _student_course_enrollment(course.id)
    if not _level_allowed(enrollment, getattr(topic, 'course_level_number', None)):
        flash("This writing level is locked in your plan.", "warning")
        return redirect(
            url_for(
                "student.course_checkout",
                course_id=course.id,
                purchase_scope="single_level",
                level=getattr(topic, 'course_level_number', 1) or 1,
            )
        )

    latest_submission = (
        WritingSubmission.query
        .filter_by(student_id=current_user.id, course_id=course.id, topic_id=topic.id, task_id=None)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .first()
    )

    recent_submissions = (
        WritingSubmission.query
        .filter_by(student_id=current_user.id, course_id=course.id, topic_id=topic.id)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "student/writing_topic_workspace.html",
        course=course,
        topic=topic,
        latest_submission=latest_submission,
        recent_submissions=recent_submissions,
    )


@bp.route("/courses/<int:course_id>/writing/task/<int:task_id>", methods=["GET"])
@login_required
@require_role("STUDENT")
def course_writing_task(course_id: int, task_id: int):
    course = _student_enrolled_course(course_id)
    task = WritingTask.query.get_or_404(task_id)
    if course and (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if not course or task.course_id != course.id:
        flash("Writing task not found.", "warning")
        return redirect(url_for("student.my_courses"))
    if not (bool(getattr(task, 'is_active', False)) and bool(getattr(task, 'is_published', False)) and bool((getattr(task, 'instructions', '') or '').strip())):
        flash("This writing task is not published for students yet.", "warning")
        return redirect(url_for("student.course_writing_home", course_id=course.id))
    enrollment = _student_course_enrollment(course.id)
    if not _level_allowed(enrollment, getattr(task, 'course_level_number', None)):
        flash("This writing level is locked in your plan.", "warning")
        return redirect(url_for("student.course_checkout", course_id=course.id, purchase_scope="single_level", level=getattr(task, 'course_level_number', 1) or 1))
    latest_submission = WritingSubmission.query.filter_by(student_id=current_user.id, task_id=task.id).order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc()).first()
    return render_template("student/writing_task.html", course=course, task=task, latest_submission=latest_submission)

@bp.post("/courses/<int:course_id>/writing/topic/<int:topic_id>/submit")
@login_required
@require_role("STUDENT")
def course_writing_topic_submit(course_id: int, topic_id: int):
    course = _student_enrolled_course(course_id)
    topic = WritingTopic.query.get_or_404(topic_id)

    if not course:
        flash("You are not enrolled in this course.", "warning")
        return redirect(url_for("student.my_courses"))

    if (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))

    if topic.course_id != course.id:
        flash("Writing topic not found.", "warning")
        return redirect(url_for("student.course_writing_home", course_id=course.id))

    enrollment = _student_course_enrollment(course.id)
    if not _level_allowed(enrollment, getattr(topic, 'course_level_number', None)):
        flash("This writing level is locked in your plan.", "warning")
        return redirect(
            url_for(
                "student.course_checkout",
                course_id=course.id,
                purchase_scope="single_level",
                level=getattr(topic, 'course_level_number', 1) or 1,
            )
        )

    submission_text = (request.form.get("submission_text") or "").strip()
    if not submission_text:
        flash("Please write your answer before submitting.", "warning")
        return redirect(url_for("student.course_writing_topic_workspace", course_id=course.id, topic_id=topic.id))

    normalized_text = _normalized_submission_text(submission_text)
    if _recent_duplicate_submission(course.id, None, topic.id, normalized_text):
        flash("This answer matches your recent submission. Improve or rewrite it before submitting again.", "warning")
        return redirect(url_for("student.course_writing_topic_workspace", course_id=course.id, topic_id=topic.id))

    pseudo_task = type("TopicTask", (), {"min_words": 0, "max_words": 0, "title": getattr(topic, "title", ""), "instructions": getattr(topic, "description", ""), "level": getattr(topic, "level", "basic"), "task_type": "paragraph"})()
    score, feedback_text, evaluation_summary, metrics = _evaluate_writing(submission_text, pseudo_task, topic=topic)
    integrity = _integrity_payload(request.form)
    metric_values = (metrics or {}).get('metrics', metrics or {})
    if isinstance(metrics, dict):
        metrics['integrity'] = integrity

    submission = WritingSubmission(
        student_id=current_user.id,
        course_id=course.id,
        topic_id=topic.id,
        task_id=None,
        submission_text=submission_text,
        word_count=int(metric_values.get('word_count') or 0),
        char_count=int(metric_values.get('char_count') or 0),
        paragraph_count=int(metric_values.get('paragraph_count') or 0),
        sentence_count=int(metric_values.get('sentence_count') or 0),
        score=score,
        feedback_text=feedback_text,
        evaluation_summary=evaluation_summary,
        evaluation_payload=json.dumps(metrics),
        status=WritingSubmission.STATUS_SUBMITTED,
    )
    db.session.add(submission)
    db.session.commit()

    flash("Writing submitted successfully.", "success")
    return redirect(url_for("student.course_writing_result", course_id=course.id, submission_id=submission.id))


@bp.post("/courses/<int:course_id>/writing/task/<int:task_id>/submit")
@login_required
@require_role("STUDENT")
def course_writing_submit(course_id: int, task_id: int):
    course = _student_enrolled_course(course_id)
    task = WritingTask.query.get_or_404(task_id)
    if course and (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if not course or task.course_id != course.id:
        flash("Writing task not found.", "warning")
        return redirect(url_for("student.my_courses"))
    if not (bool(getattr(task, 'is_active', False)) and bool(getattr(task, 'is_published', False)) and bool((getattr(task, 'instructions', '') or '').strip())):
        flash("This writing task is not published for students yet.", "warning")
        return redirect(url_for("student.course_writing_home", course_id=course.id))

    submission_text = (request.form.get("submission_text") or "").strip()
    if not submission_text:
        flash("Please write your answer before submitting.", "warning")
        return redirect(url_for("student.course_writing_task", course_id=course.id, task_id=task.id))

    normalized_text = _normalized_submission_text(submission_text)
    if _recent_duplicate_submission(course.id, task.id, task.topic_id, normalized_text):
        flash("This answer matches your recent submission. Improve or rewrite it before submitting again.", "warning")
        return redirect(url_for("student.course_writing_task", course_id=course.id, task_id=task.id))

    score, feedback_text, evaluation_summary, metrics = _evaluate_writing(submission_text, task, topic=task.topic)
    integrity = _integrity_payload(request.form)
    metric_values = (metrics or {}).get('metrics', metrics or {})
    if isinstance(metrics, dict):
        metrics['integrity'] = integrity
    submission = WritingSubmission(
        student_id=current_user.id,
        course_id=course.id,
        topic_id=task.topic_id,
        task_id=task.id,
        submission_text=submission_text,
        word_count=int(metric_values.get('word_count') or 0),
        char_count=int(metric_values.get('char_count') or 0),
        paragraph_count=int(metric_values.get('paragraph_count') or 0),
        sentence_count=int(metric_values.get('sentence_count') or 0),
        score=score,
        feedback_text=feedback_text,
        evaluation_summary=evaluation_summary,
        evaluation_payload=json.dumps(metrics),
        status=WritingSubmission.STATUS_SUBMITTED,
    )
    db.session.add(submission)
    db.session.commit()
    flash("Writing submitted successfully.", "success")
    return redirect(url_for("student.course_writing_result", course_id=course.id, submission_id=submission.id))


@bp.route("/courses/<int:course_id>/writing/submissions", methods=["GET"])
@login_required
@require_role("STUDENT")
def course_writing_history(course_id: int):
    course = _student_enrolled_course(course_id)
    if not course:
        flash("You are not enrolled in this course.", "warning")
        return redirect(url_for("student.my_courses"))
    if (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    submissions = WritingSubmission.query.filter_by(student_id=current_user.id, course_id=course.id).order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc()).all()
    return render_template("student/writing_history.html", course=course, submissions=submissions)


@bp.route("/courses/<int:course_id>/writing/submissions/<int:submission_id>", methods=["GET"])
@login_required
@require_role("STUDENT")
def course_writing_result(course_id: int, submission_id: int):
    course = _student_enrolled_course(course_id)
    submission = WritingSubmission.query.get_or_404(submission_id)
    if course and (getattr(course, 'track_type', '') or '').strip().lower() != 'writing':
        flash('This course is not configured as a writing track.', 'warning')
        return redirect(url_for('student.course_detail', course_id=course.id))
    if not course or submission.course_id != course.id or submission.student_id != current_user.id:
        flash("Writing result not found.", "warning")
        return redirect(url_for("student.my_courses"))
    return render_template("student/writing_result.html", course=course, submission=submission)
