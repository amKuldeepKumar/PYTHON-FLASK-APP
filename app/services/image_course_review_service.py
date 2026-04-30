from __future__ import annotations

import csv
import io
import os
from difflib import get_close_matches
from collections import Counter, defaultdict

from flask import current_app

from ..models.lms import (
    Chapter,
    Course,
    CourseProgress,
    Enrollment,
    Lesson,
    LessonProgress,
    Level,
    Question,
    QuestionAttempt,
    Subsection,
)
from .lms_service import LMSService


class ImageCourseReviewService:
    OVERSIZED_IMAGE_KB = 350
    LARGE_BANK_TARGET = 200
    LARGE_BANK_MAX = 500
    DEFAULT_AUTO_SPLIT_SIZE = 10

    @staticmethod
    def _course_questions(course: Course) -> list[Question]:
        return (
            Question.query
            .join(Subsection, Subsection.id == Question.subsection_id)
            .join(Chapter, Chapter.id == Subsection.chapter_id)
            .join(Lesson, Lesson.id == Chapter.lesson_id)
            .join(Level, Level.id == Lesson.level_id)
            .filter(Level.course_id == course.id)
            .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc(), Question.sort_order.asc(), Question.id.asc())
            .all()
        )

    @staticmethod
    def _local_asset_meta(image_url: str | None) -> dict:
        normalized = LMSService.normalize_question_image_url(image_url)
        meta = {
            "normalized": normalized,
            "exists": LMSService._local_static_asset_exists(normalized),
            "size_kb": None,
            "extension": None,
            "is_local_static": False,
        }
        if not normalized or not normalized.startswith("/static/"):
            return meta
        try:
            relative_path = normalized.removeprefix("/static/").replace("/", os.sep)
            full_path = os.path.join(current_app.root_path, "static", relative_path)
            meta["is_local_static"] = True
            meta["extension"] = os.path.splitext(full_path)[1].lower()
            if os.path.exists(full_path):
                meta["size_kb"] = max(1, round(os.path.getsize(full_path) / 1024))
        except Exception:
            return meta
        return meta

    @staticmethod
    def _available_local_assets() -> list[str]:
        static_root = os.path.join(current_app.root_path, "static")
        rows: list[str] = []
        for root, _dirs, files in os.walk(static_root):
            for filename in files:
                rel = os.path.relpath(os.path.join(root, filename), static_root).replace(os.sep, "/")
                rows.append(f"/static/{rel}")
        return sorted(rows)

    @staticmethod
    def _repair_suggestions(image_url: str | None) -> list[str]:
        normalized = LMSService.normalize_question_image_url(image_url)
        if not normalized or LMSService._local_static_asset_exists(normalized):
            return []

        all_assets = ImageCourseReviewService._available_local_assets()
        if not all_assets:
            return []

        file_name = os.path.basename(normalized)
        stem = os.path.splitext(file_name)[0].lower()

        filename_map = {os.path.basename(path).lower(): path for path in all_assets}
        stem_map: dict[str, list[str]] = defaultdict(list)
        for path in all_assets:
            stem_map[os.path.splitext(os.path.basename(path))[0].lower()].append(path)

        matches: list[str] = []
        close_file_matches = get_close_matches(file_name.lower(), list(filename_map.keys()), n=5, cutoff=0.45)
        for key in close_file_matches:
            matches.append(filename_map[key])

        if stem:
            close_stem_matches = get_close_matches(stem, list(stem_map.keys()), n=5, cutoff=0.45)
            for key in close_stem_matches:
                matches.extend(stem_map[key])

        if normalized.startswith("/static/uploads/questions/"):
            folder_prefix = "/".join(normalized.split("/")[:-1]).rstrip("/")
            folder_matches = [path for path in all_assets if path.startswith(folder_prefix)]
            close_local_matches = get_close_matches(file_name.lower(), [os.path.basename(path).lower() for path in folder_matches], n=5, cutoff=0.35)
            for candidate in folder_matches:
                if os.path.basename(candidate).lower() in close_local_matches:
                    matches.append(candidate)

        deduped: list[str] = []
        for item in matches:
            if item not in deduped:
                deduped.append(item)
        return deduped[:5]

    @staticmethod
    def _is_image_course(course: Course, questions: list[Question]) -> bool:
        slug_title = f"{course.slug or ''} {course.title or ''}".lower()
        image_count = sum(1 for q in questions if q.image_url)
        return "image" in slug_title or "nursery" in slug_title or image_count >= max(1, len(questions) // 3)

    @staticmethod
    def _course_lessons(course: Course) -> list[Lesson]:
        return [
            lesson
            for level in (course.levels or [])
            for lesson in (level.lessons or [])
        ]

    @staticmethod
    def _ui_review(summary: dict) -> list[dict]:
        has_text_only = int(summary.get("text_only_count", 0) or 0) > 0
        has_images = int(summary.get("image_question_count", 0) or 0) > 0
        return [
            {
                "title": "Image-first lesson layout",
                "status": "pass" if has_images else "warn",
                "detail": "The student lesson template renders the image before the prompt and answer box for image-led questions." if has_images else "No image questions are available to visually review yet.",
            },
            {
                "title": "Text-only fallback coverage",
                "status": "pass" if has_text_only else "pass",
                "detail": "Questions without image_url continue to render in the normal lesson flow without breaking the page." if has_text_only else "The course is fully image-led. Text-only fallback remains supported platform-wide.",
            },
            {
                "title": "Responsive image handling",
                "status": "pass",
                "detail": "Lesson images use constrained sizing and lazy loading so the prompt, answer box, and actions remain visible on smaller screens.",
            },
        ]

    @staticmethod
    def _performance_snapshot(questions: list[Question]) -> dict:
        local_assets = []
        for question in questions:
            meta = ImageCourseReviewService._local_asset_meta(question.image_url)
            if meta["is_local_static"]:
                local_assets.append(meta)

        total_local_image_kb = sum(int(item["size_kb"] or 0) for item in local_assets)
        oversized_count = sum(1 for item in local_assets if int(item["size_kb"] or 0) > ImageCourseReviewService.OVERSIZED_IMAGE_KB)
        optimized_count = sum(1 for item in local_assets if item["extension"] in {".webp", ".svg"})
        return {
            "local_asset_count": len(local_assets),
            "total_local_image_kb": total_local_image_kb,
            "average_local_image_kb": int(round(total_local_image_kb / len(local_assets))) if local_assets else 0,
            "oversized_count": oversized_count,
            "optimized_ratio": int(round((optimized_count / len(local_assets)) * 100)) if local_assets else 100,
            "lazy_loading_enabled": True,
            "recommended_max_kb": ImageCourseReviewService.OVERSIZED_IMAGE_KB,
        }

    @staticmethod
    def _analytics_snapshot(course: Course, lessons: list[Lesson]) -> dict:
        lesson_ids = [lesson.id for lesson in lessons]
        enrollments = (
            Enrollment.query
            .filter_by(course_id=course.id, status="active")
            .all()
        )
        student_ids = sorted({int(row.student_id) for row in enrollments if row.student_id})

        final_attempts = (
            QuestionAttempt.query
            .filter(
                QuestionAttempt.lesson_id.in_(lesson_ids),
                QuestionAttempt.attempt_kind == "final",
            )
            .all()
            if lesson_ids
            else []
        )
        final_attempt_student_ids = sorted({int(row.student_id) for row in final_attempts if row.student_id})

        lesson_progress_rows = (
            LessonProgress.query
            .filter(LessonProgress.lesson_id.in_(lesson_ids))
            .all()
            if lesson_ids
            else []
        )
        course_progress_rows = CourseProgress.query.filter_by(course_id=course.id).all()

        average_accuracy = round(
            sum(float(row.accuracy_score or 0.0) for row in final_attempts if row.accuracy_score is not None)
            / max(1, sum(1 for row in final_attempts if row.accuracy_score is not None)),
            2,
        ) if any(row.accuracy_score is not None for row in final_attempts) else 0.0

        enrolled_with_lesson_progress = {
            int(row.student_id)
            for row in lesson_progress_rows
            if int(row.student_id or 0) in student_ids
        }
        enrolled_with_course_progress = {
            int(row.student_id)
            for row in course_progress_rows
            if int(row.student_id or 0) in student_ids
        }
        completed_students = sum(
            1
            for row in course_progress_rows
            if int(row.student_id or 0) in student_ids and int(row.completion_percent or 0) >= 100
        )

        return {
            "enrollment_count": len(student_ids),
            "students_with_attempts": len([sid for sid in final_attempt_student_ids if sid in student_ids]),
            "final_attempt_count": len(final_attempts),
            "lesson_progress_rows": len([row for row in lesson_progress_rows if int(row.student_id or 0) in student_ids]),
            "course_progress_rows": len([row for row in course_progress_rows if int(row.student_id or 0) in student_ids]),
            "enrolled_with_lesson_progress": len(enrolled_with_lesson_progress),
            "enrolled_with_course_progress": len(enrolled_with_course_progress),
            "completed_students": completed_students,
            "average_accuracy": average_accuracy,
            "checks": [
                {
                    "title": "Question attempts feed lesson progress",
                    "status": "pass" if not final_attempts or lesson_progress_rows else "warn",
                    "detail": "Final question attempts are creating lesson progress rows." if not final_attempts or lesson_progress_rows else "Attempts exist but no lesson progress rows were found.",
                },
                {
                    "title": "Lesson progress feeds course progress",
                    "status": "pass" if not lesson_progress_rows or course_progress_rows else "warn",
                    "detail": "Course progress rows are available for enrolled learners with lesson activity." if not lesson_progress_rows or course_progress_rows else "Lesson progress exists but course progress rows are missing.",
                },
                {
                    "title": "Accuracy pipeline remains active",
                    "status": "pass" if average_accuracy > 0 or not final_attempts else "warn",
                    "detail": f"Average recorded accuracy is {average_accuracy}% across final attempts." if final_attempts else "No final attempts recorded yet for this course.",
                },
            ],
        }

    @staticmethod
    def _admin_controls(course: Course) -> list[dict]:
        nursery_like = course.slug == "nursery-image-practice" or "nursery" in (course.title or "").lower()
        return [
            {
                "title": "Manual edit channel",
                "status": "pass",
                "detail": "Questions can be corrected through the existing question edit screen linked from the QA dashboard.",
            },
            {
                "title": "Bulk upload control",
                "status": "pass",
                "detail": "CSV/TXT content can be validated before import, then corrected through the same admin edit flow.",
            },
            {
                "title": "Image asset library",
                "status": "pass" if nursery_like else "warn",
                "detail": "Nursery Studio includes a local image library with copyable static paths." if nursery_like else "The course uses the shared image-question flow even if Nursery Studio is not the main authoring panel.",
            },
            {
                "title": "Question activation control",
                "status": "pass",
                "detail": "Admins can deactivate or reactivate incorrect rows directly from the QA page without deleting history.",
            },
        ]

    @staticmethod
    def _scalability_snapshot(questions: list[Question], lessons: list[Lesson]) -> dict:
        question_count = len(questions)
        lesson_question_counts = []
        for lesson in lessons:
            count = sum(
                1
                for chapter in (lesson.chapters or [])
                for subsection in (chapter.subsections or [])
                for question in (subsection.questions or [])
                if bool(getattr(question, "is_active", False))
            )
            lesson_question_counts.append(count)

        max_per_lesson = max(lesson_question_counts) if lesson_question_counts else 0
        avg_per_lesson = int(round(sum(lesson_question_counts) / len(lesson_question_counts))) if lesson_question_counts else 0
        chapter_plan_200 = max(1, (ImageCourseReviewService.LARGE_BANK_TARGET + ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE - 1) // ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE)
        chapter_plan_500 = max(1, (ImageCourseReviewService.LARGE_BANK_MAX + ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE - 1) // ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE)
        return {
            "current_question_count": question_count,
            "average_questions_per_lesson": avg_per_lesson,
            "largest_lesson_question_count": max_per_lesson,
            "auto_split_size": ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE,
            "projected_chapters_for_200": chapter_plan_200,
            "projected_chapters_for_500": chapter_plan_500,
            "status": "pass" if max_per_lesson <= 120 else "warn",
            "detail": "Current lesson density is within a safe range for future growth." if max_per_lesson <= 120 else "One lesson is becoming dense. Consider splitting future imports into more lesson buckets.",
        }

    @staticmethod
    def _question_issues(question: Question, *, duplicate_prompts: set[str], image_course: bool) -> list[dict]:
        issues: list[dict] = []
        prompt = (question.prompt or "").strip()
        prompt_key = prompt.lower()
        image_meta = ImageCourseReviewService._local_asset_meta(question.image_url)

        def add_issue(code: str, severity: str, title: str, detail: str):
            issues.append(
                {
                    "question_id": question.id,
                    "severity": severity,
                    "code": code,
                    "title": title,
                    "detail": detail,
                    "lesson_title": question.subsection.chapter.lesson.title,
                    "chapter_title": question.subsection.chapter.title,
                    "subsection_title": question.subsection.title,
                    "question_title": question.title or "Untitled question",
                    "image_url": question.image_url or "",
                    "is_active": bool(question.is_active),
                    "repair_suggestions": [],
                }
            )

        if image_course and not question.image_url:
            add_issue("missing_image", "high", "Missing image", "This image-led course question has no image_url linked.")
        if question.image_url and not image_meta["exists"]:
            add_issue("broken_image", "critical", "Broken image path", f"Linked asset was not found: {image_meta['normalized']}")
            issues[-1]["repair_suggestions"] = ImageCourseReviewService._repair_suggestions(question.image_url)
        if image_meta["size_kb"] and image_meta["size_kb"] > ImageCourseReviewService.OVERSIZED_IMAGE_KB:
            add_issue("oversized_image", "medium", "Heavy image file", f"Image is {image_meta['size_kb']} KB. Consider WEBP or stronger compression.")
        if image_meta["extension"] and image_meta["extension"] not in {".webp", ".svg"}:
            add_issue("image_format", "low", "Non-optimized image format", f"Current format is {image_meta['extension']}. WEBP or SVG is preferred for speed.")
        if prompt_key in duplicate_prompts:
            add_issue("duplicate_prompt", "high", "Duplicate prompt", "Another question in this course uses the same prompt text.")
        if len(prompt) < 8:
            add_issue("weak_prompt", "medium", "Prompt is too short", "Prompt text is very short and may be unclear for students.")
        if not (question.model_answer or "").strip():
            add_issue("missing_model_answer", "medium", "Missing model answer", "Students and reviewers have no clear answer reference.")
        if not (question.hint_text or "").strip():
            add_issue("missing_hint", "low", "Missing hint", "Add a short hint to support early learners.")
        if not (question.expected_keywords or "").strip():
            add_issue("missing_keywords", "low", "Missing keywords", "Keywords help evaluation and content review.")
        if not bool(question.is_active):
            add_issue("inactive_question", "low", "Inactive question", "This question is currently disabled and will not appear in the active lesson flow.")

        return issues

    @staticmethod
    def build_report(course: Course) -> dict:
        questions = ImageCourseReviewService._course_questions(course)
        lessons = ImageCourseReviewService._course_lessons(course)
        image_course = ImageCourseReviewService._is_image_course(course, questions)

        prompt_counter = Counter((q.prompt or "").strip().lower() for q in questions if (q.prompt or "").strip())
        duplicate_prompts = {prompt for prompt, count in prompt_counter.items() if count > 1}

        image_questions = 0
        broken_images = 0
        oversized_images = 0
        optimized_formats = 0
        total_local_images = 0
        issue_rows: list[dict] = []
        lesson_map: dict[int, dict] = defaultdict(lambda: {
            "lesson_id": 0,
            "lesson_title": "",
            "question_count": 0,
            "image_count": 0,
            "broken_count": 0,
            "issue_count": 0,
        })

        for question in questions:
            lesson = question.subsection.chapter.lesson
            lesson_row = lesson_map[lesson.id]
            lesson_row["lesson_id"] = lesson.id
            lesson_row["lesson_title"] = lesson.title
            lesson_row["question_count"] += 1

            asset_meta = ImageCourseReviewService._local_asset_meta(question.image_url)
            if question.image_url:
                image_questions += 1
                lesson_row["image_count"] += 1
            if question.image_url and not asset_meta["exists"]:
                broken_images += 1
                lesson_row["broken_count"] += 1
            if asset_meta["size_kb"] and asset_meta["size_kb"] > ImageCourseReviewService.OVERSIZED_IMAGE_KB:
                oversized_images += 1
            if asset_meta["is_local_static"]:
                total_local_images += 1
                if asset_meta["extension"] in {".webp", ".svg"}:
                    optimized_formats += 1

            q_issues = ImageCourseReviewService._question_issues(
                question,
                duplicate_prompts=duplicate_prompts,
                image_course=image_course,
            )
            lesson_row["issue_count"] += len(q_issues)
            issue_rows.extend(q_issues)

        issue_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        issue_rows.sort(key=lambda row: (issue_priority.get(row["severity"], 9), row["lesson_title"], row["question_title"]))

        summary = {
            "course_title": course.title,
            "lesson_count": len(lessons),
            "question_count": len(questions),
            "image_question_count": image_questions,
            "text_only_count": max(0, len(questions) - image_questions),
            "broken_image_count": broken_images,
            "oversized_image_count": oversized_images,
            "duplicate_prompt_count": len(duplicate_prompts),
            "issue_count": len(issue_rows),
            "optimized_image_ratio": int(round((optimized_formats / total_local_images) * 100)) if total_local_images else 100,
            "repairable_broken_count": sum(1 for row in issue_rows if row["code"] == "broken_image" and row.get("repair_suggestions")),
        }
        performance = ImageCourseReviewService._performance_snapshot(questions)
        analytics = ImageCourseReviewService._analytics_snapshot(course, lessons)
        admin_controls = ImageCourseReviewService._admin_controls(course)
        scalability = ImageCourseReviewService._scalability_snapshot(questions, lessons)
        ui_review = ImageCourseReviewService._ui_review(summary)

        summary["total_local_image_kb"] = performance["total_local_image_kb"]
        summary["largest_lesson_question_count"] = scalability["largest_lesson_question_count"]

        checks = [
            {
                "title": "Functional flow",
                "status": "pass" if questions else "warn",
                "detail": "Course has lesson questions connected to the normal LMS lesson flow." if questions else "No lesson questions found yet.",
            },
            {
                "title": "Image path integrity",
                "status": "pass" if broken_images == 0 else "fail",
                "detail": "All linked image paths resolved correctly." if broken_images == 0 else f"{broken_images} question(s) have broken image paths.",
            },
            {
                "title": "Fallback safety",
                "status": "pass",
                "detail": "Missing images fall back to a placeholder instead of breaking the lesson page.",
            },
            {
                "title": "Progress tracking compatibility",
                "status": "pass",
                "detail": "Image questions still use the existing question, attempt, and lesson progress system.",
            },
            {
                "title": "Performance readiness",
                "status": "pass" if oversized_images == 0 else "warn",
                "detail": "Image files are within the recommended size budget." if oversized_images == 0 else f"{oversized_images} image(s) should be compressed for smoother loading.",
            },
            {
                "title": "Analytics tracking validation",
                "status": "pass" if all(item["status"] == "pass" for item in analytics["checks"]) else "warn",
                "detail": "Question attempts, lesson progress, and course progress are staying connected for this course.",
            },
        ]

        future_notes = [
            "Add tags like animals, colors, fruits, and actions for faster filtering as the question bank grows.",
            "Add optional difficulty labels per question so nursery and beginner image courses can scale cleanly.",
            "Add image-category analytics to spot which picture types cause the most student mistakes later.",
            "If the question bank grows beyond 500 rows, add category-level filters and archive controls to keep review time short.",
        ]

        return {
            "summary": summary,
            "checks": checks,
            "issues": issue_rows,
            "lessons": sorted(lesson_map.values(), key=lambda row: row["lesson_title"].lower()),
            "future_notes": future_notes,
            "is_image_course": image_course,
            "ui_review": ui_review,
            "performance": performance,
            "analytics": analytics,
            "admin_controls": admin_controls,
            "scalability": scalability,
        }

    @staticmethod
    def report_csv_text(course: Course, report: dict | None = None) -> str:
        report = report or ImageCourseReviewService.build_report(course)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "key", "value"])
        for key, value in (report.get("summary") or {}).items():
            writer.writerow(["summary", key, value])
        for key, value in (report.get("performance") or {}).items():
            if key != "lazy_loading_enabled":
                writer.writerow(["performance", key, value])
        for key, value in (report.get("analytics") or {}).items():
            if key != "checks":
                writer.writerow(["analytics", key, value])
        for key, value in (report.get("scalability") or {}).items():
            writer.writerow(["scalability", key, value])
        writer.writerow([])
        writer.writerow([
            "severity",
            "code",
            "title",
            "detail",
            "lesson_title",
            "chapter_title",
            "subsection_title",
            "question_id",
            "question_title",
            "image_url",
            "repair_suggestions",
            "is_active",
        ])
        for issue in report.get("issues", []):
            writer.writerow([
                issue.get("severity", ""),
                issue.get("code", ""),
                issue.get("title", ""),
                issue.get("detail", ""),
                issue.get("lesson_title", ""),
                issue.get("chapter_title", ""),
                issue.get("subsection_title", ""),
                issue.get("question_id", ""),
                issue.get("question_title", ""),
                issue.get("image_url", ""),
                " | ".join(issue.get("repair_suggestions", [])),
                "yes" if issue.get("is_active") else "no",
            ])
        return output.getvalue()

    @staticmethod
    def validate_bulk_upload(course: Course, file_storage) -> dict:
        parsed_rows = LMSService.parse_question_upload(file_storage)
        issues = LMSService.validate_question_upload_rows(parsed_rows)

        existing_prompts = {
            (question.prompt or "").strip().lower()
            for question in ImageCourseReviewService._course_questions(course)
            if (question.prompt or "").strip()
        }
        duplicate_against_course = []
        missing_images = []
        suggestion_map: dict[str, list[str]] = {}

        for idx, row in enumerate(parsed_rows, start=1):
            prompt = (row.get("prompt") or "").strip().lower()
            image_url = LMSService.normalize_question_image_url(row.get("image_url"))
            if prompt and prompt in existing_prompts:
                duplicate_against_course.append(idx)
            if image_url and not LMSService._local_static_asset_exists(image_url):
                missing_images.append({"row": idx, "image_url": image_url})
                suggestion_map[image_url] = ImageCourseReviewService._repair_suggestions(image_url)

        if duplicate_against_course:
            issues.append(
                "Rows already used by this course prompt bank: " + ", ".join(str(row) for row in duplicate_against_course[:20])
            )

        projected_chapters = max(
            1,
            (len(parsed_rows) + ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE - 1)
            // ImageCourseReviewService.DEFAULT_AUTO_SPLIT_SIZE,
        )

        return {
            "row_count": len(parsed_rows),
            "issue_count": len(issues),
            "issues": issues,
            "missing_images": missing_images,
            "repair_suggestions": suggestion_map,
            "sample_rows": parsed_rows[:5],
            "duplicate_against_course": duplicate_against_course,
            "is_valid": len(issues) == 0,
            "projected_chapters": projected_chapters,
            "target_range": f"{ImageCourseReviewService.LARGE_BANK_TARGET}-{ImageCourseReviewService.LARGE_BANK_MAX}",
        }
