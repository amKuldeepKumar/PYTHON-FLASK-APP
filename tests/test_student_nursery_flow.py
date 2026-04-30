from __future__ import annotations

import hashlib
from datetime import datetime

from app.extensions import db
from app.models.lms import Chapter, Course, CourseProgress, Enrollment, Lesson, LessonProgress, Level, Question, QuestionAttempt, Subsection
from app.models.user_session import UserSession
from app.models.user import Role, User
from app.services.image_course_review_service import ImageCourseReviewService


def _login(client, user_id: int) -> None:
    token = f"test-session-{user_id}"
    session_row = UserSession(
        user_id=user_id,
        session_key_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        device_hash="test-device",
        ip_address="127.0.0.1",
        browser="Chrome",
        os_name="Windows",
        device_type="desktop",
        user_agent="pytest",
        country="Local",
        city="Dev",
        is_current=True,
        last_seen_at=datetime.utcnow(),
    )
    db.session.add(session_row)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session["auth_session_token"] = token


def _build_student_course(*, include_image: bool = True):
    student = User(
        email=f"student-{datetime.utcnow().timestamp()}@example.com",
        username=f"student-{int(datetime.utcnow().timestamp() * 1000000)}",
        role=Role.STUDENT.value,
        password_hash="hashed",
    )
    db.session.add(student)
    db.session.flush()

    course = Course(
        title="Nursery Picture Journey",
        slug=f"nursery-picture-journey-{student.id}",
        description="A simple image-based course.",
        language_code="en",
        track_type="nursery",
        difficulty="basic",
        status="published",
        is_published=True,
    )
    db.session.add(course)
    db.session.flush()

    level = Level(course_id=course.id, title="Level 1", sort_order=1)
    db.session.add(level)
    db.session.flush()

    lesson = Lesson(
        level_id=level.id,
        title="Picture Practice",
        slug=f"picture-practice-{course.id}",
        lesson_type="guided",
        estimated_minutes=5,
        sort_order=1,
        is_published=True,
    )
    db.session.add(lesson)
    db.session.flush()

    chapter = Chapter(lesson_id=lesson.id, title="Objects", sort_order=1)
    db.session.add(chapter)
    db.session.flush()

    subsection = Subsection(chapter_id=chapter.id, title="Picture Words", sort_order=1)
    db.session.add(subsection)
    db.session.flush()

    question = Question(
        subsection_id=subsection.id,
        title="Apple Question" if include_image else "Greeting Question",
        prompt="Is this an apple?" if include_image else "Say hello in one short sentence.",
        image_url="/static/uploads/questions/nursery/apple.svg" if include_image else None,
        model_answer="Yes, this is an apple." if include_image else "Hello.",
        hint_text="Start with yes." if include_image else "Say hello.",
        expected_keywords="apple" if include_image else "hello",
        prompt_type="question",
        language_code="en",
        is_active=True,
        sort_order=1,
    )
    db.session.add(question)
    db.session.flush()

    enrollment = Enrollment(
        student_id=student.id,
        course_id=course.id,
        status="active",
        access_scope="full_course",
        welcome_seen_at=datetime.utcnow(),
    )
    db.session.add(enrollment)
    db.session.commit()

    return student, course, lesson, question


def test_learn_lesson_renders_image_question_and_seo_attrs(client, app_ctx):
    student, _course, lesson, _question = _build_student_course(include_image=True)
    _login(client, student.id)

    response = client.get(f"/student/lessons/{lesson.id}/learn")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "/static/uploads/questions/nursery/apple.svg" in html
    assert 'alt="Learning image for question: Is this an apple?"' in html
    assert 'title="Is this an apple? | Nursery Picture Journey"' in html
    assert 'loading="lazy"' in html


def test_learn_lesson_text_only_question_keeps_normal_flow(client, app_ctx):
    student, _course, lesson, _question = _build_student_course(include_image=False)
    _login(client, student.id)

    response = client.get(f"/student/lessons/{lesson.id}/learn")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Say hello in one short sentence." in html
    assert "lesson-question-image" not in html
    assert "/static/uploads/questions/nursery/apple.svg" not in html


def test_submit_question_updates_attempt_lesson_progress_course_progress_and_qa_analytics(client, app_ctx):
    student, course, lesson, question = _build_student_course(include_image=True)
    _login(client, student.id)

    response = client.post(
        f"/student/questions/{question.id}/submit",
        data={
            "response_text": "Yes, this is an apple.",
            "response_mode": "typed",
            "duration_seconds": "12",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Answer submitted and progress updated." in response.get_data(as_text=True)

    attempt = QuestionAttempt.query.filter_by(student_id=student.id, question_id=question.id, attempt_kind="final").first()
    assert attempt is not None
    assert float(attempt.accuracy_score or 0) > 0

    lesson_progress = LessonProgress.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
    assert lesson_progress is not None
    assert lesson_progress.total_questions == 1
    assert lesson_progress.completed_questions == 1
    assert int(lesson_progress.completion_percent or 0) == 100
    assert lesson_progress.completed_at is not None

    course_progress = CourseProgress.query.filter_by(student_id=student.id, course_id=course.id).first()
    assert course_progress is not None
    assert course_progress.total_lessons == 1
    assert course_progress.completed_lessons == 1
    assert course_progress.total_questions == 1
    assert course_progress.completed_questions == 1
    assert int(course_progress.completion_percent or 0) == 100

    report = ImageCourseReviewService.build_report(course)
    assert report["analytics"]["students_with_attempts"] == 1
    assert report["analytics"]["lesson_progress_rows"] == 1
    assert report["analytics"]["course_progress_rows"] == 1
    assert all(item["status"] == "pass" for item in report["analytics"]["checks"])
