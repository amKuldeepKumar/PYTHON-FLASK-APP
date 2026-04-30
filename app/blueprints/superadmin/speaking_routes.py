from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from . import bp
from ...extensions import db
from ...models.speaking_prompt import SpeakingPrompt
from ...models.speaking_topic import SpeakingTopic
from ...models.lms import Course
from ...rbac import require_role
from ...services.language_service import language_choices


LEVEL_CHOICES = ("basic", "intermediate", "advanced")
ACCESS_TYPE_CHOICES = ("free", "paid", "coupon")
COUPON_DISCOUNT_TYPE_CHOICES = ("percent", "flat")
DEFAULT_LANGUAGE_CHOICES = [("en", "English (en)")]
SPEAKING_TRACK_TYPES = ("speaking", "spoken", "topic", "interview")


def _superadmin_topic_query():
    return SpeakingTopic.query.filter(SpeakingTopic.owner_admin_id.is_(None))


def _superadmin_prompt_query():
    return SpeakingPrompt.query.filter(SpeakingPrompt.owner_admin_id.is_(None))


def _speaking_course_rows():
    return (
        Course.query
        .filter(Course.status != "archived", Course.track_type.in_(SPEAKING_TRACK_TYPES))
        .order_by(Course.title.asc())
        .all()
    )


