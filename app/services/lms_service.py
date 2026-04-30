from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models.lms import (
    Chapter,
    Course,
    Enrollment,
    Lesson,
    LessonProgress,
    CourseProgress,
    Level,
    Module,
    Question,
    QuestionAttempt,
    Subsection,
    CourseBatch,
    ContentVersion,
    CertificateRecord,
    spaced_repetition_weight,
)
from ..models.user import User
from .student_activity_service import StudentActivityService


GRAMMAR_KEYWORDS = {
    "present continuous": ["now", "currently", "at the moment"],
    "past tense": ["yesterday", "last", "ago"],
    "future tense": ["tomorrow", "next", "will"],
    "passive voice": ["made by", "was built", "is produced"],
    "interview response": ["tell me about yourself", "strength", "weakness", "experience"],
}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value or "").strip("-").lower()
    return value or f"course-{int(datetime.utcnow().timestamp())}"


def _normalize_course_track_type(track: str | None) -> str | None:
    if not track:
        return None

    value = str(track).strip().lower()

    mapping = {
        "speaking": "speaking",
        "interview": "interview",
        "spoken english": "speaking",
        "spoken_english": "speaking",
        "reading": "reading",
        "writing": "writing",
        "listening": "listening",
        "grammar": "grammar",
        "vocabulary": "vocabulary",
    }

    return mapping.get(value, value)


SUPPORT_TOOL_LIMIT_RATIO = 0.20
SUPPORT_TOOL_EVENT_KIND = "support_tool"
SUPPORT_TOOL_PENALTIES = {
    "hint": 8.0,
    "synonym": 5.0,
    "translation": 5.0,
}

