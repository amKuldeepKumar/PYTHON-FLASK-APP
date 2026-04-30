from __future__ import annotations

import base64
import binascii
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from . import bp
from .forms import ChangePasswordForm, PreferencesForm, ProfileForm
from ...audit import audit
from ...extensions import db
from ...models.language import Language
from ...models.login_event import LoginEvent
from ...models.notification import Notification
from ...models.security_policy import SecurityPolicy
from ...models.user_preferences import UserPreferences
from ...models.user import User, Role
from ...models.lms import Course, Enrollment
from ...models.user_session import UserSession
from ...services.language_service import ensure_default_languages, language_choices, language_label, resolve_language_code
from ...services.session_service import get_current_session_row, revoke_other_sessions, revoke_session_for_user, sync_device_preferences
from ...services.tenancy_service import validate_student_linkage, apply_student_ownership

ACCENT_OPTIONS = {
    "en": [("en-IN", "Indian English"), ("en-GB", "British English"), ("en-US", "American English"), ("en-AU", "Australian English")],
    "hi": [("hi-IN", "Hindi (India)")],
    "pa": [("pa-IN", "Punjabi (India)")],
}

ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
MAX_PROFILE_PHOTO_BYTES = 4 * 1024 * 1024


def _ensure_default_languages():
    ensure_default_languages(enable_all=True)


def _ensure_user_preferences():
    if getattr(current_user, "preferences", None):
        return current_user.preferences
    prefs = UserPreferences(
        user_id=current_user.id,
        ui_language_code="en",
        learning_language_code="en",
        translation_support_language_code=(getattr(current_user, "native_language", None) or "en"),
        use_native_language_support=True,
        accent="en-IN",
        preferred_study_time=current_user.preferred_study_time,
        welcome_voice_mode="once",
        auto_play_question=True,
        auto_start_listening=True,
        question_beep_enabled=True,
        playback_speed=1.0,
        voice_pitch=1.0,
        voice_gender="female",
    )
    db.session.add(prefs)
    db.session.commit()
    return prefs


