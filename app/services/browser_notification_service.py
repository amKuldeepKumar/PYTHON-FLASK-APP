from __future__ import annotations

import random
from datetime import datetime

from flask import url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..models.lms import Enrollment, LessonProgress, QuestionAttempt
from ..models.notification import Notification

MOTIVATIONAL_LINES = [
    "Great progress starts with one focused session.",
    "Your English grows every time you practice.",
    "Consistency beats intensity — keep showing up.",
    "Each lesson completed builds real confidence.",
    "Small daily effort creates big language growth.",
    "You are closer to fluency than you were yesterday.",
    "Practice today becomes confidence tomorrow.",
    "Keep going — your progress is real.",
    "Strong learners return, even on ordinary days.",
    "Every answer you try moves you forward.",
]

WORK_HOUR_LINES = [
    "This is a good hour to return to your English practice.",
    "A short session right now can keep your momentum alive.",
    "Your study hour is open — continue from where you stopped.",
    "Five focused minutes now can improve tomorrow's confidence.",
]


def _pick_line(lines: list[str]) -> str:
    return random.choice(lines)


def _safe_percent(value: float | int | None) -> int:
    try:
        return int(round(float(value or 0)))
    except Exception:
        return 0


def _ordered_value(obj):
    for attr in ("order_index", "sort_order", "position", "sequence", "id"):
        value = getattr(obj, attr, None)
        if value is not None:
            return value
    return 0


def _student_summary_payload(user) -> dict:
    enrollments = Enrollment.query.filter_by(student_id=user.id, status="active").all()
    course_ids = [row.course_id for row in enrollments]
    total_courses = len(course_ids)

    lesson_ids: list[int] = []
    for enrollment in enrollments:
        course = enrollment.course
        if not course:
            continue
        for level in sorted(course.levels, key=_ordered_value):
            for lesson in sorted(level.lessons, key=_ordered_value):
                lesson_ids.append(lesson.id)

    total_lessons = len(lesson_ids)

    completed_lessons = 0
    completion_percent = 0
    if lesson_ids:
        lesson_rows = LessonProgress.query.filter(
            LessonProgress.student_id == user.id,
            LessonProgress.lesson_id.in_(lesson_ids),
        ).all()
        completed_lessons = sum(1 for row in lesson_rows if (row.completion_percent or 0) >= 100 or row.completed_at is not None)
        if lesson_rows:
            completion_percent = _safe_percent(sum((row.completion_percent or 0) for row in lesson_rows) / max(total_lessons, 1))

    attempts = QuestionAttempt.query.filter_by(student_id=user.id, attempt_kind="final").all()
    total_attempts = len(attempts)
    accuracy_values = [row.accuracy_score for row in attempts if row.accuracy_score is not None]
    accuracy_percent = _safe_percent((sum(accuracy_values) / len(accuracy_values)) * 100) if accuracy_values else 0
    spoken_attempts = sum(1 for row in attempts if (row.response_mode or "").lower() == "spoken")
    support_events = QuestionAttempt.query.filter_by(student_id=user.id, attempt_kind="support_tool").count()

    if total_courses and completed_lessons >= total_lessons and total_lessons > 0:
        title = "Excellent work — course track completed"
    elif completion_percent >= 75:
        title = "Strong progress on your learning path"
    else:
        title = "Your Fluencify progress update"

    stats_parts = []
    if total_lessons:
        stats_parts.append(f"Lessons {completed_lessons}/{total_lessons}")
    if completion_percent:
        stats_parts.append(f"Progress {completion_percent}%")
    if total_attempts:
        stats_parts.append(f"Accuracy {accuracy_percent}%")
    if spoken_attempts:
        stats_parts.append(f"Speaking {spoken_attempts}")
    if support_events:
        stats_parts.append(f"Help tools {support_events}")

    stat_line = " • ".join(stats_parts) if stats_parts else "Start your next lesson and build momentum."
    body = f"{stat_line}. {_pick_line(MOTIVATIONAL_LINES)}"

    return {
        "ok": True,
        "kind": "student_progress",
        "permission_hint": True,
        "title": title,
        "body": body,
        "target_url": url_for("student.dashboard"),
        "tag": f"student-progress-{user.id}",
        "icon": url_for("static", filename="shared/img/avatar-placeholder.svg"),
        "cache_key": f"student-{user.id}",
        "show_after_minutes": 90,
        "stats": {
            "courses": total_courses,
            "lessons_completed": completed_lessons,
            "lessons_total": total_lessons,
            "progress_percent": completion_percent,
            "attempts": total_attempts,
            "accuracy_percent": accuracy_percent,
            "spoken_attempts": spoken_attempts,
            "support_events": support_events,
        },
    }


def _notifications_enabled(user) -> bool:
    prefs = getattr(user, "preferences", None)
    if prefs is None:
        return True
    return bool(getattr(prefs, "notify_push", False) or getattr(prefs, "browser_notifications", False))


def _latest_unread_notification(user):
    try:
        return (
            Notification.query.filter_by(user_id=user.id, is_read=False)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .first()
        )
    except SQLAlchemyError:
        db.session.rollback()
        db.create_all()
        return None


def _notification_payload(notification: Notification) -> dict:
    target_url = notification.link_path if notification.has_internal_link else url_for("account.notifications")
    level = (notification.level or "info").strip().lower()
    return {
        "ok": True,
        "kind": "notification",
        "permission_hint": True,
        "notification_id": notification.id,
        "title": notification.title,
        "body": notification.message,
        "target_url": target_url,
        "tag": f"fluencify-notification-{notification.id}",
        "icon": url_for("static", filename="shared/img/avatar-placeholder.svg"),
        "cache_key": f"notification-{notification.id}",
        "show_after_minutes": 30,
        "require_interaction": level in {"warning", "danger", "error", "urgent"},
        "stats": {
            "category": notification.category or "system",
            "level": level,
        },
    }


def _guest_payload() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        prefix = "Good morning"
    elif 12 <= hour < 18:
        prefix = "Good afternoon"
    else:
        prefix = "Good evening"

    body = f"{prefix}. {_pick_line(WORK_HOUR_LINES)} {_pick_line(MOTIVATIONAL_LINES)}"
    return {
        "ok": True,
        "kind": "guest_reminder",
        "permission_hint": True,
        "title": "Fluencify study reminder",
        "body": body,
        "target_url": url_for("auth.login"),
        "tag": "guest-study-reminder",
        "icon": url_for("static", filename="shared/img/avatar-placeholder.svg"),
        "cache_key": "guest",
        "show_after_minutes": 240,
        "stats": {},
    }


def build_browser_notification_payload() -> dict:
    if getattr(current_user, "is_authenticated", False):
        if not _notifications_enabled(current_user):
            return {
                "ok": False,
                "kind": "disabled",
                "permission_hint": False,
            }

        latest_notification = _latest_unread_notification(current_user)
        if latest_notification is not None:
            return _notification_payload(latest_notification)

        if getattr(current_user, "is_student", False):
            return _student_summary_payload(current_user)

        return {
            "ok": False,
            "kind": "empty",
            "permission_hint": False,
        }
    return _guest_payload()