class LMSService:
    NURSERY_STARTER_SLUG = "nursery-image-practice"

    @staticmethod
    def safe_decimal(value, default: str = "0.00") -> Decimal:
        try:
            if value in (None, ""):
                return Decimal(default)
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _sync_course_level_shells(course: Course) -> None:
        target_max = max(int(getattr(course, "max_level", 1) or 1), 1)
        existing = {int(level.sort_order or 0): level for level in course.levels if int(level.sort_order or 0) > 0}
        for level_number in range(1, target_max + 1):
            if level_number in existing:
                level = existing[level_number]
                if not (level.title or '').strip():
                    level.title = f"Level {level_number}"
                continue
            db.session.add(Level(course_id=course.id, title=f"Level {level_number}", sort_order=level_number))
        db.session.flush()

    @staticmethod
    def course_has_level_access(enrollment: Enrollment | None, level_number: int | None) -> bool:
        if not enrollment:
            return False
        return enrollment.has_level_access(level_number)

    @staticmethod
    def normalize_question_image_url(value: str | None) -> str | None:
        raw = (value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("\\", "/")
        if normalized.startswith(("http://", "https://", "/static/")):
            return normalized
        if normalized.startswith("static/"):
            return f"/{normalized.lstrip('/')}"
        if normalized.startswith("uploads/"):
            return f"/static/{normalized}"
        return normalized

    @staticmethod
    def humanize_image_label(image_url: str | None) -> str:
        normalized = LMSService.normalize_question_image_url(image_url) or ""
        filename = os.path.basename(normalized.split("?", 1)[0].split("#", 1)[0])
        stem = os.path.splitext(filename)[0]
        text = stem.replace("_", " ").replace("-", " ").strip()
        return text.title() if text else "Nursery Learning Image"

    @staticmethod
    def image_asset_seo(image_url: str | None, *, course_title: str | None = None) -> dict[str, str]:
        label = LMSService.humanize_image_label(image_url)
        course_name = (course_title or "Fluencify Nursery Course").strip()
        return {
            "alt": f"{label} nursery learning image",
            "title": f"{label} image for {course_name}",
        }

    @staticmethod
    def question_image_seo(question: Question | None, *, course_title: str | None = None) -> dict[str, str]:
        if question is None:
            return LMSService.image_asset_seo(None, course_title=course_title)
        prompt_text = (question.prompt or "").strip()
        title_text = (question.title or "").strip()
        course_name = (course_title or "Fluencify Lesson").strip()
        image_label = LMSService.humanize_image_label(getattr(question, "image_url", None))
        summary = prompt_text or title_text or image_label
        return {
            "alt": f"Learning image for question: {summary}",
            "title": f"{summary} | {course_name}",
        }

    @staticmethod
    def _local_static_asset_exists(image_url: str | None) -> bool:
        normalized = LMSService.normalize_question_image_url(image_url)
        if not normalized:
            return True
        if normalized.startswith(("http://", "https://")):
            return True
        if not normalized.startswith("/static/"):
            return False
        try:
            relative_path = normalized.removeprefix("/static/").replace("/", os.sep)
            full_path = os.path.join(current_app.root_path, "static", relative_path)
            return os.path.exists(full_path)
        except Exception:
            return False

    @staticmethod
    def validate_question_upload_rows(parsed_rows: list[dict]) -> list[str]:
        issues: list[str] = []
        prompt_seen: dict[str, int] = {}
        allowed_prompt_types = {"question", "speaking", "writing", "reading", "listening", "quiz"}

        if not parsed_rows:
            return ["The upload file did not contain any usable prompt rows."]

        for idx, row in enumerate(parsed_rows, start=1):
            prompt = (row.get("prompt") or "").strip()
            image_url = LMSService.normalize_question_image_url(row.get("image_url"))
            prompt_key = prompt.lower()
            model_answer = (row.get("model_answer") or "").strip()
            hint_text = (row.get("hint_text") or "").strip()
            expected_keywords = (row.get("expected_keywords") or "").strip()
            prompt_type = (row.get("prompt_type") or "question").strip().lower()
            language_code = (row.get("language_code") or "en").strip().lower()

            if not prompt:
                issues.append(f"Row {idx}: prompt is required.")
                continue
            if len(prompt) > 1000:
                issues.append(f"Row {idx}: prompt is too long. Keep it under 1000 characters.")
            if len(prompt) < 5:
                issues.append(f"Row {idx}: prompt is too short to be useful.")
            if prompt_key in prompt_seen:
                issues.append(f"Row {idx}: duplicate prompt matches row {prompt_seen[prompt_key]}.")
            else:
                prompt_seen[prompt_key] = idx
            if image_url and not LMSService._local_static_asset_exists(image_url):
                issues.append(f"Row {idx}: image path was not found - {image_url}")
            if image_url and len(str(image_url)) > 255:
                issues.append(f"Row {idx}: image path is too long.")
            if image_url and not image_url.startswith(("/static/", "http://", "https://")):
                issues.append(f"Row {idx}: image path must start with /static/, http://, or https://.")
            if not model_answer:
                issues.append(f"Row {idx}: model answer is missing.")
            if not hint_text:
                issues.append(f"Row {idx}: hint text is missing.")
            if image_url and not expected_keywords:
                issues.append(f"Row {idx}: expected keywords are missing for an image-based question.")
            if prompt_type not in allowed_prompt_types:
                issues.append(f"Row {idx}: prompt type '{prompt_type}' is not supported.")
            if not re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", language_code):
                issues.append(f"Row {idx}: language code '{language_code}' is not valid.")

        return issues

    @staticmethod
    def question_upload_template_csv() -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "title",
            "prompt",
            "image_url",
            "answer",
            "hint",
            "expected_keywords",
            "prompt_type",
            "language_code",
            "grammar_formula",
        ])
        writer.writerow([
            "Red Apple",
            "What do you see in the picture? Say the word and make one short sentence.",
            "/static/uploads/questions/nursery/apple.svg",
            "I see an apple. The apple is red.",
            "Say: I see an apple.",
            "apple,red",
            "speaking",
            "en",
            "picture words",
        ])
        writer.writerow([
            "Blue Ball",
            "Look at the picture. What is it? Say one short sentence.",
            "/static/uploads/questions/nursery/ball.svg",
            "It is a ball. The ball is blue.",
            "Say the object name first.",
            "ball,blue",
            "speaking",
            "en",
            "picture words",
        ])
        return output.getvalue()

    @staticmethod
    def enroll_full_course(student_id: int, course_id: int) -> Enrollment:
        row = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
        if row:
            row.status = "active"
            row.enrolled_by_id = None
            row.access_scope = "full_course"
            row.purchased_levels_json = None
            db.session.commit()
            return row
        row = Enrollment(student_id=student_id, course_id=course_id, enrolled_by_id=None, access_scope="full_course")
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def enroll_course_level(student_id: int, course_id: int, level_number: int) -> Enrollment:
        course = Course.query.get(course_id)
        if not course:
            raise ValueError("Course not found.")
        level_number = max(1, min(int(level_number or 1), int(course.max_level or 1)))
        row = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
        if row and row.has_full_access():
            row.status = "active"
            db.session.commit()
            return row
        if not row:
            row = Enrollment(student_id=student_id, course_id=course_id, enrolled_by_id=None, access_scope="level_only")
            db.session.add(row)
        row.status = "active"
        row.grant_level_access(level_number)
        db.session.commit()
        return row


    @staticmethod
    def create_course(title: str, owner_admin_id: int | None, created_by_id: int | None, **kwargs) -> Course:
        raw_title = (title or "").strip()
        if not raw_title:
            raise ValueError("Course title is required.")

        raw_slug = (kwargs.get("slug") or "").strip()
        final_slug = slugify(raw_slug or raw_title)

        existing = Course.query.filter(func.lower(Course.slug) == final_slug.lower()).first()
        if existing:
            raise ValueError(f'The slug "{final_slug}" already exists. Please use a different slug.')

        access_type = (kwargs.get("access_type") or "free").strip().lower()
        if access_type not in {"free", "paid"}:
            access_type = "free"
        allow_level_purchase = bool(kwargs.get("allow_level_purchase"))
        level_access_type = (kwargs.get("level_access_type") or "free").strip().lower()
        if level_access_type not in {"free", "paid"}:
            level_access_type = "free"
        max_level = max(int(kwargs.get("max_level") or 1), 1)

        base_price = LMSService.safe_decimal(kwargs.get("base_price"), "0.00")
        sale_price = kwargs.get("sale_price")
        sale_price_dec = LMSService.safe_decimal(sale_price) if sale_price not in (None, "") else None
        level_price = LMSService.safe_decimal(kwargs.get("level_price"), "0.00")
        level_sale_price = kwargs.get("level_sale_price")
        level_sale_price_dec = LMSService.safe_decimal(level_sale_price) if level_sale_price not in (None, "") else None
        if access_type == "free":
            base_price = Decimal("0.00")
            sale_price_dec = None
        if level_access_type == "free":
            level_price = Decimal("0.00")
            level_sale_price_dec = None

        try:
            course = Course(
                title=raw_title,
                slug=final_slug,
                description=(kwargs.get("description") or "").strip() or None,
                language_code=(kwargs.get("language_code") or "en").strip(),
                track_type=_normalize_course_track_type(kwargs.get("track_type")),
                difficulty=(kwargs.get("difficulty") or "").strip() or None,
                max_level=max_level,
                access_type=access_type,
                allow_level_purchase=allow_level_purchase,
                level_access_type=level_access_type,
                is_published=bool(kwargs.get("is_published")),
                is_premium=(access_type == "paid") or bool(kwargs.get("is_premium")),
                currency_code=(kwargs.get("currency_code") or "INR").strip(),
                base_price=base_price,
                sale_price=sale_price_dec,
                level_price=level_price,
                level_sale_price=level_sale_price_dec,
                status="published" if kwargs.get("is_published") else "draft",
                workflow_status="published" if kwargs.get("is_published") else "draft",
                published_at=datetime.utcnow() if kwargs.get("is_published") else None,
                owner_admin_id=owner_admin_id,
                created_by_id=created_by_id,
            )
            db.session.add(course)
            db.session.flush()

            level = Level(
                course_id=course.id,
                title=(kwargs.get("level_title") or "Level 1").strip(),
                description=(kwargs.get("level_description") or "").strip() or None,
                sort_order=1,
            )
            db.session.add(level)
            db.session.flush()
            LMSService._sync_course_level_shells(course)

            lesson = Lesson(
                level_id=level.id,
                title=(kwargs.get("lesson_title") or "Lesson 1").strip(),
                slug=slugify(kwargs.get("lesson_slug") or kwargs.get("lesson_title") or "lesson-1"),
                sort_order=1,
                lesson_type=(kwargs.get("lesson_type") or "guided").strip(),
                explanation_text=kwargs.get("explanation_text") or "Start by reading the explanation, then answer each prompt naturally.",
                explanation_tts_text=kwargs.get("explanation_tts_text") or kwargs.get("explanation_text") or "Welcome to this lesson.",
                estimated_minutes=int(kwargs.get("estimated_minutes") or 10),
                is_published=True,
            )
            db.session.add(lesson)
            db.session.flush()

            chapter = Chapter(
                lesson_id=lesson.id,
                title=(kwargs.get("chapter_title") or "Chapter 1").strip(),
                description=(kwargs.get("chapter_description") or "").strip() or None,
                sort_order=1,
            )
            db.session.add(chapter)
            db.session.flush()

            subsection = Subsection(
                chapter_id=chapter.id,
                title=(kwargs.get("subsection_title") or "Subsection 1").strip(),
                sort_order=1,
                grammar_formula=kwargs.get("grammar_formula") or None,
                grammar_tags=kwargs.get("grammar_tags") or None,
                hint_seed=kwargs.get("hint_seed") or None,
            )
            db.session.add(subsection)
            db.session.flush()

            badge_title = (kwargs.get("badge_title") or "").strip()
            if badge_title:
                try:
                    from ..models.course_badge import CourseBadge

                    db.session.add(
                        CourseBadge(
                            course_id=course.id,
                            title=badge_title,
                            subtitle=(kwargs.get("badge_subtitle") or "").strip() or None,
                            template_key=(kwargs.get("badge_template") or "gradient").strip(),
                            animation_key=(kwargs.get("badge_animation") or "none").strip(),
                            is_active=True,
                        )
                    )
                except Exception:
                    pass

            db.session.commit()
            return course

        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def create_nursery_image_starter_course(owner_admin_id: int | None, created_by_id: int | None) -> tuple[Course, bool]:
        existing = Course.query.filter(func.lower(Course.slug) == LMSService.NURSERY_STARTER_SLUG.lower()).first()
        if existing:
            return existing, False

        course = LMSService.create_course(
            title="Nursery Image Practice",
            owner_admin_id=owner_admin_id,
            created_by_id=created_by_id,
            slug=LMSService.NURSERY_STARTER_SLUG,
            description="A very basic image-led English starter course for nursery students.",
            language_code="en",
            track_type="speaking",
            difficulty="basic",
            currency_code="INR",
            access_type="free",
            allow_level_purchase=False,
            level_access_type="free",
            base_price="0.00",
            level_price="0.00",
            max_level=1,
            level_title="Nursery Starters",
            lesson_title="Look, Say, Learn",
            lesson_slug="look-say-learn",
            lesson_type="guided",
            explanation_text="Look at the picture, say the word, and answer in a very short sentence.",
            explanation_tts_text="Look at the picture. Say the word. Then answer in a short sentence.",
            chapter_title="Daily Objects",
            chapter_description="Simple object and animal pictures for nursery learners.",
            subsection_title="Picture Talk",
            grammar_formula="basic picture words",
            grammar_tags="nursery,basic,image",
            hint_seed="Name the picture first. Then say one short sentence.",
            is_published=True,
            is_premium=False,
        )

        lesson = course.levels[0].lessons[0]
        first_chapter = lesson.chapters[0]
        first_subsection = first_chapter.subsections[0]
        first_chapter.title = "Daily Objects"
        first_subsection.title = "Picture Words"
        first_subsection.grammar_formula = "picture words"
        first_subsection.grammar_tags = "nursery,picture,words"
        first_subsection.hint_seed = "Say the object name and use one easy sentence."

        chapter_two = LMSService.add_chapter(
            lesson=lesson,
            title="Animals And Nature",
            description="Friendly animals and nature pictures for very early learners.",
            sort_order=2,
        )
        subsection_two = LMSService.add_subsection(
            chapter=chapter_two,
            title="See And Speak",
            grammar_formula="see and speak",
            grammar_tags="nursery,animals,nature",
            hint_seed="Tell what you see with very simple words.",
            sort_order=1,
        )

        starter_questions = [
            {
                "subsection": first_subsection,
                "title": "Apple Yes Or No",
                "prompt": "Is this an apple?",
                "image_url": "/static/uploads/questions/nursery/apple.svg",
                "model_answer": "Yes, this is an apple.",
                "hint_text": "Start with: Yes, this is an apple.",
                "expected_keywords": "apple,red",
            },
            {
                "subsection": first_subsection,
                "title": "Blue Ball",
                "prompt": "Look at the picture. What is it? Say one short sentence.",
                "image_url": "/static/uploads/questions/nursery/ball.svg",
                "model_answer": "It is a ball. The ball is blue.",
                "hint_text": "Say the object name first.",
                "expected_keywords": "ball,blue",
            },
            {
                "subsection": first_subsection,
                "title": "Happy Sun",
                "prompt": "What is in the sky? Tell in one easy sentence.",
                "image_url": "/static/uploads/questions/nursery/sun.svg",
                "model_answer": "It is the sun. The sun is bright.",
                "hint_text": "Start with: It is...",
                "expected_keywords": "sun,sky",
            },
            {
                "subsection": subsection_two,
                "title": "Little Cat",
                "prompt": "Who is this? Name the animal and say one sentence.",
                "image_url": "/static/uploads/questions/nursery/cat.svg",
                "model_answer": "It is a cat. The cat is small.",
                "hint_text": "Say: It is a cat.",
                "expected_keywords": "cat,small",
            },
            {
                "subsection": subsection_two,
                "title": "Green Tree",
                "prompt": "What do you see? Speak one simple sentence about it.",
                "image_url": "/static/uploads/questions/nursery/tree.svg",
                "model_answer": "I see a tree. The tree is green.",
                "hint_text": "Say: I see a tree.",
                "expected_keywords": "tree,green",
            },
            {
                "subsection": subsection_two,
                "title": "Yellow Bird",
                "prompt": "Look at the picture and tell what it is in one short sentence.",
                "image_url": "/static/uploads/questions/nursery/bird.svg",
                "model_answer": "It is a bird. The bird is yellow.",
                "hint_text": "Name the bird first.",
                "expected_keywords": "bird,yellow",
            },
        ]

        for idx, item in enumerate(starter_questions, start=1):
            LMSService.add_question(
                subsection=item["subsection"],
                title=item["title"],
                prompt=item["prompt"],
                prompt_type="speaking",
                image_url=item["image_url"],
                model_answer=item["model_answer"],
                hint_text=item["hint_text"],
                expected_keywords=item["expected_keywords"],
                evaluation_rubric="Check if the learner correctly names the picture and uses one simple nursery-level sentence.",
                sort_order=idx,
                is_active=True,
            )

        return course, True

    @staticmethod
    def update_course(course: Course, **kwargs) -> Course:
        title = (kwargs.get("title") or course.title or "").strip()
        if not title:
            raise ValueError("Course title is required.")

        slug = slugify((kwargs.get("slug") or course.slug or title).strip())
        existing = Course.query.filter(func.lower(Course.slug) == slug.lower(), Course.id != course.id).first()
        if existing:
            raise ValueError(f'The slug "{slug}" already exists. Please use a different slug.')

        course.title = title
        course.slug = slug
        course.description = (kwargs.get("description") or "").strip() or None
        course.welcome_intro_script = (kwargs.get("welcome_intro_script") or "").strip() or None
        course.learning_outcomes_script = (kwargs.get("learning_outcomes_script") or "").strip() or None
        course.language_code = (kwargs.get("language_code") or course.language_code or "en").strip()
        course.track_type = _normalize_course_track_type(kwargs.get("track_type") or course.track_type)
        course.difficulty = (kwargs.get("difficulty") or "").strip() or None
        course.currency_code = (kwargs.get("currency_code") or course.currency_code or "INR").strip()
        course.max_level = max(int(kwargs.get("max_level") or course.max_level or 1), 1)
        access_type = (kwargs.get("access_type") or course.access_type or ("paid" if course.is_premium else "free")).strip().lower()
        if access_type not in {"free", "paid"}:
            access_type = "free"
        level_access_type = (kwargs.get("level_access_type") or getattr(course, "level_access_type", None) or "free").strip().lower()
        if level_access_type not in {"free", "paid"}:
            level_access_type = "free"
        course.access_type = access_type
        course.allow_level_purchase = bool(kwargs.get("allow_level_purchase"))
        course.level_access_type = level_access_type
        course.base_price = LMSService.safe_decimal(kwargs.get("base_price"), str(course.base_price or "0.00"))
        sale_price = kwargs.get("sale_price")
        course.sale_price = LMSService.safe_decimal(sale_price) if sale_price not in (None, "") else None
        course.level_price = LMSService.safe_decimal(kwargs.get("level_price"), str(getattr(course, "level_price", None) or "0.00"))
        level_sale_price = kwargs.get("level_sale_price")
        course.level_sale_price = LMSService.safe_decimal(level_sale_price) if level_sale_price not in (None, "") else None
        if access_type == "free":
            course.base_price = Decimal("0.00")
            course.sale_price = None
        if level_access_type == "free":
            course.level_price = Decimal("0.00")
            course.level_sale_price = None
        course.is_published = bool(kwargs.get("is_published"))
        course.is_premium = access_type == "paid" or bool(kwargs.get("is_premium"))
        course.status = "published" if course.is_published else ("archived" if course.status == "archived" else "draft")
        if course.is_published:
            course.workflow_status = "published"
            course.published_at = datetime.utcnow()
        elif course.workflow_status == "published":
            course.workflow_status = "draft"
        LMSService._sync_course_level_shells(course)

        LMSService.bump_content_version(course, "Course updated")
        db.session.commit()
        return course

    @staticmethod
    def delete_course(course: Course) -> None:
        db.session.delete(course)
        db.session.commit()

    @staticmethod
    def add_lesson(course: Course, title: str, **kwargs) -> Lesson:
        title = (title or "").strip()
        if not title:
            raise ValueError("Lesson title is required.")

        level = None
        level_id = kwargs.get("level_id")
        if level_id:
            level = Level.query.filter_by(id=level_id, course_id=course.id).first()

        if level is None:
            level = course.levels[0] if course.levels else None

        if level is None:
            level = Level(course_id=course.id, title="Level 1", sort_order=1)
            db.session.add(level)
            db.session.flush()

        module = None
        module_id = kwargs.get("module_id")
        if module_id:
            module = Module.query.filter_by(id=module_id, level_id=level.id).first()

        next_sort = len(level.lessons) + 1
        lesson = Lesson(
            level_id=level.id,
            module_id=module.id if module else None,
            title=title,
            slug=slugify(kwargs.get("slug") or title),
            lesson_type=(kwargs.get("lesson_type") or "guided").strip(),
            explanation_text=(kwargs.get("explanation_text") or "").strip() or None,
            explanation_tts_text=(kwargs.get("explanation_tts_text") or "").strip() or None,
            estimated_minutes=int(kwargs.get("estimated_minutes") or 10),
            is_published=bool(kwargs.get("is_published", True)),
            sort_order=next_sort,
        )
        db.session.add(lesson)
        db.session.flush()

        chapter = Chapter(
            lesson_id=lesson.id,
            title=(kwargs.get("chapter_title") or "Chapter 1").strip(),
            sort_order=1,
        )
        db.session.add(chapter)
        db.session.flush()

        subsection = Subsection(
            chapter_id=chapter.id,
            title=(kwargs.get("subsection_title") or "Subsection 1").strip(),
            sort_order=1,
            grammar_formula=(kwargs.get("grammar_formula") or "").strip() or None,
            grammar_tags=(kwargs.get("grammar_tags") or "").strip() or None,
            hint_seed=(kwargs.get("hint_seed") or "").strip() or None,
        )
        db.session.add(subsection)
        db.session.commit()
        return lesson

    @staticmethod
    def update_lesson(lesson: Lesson, **kwargs) -> Lesson:
        title = (kwargs.get("title") or lesson.title or "").strip()
        if not title:
            raise ValueError("Lesson title is required.")

        lesson.title = title
        lesson.slug = slugify(kwargs.get("slug") or lesson.slug or title)
        lesson.lesson_type = (kwargs.get("lesson_type") or lesson.lesson_type or "guided").strip()
        lesson.explanation_text = (kwargs.get("explanation_text") or "").strip() or None
        lesson.explanation_tts_text = (kwargs.get("explanation_tts_text") or "").strip() or None
        lesson.estimated_minutes = int(kwargs.get("estimated_minutes") or lesson.estimated_minutes or 10)
        lesson.is_published = bool(kwargs.get("is_published", lesson.is_published))
        db.session.commit()
        return lesson

    @staticmethod
    def delete_lesson(lesson: Lesson) -> None:
        db.session.delete(lesson)
        db.session.commit()

    @staticmethod
    def _clean_phrase(value: str) -> str:
        value = re.sub(r"\s+", " ", (value or "").strip())
        return value.strip(" ?.!,")

    @staticmethod
    def _yes_no_answer_patterns(prompt: str) -> list[str]:
        cleaned = LMSService._clean_phrase(prompt)
        lower = cleaned.lower()
        match = re.match(r"^(is|are|am|was|were)\s+(.*)$", lower)
        if match:
            verb = match.group(1)
            rest = LMSService._clean_phrase(cleaned[len(verb):])
            subject = rest.split()[0].capitalize() if rest else "It"
            complement = rest[len(rest.split()[0]):].strip() if rest.split() else ""
            complement = complement or "correct"
            pronoun_map = {"i": "I", "you": "You", "he": "He", "she": "She", "we": "We", "they": "They", "it": "It", "this": "It", "that": "It", "these": "They", "those": "They"}
            subject_word = rest.split()[0].lower() if rest.split() else 'it'
            answer_subject = pronoun_map.get(subject_word, subject)
            answer_verb = verb.capitalize() if answer_subject == 'I' and verb == 'am' else verb
            if answer_subject in {'It','He','She','This','That'} and verb == 'are':
                answer_verb = 'is'
            patterns = [
                f"Yes, {answer_subject} {answer_verb} {complement}.",
                f"No, {answer_subject} {answer_verb} not {complement}.",
                f"Yes, {answer_subject.lower() if answer_subject != 'I' else 'I'} looks like {complement}.",
                f"No, that seems to be something else.",
                f"It might be {complement}.",
                f"I think {answer_subject.lower() if answer_subject != 'I' else 'I'} {answer_verb} {complement}.",
                f"I'm not sure, but it could be {complement}.",
                f"Yes, that appears to be {complement}.",
                f"No, it doesn't look like {complement}.",
                f"It could possibly be {complement}.",
            ]
            return patterns
        for aux in ["do","does","did","can","could","will","would","should","has","have","had"]:
            if lower.startswith(aux + " "):
                clause = LMSService._clean_phrase(cleaned[len(aux):])
                aux_cap = aux.capitalize()
                return [
                    f"Yes, {clause}.",
                    f"No, {clause} not.",
                    f"Yes, I think {clause}.",
                    f"No, I don't think so.",
                    f"It might be possible.",
                ]
        return []

    @staticmethod
    def make_answer_patterns(prompt: str, grammar_formula: str | None = None) -> list[str]:
        prompt = LMSService._clean_phrase(prompt)
        if not prompt:
            return []
        lower = prompt.lower()

        yes_no = LMSService._yes_no_answer_patterns(prompt)
        if yes_no:
            return yes_no[:10]

        if lower.startswith(("what is ", "what's ")):
            topic = LMSService._clean_phrase(re.sub(r"^what(?: is|'s)\s+", "", prompt, flags=re.I))
            return [
                f"{topic} is ...",
                f"It is ...",
                f"I think {topic} is ...",
                f"In simple words, it is ...",
            ]
        if lower.startswith("what are "):
            topic = LMSService._clean_phrase(re.sub(r"^what are\s+", "", prompt, flags=re.I))
            return [
                f"{topic} are ...",
                f"They are ...",
                f"I think {topic} are ...",
                f"In simple words, they are ...",
            ]
        if lower.startswith("who "):
            return ["He/She is ...", "It is ...", "The person is ...", "I think it is ..."]
        if lower.startswith("where "):
            return ["It is in/at ...", "He/She is in ...", "I think it is near ...", "It may be in ..."]
        if lower.startswith("when "):
            return ["It happens in/on ...", "It is at ...", "I think it is during ...", "It may be around ..."]
        if lower.startswith("why "):
            return ["Because ...", "It is because ...", "I think the reason is ...", "This happens because ..."]
        if lower.startswith("how many ") or lower.startswith("how much "):
            return ["There is/are ...", "It is about ...", "I think it is ...", "Approximately ..."]
        if lower.startswith(("describe ", "talk about ", "speak about ", "write about ")):
            return [
                "First, I would introduce the topic clearly.",
                "Then, I would add one or two simple points.",
                "After that, I would give a real example.",
                "Finally, I would finish with a clear closing sentence.",
            ]
        return [
            "Start with a short direct answer.",
            "Then add one simple supporting detail.",
            "Finish with a clear complete sentence.",
        ]

    @staticmethod
    def make_synonym_help(prompt: str) -> str:
        prompt_words = [w.lower() for w in re.findall(r"[A-Za-z]+", prompt or "") if len(w) > 3]
        presets = {
            "good": "good → nice / useful / great",
            "big": "big → large / huge",
            "small": "small → little / tiny",
            "important": "important → necessary / valuable / major",
            "like": "like → enjoy / prefer",
            "happy": "happy → glad / joyful",
            "sad": "sad → unhappy / upset",
            "beautiful": "beautiful → lovely / attractive",
            "quick": "quick → fast / rapid",
            "smart": "smart → clever / bright",
        }
        lines = [value for key, value in presets.items() if key in prompt_words]
        if not lines:
            lines = [
                "good → nice / useful",
                "big → large",
                "small → little",
                "important → necessary",
                "like → enjoy",
            ]
        return " ; ".join(lines[:6])

    @staticmethod
    def make_translation_help(prompt: str) -> str:
        patterns = LMSService.make_answer_patterns(prompt)
        if patterns:
            preview = patterns[0]
            return f"First understand the meaning in your own language. Then write it in simple English like: {preview}"
        return "Think in your own language first, then write one short and clear sentence in simple English."

    @staticmethod
    def ensure_question_enrichment(question: Question, force: bool = False) -> Question:
        changed = False
        grammar_formula = question.subsection.grammar_formula if getattr(question, 'subsection', None) else None
        patterns = question.answer_patterns_list if hasattr(question, 'answer_patterns_list') else []
        if force or not patterns:
            generated = LMSService.make_answer_patterns(question.prompt, grammar_formula)
            question.answer_patterns_text = "\n".join(generated)
            question.answer_generation_status = "generated" if generated else "pending"
            question.answer_generated_at = datetime.utcnow() if generated else question.answer_generated_at
            changed = True
        if force or not (question.hint_text or '').strip():
            patterns = question.answer_patterns_list if hasattr(question, 'answer_patterns_list') else []
            question.hint_text = patterns[0] if patterns else LMSService.make_hint(question.prompt)
            changed = True
        if force or not (question.model_answer or '').strip():
            patterns = question.answer_patterns_list if hasattr(question, 'answer_patterns_list') else []
            question.model_answer = (patterns[0] if patterns else LMSService.make_model_answer(question.prompt, grammar_formula))
            changed = True
        if force or not (getattr(question, 'synonym_help_text', '') or '').strip():
            question.synonym_help_text = LMSService.make_synonym_help(question.prompt)
            changed = True
        if force or not (getattr(question, 'translation_help_text', '') or '').strip():
            question.translation_help_text = LMSService.make_translation_help(question.prompt)
            changed = True
        return question

    @staticmethod
    def add_question(
        subsection: Subsection,
        prompt: str,
        prompt_type: str = "question",
        **kwargs,
    ) -> Question:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("Question prompt is required.")

        next_sort = len(subsection.questions) + 1
        question = Question(
            subsection_id=subsection.id,
            title=(kwargs.get("title") or "").strip() or None,
            prompt=prompt,
            prompt_type=(prompt_type or "question").strip(),
            image_url=LMSService.normalize_question_image_url(kwargs.get("image_url")),
            hint_text=(kwargs.get("hint_text") or "").strip() or None,
            model_answer=(kwargs.get("model_answer") or "").strip() or None,
            evaluation_rubric=(kwargs.get("evaluation_rubric") or "").strip() or None,
            expected_keywords=(kwargs.get("expected_keywords") or "").strip() or None,
            answer_patterns_text=(kwargs.get("answer_patterns_text") or "").strip() or None,
            answer_generation_status=(kwargs.get("answer_generation_status") or "pending").strip() or "pending",
            synonym_help_text=(kwargs.get("synonym_help_text") or "").strip() or None,
            translation_help_text=(kwargs.get("translation_help_text") or "").strip() or None,
            language_code=(kwargs.get("language_code") or "en").strip(),
            is_active=bool(kwargs.get("is_active", True)),
            sort_order=int(kwargs.get("sort_order") or next_sort),
        )
        LMSService.ensure_question_enrichment(question)
        db.session.add(question)
        db.session.commit()
        return question

    @staticmethod
    def update_question(question: Question, **kwargs) -> Question:
        prompt = (kwargs.get("prompt") or question.prompt or "").strip()
        if not prompt:
            raise ValueError("Question prompt is required.")

        question.title = (kwargs.get("title") or "").strip() or None
        question.prompt = prompt
        question.prompt_type = (kwargs.get("prompt_type") or question.prompt_type or "question").strip()
        question.image_url = LMSService.normalize_question_image_url(kwargs.get("image_url"))
        question.hint_text = (kwargs.get("hint_text") or "").strip() or None
        question.model_answer = (kwargs.get("model_answer") or "").strip() or None
        question.evaluation_rubric = (kwargs.get("evaluation_rubric") or "").strip() or None
        question.expected_keywords = (kwargs.get("expected_keywords") or "").strip() or None
        question.answer_patterns_text = (kwargs.get("answer_patterns_text") or "").strip() or None
        question.synonym_help_text = (kwargs.get("synonym_help_text") or "").strip() or None
        question.translation_help_text = (kwargs.get("translation_help_text") or "").strip() or None
        question.language_code = (kwargs.get("language_code") or question.language_code or "en").strip()
        question.is_active = bool(kwargs.get("is_active", question.is_active))
        LMSService.ensure_question_enrichment(question)
        db.session.commit()
        return question

    @staticmethod
    def delete_question(question: Question) -> None:
        db.session.delete(question)
        db.session.commit()

    @staticmethod
    def auto_enroll_paid_student(student_id: int, course_id: int) -> Enrollment:
        return LMSService.enroll_full_course(student_id, course_id)

    @staticmethod
    def self_enroll_free_course(student_id: int, course: Course) -> Enrollment:
        if Decimal(str(course.current_price or 0)) > Decimal("0.00"):
            raise ValueError("This course requires payment before enrollment.")
        return LMSService.enroll_full_course(student_id, course.id)

    @staticmethod
    def self_enroll_free_level(student_id: int, course: Course, level_number: int) -> Enrollment:
        if not getattr(course, "allow_level_purchase", False):
            raise ValueError("This course does not support level-wise enrollment.")
        if Decimal(str(getattr(course, "current_level_price", 0) or 0)) > Decimal("0.00"):
            raise ValueError("This level requires payment before enrollment.")
        return LMSService.enroll_course_level(student_id, course.id, level_number)

    @staticmethod
    def set_course_status(course: Course, action: str):
        action = (action or "").strip().lower()

        if action == "publish":
            course.is_published = True
            course.status = "published"
        elif action == "unpublish":
            course.is_published = False
            course.status = "draft"
        elif action == "disable":
            course.status = "disabled"
        elif action == "archive":
            course.status = "archived"
            course.archived_at = datetime.utcnow()
            course.is_published = False
        elif action == "restore":
            course.status = "draft"
            course.archived_at = None

        db.session.commit()
        return course

    @staticmethod
    def parse_question_upload(file_storage) -> list[dict]:
        raw = file_storage.read()
        try:
            text = raw.decode("utf-8-sig")
        except Exception:
            text = raw.decode("latin-1", errors="ignore")

        filename = (file_storage.filename or "").lower()
        rows: list[dict] = []

        if filename.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(text))
            for idx, row in enumerate(reader, start=1):
                rows.append(
                    {
                        "title": (row.get("title") or "").strip(),
                        "prompt": (row.get("prompt") or row.get("question") or row.get("topic") or "").strip(),
                        "image_url": LMSService.normalize_question_image_url(row.get("image_url") or row.get("image") or row.get("image_path")),
                        "hint_text": (row.get("hint") or row.get("hint_text") or "").strip(),
                        "model_answer": (row.get("model_answer") or row.get("answer") or "").strip(),
                        "grammar_formula": (row.get("grammar_formula") or row.get("grammar") or "").strip(),
                        "evaluation_rubric": (row.get("evaluation_rubric") or "").strip(),
                        "expected_keywords": (row.get("expected_keywords") or "").strip(),
                        "answer_patterns_text": (row.get("answer_patterns_text") or row.get("possible_answers") or "").strip(),
                        "language_code": (row.get("language_code") or "en").strip(),
                        "prompt_type": (row.get("prompt_type") or "question").strip(),
                        "sort_order": idx,
                    }
                )
        else:
            for idx, line in enumerate([ln.strip() for ln in text.splitlines() if ln.strip()], start=1):
                rows.append(
                    {
                        "title": "",
                        "prompt": line,
                        "image_url": None,
                        "hint_text": "",
                        "model_answer": "",
                        "grammar_formula": "",
                        "evaluation_rubric": "",
                        "expected_keywords": "",
                        "answer_patterns_text": "",
                        "language_code": "en",
                        "prompt_type": "question",
                        "sort_order": idx,
                    }
                )

        return [r for r in rows if r["prompt"]]

    @staticmethod
    def infer_grammar(prompt: str) -> str:
        p = (prompt or "").lower()

        for label, markers in GRAMMAR_KEYWORDS.items():
            if any(marker in p for marker in markers):
                return label

        if p.startswith("describe ") or p.startswith("talk about "):
            return "topic speaking"

        if "read the passage" in p or "according to the passage" in p:
            return "reading task"

        if "listen and answer" in p or "audio" in p:
            return "listening task"

        if "write an essay" in p or "write about" in p:
            return "writing task"

        return "general speaking"

    @staticmethod
    def make_hint(prompt: str) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return "Give a short, clear answer."

        return " | ".join(
            [
                "Start with a direct answer.",
                "Add one real example from daily life.",
                "Finish with a reason or result.",
            ]
        )

    @staticmethod
    def make_model_answer(prompt: str, grammar_formula: str | None = None) -> str:
        grammar_formula = grammar_formula or LMSService.infer_grammar(prompt)

        if "interview" in grammar_formula:
            return "I would answer with a short introduction, relevant experience, and one concrete example."
        if "passive" in grammar_formula:
            return "A good answer should use the passive structure naturally and clearly."
        if "topic" in grammar_formula:
            return "A strong answer should include an introduction, two supporting points, and a conclusion."
        if "reading" in grammar_formula:
            return "A good answer should directly use the information given in the passage."
        if "listening" in grammar_formula:
            return "A strong answer should accurately reflect the key details from the audio."
        if "writing" in grammar_formula:
            return "A strong answer should have a clear structure, strong grammar, and relevant examples."

        return "A good answer should be clear, grammatical, and supported by one example."

    @staticmethod
    def upload_questions_to_lesson(lesson: Lesson, parsed_rows: list[dict], auto_split_size: int = 10) -> int:
        if auto_split_size < 1:
            auto_split_size = 10

        created = 0
        chapter_map: dict[int, Chapter] = {}
        subsection_map: dict[tuple[int, str], Subsection] = {}

        for idx, row in enumerate(parsed_rows, start=1):
            chapter_no = ((idx - 1) // auto_split_size) + 1

            if chapter_no not in chapter_map:
                chapter = Chapter(
                    lesson_id=lesson.id,
                    title=f"Chapter {chapter_no}",
                    sort_order=chapter_no,
                )
                db.session.add(chapter)
                db.session.flush()
                chapter_map[chapter_no] = chapter

            grammar = row.get("grammar_formula") or LMSService.infer_grammar(row["prompt"])
            subsection_key = (chapter_no, grammar)

            if subsection_key not in subsection_map:
                subsection = Subsection(
                    chapter_id=chapter_map[chapter_no].id,
                    title=grammar.title(),
                    sort_order=len([k for k in subsection_map if k[0] == chapter_no]) + 1,
                    grammar_formula=grammar,
                    grammar_tags=grammar.replace(" ", ","),
                    hint_seed=LMSService.make_hint(row["prompt"]),
                )
                db.session.add(subsection)
                db.session.flush()
                subsection_map[subsection_key] = subsection

            question = Question(
                subsection_id=subsection_map[subsection_key].id,
                title=row.get("title") or None,
                prompt=row["prompt"],
                prompt_type=row.get("prompt_type") or "question",
                image_url=LMSService.normalize_question_image_url(row.get("image_url")),
                hint_text=row.get("hint_text") or None,
                model_answer=row.get("model_answer") or None,
                evaluation_rubric=row.get("evaluation_rubric") or f"Check clarity, grammar, and relevance for {grammar}.",
                expected_keywords=row.get("expected_keywords") or None,
                answer_patterns_text=row.get("answer_patterns_text") or None,
                language_code=row.get("language_code") or "en",
                sort_order=idx,
            )
            LMSService.ensure_question_enrichment(question)
            db.session.add(question)
            created += 1

        db.session.commit()
        return created

    @staticmethod
    def lesson_first_subsection(lesson: Lesson) -> Subsection | None:
        for chapter in lesson.chapters:
            for subsection in chapter.subsections:
                return subsection
        return None

    @staticmethod
    def student_next_question(student_id: int, lesson_id: int, cooldown_days: int = 7) -> Question | None:
        questions = (
            Question.query.join(Subsection, Subsection.id == Question.subsection_id)
            .join(Chapter, Chapter.id == Subsection.chapter_id)
            .filter(Chapter.lesson_id == lesson_id, Question.is_active.is_(True))
            .order_by(Chapter.sort_order.asc(), Subsection.sort_order.asc(), Question.sort_order.asc(), Question.id.asc())
            .all()
        )
        if not questions:
            return None

        final_answered_ids = {
            row[0]
            for row in db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson_id,
                QuestionAttempt.attempt_kind == "final",
            )
            .distinct()
            .all()
        }

        for question in questions:
            if question.id not in final_answered_ids:
                return question
        return None

    @staticmethod
    def _normalize_eval_text(value: str) -> str:
        value = (value or "").strip().lower()
        value = value.replace("’", "'")
        value = re.sub(r"[^a-z0-9\s']", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    @staticmethod
    def _tokenize_eval_text(value: str) -> list[str]:
        normalized = LMSService._normalize_eval_text(value)
        return [token for token in normalized.split() if token]

    @staticmethod
    def _expand_eval_synonyms(tokens: list[str]) -> set[str]:
        synonym_map = {
            "yes": {"yes", "yeah", "yep", "correct", "right", "true"},
            "no": {"no", "not", "wrong", "false"},
            "pen": {"pen", "ballpen", "marker", "writing", "write"},
            "looks": {"look", "looks", "seems", "appears"},
            "maybe": {"maybe", "perhaps", "possibly", "probably", "might", "could"},
            "think": {"think", "believe", "feel"},
            "big": {"big", "large", "huge"},
            "small": {"small", "little", "tiny"},
            "good": {"good", "nice", "great", "fine"},
            "bad": {"bad", "poor", "wrong"},
        }
        expanded = set(tokens)
        for token in list(tokens):
            for group in synonym_map.values():
                if token in group:
                    expanded.update(group)
        return expanded

    @staticmethod
    def _pattern_match_details(question: Question, response_text: str) -> dict:
        response_normalized = LMSService._normalize_eval_text(response_text)
        response_tokens = LMSService._tokenize_eval_text(response_text)
        response_expanded = LMSService._expand_eval_synonyms(response_tokens)

        stored_patterns = []
        if question.answer_patterns_list:
            stored_patterns.extend(question.answer_patterns_list)
        if question.model_answer:
            stored_patterns.extend(
                [s.strip() for s in re.split(r"[\n;/]+", question.model_answer) if s.strip()]
            )

        clean_patterns = []
        seen = set()
        for pattern in stored_patterns:
            key = LMSService._normalize_eval_text(pattern)
            if key and key not in seen:
                clean_patterns.append(pattern.strip())
                seen.add(key)

        best_pattern = None
        best_score = 0.0
        exact_match = False
        strong_pattern_match = False
        partial_pattern_match = False

        for pattern in clean_patterns[:12]:
            pattern_normalized = LMSService._normalize_eval_text(pattern)
            pattern_tokens = LMSService._tokenize_eval_text(pattern)
            if not pattern_tokens:
                continue

            pattern_expanded = LMSService._expand_eval_synonyms(pattern_tokens)
            overlap = len(pattern_expanded & response_expanded)
            ratio = overlap / max(len(pattern_expanded), 1)

            if response_normalized == pattern_normalized:
                exact_match = True
                best_pattern = pattern
                best_score = 1.0
                break

            if ratio > best_score:
                best_score = ratio
                best_pattern = pattern

        if exact_match:
            strong_pattern_match = True
        elif best_score >= 0.55:
            strong_pattern_match = True
        elif best_score >= 0.30:
            partial_pattern_match = True

        return {
            "patterns": clean_patterns,
            "best_pattern": best_pattern,
            "best_score": round(best_score, 3),
            "exact_match": exact_match,
            "strong_pattern_match": strong_pattern_match,
            "partial_pattern_match": partial_pattern_match,
        }

    @staticmethod
    def evaluate_response(question: Question, response_text: str) -> dict:
        text = (response_text or "").strip()
        normalized = LMSService._normalize_eval_text(text)
        words = LMSService._tokenize_eval_text(text)
        word_count = len(words)

        grammar = question.subsection.grammar_formula or LMSService.infer_grammar(question.prompt)
        keywords = [k.strip().lower() for k in (question.expected_keywords or "").split(",") if k.strip()]
        keyword_hits = sum(1 for kw in keywords if kw in normalized)

        match = LMSService._pattern_match_details(question, text)
        exact_text_match = match["exact_match"]
        strong_pattern_match = match["strong_pattern_match"]
        partial_pattern_match = match["partial_pattern_match"]
        best_pattern = match["best_pattern"]
        pattern_score = match["best_score"]

        base_accuracy = 20 + min(word_count * 4, 28)
        if keywords:
            base_accuracy += min(keyword_hits * 10, 20)

        if exact_text_match:
            base_accuracy = max(base_accuracy, 95)
        elif strong_pattern_match:
            base_accuracy = max(base_accuracy, 82 + int(pattern_score * 10))
        elif partial_pattern_match:
            base_accuracy = max(base_accuracy, 62 + int(pattern_score * 12))
        elif word_count >= 4:
            base_accuracy += 8

        grammar_score = 38 + min(word_count * 2, 30)
        clarity_score = 35 + min(word_count * 2, 32)
        confidence_score = 30 + min(word_count * 2, 36)

        if exact_text_match:
            grammar_score = max(grammar_score, 90)
            clarity_score = max(clarity_score, 90)
            confidence_score = max(confidence_score, 88)
        elif strong_pattern_match:
            grammar_score = max(grammar_score, 78)
            clarity_score = max(clarity_score, 78)
            confidence_score = max(confidence_score, 75)
        elif partial_pattern_match:
            grammar_score = max(grammar_score, 64)
            clarity_score = max(clarity_score, 64)
            confidence_score = max(confidence_score, 60)

        accuracy = float(min(base_accuracy, 98))
        grammar_score = float(min(grammar_score, 95))
        clarity_score = float(min(clarity_score, 95))
        confidence_score = float(min(confidence_score, 95))

        verdict = "needs_improvement"
        if exact_text_match:
            verdict = "correct"
        elif strong_pattern_match:
            verdict = "acceptable"
        elif partial_pattern_match or accuracy >= 60 or (keyword_hits >= 1 and word_count >= 4):
            verdict = "partially_correct"

        is_correctish = verdict in {"correct", "acceptable", "partially_correct"}

        feedback = (
            f"Your answer needs improvement. Try to answer more directly and use the grammar pattern: {grammar}."
        )
        if verdict == "correct":
            feedback = "Excellent. Your answer matches a stored valid answer pattern."
        elif verdict == "acceptable":
            feedback = (
                f"Good job. Your answer matches the meaning of a valid stored answer. "
                f"To improve further, make it a little smoother and more natural."
            )
        elif verdict == "partially_correct":
            feedback = (
                f"Your answer is on the right track, but it should be closer to the expected meaning. "
                f"Try to answer more directly using the grammar pattern: {grammar}."
            )

        if best_pattern and verdict != "correct":
            feedback += f" Best matching stored pattern: {best_pattern}"

        explanation_text = (question.model_answer or question.hint_text or "").strip()

        return {
            "accuracy_score": accuracy,
            "grammar_score": grammar_score,
            "clarity_score": clarity_score,
            "confidence_score": confidence_score,
            "ai_feedback": feedback,
            "ai_detected_grammar": grammar,
            "is_correctish": is_correctish,
            "word_count": word_count,
            "keyword_hits": keyword_hits,
            "evaluation_verdict": verdict,
            "matched_pattern": best_pattern,
            "pattern_match_score": pattern_score,
            "exact_text_match": exact_text_match,
            "explanation_text": explanation_text,
        }
    
    @staticmethod
    def support_tool_limit(total_questions: int) -> int:
        if total_questions <= 0:
            return 0
        return max(1, int(math.ceil(total_questions * SUPPORT_TOOL_LIMIT_RATIO)))

    @staticmethod
    def support_tool_status(student_id: int, lesson: Lesson) -> dict:
        total_questions = lesson.question_count or (
            Question.query.join(Subsection, Subsection.id == Question.subsection_id)
            .join(Chapter, Chapter.id == Subsection.chapter_id)
            .filter(Chapter.lesson_id == lesson.id, Question.is_active.is_(True))
            .count()
        )
        quota = LMSService.support_tool_limit(total_questions)
        used = (
            QuestionAttempt.query.filter_by(
                student_id=student_id,
                lesson_id=lesson.id,
                attempt_kind=SUPPORT_TOOL_EVENT_KIND,
            ).count()
        )
        penalty_points = float(
            db.session.query(func.coalesce(func.sum(QuestionAttempt.support_tool_penalty_points), 0.0))
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == SUPPORT_TOOL_EVENT_KIND,
            )
            .scalar()
            or 0.0
        )
        return {
            "total_questions": int(total_questions or 0),
            "quota": int(quota),
            "used": int(used),
            "remaining": max(0, int(quota) - int(used)),
            "reached": bool(quota <= 0 or used >= quota),
            "penalty_points": round(penalty_points, 2),
        }

    @staticmethod
    def apply_support_tool_penalty(metrics: dict, *, hint_used: bool = False, synonym_used: bool = False, translation_used: bool = False) -> tuple[dict, float]:
        penalty = 0.0
        if hint_used:
            penalty += SUPPORT_TOOL_PENALTIES["hint"]
        if synonym_used:
            penalty += SUPPORT_TOOL_PENALTIES["synonym"]
        if translation_used:
            penalty += SUPPORT_TOOL_PENALTIES["translation"]
        if penalty <= 0:
            metrics["support_tool_penalty_points"] = 0.0
            return metrics, 0.0

        for key in ("accuracy_score", "grammar_score", "clarity_score", "confidence_score"):
            value = float(metrics.get(key) or 0.0)
            drop = penalty if key == "accuracy_score" else penalty * 0.35
            metrics[key] = max(0.0, round(value - drop, 2))

        metrics["support_tool_penalty_points"] = round(penalty, 2)
        feedback = (metrics.get("ai_feedback") or "").strip()
        penalty_note = f" Support tool penalty applied: -{int(round(penalty))} points."
        metrics["ai_feedback"] = (feedback + penalty_note).strip()
        return metrics, penalty

    @staticmethod
    def consume_support_tool(student_id: int, question: Question, tool_name: str) -> dict:
        tool = (tool_name or "").strip().lower()
        if tool not in SUPPORT_TOOL_PENALTIES:
            raise ValueError("Unsupported support tool.")

        subsection = question.subsection
        chapter = subsection.chapter
        lesson = chapter.lesson
        status = LMSService.support_tool_status(student_id, lesson)
        if status["reached"]:
            return status

        payload = {"tool": tool, "event": "opened"}
        user = db.session.get(User, student_id)
        allow_ml_training = bool(getattr(getattr(user, "preferences", None), "allow_ml_training", False))

        attempt = QuestionAttempt(
            student_id=student_id,
            lesson_id=lesson.id,
            chapter_id=chapter.id,
            subsection_id=subsection.id,
            question_id=question.id,
            response_mode="support_tool",
            attempt_kind=SUPPORT_TOOL_EVENT_KIND,
            hint_used=(tool == "hint"),
            synonym_used=(tool == "synonym"),
            translation_used=(tool == "translation"),
            support_tools_json=json.dumps(payload, ensure_ascii=False),
            support_tool_penalty_points=float(SUPPORT_TOOL_PENALTIES.get(tool, 0.0)),
            is_correctish=False,
        )
        db.session.add(attempt)
        db.session.flush()

        progress = LessonProgress.query.filter_by(student_id=student_id, lesson_id=lesson.id).first()
        if not progress:
            progress = LessonProgress(student_id=student_id, lesson_id=lesson.id)
            db.session.add(progress)

        updated = LMSService.support_tool_status(student_id, lesson)
        progress.total_questions = updated["total_questions"]
        progress.support_tool_usage_count = updated["used"]
        progress.support_tool_penalty_points = updated["penalty_points"]
        progress.last_activity_at = datetime.utcnow()
        db.session.commit()
        LMSService.sync_course_progress(student_id, lesson.course)
        return updated

    @staticmethod
    def log_attempt(
        student_id: int,
        question: Question,
        response_text: str,
        response_mode: str = "typed",
        duration_seconds: int | None = None,
        *,
        attempt_kind: str = "final",
        hint_used: bool = False,
        synonym_used: bool = False,
        translation_used: bool = False,
        skipped: bool = False,
        returned_after_skip: bool = False,
        skip_reason: str | None = None,
        support_tools: dict | None = None,
    ) -> QuestionAttempt:
        metrics = LMSService.evaluate_response(question, response_text)
        metrics, support_tool_penalty = LMSService.apply_support_tool_penalty(
            metrics,
            hint_used=bool(hint_used),
            synonym_used=bool(synonym_used),
            translation_used=bool(translation_used),
        )
        subsection = question.subsection
        chapter = subsection.chapter
        lesson = chapter.lesson

        prior_attempt_count = (
            QuestionAttempt.query.filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.question_id == question.id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind.in_(["check", "final"]),
            ).count()
        )
        retry_count = max(0, prior_attempt_count)
        is_retry = retry_count > 0 and attempt_kind == "final"

        user = db.session.get(User, student_id)
        allow_ml_training = bool(getattr(getattr(user, "preferences", None), "allow_ml_training", False))

        attempt = QuestionAttempt(
            student_id=student_id,
            lesson_id=lesson.id,
            chapter_id=chapter.id,
            subsection_id=subsection.id,
            question_id=question.id,
            response_text=response_text,
            stt_transcript=response_text if response_mode == "spoken" else None,
            response_mode=response_mode,
            duration_seconds=duration_seconds,
            attempt_kind=attempt_kind,
            retry_count=retry_count,
            is_retry=is_retry,
            hint_used=bool(hint_used),
            synonym_used=bool(synonym_used),
            translation_used=bool(translation_used),
            skipped=bool(skipped),
            returned_after_skip=bool(returned_after_skip),
            skip_reason=(skip_reason or "").strip() or None,
            support_tools_json=json.dumps(support_tools or {}, ensure_ascii=False) if support_tools else None,
            support_tool_penalty_points=support_tool_penalty,
            ml_consent_granted=allow_ml_training,
            accuracy_score=metrics.get("accuracy_score"),
            grammar_score=metrics.get("grammar_score"),
            clarity_score=metrics.get("clarity_score"),
            confidence_score=metrics.get("confidence_score"),
            ai_feedback=metrics.get("ai_feedback"),
            ai_detected_grammar=metrics.get("ai_detected_grammar"),
            is_correctish=bool(metrics.get("is_correctish")),
        )
        db.session.add(attempt)
        db.session.flush()

        progress = LessonProgress.query.filter_by(student_id=student_id, lesson_id=lesson.id).first()
        if not progress:
            progress = LessonProgress(student_id=student_id, lesson_id=lesson.id)
            db.session.add(progress)
        was_completed = bool(progress.completed_at)

        total = (
            Question.query.join(Subsection, Subsection.id == Question.subsection_id)
            .join(Chapter, Chapter.id == Subsection.chapter_id)
            .filter(Chapter.lesson_id == lesson.id, Question.is_active.is_(True))
            .count()
        )
        done = (
            db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == "final",
            )
            .distinct()
            .count()
        )
        skipped_count = (
            db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == "skip",
            )
            .distinct()
            .count()
        )
        retry_count_questions = (
            db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.is_retry.is_(True),
            )
            .distinct()
            .count()
        )

        support_tool_uses = (
            QuestionAttempt.query.filter_by(
                student_id=student_id,
                lesson_id=lesson.id,
                attempt_kind=SUPPORT_TOOL_EVENT_KIND,
            ).count()
        )
        support_tool_penalty_total = float(
            db.session.query(func.coalesce(func.sum(QuestionAttempt.support_tool_penalty_points), 0.0))
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == SUPPORT_TOOL_EVENT_KIND,
            )
            .scalar()
            or 0.0
        )

        progress.chapter_id = chapter.id
        progress.subsection_id = subsection.id
        progress.total_questions = total
        progress.completed_questions = done
        progress.skipped_questions = skipped_count
        progress.retry_questions = retry_count_questions
        progress.support_tool_usage_count = support_tool_uses
        progress.support_tool_penalty_points = support_tool_penalty_total
        progress.completion_percent = int(round((done / total) * 100)) if total else 0
        progress.last_activity_at = datetime.utcnow()
        if total and done >= total:
            progress.completed_at = datetime.utcnow()

        just_completed = False
        if total and done >= total and not was_completed:
            just_completed = True

        db.session.commit()
        try:
            StudentActivityService.track_attempt(attempt, lesson_completed=just_completed)
            db.session.commit()
        except Exception:
            db.session.rollback()
        LMSService.sync_course_progress(student_id, lesson.course)
        if just_completed:
            try:
                from .economy_service import EconomyService

                accuracy_score = float(getattr(attempt, "accuracy_score", 0.0) or 0.0)
                reward_plan = EconomyService.lesson_completion_reward_plan(
                    lesson.course,
                    accuracy_score=accuracy_score,
                )
                lesson_reward = int(reward_plan["coins_awarded"])

                EconomyService.award_coins(
                    student_id,
                    lesson_reward,
                    reference_type="lesson_completion",
                    reference_id=lesson.id,
                    title=f"Lesson complete: {lesson.title}",
                    description=" • ".join(reward_plan["notes"]) + f" • {int(round(accuracy_score))}% accuracy.",
                    created_by="system",
                    idempotency_key=f"lesson-complete:{student_id}:{lesson.id}",
                    activity_date=datetime.utcnow().date(),
                )
                current_streak = StudentActivityService.active_streak(student_id)
                EconomyService.award_streak_milestone_if_eligible(student_id, current_streak)
                db.session.commit()
            except Exception:
                db.session.rollback()
        return attempt

    @staticmethod
    def sync_course_progress(student_id: int, course: Course | None):
        if not course:
            return None

        lesson_ids = [lesson.id for level in course.levels for lesson in level.lessons]
        progress = CourseProgress.query.filter_by(student_id=student_id, course_id=course.id).first()

        if not progress:
            progress = CourseProgress(student_id=student_id, course_id=course.id)
            db.session.add(progress)

        lesson_rows = (
            LessonProgress.query.filter(
                LessonProgress.student_id == student_id,
                LessonProgress.lesson_id.in_(lesson_ids),
            ).all()
            if lesson_ids else []
        )

        progress.total_lessons = len(lesson_ids)
        progress.completed_lessons = sum(1 for row in lesson_rows if (row.completion_percent or 0) >= 100 or row.completed_at is not None)
        progress.total_questions = sum(int(row.total_questions or 0) for row in lesson_rows)
        progress.completed_questions = sum(int(row.completed_questions or 0) for row in lesson_rows)
        progress.completion_percent = int(round(sum(int(row.completion_percent or 0) for row in lesson_rows) / len(lesson_rows))) if lesson_rows else 0

        final_attempts = (
            QuestionAttempt.query
            .join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
            .join(Level, Level.id == Lesson.level_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                Level.course_id == course.id,
                QuestionAttempt.attempt_kind == "final",
            )
            .all()
        )
        accuracy_values = [float(row.accuracy_score) for row in final_attempts if row.accuracy_score is not None]
        progress.average_accuracy = round(sum(accuracy_values) / len(accuracy_values), 2) if accuracy_values else 0.0
        started_values = [row.started_at for row in lesson_rows if row.started_at]
        last_values = [row.last_activity_at for row in lesson_rows if row.last_activity_at]
        progress.first_started_at = min(started_values) if started_values else progress.first_started_at
        progress.last_activity_at = max(last_values) if last_values else progress.last_activity_at
        progress.completed_at = datetime.utcnow() if progress.total_lessons and progress.completed_lessons >= progress.total_lessons else None

        db.session.commit()
        return progress

    @staticmethod
    def lesson_progress_breakdown(student_id: int, lesson: Lesson) -> dict:
        progress = LessonProgress.query.filter_by(student_id=student_id, lesson_id=lesson.id).first()

        final_ids = {
            row[0]
            for row in db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == "final",
            )
            .distinct()
            .all()
        }
        skipped_ids = {
            row[0]
            for row in db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.attempt_kind == "skip",
            )
            .distinct()
            .all()
        }
        retry_ids = {
            row[0]
            for row in db.session.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.student_id == student_id,
                QuestionAttempt.lesson_id == lesson.id,
                QuestionAttempt.is_retry.is_(True),
            )
            .distinct()
            .all()
        }

        chapter_rows: list[dict] = []
        total_questions = 0
        completed_questions = 0
        skipped_questions = 0
        retry_questions = 0

        for chapter in lesson.chapters:
            subsection_rows: list[dict] = []
            chapter_total = 0
            chapter_done = 0
            chapter_skipped = 0
            chapter_retry = 0

            for subsection in chapter.subsections:
                questions = [q for q in subsection.questions if q.is_active]
                total = len(questions)
                done = sum(1 for q in questions if q.id in final_ids)
                skipped = sum(1 for q in questions if q.id in skipped_ids and q.id not in final_ids)
                retry = sum(1 for q in questions if q.id in retry_ids)
                percent = int(round((done / total) * 100)) if total else 0
                subsection_rows.append({
                    "id": subsection.id,
                    "title": subsection.title,
                    "grammar_formula": subsection.grammar_formula,
                    "total_questions": total,
                    "completed_questions": done,
                    "pending_questions": max(0, total - done),
                    "skipped_questions": skipped,
                    "retry_questions": retry,
                    "completion_percent": percent,
                })
                chapter_total += total
                chapter_done += done
                chapter_skipped += skipped
                chapter_retry += retry

            chapter_percent = int(round((chapter_done / chapter_total) * 100)) if chapter_total else 0
            chapter_rows.append({
                "id": chapter.id,
                "title": chapter.title,
                "description": chapter.description,
                "total_questions": chapter_total,
                "completed_questions": chapter_done,
                "pending_questions": max(0, chapter_total - chapter_done),
                "skipped_questions": chapter_skipped,
                "retry_questions": chapter_retry,
                "completion_percent": chapter_percent,
                "subsections": subsection_rows,
            })
            total_questions += chapter_total
            completed_questions += chapter_done
            skipped_questions += chapter_skipped
            retry_questions += chapter_retry

        lesson_percent = int(round((completed_questions / total_questions) * 100)) if total_questions else 0
        return {
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "total_questions": total_questions,
            "completed_questions": completed_questions,
            "pending_questions": max(0, total_questions - completed_questions),
            "skipped_questions": skipped_questions,
            "retry_questions": retry_questions,
            "completion_percent": progress.completion_percent if progress else lesson_percent,
            "support_tool_usage_count": int(progress.support_tool_usage_count if progress else 0),
            "support_tool_penalty_points": float(progress.support_tool_penalty_points if progress else 0.0),
            "completed_at": progress.completed_at if progress else None,
            "last_activity_at": progress.last_activity_at if progress else None,
            "chapters": chapter_rows,
        }

    @staticmethod
    def course_progress_breakdown(student_id: int, course: Course) -> dict:
        level_rows: list[dict] = []
        total_questions = 0
        completed_questions = 0
        skipped_questions = 0
        retry_questions = 0
        lesson_count = 0
        completed_lessons = 0

        for level in course.levels:
            lesson_rows: list[dict] = []
            level_total = 0
            level_done = 0
            level_skipped = 0
            level_retry = 0
            for lesson in level.lessons:
                breakdown = LMSService.lesson_progress_breakdown(student_id, lesson)
                lesson_rows.append(breakdown)
                level_total += breakdown["total_questions"]
                level_done += breakdown["completed_questions"]
                level_skipped += breakdown["skipped_questions"]
                level_retry += breakdown["retry_questions"]
                lesson_count += 1
                if breakdown["completed_at"] or breakdown["completion_percent"] >= 100:
                    completed_lessons += 1
            level_percent = int(round((level_done / level_total) * 100)) if level_total else 0
            level_rows.append({
                "id": level.id,
                "title": level.title,
                "description": level.description,
                "total_questions": level_total,
                "completed_questions": level_done,
                "pending_questions": max(0, level_total - level_done),
                "skipped_questions": level_skipped,
                "retry_questions": level_retry,
                "completion_percent": level_percent,
                "lessons": lesson_rows,
            })
            total_questions += level_total
            completed_questions += level_done
            skipped_questions += level_skipped
            retry_questions += level_retry

        overall_percent = int(round((completed_questions / total_questions) * 100)) if total_questions else 0
        return {
            "course_id": course.id,
            "course_title": course.title,
            "total_questions": total_questions,
            "completed_questions": completed_questions,
            "pending_questions": max(0, total_questions - completed_questions),
            "skipped_questions": skipped_questions,
            "retry_questions": retry_questions,
            "lesson_count": lesson_count,
            "completed_lessons": completed_lessons,
            "completion_percent": overall_percent,
            "levels": level_rows,
        }

    @staticmethod
    def lesson_metrics(lesson: Lesson) -> dict:
        question_count = 0
        for chapter in lesson.chapters:
            for subsection in chapter.subsections:
                question_count += len(subsection.questions)

        attempt_count = QuestionAttempt.query.filter_by(lesson_id=lesson.id).count()

        avg_accuracy = (
            db.session.query(func.avg(QuestionAttempt.accuracy_score))
            .filter(QuestionAttempt.lesson_id == lesson.id)
            .scalar()
            or 0
        )

        return {
            "question_count": question_count,
            "attempt_count": attempt_count,
            "avg_accuracy": int(round(avg_accuracy or 0)),
        }

    @staticmethod
    def course_metrics(course_id: int) -> dict:
        course = Course.query.get(course_id)
        if not course:
            return {
                "enrollments": 0,
                "question_count": 0,
                "lesson_count": 0,
                "avg_accuracy": 0,
            }

        enrollments = Enrollment.query.filter_by(course_id=course_id, status="active").count()

        question_count = (
            Question.query.join(Subsection, Subsection.id == Question.subsection_id)
            .join(Chapter, Chapter.id == Subsection.chapter_id)
            .join(Lesson, Lesson.id == Chapter.lesson_id)
            .join(Level, Level.id == Lesson.level_id)
            .filter(Level.course_id == course_id)
            .count()
        )

        lesson_count = (
            Lesson.query.join(Level, Level.id == Lesson.level_id)
            .filter(Level.course_id == course_id)
            .count()
        )

        avg_accuracy = (
            db.session.query(func.avg(QuestionAttempt.accuracy_score))
            .join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
            .join(Level, Level.id == Lesson.level_id)
            .filter(Level.course_id == course_id)
            .scalar()
            or 0
        )

        return {
            "enrollments": enrollments,
            "question_count": question_count,
            "lesson_count": lesson_count,
            "avg_accuracy": int(round(avg_accuracy or 0)),
        }

    @staticmethod
    def student_progress_report(student: User) -> dict:
        attempts = student.question_attempts.order_by(QuestionAttempt.attempted_at.asc()).all()
        enrollments = student.enrollments.filter_by(status="active").count()
        lesson_progress = student.lesson_progress.all()

        avg_accuracy = 0
        avg_grammar = 0
        avg_clarity = 0
        avg_confidence = 0

        if attempts:
            def _avg(values):
                return int(round(sum(values) / len(values))) if values else 0

            avg_accuracy = _avg([a.accuracy_score for a in attempts if a.accuracy_score is not None])
            avg_grammar = _avg([a.grammar_score for a in attempts if a.grammar_score is not None])
            avg_clarity = _avg([a.clarity_score for a in attempts if a.clarity_score is not None])
            avg_confidence = _avg([a.confidence_score for a in attempts if a.confidence_score is not None])

        overall_completion = 0
        if lesson_progress:
            overall_completion = int(round(sum(lp.completion_percent for lp in lesson_progress) / len(lesson_progress)))

        return {
            "active_enrollments": enrollments,
            "attempt_count": len(attempts),
            "avg_accuracy": avg_accuracy,
            "avg_grammar": avg_grammar,
            "avg_clarity": avg_clarity,
            "avg_confidence": avg_confidence,
            "overall_completion": overall_completion,
            "trend": student.performance_snapshot().get("progress_trend", "Stable"),
        }

    @staticmethod
    def export_students_csv_rows(students: list[User]) -> list[dict]:
        rows: list[dict] = []
        for student in students:
            perf = LMSService.student_progress_report(student)
            latest = student.login_events.order_by(db.text("created_at desc")).first()

            rows.append(
                {
                    "id": student.id,
                    "name": student.full_name,
                    "username": student.username,
                    "email": student.email,
                    "phone": student.phone or "",
                    "country": student.country or "",
                    "target_exam": student.target_exam or "",
                    "current_level": student.current_level or "",
                    "active_enrollments": perf["active_enrollments"],
                    "attempt_count": perf["attempt_count"],
                    "avg_accuracy": perf["avg_accuracy"],
                    "avg_grammar": perf["avg_grammar"],
                    "avg_clarity": perf["avg_clarity"],
                    "avg_confidence": perf["avg_confidence"],
                    "overall_completion": perf["overall_completion"],
                    "trend": perf["trend"],
                    "last_browser": latest.browser if latest else "",
                    "last_os": latest.os_name if latest else "",
                    "last_ip": latest.ip_address if latest else "",
                }
            )
        return rows