def _seed_default_notifications_for_user(user):
    try:
        if Notification.query.filter_by(user_id=user.id).count() > 0:
            return
    except SQLAlchemyError:
        db.session.rollback()
        db.create_all()
        if Notification.query.filter_by(user_id=user.id).count() > 0:
            return
    try:
        db.session.add(
            Notification(
                user_id=user.id,
                title="Preferences ready",
                message="Choose your language and accent in Preferences.",
                category="student",
                link_path="/account/preferences",
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        db.create_all()


def _student_active_courses_for_profile():
    if not getattr(current_user, "is_authenticated", False) or not getattr(current_user, "is_student", False):
        return []
    enrollments = (
        Enrollment.query.join(Course, Course.id == Enrollment.course_id)
        .filter(Enrollment.student_id == current_user.id, Enrollment.status == "active")
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    rows = []
    for enrollment in enrollments:
        course = enrollment.course
        if not course:
            continue
        rows.append({
            "course": course,
            "enrolled_at": enrollment.enrolled_at,
            "lesson_count": getattr(course, "lesson_count", 0) or 0,
            "question_count": getattr(course, "question_count", 0) or 0,
        })
    return rows


def _profile_photo_folder() -> Path:
    root = Path(current_app.root_path) / "static" / "uploads" / "profile_photos"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_profile_upload(file_storage) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError("Only JPG, JPEG, PNG, and WEBP images are allowed.")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_PROFILE_PHOTO_BYTES:
        raise ValueError("Profile photo must be smaller than 4 MB.")

    new_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = _profile_photo_folder() / new_name
    file_storage.save(save_path)
    return f"/static/uploads/profile_photos/{new_name}"


def _save_camera_image(data_url: str) -> str | None:
    if not data_url:
        return None
    match = data_url.split(",", 1)
    if len(match) != 2:
        raise ValueError("Camera image format is invalid.")

    header, raw = match
    header = header.lower()
    if "image/jpeg" in header or "image/jpg" in header:
        ext = "jpg"
    elif "image/png" in header:
        ext = "png"
    elif "image/webp" in header:
        ext = "webp"
    else:
        raise ValueError("Camera photo format is not supported.")

    try:
        binary = base64.b64decode(raw)
    except (binascii.Error, ValueError):
        raise ValueError("Camera photo could not be decoded.")

    if len(binary) > MAX_PROFILE_PHOTO_BYTES:
        raise ValueError("Camera photo must be smaller than 4 MB.")

    new_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = _profile_photo_folder() / new_name
    save_path.write_bytes(binary)
    return f"/static/uploads/profile_photos/{new_name}"


def _handle_profile_photo_post() -> tuple[str | None, bool]:
    remove_avatar = request.form.get("remove_avatar") == "1"
    if remove_avatar:
        return None, True

    file_storage = request.files.get("avatar_file")
    camera_image = (request.form.get("camera_image") or "").strip()

    if file_storage and getattr(file_storage, "filename", ""):
        return _save_profile_upload(file_storage), False
    if camera_image:
        return _save_camera_image(camera_image), False
    return current_user.avatar_url, False




def _institute_choices() -> list[tuple[int, str]]:
    rows = (
        User.query.filter(User.role.in_([Role.ADMIN.value, Role.SUB_ADMIN.value]), User.is_active.is_(True))
        .order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast(), User.created_at.desc())
        .all()
    )
    choices = [(0, "Independent Learner")]
    seen = set()
    for row in rows:
        if row.role == Role.SUB_ADMIN.value and row.organization_id:
            continue
        label = (row.organization_name or row.full_name or row.username).strip()
        if row.id in seen or not label:
            continue
        seen.add(row.id)
        choices.append((row.id, label))
    return choices


def _teacher_catalog() -> list[dict]:
    rows = (
        User.query.filter(User.role == Role.TEACHER.value, User.is_active.is_(True))
        .order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast(), User.created_at.desc())
        .all()
    )
    items = [{"id": 0, "label": "Not assigned yet", "organization_id": 0}]
    for row in rows:
        org_id = int(row.organization_id or 0)
        org_name = row.organization_name or (row.organization.organization_name if row.organization else None) or (row.organization.full_name if row.organization else None)
        label = row.full_name
        if org_name:
            label = f"{label} • {org_name}"
        items.append({"id": row.id, "label": label, "organization_id": org_id})
    return items


def _teacher_choices_for_profile(selected_org_id: int | None) -> tuple[list[tuple[int, str]], list[dict]]:
    catalog = _teacher_catalog()
    org_id = int(selected_org_id or 0)
    if org_id:
        filtered = [row for row in catalog if row["id"] == 0 or row["organization_id"] == org_id]
    else:
        filtered = [row for row in catalog if row["id"] == 0 or row["organization_id"] == 0]
    return [(row["id"], row["label"]) for row in filtered], catalog

@bp.get("/profile")
@bp.post("/profile")
@login_required
def profile():
    form = ProfileForm()
    prefs = _ensure_user_preferences()
    native_choices = [("", "Select native language")] + language_choices(enabled_only=True, include_codes=False)
    form.native_language.choices = native_choices
    form.organization_id.choices = _institute_choices()
    selected_org_id = current_user.organization_id or 0
    if request.method == "POST":
        selected_org_id = form.organization_id.data or 0
    form.teacher_id.choices, teacher_catalog = _teacher_choices_for_profile(selected_org_id)

    if request.method == "GET":
        for field in [
            "first_name",
            "last_name",
            "father_name",
            "phone",
            "country",
            "state",
            "city",
            "address",
            "target_score",
            "bio",
            "study_goal",
        ]:
            getattr(form, field).data = getattr(current_user, field)
        form.native_language.data = resolve_language_code(current_user.native_language, default="") if current_user.native_language else ""
        form.organization_id.data = current_user.organization_id or 0
        form.teacher_id.data = current_user.teacher_id or 0
        form.gender.data = current_user.gender or ""
        form.date_of_birth.data = current_user.date_of_birth
        form.target_exam.data = current_user.target_exam or ""
        form.current_level.data = current_user.current_level or ""
        form.preferred_study_time.data = current_user.preferred_study_time or ""

    if form.validate_on_submit():
        for field in [
            "first_name",
            "last_name",
            "father_name",
            "phone",
            "country",
            "state",
            "city",
            "address",
            "target_score",
            "bio",
            "study_goal",
        ]:
            setattr(current_user, field, (getattr(form, field).data or "").strip() or None)
        current_user.native_language = resolve_language_code(form.native_language.data, default="") or None

        selected_org_id = int(form.organization_id.data or 0)
        selected_teacher_id = int(form.teacher_id.data or 0)
        teacher = User.query.get(selected_teacher_id) if selected_teacher_id else None
        if teacher and teacher.role != Role.TEACHER.value:
            flash("Selected teacher is invalid.", "danger")
            return render_template(
                "account/profile.html",
                form=form,
                completion=current_user.profile_completion_percent(),
                next_steps=current_user.profile_next_steps(),
                onboarding=request.args.get("onboarding") == "1",
                prefs=prefs,
                teacher_catalog=teacher_catalog,
                active_courses=_student_active_courses_for_profile(),
            )
        if selected_org_id and teacher and int(teacher.organization_id or 0) != selected_org_id:
            flash("Selected teacher does not belong to the chosen institute.", "danger")
            return render_template(
                "account/profile.html",
                form=form,
                completion=current_user.profile_completion_percent(),
                next_steps=current_user.profile_next_steps(),
                onboarding=request.args.get("onboarding") == "1",
                prefs=prefs,
                teacher_catalog=teacher_catalog,
                active_courses=_student_active_courses_for_profile(),
            )

        current_user.organization_id = selected_org_id or None
        current_user.teacher_id = selected_teacher_id or None
        if current_user.organization_id:
            org_user = User.query.get(current_user.organization_id)
            current_user.admin_id = current_user.organization_id
            current_user.organization_name = (org_user.organization_name if org_user else None) or (org_user.full_name if org_user else None)
        else:
            current_user.admin_id = None
            current_user.organization_name = None

        current_user.gender = form.gender.data or None
        current_user.date_of_birth = form.date_of_birth.data or None
        current_user.target_exam = form.target_exam.data or None
        current_user.current_level = form.current_level.data or None
        current_user.preferred_study_time = form.preferred_study_time.data or None

        try:
            avatar_path, removed = _handle_profile_photo_post()
            current_user.avatar_url = None if removed else avatar_path
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "account/profile.html",
                form=form,
                completion=current_user.profile_completion_percent(),
                next_steps=current_user.profile_next_steps(),
                onboarding=request.args.get("onboarding") == "1",
                prefs=prefs,
                teacher_catalog=teacher_catalog,
                active_courses=_student_active_courses_for_profile(),
            )

        if not current_user.needs_student_onboarding() and current_user.profile_completed_at is None:
            current_user.profile_completed_at = datetime.utcnow()

        if current_user.preferred_study_time and not prefs.preferred_study_time:
            prefs.preferred_study_time = current_user.preferred_study_time

        db.session.commit()
        audit("profile_update", target=str(current_user.id))
        flash("Profile updated.", "success")
        return redirect(url_for("student.dashboard") if request.args.get("onboarding") == "1" else url_for("account.profile"))

    return render_template(
        "account/profile.html",
        form=form,
        completion=current_user.profile_completion_percent(),
        next_steps=current_user.profile_next_steps(),
        onboarding=request.args.get("onboarding") == "1",
        prefs=prefs,
        teacher_catalog=teacher_catalog,
        active_courses=_student_active_courses_for_profile(),
    )


