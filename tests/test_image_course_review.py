from __future__ import annotations

from app.extensions import db
from app.models.lms import Chapter, Course, Lesson, Level, Question, Subsection
from app.services.image_course_review_service import ImageCourseReviewService
from app.services.lms_service import LMSService


def _build_image_course():
    course = Course(
        title="Nursery QA Course",
        slug="nursery-qa-course",
        description="Image-led nursery QA test course.",
        language_code="en",
        track_type="speaking",
        difficulty="basic",
        status="published",
        is_published=True,
    )
    db.session.add(course)
    db.session.flush()

    level = Level(course_id=course.id, title="Level 1", sort_order=1)
    db.session.add(level)
    db.session.flush()

    lesson = Lesson(level_id=level.id, title="Picture Talk", slug="picture-talk", lesson_type="guided", estimated_minutes=10, sort_order=1, is_published=True)
    db.session.add(lesson)
    db.session.flush()

    chapter = Chapter(lesson_id=lesson.id, title="Daily Objects", sort_order=1)
    db.session.add(chapter)
    db.session.flush()

    subsection = Subsection(chapter_id=chapter.id, title="Picture Words", sort_order=1)
    db.session.add(subsection)
    db.session.flush()

    return course, subsection


def test_image_course_report_detects_broken_image_and_suggestions(app_ctx):
    course, subsection = _build_image_course()
    question = Question(
        subsection_id=subsection.id,
        title="Broken Apple",
        prompt="Is this an apple?",
        image_url="/static/uploads/questions/nursery/appl.svg",
        model_answer="Yes, this is an apple.",
        hint_text="Start with yes.",
        expected_keywords="apple",
        prompt_type="question",
        language_code="en",
        is_active=True,
        sort_order=1,
    )
    db.session.add(question)
    db.session.commit()

    report = ImageCourseReviewService.build_report(course)

    assert report["summary"]["broken_image_count"] == 1
    broken_issue = next(issue for issue in report["issues"] if issue["code"] == "broken_image")
    assert "/static/uploads/questions/nursery/apple.svg" in broken_issue["repair_suggestions"]


def test_bulk_validation_flags_duplicate_prompt_and_missing_image(app_ctx):
    course, subsection = _build_image_course()
    existing = Question(
        subsection_id=subsection.id,
        title="Apple",
        prompt="Is this an apple?",
        image_url="/static/uploads/questions/nursery/apple.svg",
        model_answer="Yes, this is an apple.",
        hint_text="Use yes.",
        expected_keywords="apple",
        prompt_type="question",
        language_code="en",
        is_active=True,
        sort_order=1,
    )
    db.session.add(existing)
    db.session.commit()

    csv_text = "\n".join([
        "title,prompt,image_url,answer,hint,expected_keywords,prompt_type,language_code",
        "Apple Copy,Is this an apple?,/static/uploads/questions/nursery/appl.svg,Yes,Use yes,apple,question,en",
    ])

    class _Upload:
        filename = "nursery.csv"

        def read(self):
            return csv_text.encode("utf-8")

    report = ImageCourseReviewService.validate_bulk_upload(course, _Upload())

    assert report["is_valid"] is False
    assert any("Rows already used by this course prompt bank" in item for item in report["issues"])
    assert report["missing_images"][0]["image_url"] == "/static/uploads/questions/nursery/appl.svg"
    assert "/static/uploads/questions/nursery/apple.svg" in report["repair_suggestions"]["/static/uploads/questions/nursery/appl.svg"]


def test_question_upload_validation_blocks_duplicate_rows_and_broken_paths(app_ctx):
    parsed_rows = [
        {
            "prompt": "Is this an apple?",
            "image_url": "/static/uploads/questions/nursery/appl.svg",
        },
        {
            "prompt": "Is this an apple?",
            "image_url": "/static/uploads/questions/nursery/apple.svg",
        },
    ]

    issues = LMSService.validate_question_upload_rows(parsed_rows)

    assert any("duplicate prompt" in issue.lower() for issue in issues)
    assert any("image path was not found" in issue.lower() for issue in issues)


def test_question_upload_validation_flags_missing_content_fields(app_ctx):
    parsed_rows = [
        {
            "prompt": "Cat",
            "image_url": "uploads/questions/nursery/cat.svg",
            "model_answer": "",
            "hint_text": "",
            "expected_keywords": "",
            "prompt_type": "unknown",
            "language_code": "english",
        },
    ]

    issues = LMSService.validate_question_upload_rows(parsed_rows)

    assert any("too short" in issue.lower() for issue in issues)
    assert not any("must start with /static/" in issue.lower() for issue in issues)
    assert any("model answer is missing" in issue.lower() for issue in issues)
    assert any("hint text is missing" in issue.lower() for issue in issues)
    assert any("expected keywords are missing" in issue.lower() for issue in issues)
    assert any("prompt type" in issue.lower() for issue in issues)
    assert any("language code" in issue.lower() for issue in issues)