def _next_sort(existing_rows) -> int:
    current = [int(getattr(row, "sort_order", 0) or 0) for row in existing_rows]
    return (max(current) if current else 0) + 1


def _add_level(course: Course, title: str, **kwargs) -> Level:
    title = (title or "").strip()
    if not title:
        raise ValueError("Level title is required.")

    level = Level(
        course_id=course.id,
        title=title,
        description=(kwargs.get("description") or "").strip() or None,
        sort_order=int(kwargs.get("sort_order") or _next_sort(course.levels)),
    )
    db.session.add(level)
    db.session.commit()
    return level


def _delete_level(level: Level) -> None:
    db.session.delete(level)
    db.session.commit()


def _add_module(level: Level, title: str, **kwargs) -> Module:
    title = (title or "").strip()
    if not title:
        raise ValueError("Module title is required.")

    module = Module(
        level_id=level.id,
        title=title,
        description=(kwargs.get("description") or "").strip() or None,
        sort_order=int(kwargs.get("sort_order") or (len(level.modules) + 1)),
    )
    db.session.add(module)
    db.session.commit()
    return module


def _delete_module(module: Module) -> None:
    ordered_lessons = sorted(module.lessons, key=lambda row: ((row.sort_order or 0), row.id))
    for idx, lesson in enumerate(ordered_lessons, start=1):
        lesson.module_id = None
        lesson.sort_order = idx
    db.session.delete(module)
    db.session.commit()