@bp.get("/preferences")
@bp.post("/preferences")
@login_required
def preferences():
    _ensure_default_languages()
    prefs = _ensure_user_preferences()
    enabled_langs = Language.query.filter_by(is_enabled=True).order_by(Language.name.asc()).all()
    choices = [(l.code, f"{l.name} ({l.code})") for l in enabled_langs]

    form = PreferencesForm()
    form.ui_language_code.choices = choices
    form.learning_language_code.choices = choices
    form.translation_support_language_code.choices = choices

    selected_learning = (request.form.get("learning_language_code") or prefs.learning_language_code or "en").strip().lower()
    accent_choices = ACCENT_OPTIONS.get(selected_learning, [(f"{selected_learning}-standard", "Standard")])
    form.accent.choices = accent_choices

    def _bounded_float(value, default, lower, upper):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = float(default)
        return max(lower, min(upper, numeric))

    if request.method == "GET":
        form.ui_language_code.data = prefs.ui_language_code
        form.learning_language_code.data = prefs.learning_language_code
        form.translation_support_language_code.data = getattr(prefs, "translation_support_language_code", None) or current_user.native_language or "en"
        form.use_native_language_support.data = getattr(prefs, "use_native_language_support", True)
        form.speaking_speed.data = prefs.speaking_speed
        form.playback_speed.data = getattr(prefs, "playback_speed", 1.0)
        form.voice_pitch.data = getattr(prefs, "voice_pitch", 1.0)
        form.accent.data = prefs.accent or accent_choices[0][0]
        form.voice_gender.data = getattr(prefs, "voice_gender", "female") or "female"
        form.autoplay_voice.data = getattr(prefs, "autoplay_voice", True)
        form.dark_mode.data = getattr(prefs, "dark_mode", True)
        form.voice_name.data = prefs.voice_name
        form.preferred_study_time.data = prefs.preferred_study_time or current_user.preferred_study_time
        form.notify_email.data = prefs.notify_email
        form.notify_push.data = prefs.notify_push
        form.allow_ml_training.data = getattr(prefs, "allow_ml_training", False)
        form.welcome_voice_mode.data = prefs.welcome_voice_mode or "once"
        form.auto_play_question.data = getattr(prefs, "auto_play_question", True)
        form.auto_start_listening.data = getattr(prefs, "auto_start_listening", True)
        form.question_beep_enabled.data = getattr(prefs, "question_beep_enabled", True)

    if form.validate_on_submit():
        prefs.ui_language_code = form.ui_language_code.data
        prefs.learning_language_code = (form.learning_language_code.data or "en").strip().lower()
        prefs.translation_support_language_code = (form.translation_support_language_code.data or current_user.native_language or "en").strip().lower()
        prefs.use_native_language_support = bool(form.use_native_language_support.data)
        prefs.speaking_speed = _bounded_float(form.speaking_speed.data, 1.0, 0.5, 2.0)
        prefs.playback_speed = _bounded_float(form.playback_speed.data, 1.0, 0.5, 2.0)
        prefs.voice_pitch = _bounded_float(form.voice_pitch.data, 1.0, 0.5, 1.8)
        allowed_accents = {code for code, _label in ACCENT_OPTIONS.get(prefs.learning_language_code, accent_choices)}
        requested_accent = (form.accent.data or "").strip()
        prefs.accent = requested_accent if requested_accent in allowed_accents else accent_choices[0][0]
        prefs.voice_gender = form.voice_gender.data or "female"
        prefs.autoplay_voice = bool(form.autoplay_voice.data)
        prefs.dark_mode = bool(form.dark_mode.data)
        prefs.voice_name = (form.voice_name.data or "").strip() or None
        sync_device_preferences(prefs.ui_language_code, prefs.learning_language_code, user_id=current_user.id)
        prefs.preferred_study_time = (form.preferred_study_time.data or "").strip() or None
        prefs.notify_email = bool(form.notify_email.data)
        prefs.notify_push = bool(form.notify_push.data)
        prefs.email_notifications = prefs.notify_email
        prefs.browser_notifications = prefs.notify_push
        prefs.allow_ml_training = bool(form.allow_ml_training.data)
        prefs.welcome_voice_mode = form.welcome_voice_mode.data or "once"
        prefs.auto_play_question = bool(form.auto_play_question.data)
        prefs.auto_start_listening = bool(form.auto_start_listening.data)
        prefs.question_beep_enabled = bool(form.question_beep_enabled.data)

        if prefs.preferred_study_time:
            current_user.preferred_study_time = prefs.preferred_study_time

        db.session.commit()
        audit("preferences_update", target=str(current_user.id))
        flash("Preferences updated.", "success")
        return redirect(url_for("account.preferences"))
    elif request.method == "POST":
        for field_name, errors in form.errors.items():
            label = getattr(getattr(form, field_name), "label", None)
            label_text = getattr(label, "text", field_name.replace("_", " ").title())
            for error in errors:
                flash(f"{label_text}: {error}", "danger")

    selected_support_code = getattr(prefs, "translation_support_language_code", None) or current_user.native_language or "en"
    selected_support_name = language_label(selected_support_code, fallback="English")
    return render_template("account/preferences.html", form=form, accent_map=ACCENT_OPTIONS, selected_support_name=selected_support_name)


