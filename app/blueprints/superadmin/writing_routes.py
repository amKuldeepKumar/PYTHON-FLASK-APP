from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from . import bp
from ...extensions import db
from ...models.lms import Course
from ...models.writing_task import WritingTask
from ...models.writing_topic import WritingTopic
from ...rbac import require_role
from ...services.language_service import language_choices

LEVEL_CHOICES = ("basic", "intermediate", "advanced")
TASK_TYPE_CHOICES = ("essay", "letter", "story", "paragraph")
DEFAULT_LANGUAGE_CHOICES = [("en", "English (en)")]


def _safe_int(value, default=0, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _normalize_code(raw: str | None) -> str:
    return (raw or "").strip().lower().replace(" ", "-")


def _writing_course_rows():
    return Course.query.filter(Course.status != "archived", Course.track_type == "writing").order_by(Course.title.asc()).all()


@bp.route("/writing/topics", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def writing_topics():
    selected_course_id = _safe_int(request.values.get("course_id"), default=0, minimum=0)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None

    if request.method == "POST":
        code = _normalize_code(request.form.get("code"))
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "").strip() or None
        level = (request.form.get("level") or "basic").strip().lower()
        description = (request.form.get("description") or "").strip() or None
        course_id = _safe_int(request.form.get("course_id"), default=0, minimum=0) or None
        course_level_number = _safe_int(request.form.get("course_level_number"), default=0, minimum=0) or None
        display_order = _safe_int(request.form.get("display_order"), default=0, minimum=0)
        is_active = bool(request.form.get("is_active"))
        is_published = bool(request.form.get("is_published"))

        errors = []
        if not code:
            errors.append("Topic code is required.")
        if not title:
            errors.append("Topic title is required.")
        if level not in LEVEL_CHOICES:
            errors.append("Please select a valid level.")
        course = Course.query.get(course_id) if course_id else None
        if not course_id:
            errors.append("Please open a writing course first. Writing topics now live only inside a course.")
        elif not course or (course.track_type or "").strip().lower() != "writing":
            errors.append("Please link writing topics only to writing courses.")
        elif course_level_number and course_level_number > max(int(getattr(course, "max_level", 1) or 1), 1):
            errors.append("Course level number is higher than the selected writing course max level.")
        if WritingTopic.query.filter_by(code=code).first():
            errors.append("A writing topic with this code already exists.")

        if errors:
            for message in errors:
                flash(message, "warning")
            return redirect(url_for("superadmin.writing_topics", course_id=course_id) if course_id else url_for("superadmin.courses"))

        topic = WritingTopic(
            code=code, title=title, category=category, level=level, description=description,
            course_id=course_id, course_level_number=course_level_number, display_order=display_order,
            is_active=is_active, is_published=is_published,
        )
        db.session.add(topic)
        db.session.commit()
        flash("Writing topic created successfully.", "success")
        return redirect(url_for("superadmin.writing_topics", course_id=course_id))

    topics = WritingTopic.query.filter_by(course_id=selected_course_id).order_by(WritingTopic.display_order.asc(), WritingTopic.title.asc()).all() if selected_course_id else []
    return render_template("superadmin/writing_topics.html", topics=topics, selected_course=selected_course, selected_course_id=selected_course_id, course_choices=_writing_course_rows(), level_choices=LEVEL_CHOICES)


@bp.route("/writing/topics/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def writing_topic_edit(topic_id: int):
    topic = WritingTopic.query.get_or_404(topic_id)
    if request.method == "POST":
        topic.title = (request.form.get("title") or topic.title).strip()
        topic.category = (request.form.get("category") or "").strip() or None
        topic.level = (request.form.get("level") or topic.level or "basic").strip().lower()
        topic.description = (request.form.get("description") or "").strip() or None
        topic.display_order = _safe_int(request.form.get("display_order"), default=topic.display_order or 0, minimum=0)
        topic.course_level_number = _safe_int(request.form.get("course_level_number"), default=topic.course_level_number or 0, minimum=0) or None
        topic.is_active = bool(request.form.get("is_active"))
        topic.is_published = bool(request.form.get("is_published"))
        db.session.commit()
        flash("Writing topic updated successfully.", "success")
        return redirect(url_for("superadmin.writing_topics", course_id=topic.course_id))
    return render_template("superadmin/writing_topic_edit.html", topic=topic, level_choices=LEVEL_CHOICES)


@bp.post("/writing/topics/<int:topic_id>/toggle")
@login_required
@require_role("SUPERADMIN")
def writing_topic_toggle(topic_id: int):
    topic = WritingTopic.query.get_or_404(topic_id)
    topic.is_active = not bool(topic.is_active)
    db.session.commit()
    flash("Writing topic status updated.", "success")
    return redirect(url_for("superadmin.writing_topics", course_id=topic.course_id))


@bp.post("/writing/topics/<int:topic_id>/delete")
@login_required
@require_role("SUPERADMIN")
def writing_topic_delete(topic_id: int):
    topic = WritingTopic.query.get_or_404(topic_id)
    course_id = topic.course_id
    db.session.delete(topic)
    db.session.commit()
    flash("Writing topic deleted successfully.", "success")
    return redirect(url_for("superadmin.writing_topics", course_id=course_id))


@bp.route("/writing/tasks", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def writing_tasks():
    selected_course_id = _safe_int(request.values.get("course_id"), default=0, minimum=0)
    selected_topic_id = _safe_int(request.values.get("topic_id"), default=0, minimum=0)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None

    if request.method == "POST":
        topic_id = _safe_int(request.form.get("topic_id"), default=0, minimum=0)
        topic = WritingTopic.query.get(topic_id) if topic_id else None
        title = (request.form.get("title") or "").strip()
        instructions = (request.form.get("instructions") or "").strip()
        task_type = (request.form.get("task_type") or "essay").strip().lower()
        level = (request.form.get("level") or getattr(topic, "level", "basic")).strip().lower()
        min_words = _safe_int(request.form.get("min_words"), default=80, minimum=0)
        max_words = _safe_int(request.form.get("max_words"), default=0, minimum=0) or None
        language_code = (request.form.get("language_code") or "en").strip().lower() or "en"
        display_order = _safe_int(request.form.get("display_order"), default=0, minimum=0)
        is_active = bool(request.form.get("is_active"))
        is_published = bool(request.form.get("is_published"))
        course_level_number = _safe_int(request.form.get("course_level_number"), default=0, minimum=0) or None

        errors = []
        if not topic:
            errors.append("Please select a writing topic.")
        if not title:
            errors.append("Task title is required.")
        if not instructions:
            errors.append("Task instructions are required.")
        if task_type not in TASK_TYPE_CHOICES:
            errors.append("Please select a valid writing task type.")
        if max_words is not None and max_words > 0 and min_words > 0 and max_words <= min_words:
            errors.append("Maximum words must be greater than minimum words.")

        if errors:
            for message in errors:
                flash(message, "warning")
            return redirect(url_for("superadmin.writing_tasks", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0))

        task = WritingTask(
            topic_id=topic.id,
            topic_title_snapshot=topic.title,
            title=title,
            instructions=instructions,
            task_type=task_type,
            level=level,
            min_words=min_words,
            max_words=max_words,
            language_code=language_code,
            course_id=topic.course_id,
            course_level_number=course_level_number,
            display_order=display_order,
            is_active=is_active,
            is_published=is_published,
        )
        db.session.add(task)
        db.session.commit()
        flash("Writing task created successfully.", "success")
        return redirect(url_for("superadmin.writing_tasks", course_id=task.course_id, topic_id=task.topic_id))

    topic_query = WritingTopic.query
    if selected_course_id:
        topic_query = topic_query.filter_by(course_id=selected_course_id)
    topics = topic_query.order_by(WritingTopic.display_order.asc(), WritingTopic.title.asc()).all()

    task_query = WritingTask.query
    if selected_course_id:
        task_query = task_query.filter_by(course_id=selected_course_id)
    if selected_topic_id:
        task_query = task_query.filter_by(topic_id=selected_topic_id)
    tasks = task_query.order_by(WritingTask.display_order.asc(), WritingTask.title.asc()).all()

    return render_template("superadmin/writing_tasks.html", tasks=tasks, topics=topics, selected_course=selected_course, selected_course_id=selected_course_id, selected_topic_id=selected_topic_id, course_choices=_writing_course_rows(), level_choices=LEVEL_CHOICES, task_type_choices=TASK_TYPE_CHOICES, language_choices=language_choices(enabled_only=True, include_codes=True) or DEFAULT_LANGUAGE_CHOICES)


@bp.route("/writing/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def writing_task_edit(task_id: int):
    task = WritingTask.query.get_or_404(task_id)
    if request.method == "POST":
        task.title = (request.form.get("title") or task.title).strip()
        task.instructions = (request.form.get("instructions") or task.instructions).strip()
        task.task_type = (request.form.get("task_type") or task.task_type or "essay").strip().lower()
        task.level = (request.form.get("level") or task.level or "basic").strip().lower()
        task.min_words = _safe_int(request.form.get("min_words"), default=task.min_words or 80, minimum=0)
        task.max_words = _safe_int(request.form.get("max_words"), default=task.max_words or 0, minimum=0) or None
        task.language_code = (request.form.get("language_code") or task.language_code or "en").strip().lower() or "en"
        task.display_order = _safe_int(request.form.get("display_order"), default=task.display_order or 0, minimum=0)
        task.course_level_number = _safe_int(request.form.get("course_level_number"), default=task.course_level_number or 0, minimum=0) or None
        task.is_active = bool(request.form.get("is_active"))
        task.is_published = bool(request.form.get("is_published"))
        if task.max_words is not None and task.max_words > 0 and task.min_words > 0 and task.max_words <= task.min_words:
            flash("Maximum words must be greater than minimum words.", "warning")
            return redirect(url_for("superadmin.writing_task_edit", task_id=task.id))
        db.session.commit()
        flash("Writing task updated successfully.", "success")
        return redirect(url_for("superadmin.writing_tasks", course_id=task.course_id, topic_id=task.topic_id))
    return render_template("superadmin/writing_task_edit.html", task=task, level_choices=LEVEL_CHOICES, task_type_choices=TASK_TYPE_CHOICES, language_choices=language_choices(enabled_only=True, include_codes=True) or DEFAULT_LANGUAGE_CHOICES)


@bp.post("/writing/tasks/<int:task_id>/toggle")
@login_required
@require_role("SUPERADMIN")
def writing_task_toggle(task_id: int):
    task = WritingTask.query.get_or_404(task_id)
    task.is_active = not bool(task.is_active)
    db.session.commit()
    flash("Writing task status updated.", "success")
    return redirect(url_for("superadmin.writing_tasks", course_id=task.course_id, topic_id=task.topic_id))


@bp.post("/writing/tasks/<int:task_id>/delete")
@login_required
@require_role("SUPERADMIN")
def writing_task_delete(task_id: int):
    task = WritingTask.query.get_or_404(task_id)
    course_id = task.course_id
    topic_id = task.topic_id
    db.session.delete(task)
    db.session.commit()
    flash("Writing task deleted successfully.", "success")
    return redirect(url_for("superadmin.writing_tasks", course_id=course_id, topic_id=topic_id))