def _add_chapter(lesson: Lesson, title: str, **kwargs) -> Chapter:
    title = (title or "").strip()
    if not title:
        raise ValueError("Chapter title is required.")

    chapter = Chapter(
        lesson_id=lesson.id,
        title=title,
        description=(kwargs.get("description") or "").strip() or None,
        sort_order=int(kwargs.get("sort_order") or _next_sort(lesson.chapters)),
    )
    db.session.add(chapter)
    db.session.commit()
    return chapter


def _delete_chapter(chapter: Chapter) -> None:
    db.session.delete(chapter)
    db.session.commit()


def _add_subsection(chapter: Chapter, title: str, **kwargs) -> Subsection:
    title = (title or "").strip()
    if not title:
        raise ValueError("Subsection title is required.")

    subsection = Subsection(
        chapter_id=chapter.id,
        title=title,
        grammar_formula=(kwargs.get("grammar_formula") or "").strip() or None,
        grammar_tags=(kwargs.get("grammar_tags") or "").strip() or None,
        hint_seed=(kwargs.get("hint_seed") or "").strip() or None,
        sort_order=int(kwargs.get("sort_order") or _next_sort(chapter.subsections)),
    )
    db.session.add(subsection)
    db.session.commit()
    return subsection


def _delete_subsection(subsection: Subsection) -> None:
    db.session.delete(subsection)
    db.session.commit()