@bp.get("/security")
@bp.post("/security")
@login_required
def security():
    form = ChangePasswordForm()
    policy = SecurityPolicy.singleton()
    otp_enabled = (policy.otp_mode or "OFF") != "OFF"
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("account/security.html", form=form, otp_enabled=otp_enabled, policy=policy)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        audit("change_password", target=str(current_user.id))
        flash("Password updated.", "success")
        return redirect(url_for("account.security"))
    return render_template("account/security.html", form=form, otp_enabled=otp_enabled, policy=policy)


@bp.get("/login-history")
@login_required
def login_history():
    login_events = LoginEvent.query.filter(LoginEvent.user_id == current_user.id).order_by(LoginEvent.created_at.desc()).limit(50).all()
    return render_template("account/login_history.html", login_events=login_events)


@bp.get("/notifications")
@login_required
def notifications():
    _seed_default_notifications_for_user(current_user)
    try:
        rows = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(200).all()
    except SQLAlchemyError:
        db.session.rollback()
        db.create_all()
        rows = []
    return render_template("account/notifications.html", rows=rows)


@bp.post("/notifications/<int:notif_id>/read")
@login_required
def notifications_mark_read(notif_id: int):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return redirect(url_for("account.notifications"))


@bp.post("/notifications/read-all")
@login_required
def notifications_read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("account.notifications"))


@bp.get("/sessions")
@login_required
def sessions():
    rows = UserSession.query.filter_by(user_id=current_user.id).order_by(UserSession.last_seen_at.desc()).all()
    current_row = get_current_session_row()
    return render_template("account/sessions.html", sessions=rows, current_session=current_row)


@bp.post("/sessions/revoke/<int:session_id>")
@login_required
def revoke_session(session_id: int):
    current_row = get_current_session_row()
    if current_row and current_row.id == session_id:
        flash("Use logout to end the current device session.", "warning")
        return redirect(url_for("account.sessions"))
    if revoke_session_for_user(current_user.id, session_id):
        flash("Selected session revoked.", "success")
    else:
        flash("Session not found or already revoked.", "warning")
    return redirect(url_for("account.sessions"))


@bp.post("/sessions/revoke-others")
@login_required
def revoke_other_sessions_route():
    count = revoke_other_sessions(current_user.id)
    flash(f"Revoked {count} other active session(s).", "success")
    return redirect(url_for("account.sessions"))