def _safe_int(value, default=0, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _safe_float(value, *, default: float | None = None) -> float | None:
    text = (value or "").strip() if isinstance(value, str) else value
    if text in (None, ""):
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_topic_code(raw: str | None) -> str:
    return (raw or "").strip().lower().replace(" ", "-")


def _parse_topic_form(existing_topic: SpeakingTopic | None = None):
    code = _normalize_topic_code(request.form.get("code") if existing_topic is None else existing_topic.code)
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    level = (request.form.get("level") or "basic").strip().lower()
    language_code = (request.form.get("language_code") or "en").strip().lower() or "en"
    display_order = _safe_int(request.form.get("display_order"), default=0, minimum=0)
    course_id = _safe_int(request.form.get("course_id") or request.args.get("course_id"), default=0, minimum=0) or None
    course_level_number = _safe_int(request.form.get("course_level_number"), default=0, minimum=0) or None

    is_active = bool(request.form.get("is_active"))
    is_published = bool(request.form.get("is_published"))

    access_type = (request.form.get("access_type") or "free").strip().lower()
    currency = ((request.form.get("currency") or "INR").strip().upper() or "INR")

    price = _safe_float(request.form.get("price"), default=0)
    discount_price = _safe_float(request.form.get("discount_price"), default=None)

    coupon_enabled = bool(request.form.get("coupon_enabled"))
    coupon_code = (request.form.get("coupon_code") or "").strip() or None
    coupon_discount_type = (request.form.get("coupon_discount_type") or "").strip().lower() or None
    coupon_discount_value = _safe_float(request.form.get("coupon_discount_value"), default=None)
    coupon_valid_from = (request.form.get("coupon_valid_from") or "").strip() or None
    coupon_valid_until = (request.form.get("coupon_valid_until") or "").strip() or None

    errors: list[str] = []

    if existing_topic is None and not code:
        errors.append("Topic code is required.")
    if not title:
        errors.append("Topic title is required.")
    if level not in LEVEL_CHOICES:
        errors.append("Please select a valid level.")
    if access_type not in ACCESS_TYPE_CHOICES:
        errors.append("Please select a valid access type.")
    if price is None:
        errors.append("Invalid price value.")
    if request.form.get("discount_price", "").strip() and discount_price is None:
        errors.append("Invalid discount price value.")
    if request.form.get("coupon_discount_value", "").strip() and coupon_discount_value is None:
        errors.append("Invalid coupon discount value.")

    course = Course.query.get(course_id) if course_id else None
    if not course_id:
        errors.append("Please open a speaking course first. Speaking topics now live only inside a course.")
    else:
        track_type = ((getattr(course, "track_type", "") or "").strip().lower() if course else "")
        if not course or track_type not in SPEAKING_TRACK_TYPES:
            errors.append("Please link speaking topics only to speaking courses.")
        elif course_level_number and course_level_number > max(int(getattr(course, "max_level", 1) or 1), 1):
            errors.append("Course level number is higher than the selected speaking course max level.")

    if access_type == "free":
        price = 0
        discount_price = None
        coupon_enabled = False
        coupon_code = None
        coupon_discount_type = None
        coupon_discount_value = None
        coupon_valid_from = None
        coupon_valid_until = None
    elif access_type == "paid":
        if (price or 0) <= 0:
            errors.append("Premium topics must have a price greater than 0.")
        if discount_price is not None and price is not None and discount_price > price:
            errors.append("Discount price cannot be greater than price.")
        if coupon_enabled:
            if not coupon_code:
                errors.append("Coupon code is required when coupon support is enabled.")
            if coupon_discount_type not in COUPON_DISCOUNT_TYPE_CHOICES:
                errors.append("Coupon discount type must be percent or flat.")
            if coupon_discount_value is None or coupon_discount_value <= 0:
                errors.append("Coupon discount value must be greater than 0.")
        else:
            coupon_code = None
            coupon_discount_type = None
            coupon_discount_value = None
            coupon_valid_from = None
            coupon_valid_until = None
    elif access_type == "coupon":
        coupon_enabled = True
        if not coupon_code:
            errors.append("Coupon code is required for coupon-based topics.")
        if coupon_discount_type not in COUPON_DISCOUNT_TYPE_CHOICES:
            errors.append("Coupon discount type must be percent or flat.")
        if coupon_discount_value is None or coupon_discount_value <= 0:
            errors.append("Coupon discount value must be greater than 0.")

    return {
        "code": code,
        "title": title,
        "description": description,
        "level": level,
        "language_code": language_code,
        "display_order": display_order,
        "course_id": course_id,
        "course_level_number": course_level_number,
        "is_active": is_active,
        "is_published": is_published,
        "access_type": access_type,
        "currency": currency,
        "price": price or 0,
        "discount_price": discount_price,
        "coupon_enabled": coupon_enabled,
        "coupon_code": coupon_code,
        "coupon_discount_type": coupon_discount_type,
        "coupon_discount_value": coupon_discount_value,
        "coupon_valid_from": coupon_valid_from,
        "coupon_valid_until": coupon_valid_until,
    }, errors




@bp.get("/courses/<int:course_id>/speaking")
@login_required
@require_role("SUPERADMIN")
def course_speaking_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track_type = ((getattr(course, "track_type", "") or "").strip().lower())
    if track_type not in SPEAKING_TRACK_TYPES:
        flash("Please open this manager only for a speaking course.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=course.id))
    return redirect(url_for("superadmin.speaking_topics", course_id=course.id))


@bp.get("/courses/<int:course_id>/speaking/prompts")
@login_required
@require_role("SUPERADMIN")
def course_speaking_prompts_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track_type = ((getattr(course, "track_type", "") or "").strip().lower())
    if track_type not in SPEAKING_TRACK_TYPES:
        flash("Please open this manager only for a speaking course.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=course.id))
    return redirect(url_for("superadmin.speaking_prompts", course_id=course.id))


@bp.get("/courses/<int:course_id>/speaking/preview")
@login_required
@require_role("SUPERADMIN")
def course_speaking_preview_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track_type = ((getattr(course, "track_type", "") or "").strip().lower())
    if track_type not in SPEAKING_TRACK_TYPES:
        flash("Please open this preview only for a speaking course.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=course.id))
    return redirect(url_for("superadmin.course_student_preview", course_id=course.id))


@bp.route("/speaking/topics", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_topics():
    selected_course_id = _safe_int(request.values.get("course_id"), default=0, minimum=0)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and ((selected_course.track_type or "").strip().lower() not in SPEAKING_TRACK_TYPES):
        flash("Please open speaking topics from a speaking course only.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=selected_course.id))

    if request.method == "POST":
        payload, errors = _parse_topic_form()
        exists = _superadmin_topic_query().filter(SpeakingTopic.code == payload["code"]).first()
        if exists:
            errors.append("A topic with this code already exists.")
        if errors:
            for message in errors:
                flash(message, "warning")
            if payload.get("course_id"):
                return redirect(url_for("superadmin.speaking_topics", course_id=payload.get("course_id")))
            return redirect(url_for("superadmin.courses"))

        topic = SpeakingTopic(owner_admin_id=None, **payload)
        db.session.add(topic)
        db.session.commit()
        flash("Speaking topic created successfully.", "success")
        return redirect(url_for("superadmin.speaking_topics", course_id=topic.course_id))

    topics_query = _superadmin_topic_query().order_by(SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc())
    if selected_course_id:
        topics_query = topics_query.filter(SpeakingTopic.course_id == selected_course_id)
    topics = topics_query.all()
    course_choices = _speaking_course_rows()
    return render_template(
        "superadmin/speaking_topics.html",
        topics=topics,
        selected_course=selected_course,
        selected_course_id=selected_course_id,
        level_choices=LEVEL_CHOICES,
        access_type_choices=ACCESS_TYPE_CHOICES,
        coupon_discount_type_choices=COUPON_DISCOUNT_TYPE_CHOICES,
        language_choices=language_choices(enabled_only=True, include_codes=True) or DEFAULT_LANGUAGE_CHOICES,
        course_choices=course_choices,
    )


@bp.route("/speaking/topics/<int:topic_id>/toggle", methods=["POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_topic_toggle(topic_id):
    topic = _superadmin_topic_query().filter(SpeakingTopic.id == topic_id).first_or_404()
    topic.is_active = not bool(topic.is_active)
    db.session.commit()
    flash("Topic status updated.", "success")
    return redirect(url_for("superadmin.speaking_topics", course_id=topic.course_id) if topic.course_id else url_for("superadmin.courses"))




@bp.route("/speaking/topics/<int:topic_id>/publish", methods=["POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_topic_publish(topic_id):
    topic = _superadmin_topic_query().filter(SpeakingTopic.id == topic_id).first_or_404()
    topic.is_published = not bool(topic.is_published)
    if topic.is_published and not topic.is_active:
        topic.is_active = True
    db.session.commit()
    flash("Topic publication updated.", "success")
    return redirect(url_for("superadmin.speaking_topics", course_id=topic.course_id) if topic.course_id else url_for("superadmin.courses"))


@bp.route("/speaking/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_topic_delete(topic_id):
    topic = _superadmin_topic_query().filter(SpeakingTopic.id == topic_id).first_or_404()
    course_id = topic.course_id
    db.session.delete(topic)
    db.session.commit()
    flash("Topic deleted successfully.", "success")
    return redirect(url_for("superadmin.speaking_topics", course_id=course_id) if course_id else url_for("superadmin.courses"))


@bp.route("/speaking/topics/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_topic_edit(topic_id):
    topic = _superadmin_topic_query().filter(SpeakingTopic.id == topic_id).first_or_404()
    back_course_id = _safe_int(request.args.get("course_id"), default=0, minimum=0) or topic.course_id
    if request.method == "GET" and not topic.course_id:
        flash("This speaking topic is active/published, but it is not linked to any course yet. Link a course here to make it appear inside Course Content Manager.", "warning")
    if request.method == "POST":
        payload, errors = _parse_topic_form(existing_topic=topic)
        if errors:
            for message in errors:
                flash(message, "warning")
            return redirect(url_for("superadmin.speaking_topic_edit", topic_id=topic.id))

        for key, value in payload.items():
            if key != 'code':
                setattr(topic, key, value)
        db.session.commit()
        flash("Topic updated successfully.", "success")
        return redirect(url_for("superadmin.speaking_topics", course_id=topic.course_id) if topic.course_id else url_for("superadmin.courses"))

    course_choices = _speaking_course_rows()
    return render_template(
        "superadmin/speaking_topic_edit.html",
        topic=topic,
        back_course_id=back_course_id,
        level_choices=LEVEL_CHOICES,
        access_type_choices=ACCESS_TYPE_CHOICES,
        coupon_discount_type_choices=COUPON_DISCOUNT_TYPE_CHOICES,
        language_choices=language_choices(enabled_only=True, include_codes=True) or DEFAULT_LANGUAGE_CHOICES,
        course_choices=course_choices,
    )


@bp.route("/speaking/prompts", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_prompts():
    selected_course_id = _safe_int(request.values.get("course_id"), default=0, minimum=0)
    selected_topic_id = request.values.get("topic_id", type=int)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and ((selected_course.track_type or "").strip().lower() not in SPEAKING_TRACK_TYPES):
        flash("Please open speaking prompts from a speaking course only.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=selected_course.id))

    topics_query = _superadmin_topic_query()
    if selected_course_id:
        topics_query = topics_query.filter(SpeakingTopic.course_id == selected_course_id)
    topics = topics_query.order_by(SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc()).all()

    if request.method == "POST":
        topic_id = request.form.get("topic_id", type=int)
        title = (request.form.get("title") or "").strip()
        prompt_text = (request.form.get("prompt_text") or "").strip()
        instruction_text = (request.form.get("instruction_text") or "").strip() or None
        difficulty = (request.form.get("difficulty") or "basic").strip().lower()
        estimated_seconds = _safe_int(request.form.get("estimated_seconds"), default=60, minimum=15)
        target_duration_seconds = _safe_int(request.form.get("target_duration_seconds"), default=estimated_seconds, minimum=15)
        min_duration_seconds = _safe_int(request.form.get("min_duration_seconds"), default=max(10, int(round(target_duration_seconds * 0.5))), minimum=5)
        max_duration_seconds = _safe_int(request.form.get("max_duration_seconds"), default=max(target_duration_seconds, int(round(target_duration_seconds * 1.5))), minimum=target_duration_seconds)
        display_order = _safe_int(request.form.get("display_order"), default=0, minimum=0)
        is_active = bool(request.form.get("is_active"))

        topic = _superadmin_topic_query().filter(SpeakingTopic.id == topic_id).first()
        if not topic:
            flash("Please select a valid topic.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0))
        if not title:
            flash("Prompt title is required.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0, topic_id=topic_id))
        if not prompt_text:
            flash("Prompt text is required.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0, topic_id=topic_id))
        if difficulty not in LEVEL_CHOICES:
            flash("Please select a valid difficulty.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0, topic_id=topic_id))
        if min_duration_seconds > target_duration_seconds:
            flash("Minimum time cannot be greater than target time.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0, topic_id=topic_id))
        if max_duration_seconds < target_duration_seconds:
            flash("Maximum time cannot be less than target time.", "warning")
            return redirect(url_for("superadmin.speaking_prompts", course_id=selected_course_id or getattr(topic, 'course_id', None) or 0, topic_id=topic_id))

        prompt = SpeakingPrompt(
            owner_admin_id=None,
            topic_id=topic.id,
            title=title,
            prompt_text=prompt_text,
            instruction_text=instruction_text,
            difficulty=difficulty,
            estimated_seconds=target_duration_seconds,
            target_duration_seconds=target_duration_seconds,
            min_duration_seconds=min_duration_seconds,
            max_duration_seconds=max_duration_seconds,
            display_order=display_order,
            is_active=is_active,
        )
        db.session.add(prompt)
        if not topic.is_active:
            topic.is_active = True
        if not topic.is_published:
            topic.is_published = True
        db.session.commit()
        flash("Speaking prompt created successfully.", "success")
        return redirect(url_for("superadmin.speaking_prompts", course_id=topic.course_id or 0, topic_id=topic.id))

    prompts_query = SpeakingPrompt.query.join(SpeakingTopic, SpeakingTopic.id == SpeakingPrompt.topic_id).filter(
        SpeakingPrompt.owner_admin_id.is_(None),
        SpeakingTopic.owner_admin_id.is_(None),
    )
    if selected_course_id:
        prompts_query = prompts_query.filter(SpeakingTopic.course_id == selected_course_id)
    if selected_topic_id:
        prompts_query = prompts_query.filter(SpeakingPrompt.topic_id == selected_topic_id)
    prompts = prompts_query.order_by(
        SpeakingTopic.display_order.asc(),
        SpeakingPrompt.display_order.asc(),
        SpeakingPrompt.title.asc(),
    ).all()

    return render_template(
        "superadmin/speaking_prompts.html",
        prompts=prompts,
        topics=topics,
        selected_course=selected_course,
        selected_course_id=selected_course_id,
        selected_topic_id=selected_topic_id,
        level_choices=LEVEL_CHOICES,
        course_choices=_speaking_course_rows(),
    )


@bp.route("/speaking/prompts/<int:prompt_id>/toggle", methods=["POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_prompt_toggle(prompt_id):
    prompt = _superadmin_prompt_query().filter(SpeakingPrompt.id == prompt_id).first_or_404()
    prompt.is_active = not bool(prompt.is_active)
    db.session.commit()
    flash("Prompt status updated.", "success")
    return redirect(url_for("superadmin.speaking_prompts", course_id=getattr(prompt.topic, 'course_id', None) or 0, topic_id=prompt.topic_id))