def _course_tree(course: Course) -> list[dict]:
    tree: list[dict] = []
    for level in sorted(course.levels, key=lambda x: ((x.sort_order or 0), x.id)):
        level_payload = {
            "id": level.id,
            "title": level.title,
            "description": level.description,
            "sort_order": level.sort_order,
            "lessons": [],
        }
        for lesson in sorted(level.lessons, key=lambda x: ((x.sort_order or 0), x.id)):
            lesson_payload = {
                "id": lesson.id,
                "title": lesson.title,
                "sort_order": lesson.sort_order,
                "lesson_type": lesson.lesson_type,
                "module_title": lesson.module.title if lesson.module else None,
                "chapters": [],
            }
            for chapter in sorted(lesson.chapters, key=lambda x: ((x.sort_order or 0), x.id)):
                chapter_payload = {
                    "id": chapter.id,
                    "title": chapter.title,
                    "sort_order": chapter.sort_order,
                    "description": chapter.description,
                    "subsections": [],
                }
                for subsection in sorted(chapter.subsections, key=lambda x: ((x.sort_order or 0), x.id)):
                    chapter_payload["subsections"].append(
                        {
                            "id": subsection.id,
                            "title": subsection.title,
                            "sort_order": subsection.sort_order,
                            "grammar_formula": subsection.grammar_formula,
                            "grammar_tags": subsection.grammar_tags,
                            "question_count": len(subsection.questions),
                        }
                    )
                lesson_payload["chapters"].append(chapter_payload)
            level_payload["lessons"].append(lesson_payload)
        tree.append(level_payload)
    return tree


LMSService.add_level = staticmethod(_add_level)
LMSService.delete_level = staticmethod(_delete_level)
LMSService.add_module = staticmethod(_add_module)
LMSService.delete_module = staticmethod(_delete_module)
LMSService.add_chapter = staticmethod(_add_chapter)
LMSService.delete_chapter = staticmethod(_delete_chapter)
LMSService.add_subsection = staticmethod(_add_subsection)
LMSService.delete_subsection = staticmethod(_delete_subsection)
LMSService.course_tree = staticmethod(_course_tree)



def _content_snapshot(entity) -> dict:
    payload = {"id": getattr(entity, "id", None), "type": entity.__class__.__name__}
    for key in ["title", "slug", "description", "prompt", "model_answer", "status", "workflow_status", "version_number"]:
        if hasattr(entity, key):
            payload[key] = getattr(entity, key)
    return payload


def _bump_content_version(entity, summary: str = "Updated", created_by_id: int | None = None):
    if hasattr(entity, "version_number"):
        entity.version_number = int(getattr(entity, "version_number", 1) or 1) + 1
    version_no = int(getattr(entity, "version_number", 1) or 1)
    db.session.add(ContentVersion(
        entity_type=entity.__class__.__name__.lower(),
        entity_id=entity.id,
        version_number=version_no,
        change_summary=summary,
        snapshot_json=json.dumps(_content_snapshot(entity), ensure_ascii=False),
        created_by_id=created_by_id,
    ))
    return entity


def _submit_course_for_review(course: Course, actor_id: int | None = None) -> Course:
    course.workflow_status = "in_review"
    course.status = "in_review"
    course.submitted_for_review_at = datetime.utcnow()
    _bump_content_version(course, "Submitted for review", actor_id)
    db.session.commit()
    return course


def _publish_course(course: Course, actor_id: int | None = None) -> Course:
    course.workflow_status = "published"
    course.status = "published"
    course.is_published = True
    course.reviewed_at = datetime.utcnow()
    course.published_at = datetime.utcnow()
    _bump_content_version(course, "Published", actor_id)
    db.session.commit()
    return course


def _course_batches_for_admin(admin_id: int | None, course: Course) -> list[CourseBatch]:
    rows = CourseBatch.query.filter_by(course_id=course.id).all()
    if admin_id:
        rows = [row for row in rows if row.admin_id in {None, admin_id}]
    return sorted(rows, key=lambda row: ((row.starts_at or datetime.max), row.title.lower()))


def _ensure_default_batch(course: Course, admin_id: int | None = None) -> CourseBatch:
    existing = CourseBatch.query.filter_by(course_id=course.id, code=f"{course.slug}-general").first()
    if existing:
        return existing
    batch = CourseBatch(
        admin_id=admin_id,
        course_id=course.id,
        title="General Batch",
        code=f"{course.slug}-general",
        is_active=True,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def _ensure_certificate_placeholder(student_id: int, course: Course) -> CertificateRecord | None:
    lesson_ids = [lesson.id for level in course.levels for lesson in level.lessons]
    if not lesson_ids:
        return None

    student = User.query.get(student_id)
    if not student:
        return None

    progress = CourseProgress.query.filter_by(student_id=student_id, course_id=course.id).first()
    if progress and int(progress.completion_percent or 0) < 100:
        return None

    completed = LessonProgress.query.filter(
        LessonProgress.student_id == student_id,
        LessonProgress.lesson_id.in_(lesson_ids),
        LessonProgress.completion_percent >= 100,
    ).count()
    if completed < len(lesson_ids):
        return None

    cert = CertificateRecord.query.filter_by(student_id=student_id, course_id=course.id).first()
    profile_ready = bool((student.first_name or '').strip() and (student.father_name or '').strip() and (student.address or '').strip())
    desired_status = "eligible" if profile_ready else "profile_pending"
    if cert:
        if (cert.status or '') != desired_status:
            cert.status = desired_status
            db.session.commit()
        return cert

    code = f"FLU-{course.id:04d}-{student_id:04d}"
    cert = CertificateRecord(student_id=student_id, course_id=course.id, status=desired_status, certificate_code=code)
    db.session.add(cert)
    db.session.commit()
    return cert


def _question_spaced_priority(student_id: int, lesson_id: int, question_id: int) -> float:
    latest = QuestionAttempt.query.filter_by(
        student_id=student_id, lesson_id=lesson_id, question_id=question_id, attempt_kind="final"
    ).order_by(QuestionAttempt.attempted_at.desc()).first()
    if not latest:
        return 999.0
    return spaced_repetition_weight(latest.attempted_at, latest.accuracy_score)


def calculate_profile_completion(user):
    fields = [
        getattr(user, "avatar_path", None),
        getattr(user, "first_name", None),
        getattr(user, "last_name", None),
        getattr(user, "phone", None),
        getattr(user, "gender", None),
        getattr(user, "date_of_birth", None),
        getattr(user, "country", None),
        getattr(user, "state", None),
        getattr(user, "city", None),
        getattr(user, "native_language", None),
        getattr(user, "target_exam", None),
        getattr(user, "current_level", None),
        getattr(user, "target_score", None),
        getattr(user, "bio", None),
        getattr(user, "study_goal", None),
    ]

    total = len(fields)
    filled = 0

    for value in fields:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                filled += 1
        else:
            filled += 1

    if total == 0:
        return 0

    return int(round((filled / total) * 100))


def get_skill_breakdown(db, student_id):
    from app.models.lms import QuestionAttempt, LessonProgress

    attempts = (
        db.session.query(QuestionAttempt)
        .filter(
            QuestionAttempt.student_id == student_id,
            QuestionAttempt.attempt_kind == "final",
        )
        .all()
    )

    if attempts:
        accuracy = round(sum(float(a.accuracy_score or 0) for a in attempts) / len(attempts))
        grammar = round(sum(float(a.grammar_score or 0) for a in attempts) / len(attempts))
        clarity = round(sum(float(a.clarity_score or 0) for a in attempts) / len(attempts))
        confidence = round(sum(float(a.confidence_score or 0) for a in attempts) / len(attempts))
    else:
        accuracy = 0
        grammar = 0
        clarity = 0
        confidence = 0

    lesson_rows = (
        db.session.query(LessonProgress)
        .filter(LessonProgress.student_id == student_id)
        .all()
    )

    if lesson_rows:
        completion = round(
            sum(int(row.completion_percent or 0) for row in lesson_rows) / len(lesson_rows)
        )
        lessons_done = sum(1 for row in lesson_rows if int(row.completion_percent or 0) >= 100)
        completed_questions = sum(int(row.completed_questions or 0) for row in lesson_rows)
        skipped_tracked = sum(int(row.skipped_questions or 0) for row in lesson_rows)
        retries_tracked = sum(int(row.retry_questions or 0) for row in lesson_rows)
        support_tool_uses = sum(int(row.support_tool_usage_count or 0) for row in lesson_rows)
        penalty_tracked = round(
            sum(float(row.support_tool_penalty_points or 0) for row in lesson_rows)
        )
    else:
        completion = 0
        lessons_done = 0
        completed_questions = 0
        skipped_tracked = 0
        retries_tracked = 0
        support_tool_uses = 0
        penalty_tracked = 0

    return {
        "accuracy": accuracy,
        "grammar": grammar,
        "clarity": clarity,
        "confidence": confidence,
        "completion": completion,
        "lessons_done": lessons_done,
        "completed_questions": completed_questions,
        "skipped_tracked": skipped_tracked,
        "retries_tracked": retries_tracked,
        "support_tool_uses": support_tool_uses,
        "penalty_tracked": penalty_tracked,
    }

# Backward-compatible bindings for workflow helpers used by routes
LMSService.submit_course_for_review = staticmethod(_submit_course_for_review)
LMSService.publish_course = staticmethod(_publish_course)
LMSService.course_batches_for_admin = staticmethod(_course_batches_for_admin)
LMSService.ensure_default_batch = staticmethod(_ensure_default_batch)
LMSService.ensure_certificate_placeholder = staticmethod(_ensure_certificate_placeholder)

LMSService.question_spaced_priority = staticmethod(_question_spaced_priority)
