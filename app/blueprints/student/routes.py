from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import bp
from ...audit import audit
from ...extensions import db
from ...models.lms import (
    Chapter,
    Course,
    Enrollment,
    Level,
    Lesson,
    LessonProgress,
    CourseProgress,
    Question,
    QuestionAttempt,
    Subsection,
    CertificateRecord,
)
from ...models.translation_provider import TranslationProvider
from ...models.speaking_topic import SpeakingTopic
from ...models.reading_passage import ReadingPassage
from ...models.reading_topic import ReadingTopic
from ...models.reading_question import ReadingQuestion
from ...models.writing_topic import WritingTopic
from ...models.writing_task import WritingTask
from ...models.writing_submission import WritingSubmission
from ...models.reading_session_log import ReadingSessionLog
from ...models.speaking_session import SpeakingSession
from ...models.interview_session import InterviewSession
from ...models.student_daily_activity import StudentDailyActivity
from ...models.user_preferences import UserPreferences
from ...services.lms_client import (
    get_student_active_courses,
    get_student_dashboard_cards,
    get_student_progress_summary,
)
from ...services.language_service import resolve_language_code, language_label
from ...services.lms_service import LMSService, calculate_profile_completion, get_skill_breakdown
from ...services.translation_engine import translate_text
from ...services.tenancy_service import student_support_chain
from ...services.student_activity_service import StudentActivityService
from ...services.payment_service import PaymentService
from ...services.speaking.prompt_service import PromptService
from ...services.placement_test_service import PlacementTestService
from ...services.student_progress_analytics import StudentProgressAnalyticsService
from ...services.student_ai_intelligence import StudentAIIntelligenceService
from ...services.course_recommendation_service import CourseRecommendationService
from ...services.spoken_english_service import SpokenEnglishService
from ...services.speaking.speaking_session_service import SpeakingSessionService
from ...services.economy_service import EconomyService
from ...models.speaking_prompt import SpeakingPrompt
from ...models.payment import Payment


SKIPPED_SESSION_KEY = "student_skipped_questions"
INTRO_SESSION_KEY = "student_seen_lesson_intro"
SUPPORT_TOOL_SESSION_KEY = "student_support_tool_state"
LESSON_FLOW_SESSION_KEY = "student_lesson_flow_state"
LESSON_RECENT_WINDOW = 3
TRANSLATION_RUNTIME_VERSION = "lesson-runtime-v1"
PLACEMENT_TEST_SESSION_KEY = "student_placement_test_result"



def _translated_or_source(source_text: str | None, target_lang: str, *, context: str, version: str | None = None) -> str:
    source = (source_text or "").strip()
    if not source:
        return ""
    if not target_lang or target_lang == "en":
        return source
    try:
        translated, _from_cache = translate_text(
            source,
            target_lang,
            source_lang="en",
            context=context,
            version=version or TRANSLATION_RUNTIME_VERSION,
        )
        return (translated or source).strip() or source
    except Exception as exc:
        current_app.logger.warning("Lesson translation fallback for %s: %s", context, exc)
        return source


def _build_question_translation_payload(question: Question | None, target_lang: str, enabled: bool) -> dict:
    payload = {
        "provider_enabled": False,
        "question_prompt": "",
        "question_support": "",
        "answer_support": "",
        "translated_answer_pattern": "",
        "english_answer_pattern": "",
    }
    if not question or not enabled or not target_lang or target_lang == "en":
        return payload

    provider = TranslationProvider.primary()
    payload["provider_enabled"] = bool(provider.is_enabled)

    answer_pattern = (
        (question.model_answer or "").strip()
        or (question.answer_patterns_list[0] if question.answer_patterns_list else "")
        or "Use one direct sentence that answers the question clearly."
    )
    question_support_source = (question.translation_help_text or "").strip() or question.prompt
    answer_support_source = (question.translation_help_text or question.hint_text or "").strip() or (
        "Say your answer in your own language first. Then convert it into one short, clear English sentence."
    )

    payload["question_prompt"] = _translated_or_source(
        question.prompt,
        target_lang,
        context=f"question:prompt:{question.id}",
        version=f"q{question.id}:v{question.version_number}",
    )
    payload["question_support"] = _translated_or_source(
        question_support_source,
        target_lang,
        context=f"question:support:{question.id}",
        version=f"q{question.id}:v{question.version_number}",
    )
    payload["answer_support"] = _translated_or_source(
        answer_support_source,
        target_lang,
        context=f"question:answer_support:{question.id}",
        version=f"q{question.id}:v{question.version_number}",
    )
    payload["translated_answer_pattern"] = _translated_or_source(
        answer_pattern,
        target_lang,
        context=f"question:answer_pattern:{question.id}",
        version=f"q{question.id}:v{question.version_number}",
    )
    payload["english_answer_pattern"] = answer_pattern
    return payload


def _student_prefs():
    prefs = getattr(current_user, "preferences", None)
    if prefs:
        return prefs

    prefs = UserPreferences(
        user_id=current_user.id,
        accent="en-IN",
        translation_support_language_code=(getattr(current_user, "native_language", None) or "en"),
        use_native_language_support=True,
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


def _resolve_translation_support_context(prefs) -> tuple[str, str, bool]:
    pref_support_code = resolve_language_code(
        getattr(prefs, "translation_support_language_code", None),
        default="",
    )
    native_support_code = resolve_language_code(
        getattr(current_user, "native_language", None),
        default="",
    )

    # Prefer explicit support language from preferences.
    # If old data still has English there but profile native language is non-English,
    # fall back to native language until preferences are saved again.
    if pref_support_code and pref_support_code != "en":
        translation_language_code = pref_support_code
    elif native_support_code and native_support_code != "en":
        translation_language_code = native_support_code
    else:
        translation_language_code = "en"

    translation_language_name = language_label(
        translation_language_code,
        fallback="English",
    )

    translation_support_enabled = bool(
        getattr(prefs, "use_native_language_support", True)
        and translation_language_code
        and translation_language_code != "en"
    )

    return translation_language_code, translation_language_name, translation_support_enabled


def _course_lesson_ids(course: Course) -> list[int]:
    lesson_ids: list[int] = []
    for level in course.levels:
        for lesson in level.lessons:
            lesson_ids.append(lesson.id)
    return lesson_ids


def _lesson_questions(lesson_id: int) -> list[Question]:
    return (
        Question.query.join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .filter(Chapter.lesson_id == lesson_id, Question.is_active.is_(True))
        .order_by(
            Chapter.sort_order.asc(),
            Subsection.sort_order.asc(),
            Question.sort_order.asc(),
            Question.id.asc(),
        )
        .all()
    )


def _skipped_question_ids(lesson_id: int) -> list[int]:
    payload = session.get(SKIPPED_SESSION_KEY, {}) or {}
    ids = payload.get(str(lesson_id), []) or []
    clean = []
    for item in ids:
        try:
            clean.append(int(item))
        except Exception:
            continue
    return clean


def _set_skipped_question_ids(lesson_id: int, values: list[int]) -> None:
    payload = session.get(SKIPPED_SESSION_KEY, {}) or {}
    payload[str(lesson_id)] = [int(v) for v in values]
    session[SKIPPED_SESSION_KEY] = payload
    session.modified = True


def _lesson_flow_state(lesson_id: int) -> dict:
    payload = session.get(LESSON_FLOW_SESSION_KEY, {}) or {}
    state = payload.get(str(lesson_id), {}) or {}
    return {
        "queue": [int(v) for v in state.get("queue", []) if str(v).isdigit()],
        "deferred": [int(v) for v in state.get("deferred", []) if str(v).isdigit()],
        "recent": [int(v) for v in state.get("recent", []) if str(v).isdigit()],
        "active_question_id": (
            int(state.get("active_question_id"))
            if str(state.get("active_question_id", "")).isdigit()
            else None
        ),
    }


def _store_lesson_flow_state(lesson_id: int, state: dict) -> None:
    payload = session.get(LESSON_FLOW_SESSION_KEY, {}) or {}
    payload[str(lesson_id)] = {
        "queue": [int(v) for v in state.get("queue", [])],
        "deferred": [int(v) for v in state.get("deferred", [])],
        "recent": [int(v) for v in state.get("recent", [])][-LESSON_RECENT_WINDOW:],
        "active_question_id": state.get("active_question_id"),
    }
    session[LESSON_FLOW_SESSION_KEY] = payload
    session.modified = True


def _refresh_lesson_flow(student_id: int, lesson_id: int) -> dict:
    questions = _lesson_questions(lesson_id)
    ordered_ids = [q.id for q in questions]
    valid_ids = set(ordered_ids)
    final_ids = _question_final_ids(student_id, lesson_id)

    state = _lesson_flow_state(lesson_id)
    queue = [qid for qid in state.get("queue", []) if qid in valid_ids and qid not in final_ids]
    deferred = [qid for qid in state.get("deferred", []) if qid in valid_ids and qid not in final_ids]
    recent = [qid for qid in state.get("recent", []) if qid in valid_ids]
    active_question_id = state.get("active_question_id")
    if active_question_id not in valid_ids or active_question_id in final_ids:
        active_question_id = None

    seen = set(queue) | set(deferred) | final_ids
    for qid in ordered_ids:
        if qid not in seen:
            queue.append(qid)

    if not queue and deferred:
        queue = deferred[:]
        deferred = []

    state = {
        "queue": queue,
        "deferred": deferred,
        "recent": recent[-LESSON_RECENT_WINDOW:],
        "active_question_id": active_question_id,
    }
    _store_lesson_flow_state(lesson_id, state)
    _set_skipped_question_ids(lesson_id, deferred)
    return state


def _choose_next_from_queue(queue: list[int], recent: list[int]) -> int | None:
    if not queue:
        return None
    if len(queue) == 1:
        return queue[0]
    recent_set = set(recent[-LESSON_RECENT_WINDOW:])
    for qid in queue:
        if qid not in recent_set:
            return qid
    return queue[0]


def _activate_next_question(student_id: int, lesson_id: int) -> Question | None:
    state = _refresh_lesson_flow(student_id, lesson_id)
    active_question_id = state.get("active_question_id")
    pending_ids = set(state.get("queue", [])) | set(state.get("deferred", []))
    if active_question_id and active_question_id in pending_ids:
        return Question.query.get(active_question_id)

    queue = list(state.get("queue", []))
    deferred = list(state.get("deferred", []))
    recent = list(state.get("recent", []))

    if not queue and deferred:
        queue = deferred[:]
        deferred = []

    next_id = _choose_next_from_queue(queue, recent)
    if next_id is None:
        state["active_question_id"] = None
        state["queue"] = queue
        state["deferred"] = deferred
        _store_lesson_flow_state(lesson_id, state)
        _set_skipped_question_ids(lesson_id, deferred)
        return None

    state["queue"] = queue
    state["deferred"] = deferred
    state["active_question_id"] = next_id
    _store_lesson_flow_state(lesson_id, state)
    _set_skipped_question_ids(lesson_id, deferred)
    return Question.query.get(next_id)


def _complete_active_question(student_id: int, lesson_id: int, question_id: int) -> None:
    state = _refresh_lesson_flow(student_id, lesson_id)
    state["queue"] = [qid for qid in state.get("queue", []) if qid != question_id]
    state["deferred"] = [qid for qid in state.get("deferred", []) if qid != question_id]
    recent = [qid for qid in state.get("recent", []) if qid != question_id]
    recent.append(question_id)
    state["recent"] = recent[-LESSON_RECENT_WINDOW:]
    if state.get("active_question_id") == question_id:
        state["active_question_id"] = None
    _store_lesson_flow_state(lesson_id, state)
    _set_skipped_question_ids(lesson_id, state.get("deferred", []))


def _defer_active_question(student_id: int, lesson_id: int, question_id: int) -> None:
    state = _refresh_lesson_flow(student_id, lesson_id)
    queue = [qid for qid in state.get("queue", []) if qid != question_id]
    deferred = [qid for qid in state.get("deferred", []) if qid != question_id]
    deferred.append(question_id)
    recent = [qid for qid in state.get("recent", []) if qid != question_id]
    recent.append(question_id)
    state["queue"] = queue
    state["deferred"] = deferred
    state["recent"] = recent[-LESSON_RECENT_WINDOW:]
    if state.get("active_question_id") == question_id:
        state["active_question_id"] = None
    if not state["queue"] and state["deferred"]:
        state["queue"] = state["deferred"][:]
        state["deferred"] = []
    _store_lesson_flow_state(lesson_id, state)
    _set_skipped_question_ids(lesson_id, state.get("deferred", []))


def _clear_lesson_flow(lesson_id: int) -> None:
    payload = session.get(LESSON_FLOW_SESSION_KEY, {}) or {}
    payload.pop(str(lesson_id), None)
    session[LESSON_FLOW_SESSION_KEY] = payload
    session.modified = True


def _mark_intro_seen(lesson_id: int) -> None:
    payload = session.get(INTRO_SESSION_KEY, []) or []
    lesson_key = str(lesson_id)
    if lesson_key not in payload:
        payload.append(lesson_key)
    session[INTRO_SESSION_KEY] = payload
    session.modified = True


def _has_seen_intro(lesson_id: int) -> bool:
    progress = (
        LessonProgress.query.filter_by(student_id=current_user.id, lesson_id=lesson_id).first()
        if getattr(current_user, "is_authenticated", False)
        else None
    )
    if progress and (progress.started_at or progress.last_activity_at or progress.completed_questions > 0):
        return True
    payload = session.get(INTRO_SESSION_KEY, []) or []
    return str(lesson_id) in payload


def _question_final_ids(student_id: int, lesson_id: int) -> set[int]:
    return {
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


def _question_has_skip_history(student_id: int, lesson_id: int, question_id: int) -> bool:
    return (
        QuestionAttempt.query.filter_by(
            student_id=student_id,
            lesson_id=lesson_id,
            question_id=question_id,
            attempt_kind="skip",
        ).count()
        > 0
    )


def _select_next_question(student_id: int, lesson_id: int) -> Question | None:
    questions = _lesson_questions(lesson_id)
    if not questions:
        return None

    final_ids = _question_final_ids(student_id, lesson_id)
    skipped_ids = set(_skipped_question_ids(lesson_id))

    def _sort_key(q: Question):
        return (-float(LMSService.question_spaced_priority(student_id, lesson_id, q.id)), q.sort_order or 0, q.id)

    primary_pool = sorted(
        [q for q in questions if q.id not in final_ids and q.id not in skipped_ids],
        key=_sort_key,
    )
    deferred_pool = sorted(
        [q for q in questions if q.id not in final_ids and q.id in skipped_ids],
        key=_sort_key,
    )

    if primary_pool:
        return primary_pool[0]
    if deferred_pool:
        return deferred_pool[0]
    return None


def _active_enrollment(course_id: int) -> Enrollment | None:
    return (
        Enrollment.query.filter_by(
            student_id=current_user.id,
            course_id=course_id,
            status="active",
        )
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .first()
    )


def _course_welcome_required(enrollment: Enrollment | None) -> bool:
    return bool(enrollment and not getattr(enrollment, "welcome_seen_at", None))


def _course_welcome_points(course: Course) -> list[str]:
    custom_script = (getattr(course, "welcome_intro_script", None) or "").strip()
    if custom_script:
        return [line.strip() for line in custom_script.splitlines() if line.strip()][:4]

    points: list[str] = []
    lesson_titles = []
    for level in course.levels[:2]:
        for lesson in level.lessons[:3]:
            if lesson.title:
                lesson_titles.append(lesson.title)
    if lesson_titles:
        points.append(f"You will work through lessons like {', '.join(lesson_titles[:3])}.")

    if getattr(course, "question_count", 0):
        points.append(f"You will practice with {int(course.question_count or 0)} guided questions and activities.")

    track_type = _normalized_track_type(course).replace("_", " ").title()
    points.append(f"You will build confidence in {track_type.lower()} with short, step-by-step practice.")

    description = (course.description or "").strip()
    if description:
        points.append(description)

    return points[:4]


def _course_learning_outcomes(course: Course) -> list[str]:
    custom_script = (getattr(course, "learning_outcomes_script", None) or "").strip()
    if custom_script:
        return [line.strip() for line in custom_script.splitlines() if line.strip()][:4]

    outcomes: list[str] = []
    difficulty = (getattr(course, "difficulty", "") or "basic").strip().title()
    outcomes.append(f"You will learn {difficulty.lower()} skills in {(_normalized_track_type(course) or 'guided').replace('_', ' ').lower()}.")

    lesson_titles = []
    for level in course.levels[:2]:
        for lesson in level.lessons[:4]:
            if lesson.title:
                lesson_titles.append(lesson.title)
    if lesson_titles:
        outcomes.append(f"You will learn through topics such as {', '.join(lesson_titles[:4])}.")

    if getattr(course, "community_enabled", False):
        outcomes.append("You can also ask safe questions in the student course chat whenever you need help.")

    outcomes.append("Take your time, answer clearly, and keep moving one lesson at a time.")
    return outcomes[:4]


def _course_welcome_message(course: Course) -> str:
    welcome_lines = [
        f"Welcome to {course.title}.",
        * _course_welcome_points(course),
        * _course_learning_outcomes(course),
        "Thanks. Start your course journey.",
    ]
    return " ".join(line.strip() for line in welcome_lines if line.strip())


def _normalize_course_level_number(course: Course, value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 1
    return max(1, min(number, int(getattr(course, "max_level", 1) or 1)))


def _enrollment_level_summary(enrollment: Enrollment | None) -> str:
    if not enrollment:
        return "No access"
    if enrollment.has_full_access():
        return "All levels unlocked"
    levels = enrollment.purchased_levels
    if not levels:
        return "No levels unlocked"
    return ", ".join(f"L{level}" for level in levels)


def _course_level_access(course: Course, enrollment: Enrollment | None, level_number: int | None) -> bool:
    if not enrollment:
        return False
    return LMSService.course_has_level_access(enrollment, _normalize_course_level_number(course, level_number or 1))


def _course_level_checkout_url(course: Course, level_number: int | None = None) -> str:
    if level_number in (None, 0):
        return url_for("student.course_checkout", course_id=course.id)
    return url_for("student.course_checkout", course_id=course.id, purchase_scope="single_level", level=_normalize_course_level_number(course, level_number))


def _course_progress_percent(course: Course) -> int:
    row = CourseProgress.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if row:
        return int(row.completion_percent or 0)
    lesson_ids = _course_lesson_ids(course)
    if not lesson_ids:
        return 0
    rows = LessonProgress.query.filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id.in_(lesson_ids),
    ).all()
    if not rows:
        return 0
    return int(round(sum((row.completion_percent or 0) for row in rows) / len(rows)))


def _student_enrollment_map(student_id: int) -> dict[int, Enrollment]:
    rows = (
        Enrollment.query
        .filter_by(student_id=student_id, status="active")
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .all()
    )
    enrollment_map: dict[int, Enrollment] = {}
    for row in rows:
        enrollment_map.setdefault(row.course_id, row)
    return enrollment_map


def _student_course_progress_map(student_id: int, course_ids: set[int] | list[int] | tuple[int, ...]) -> dict[int, int]:
    normalized_ids = {int(course_id) for course_id in (course_ids or []) if course_id}
    if not normalized_ids:
        return {}

    progress_map: dict[int, int] = {course_id: 0 for course_id in normalized_ids}
    rows = CourseProgress.query.filter(
        CourseProgress.student_id == student_id,
        CourseProgress.course_id.in_(normalized_ids),
    ).all()
    for row in rows:
        progress_map[int(row.course_id)] = int(row.completion_percent or 0)
    return progress_map


def _bool_from_form(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _support_tool_state_from_request() -> dict:
    return {
        "hint_used": _bool_from_form(request.form.get("hint_used")),
        "synonym_used": _bool_from_form(request.form.get("synonym_used")),
        "translation_used": _bool_from_form(request.form.get("translation_used")),
    }


def _store_support_tool_state(question_id: int, state: dict) -> None:
    payload = session.get(SUPPORT_TOOL_SESSION_KEY, {}) or {}
    payload[str(question_id)] = {
        "hint_used": bool(state.get("hint_used")),
        "synonym_used": bool(state.get("synonym_used")),
        "translation_used": bool(state.get("translation_used")),
    }
    session[SUPPORT_TOOL_SESSION_KEY] = payload
    session.modified = True


def _support_tool_state(question_id: int) -> dict:
    payload = session.get(SUPPORT_TOOL_SESSION_KEY, {}) or {}
    return payload.get(
        str(question_id),
        {"hint_used": False, "synonym_used": False, "translation_used": False},
    )


def _normalized_support_tool_state(question_id: int) -> dict:
    state = _support_tool_state(question_id)
    return {
        "hint_used": bool(state.get("hint_used")),
        "synonym_used": bool(state.get("synonym_used")),
        "translation_used": bool(state.get("translation_used")),
    }


def _clear_support_tool_state(question_id: int) -> None:
    payload = session.get(SUPPORT_TOOL_SESSION_KEY, {}) or {}
    payload.pop(str(question_id), None)
    session[SUPPORT_TOOL_SESSION_KEY] = payload
    session.modified = True


def _next_learning_target(courses: list[Course]) -> tuple[Course | None, Lesson | None, int]:
    if not courses:
        return None, None, 0

    best_course = courses[0]
    best_lesson = None
    best_progress = 0

    for course in courses:
        course_progress = _course_progress_percent(course)
        if course_progress > best_progress:
            best_progress = course_progress
            best_course = course

        for level in course.levels:
            for lesson in level.lessons:
                progress = LessonProgress.query.filter_by(student_id=current_user.id, lesson_id=lesson.id).first()
                if not progress or int(progress.completion_percent or 0) < 100:
                    return course, lesson, course_progress

    fallback_lesson = None
    if best_course.levels and best_course.levels[0].lessons:
        fallback_lesson = best_course.levels[0].lessons[0]
    return best_course, fallback_lesson, best_progress


def _latest_attempts(student_id: int, limit: int = 5) -> list[QuestionAttempt]:
    return (
        QuestionAttempt.query.filter_by(student_id=student_id, attempt_kind="final")
        .order_by(QuestionAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )


def _student_calendar_context(student_id: int) -> dict:
    today = date.today()
    payload = StudentActivityService.build_month_grid(student_id, today.year, today.month)
    today_row = StudentDailyActivity.query.filter_by(student_id=student_id, activity_date=today).first()
    payload["today"] = today_row
    payload["streak"] = StudentActivityService.active_streak(student_id)
    payload["month_attempts"] = sum(int(getattr(row, "questions_attempted", 0) or 0) for row in StudentActivityService.monthly_rows(student_id, date(today.year, today.month, 1), date(today.year, today.month, monthrange(today.year, today.month)[1])))
    return payload


def _weak_areas(skills: dict, summary: dict) -> list[dict]:
    items = [
        ("Grammar", int(skills.get("grammar", 0) or 0), "Work on cleaner sentence structure and tense usage."),
        ("Confidence", int(skills.get("confidence", 0) or 0), "Practice speaking more often in short, complete sentences."),
        ("Accuracy", int(skills.get("accuracy", 0) or 0), "Slow down slightly and focus on answering the exact question."),
        ("Completion", int(skills.get("completion", 0) or 0), "Finish more lessons regularly to build consistency."),
    ]
    ranked = sorted(items, key=lambda item: item[1])
    result = []
    for label, score, note in ranked[:3]:
        result.append({"label": label, "score": score, "note": note})
    if int(summary.get("translation_usage_count", 0) or 0) >= 5:
        result.append({"label": "Translation dependence", "score": max(0, 100 - int(summary.get("translation_usage_count", 0) * 4)), "note": "Try answering first in simple English before opening translation support."})
    return result[:3]


def _dashboard_recommendations(skills: dict, summary: dict, profile_completion: int, continue_lesson: Lesson | None) -> list[dict]:
    recs = []
    if continue_lesson is not None:
        recs.append({
            "title": "Continue your next lesson",
            "text": f"Resume {continue_lesson.title} and keep today's learning streak alive.",
            "badge": "Next step",
        })
    if int(skills.get("grammar", 0) or 0) < 65:
        recs.append({
            "title": "Grammar needs attention",
            "text": "Write shorter answers with one tense and one clear idea in each sentence.",
            "badge": "Priority",
        })
    if int(skills.get("confidence", 0) or 0) < 65:
        recs.append({
            "title": "Build speaking confidence",
            "text": "Use the speaking practice flow daily, even for 5 to 10 minutes.",
            "badge": "Practice",
        })
    if profile_completion < 80:
        recs.append({
            "title": "Complete your profile",
            "text": "A fuller profile helps personalize support language, goals, and certificates.",
            "badge": "Setup",
        })
    if int(summary.get("support_tool_usage_count", 0) or 0) >= 8:
        recs.append({
            "title": "Reduce support-tool usage",
            "text": "Try your answer first, then use hint or translation only when needed.",
            "badge": "AI tip",
        })
    return recs[:3]


def _dashboard_continue_target(current_course: Course | None, continue_lesson: Lesson | None) -> tuple[str, str]:
    if current_course is not None:
        track_type = _normalized_track_type(current_course)
        if track_type == "interview":
            return url_for("student.course_interview_start", course_id=current_course.id), "Open AI Interview"
        return _course_continue_url(current_course, current_user.id), "Continue Learning"

    if continue_lesson is not None:
        return url_for("student.lesson_entry", lesson_id=continue_lesson.id), "Continue Learning"

    return url_for("student.course_library"), "Explore Courses"


@bp.get("/dashboard")
@login_required
def dashboard():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    prefs = _student_prefs()
    ai_voice_payload = session.pop("ai_voice_payload", None)

    if ai_voice_payload:
        ai_voice_payload["lang"] = (
            ai_voice_payload.get("lang")
            or ai_voice_payload.get("accent")
            or prefs.accent
            or "en-IN"
        )
        ai_voice_payload["voice_name"] = getattr(prefs, "voice_name", None) or ""

    profile_completion = calculate_profile_completion(current_user)
    skills = get_skill_breakdown(db, current_user.id)
    translation_language_code, translation_language_name, translation_support_enabled = (
        _resolve_translation_support_context(prefs)
    )

    summary = get_student_progress_summary(current_user.id)
    learning_support = student_support_chain(current_user)
    active_courses = get_student_active_courses(current_user.id)
    latest_attempts = _latest_attempts(current_user.id, limit=5)
    current_course, continue_lesson, continue_progress = _next_learning_target(active_courses)
    calendar_context = _student_calendar_context(current_user.id)
    analytics_overview = StudentProgressAnalyticsService.overview(current_user.id)
    ai_intelligence_payload = StudentAIIntelligenceService.build(current_user.id)
    placement_result = _placement_test_result()
    placement_path = CourseRecommendationService.learning_path_payload(placement_result)
    weak_areas = analytics_overview.get("weak_areas") or _weak_areas(skills, summary)
    recommendations = _dashboard_recommendations(skills, summary, profile_completion, continue_lesson)
    for item in ai_intelligence_payload.get("recommendations") or []:
        recommendations.append({
            "title": item.get("title") or "AI recommendation",
            "text": item.get("summary") or item.get("reason") or "",
            "badge": item.get("badge") or "AI",
        })
    seen_recommendations = set()
    deduped_recommendations = []
    for item in recommendations:
        key = (str(item.get("title") or "").strip().lower(), str(item.get("text") or "").strip().lower())
        if key in seen_recommendations:
            continue
        seen_recommendations.add(key)
        deduped_recommendations.append(item)
    recommendations = deduped_recommendations[:5]
    continue_url, continue_cta_label = _dashboard_continue_target(current_course, continue_lesson)

    return render_template(
        "student/dashboard.html",
        cards=get_student_dashboard_cards(current_user),
        translation_language_code=translation_language_code,
        translation_language_name=translation_language_name,
        translation_support_enabled=translation_support_enabled,
        ai_voice_payload=ai_voice_payload,
        accent=getattr(prefs, "accent", "en-IN") or "en-IN",
        welcome_voice_mode=getattr(prefs, "welcome_voice_mode", "once") or "once",
        welcome_voice_save_url=url_for("student.welcome_voice_mode"),
        profile_completion=profile_completion,
        skills=skills,
        summary=summary,
        learning_support=learning_support,
        active_courses=active_courses,
        latest_attempts=latest_attempts,
        current_course=current_course,
        continue_lesson=continue_lesson,
        continue_progress=continue_progress,
        learning_summary=current_user.latest_learning_summary(),
        next_steps=current_user.profile_next_steps(),
        calendar_context=calendar_context,
        analytics_overview=analytics_overview,
        ai_intelligence_payload=ai_intelligence_payload,
        weak_areas=weak_areas,
        recommendations=recommendations,
        continue_url=continue_url,
        continue_cta_label=continue_cta_label,
        placement_result=placement_result,
        placement_path=placement_path,
    )


@bp.get("/progress-analytics")
@login_required
def progress_analytics():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    analytics = StudentProgressAnalyticsService.overview(current_user.id)
    intelligence = StudentAIIntelligenceService.build(current_user.id)
    return render_template("student/progress_analytics.html", analytics=analytics, intelligence=intelligence)


@bp.get("/ai-intelligence")
@login_required
def ai_intelligence():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    intelligence = StudentAIIntelligenceService.build(current_user.id)
    analytics = StudentProgressAnalyticsService.overview(current_user.id)
    return render_template("student/ai_intelligence.html", intelligence=intelligence, analytics=analytics)


@bp.post("/welcome-voice/mode")
@login_required
def welcome_voice_mode():
    if not getattr(current_user, "is_student", False):
        return jsonify({"ok": False, "message": "Student access required."}), 403

    prefs = _student_prefs()
    payload = request.get_json(silent=True) or {}

    mode = (payload.get("welcome_voice_mode") or payload.get("mode") or "once").strip().lower()
    if mode not in {"once", "muted", "mute"}:
        return jsonify({"ok": False, "message": "Invalid mode."}), 400

    if mode == "mute":
        mode = "muted"

    prefs.welcome_voice_mode = mode
    db.session.commit()

    audit("welcome_voice_mode", target=str(current_user.id), meta=mode)
    return jsonify({"ok": True, "mode": mode})


def _owner_admin_id() -> int | None:
    return getattr(current_user, "created_by_id", None)


def _course_skill_value(course: Course | None) -> str:
    raw = ((getattr(course, "track_type", "") or "").strip().lower())
    return "speaking" if raw in {"spoken", "topic"} else raw


def _course_level_value(course: Course | None) -> str:
    value = (getattr(course, "difficulty", "") or "").strip().lower()
    if value.startswith("adv"):
        return "advanced"
    if value.startswith("int"):
        return "intermediate"
    if value:
        return "basic" if value.startswith("bas") else value
    return ""

def _level_rank(value: str | None) -> int:
    normalized = (value or "").strip().lower()
    if normalized.startswith("bas"):
        return 1
    if normalized.startswith("int"):
        return 2
    if normalized.startswith("adv"):
        return 3
    return 9


def _course_category_key(course: Course | None) -> str:
    title = str(getattr(course, "title", "") or "").strip().lower()
    track = _course_skill_value(course)
    if track == "interview" or "interview" in title:
        return "interview"
    if "spoken english" in title or (track == "speaking" and "spoken" in title):
        return "spoken_english"
    if "ielts" in title or "exam" in title or "test prep" in title:
        return "exam_prep"
    if "super advanced" in title:
        return "super_advanced"
    if track == "speaking":
        return "speaking_path"
    if track == "reading":
        return "reading_path"
    if track == "writing":
        return "writing_path"
    if track == "listening":
        return "listening_path"
    return "general"


def _course_category_label(category_key: str) -> str:
    labels = {
        "spoken_english": "Spoken English",
        "interview": "Interview Prep",
        "exam_prep": "Exam Prep",
        "super_advanced": "Super Advanced",
        "speaking_path": "Speaking Course",
        "reading_path": "Reading Course",
        "writing_path": "Writing Course",
        "listening_path": "Listening Course",
        "general": "General Course",
    }
    return labels.get(category_key, "Course")


def _is_spoken_english_course(course: Course | None) -> bool:
    return SpokenEnglishService.is_spoken_english_course(course)


def _spoken_english_home_url(course: Course) -> str:
    return url_for("student.course_spoken_english_home", course_id=course.id)


def _spoken_english_daily_practice_url(course: Course) -> str:
    return url_for("student.course_spoken_english_daily_practice", course_id=course.id)


def _spoken_english_topic_practice_url(course: Course, topic_id: int | None) -> str:
    if topic_id:
        return url_for("student.course_spoken_english_topic_practice", course_id=course.id, topic_id=topic_id)
    return _spoken_english_daily_practice_url(course)


def _progress_label(progress_value: int) -> str:
    value = max(0, min(int(progress_value or 0), 100))
    if value >= 100:
        return "Completed"
    if value >= 70:
        return "Almost done"
    if value >= 35:
        return "In progress"
    if value > 0:
        return "Started"
    return "Not started"


def _course_library_extra_content(courses: list[Course]) -> tuple[dict[int, int], dict[int, int], dict[int, list[WritingTask]], dict[int, int]]:
    course_ids = [int(course.id) for course in (courses or []) if getattr(course, "id", None)]
    if not course_ids:
        return {}, {}, {}, {}

    writing_counts = {
        int(course_id): int(total or 0)
        for course_id, total in db.session.query(WritingTask.course_id, func.count(WritingTask.id))
        .filter(
            WritingTask.course_id.in_(course_ids),
            WritingTask.is_active.is_(True),
            WritingTask.is_published.is_(True),
        )
        .group_by(WritingTask.course_id)
        .all()
    }
    writing_task_map: dict[int, list[WritingTask]] = {course_id: [] for course_id in course_ids}
    writing_rows = (
        WritingTask.query
        .filter(
            WritingTask.course_id.in_(course_ids),
            WritingTask.is_active.is_(True),
            WritingTask.is_published.is_(True),
        )
        .order_by(WritingTask.course_id.asc(), WritingTask.display_order.asc(), WritingTask.id.asc())
        .all()
    )
    for task in writing_rows:
        writing_task_map.setdefault(int(task.course_id), []).append(task)

    listening_counts = {
        int(course_id): int(total or 0)
        for course_id, total in db.session.query(Level.course_id, func.count(Lesson.id))
        .join(Lesson, Lesson.level_id == Level.id)
        .filter(Level.course_id.in_(course_ids))
        .group_by(Level.course_id)
        .all()
    }

    enrollment_counts = {
        int(course_id): int(total or 0)
        for course_id, total in db.session.query(Enrollment.course_id, func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(course_ids), Enrollment.status == "active")
        .group_by(Enrollment.course_id)
        .all()
    }

    return writing_counts, listening_counts, writing_task_map, enrollment_counts



# Compatibility helpers used by newer course-library/dashboard code.
# They are intentionally safe: if one optional model/table is missing, the page still loads.
def _safe_group_count(model, course_id_column, course_ids, *filters) -> dict[int, int]:
    if not course_ids:
        return {}
    try:
        rows = (
            db.session.query(course_id_column, func.count(model.id))
            .filter(course_id_column.in_(course_ids), *filters)
            .group_by(course_id_column)
            .all()
        )
        return {int(course_id): int(total or 0) for course_id, total in rows}
    except Exception as exc:
        current_app.logger.warning("Course helper count fallback: %s", exc)
        return {}


def _active_speaking_topics_by_course(course_ids) -> dict[int, int]:
    return _safe_group_count(
        SpeakingTopic,
        SpeakingTopic.course_id,
        course_ids,
        SpeakingTopic.is_active.is_(True),
        SpeakingTopic.is_published.is_(True),
    )


def _active_reading_topics_by_course(course_ids) -> dict[int, int]:
    return _safe_group_count(
        ReadingTopic,
        ReadingTopic.course_id,
        course_ids,
        ReadingTopic.is_active.is_(True),
    )


def _approved_reading_passages_by_course(course_ids) -> dict[int, int]:
    return _safe_group_count(
        ReadingPassage,
        ReadingPassage.course_id,
        course_ids,
        ReadingPassage.is_active.is_(True),
        ReadingPassage.is_published.is_(True),
        ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
    )


def _published_writing_task_counts_by_course(course_ids) -> dict[int, int]:
    return _safe_group_count(
        WritingTask,
        WritingTask.course_id,
        course_ids,
        WritingTask.is_active.is_(True),
        WritingTask.is_published.is_(True),
    )


def _listening_lesson_counts_by_course(course_ids) -> dict[int, int]:
    if not course_ids:
        return {}
    try:
        rows = (
            db.session.query(Level.course_id, func.count(Lesson.id))
            .join(Lesson, Lesson.level_id == Level.id)
            .filter(Level.course_id.in_(course_ids))
            .group_by(Level.course_id)
            .all()
        )
        return {int(course_id): int(total or 0) for course_id, total in rows}
    except Exception as exc:
        current_app.logger.warning("Listening lesson count fallback: %s", exc)
        return {}


def _published_writing_tasks_by_course(course_ids) -> dict[int, list[WritingTask]]:
    task_map: dict[int, list[WritingTask]] = {int(course_id): [] for course_id in (course_ids or [])}
    if not course_ids:
        return task_map
    try:
        rows = (
            WritingTask.query
            .filter(
                WritingTask.course_id.in_(course_ids),
                WritingTask.is_active.is_(True),
                WritingTask.is_published.is_(True),
            )
            .order_by(WritingTask.course_id.asc(), WritingTask.display_order.asc(), WritingTask.id.asc())
            .all()
        )
        for task in rows:
            task_map.setdefault(int(task.course_id), []).append(task)
    except Exception as exc:
        current_app.logger.warning("Writing task map fallback: %s", exc)
    return task_map


def _course_enrollment_counts(course_ids) -> dict[int, int]:
    return _safe_group_count(
        Enrollment,
        Enrollment.course_id,
        course_ids,
        Enrollment.status == "active",
    )
def _build_course_library_sections(cards: list[dict]) -> list[dict]:
    level_order = [
        ("basic", "Basic", "Start from strong foundations with simpler lessons and guided practice."),
        ("intermediate", "Intermediate", "Move into richer vocabulary, longer responses, and mixed-skill work."),
        ("advanced", "Advanced", "Push fluency, precision, and high-difficulty performance."),
    ]
    course_cards = [card for card in (cards or []) if (card.get("card_kind") or "") == "course"]
    sections: list[dict] = []
    for key, title, description in level_order:
        section_cards = [card for card in course_cards if (card.get("difficulty") or "").strip().lower() == key]
        if section_cards:
            sections.append({"key": key, "title": title, "description": description, "cards": section_cards})
    other_cards = [card for card in course_cards if (card.get("difficulty") or "").strip().lower() not in {"basic", "intermediate", "advanced"}]
    if other_cards:
        sections.append({"key": "other", "title": "Other Levels", "description": "Published courses without a standard level label.", "cards": other_cards})
    return sections


def _build_course_library_track_sections(cards: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {"speaking": [], "reading": [], "writing": [], "listening": []}
    for card in cards or []:
        kind = (card.get("card_kind") or "")
        if kind == "course":
            continue
        skill = (card.get("skill_code") or "").strip().lower()
        if skill in grouped:
            grouped[skill].append(card)
    sections = []
    for key in ("speaking", "reading", "writing", "listening"):
        if grouped[key]:
            sections.append({
                "key": key,
                "title": f"{_track_label(key)} Shortcuts",
                "description": f"Jump straight into {_track_label(key).lower()} practice.",
                "cards": grouped[key],
            })
    return sections


def _fallback_speaking_topics_for_course(course: Course) -> list[SpeakingTopic]:
    if _course_skill_value(course) != "speaking":
        return []

    owner_admin_id = _owner_admin_id()
    topics = PromptService.list_student_visible_topics(owner_admin_id)
    course_language = (course.language_code or "").strip().lower()
    course_level = _course_level_value(course)

    filtered = []
    for topic in topics:
        if topic.course_id:
            continue
        topic_language = (getattr(topic, "language_code", "") or "").strip().lower()
        topic_level = (getattr(topic, "level", "") or "").strip().lower()
        if course_language and topic_language and topic_language != course_language:
            continue
        if course_level and topic_level and topic_level != course_level:
            continue
        filtered.append(topic)

    return filtered or [topic for topic in topics if not topic.course_id]


def _fallback_reading_passages_for_course(course: Course) -> list[ReadingPassage]:
    if _course_skill_value(course) != "reading":
        return []

    course_level = _course_level_value(course)
    course_language = (course.language_code or "").strip().lower()
    base_query = (
        ReadingPassage.query
        .filter(
            ReadingPassage.course_id.is_(None),
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
        )
        .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
    )

    passages = base_query.all()
    if not passages:
        return []

    filtered = []
    for passage in passages:
        topic_language = ((getattr(getattr(passage, "topic", None), "language_code", "") or "").strip().lower())
        passage_level = (getattr(passage, "level", "") or "").strip().lower()
        if course_language and topic_language and topic_language != course_language:
            continue
        if course_level and passage_level and passage_level != course_level:
            continue
        filtered.append(passage)

    return filtered or passages


def _fallback_reading_topics_for_course(course: Course) -> list[ReadingTopic]:
    if _course_skill_value(course) != "reading":
        return []

    course_level = _course_level_value(course)
    topics = (
        ReadingTopic.query
        .filter(ReadingTopic.is_active.is_(True), ReadingTopic.course_id.is_(None))
        .order_by(ReadingTopic.display_order.asc(), ReadingTopic.title.asc())
        .all()
    )
    if not topics:
        return []

    if not course_level:
        return topics

    filtered = [
        topic for topic in topics
        if (getattr(topic, "level", "") or "").strip().lower() == course_level
    ]
    return filtered or topics


def _speaking_count_for_course(course: Course, linked_counts: dict[int, int] | None = None) -> int:
    linked_counts = linked_counts or {}
    linked = int(linked_counts.get(course.id, 0) or 0)
    if linked:
        return linked
    return len(_fallback_speaking_topics_for_course(course))


def _reading_count_for_course(course: Course, linked_counts: dict[int, int] | None = None) -> int:
    linked_counts = linked_counts or {}
    linked = int(linked_counts.get(course.id, 0) or 0)
    if linked:
        return linked
    return len(_fallback_reading_passages_for_course(course))


def _course_library_content(courses: list[Course]) -> tuple[dict[int, int], dict[int, int], dict[int, list[SpeakingTopic]], dict[int, list[ReadingPassage]], dict[int, list[ReadingTopic]]]:
    linked_speaking_counts = {
        row[0]: row[1]
        for row in db.session.query(SpeakingTopic.course_id, func.count(SpeakingTopic.id))
        .filter(
            SpeakingTopic.course_id.isnot(None),
            SpeakingTopic.is_active.is_(True),
            SpeakingTopic.is_published.is_(True),
        )
        .group_by(SpeakingTopic.course_id)
        .all()
    }
    linked_reading_counts = {
        row[0]: row[1]
        for row in db.session.query(ReadingPassage.course_id, func.count(ReadingPassage.id))
        .filter(
            ReadingPassage.course_id.isnot(None),
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
        )
        .group_by(ReadingPassage.course_id)
        .all()
    }

    course_speaking_counts = {}
    course_reading_counts = {}
    course_speaking_topics = {}
    course_reading_passages = {}
    course_reading_topics = {}

    for course in courses:
        linked_topics = (
            SpeakingTopic.query
            .filter(
                SpeakingTopic.course_id == course.id,
                SpeakingTopic.is_active.is_(True),
                SpeakingTopic.is_published.is_(True),
            )
            .order_by(SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc())
            .all()
        ) if linked_speaking_counts.get(course.id) else []
        if not linked_topics:
            linked_topics = _fallback_speaking_topics_for_course(course)
        course_speaking_topics[course.id] = linked_topics
        course_speaking_counts[course.id] = len(linked_topics)

        linked_passages = (
            ReadingPassage.query
            .filter(
                ReadingPassage.course_id == course.id,
                ReadingPassage.is_active.is_(True),
                ReadingPassage.is_published.is_(True),
                ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            )
            .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
            .all()
        ) if linked_reading_counts.get(course.id) else []
        if not linked_passages:
            linked_passages = _fallback_reading_passages_for_course(course)
        course_reading_passages[course.id] = linked_passages

        reading_topics = (
            ReadingTopic.query
            .filter(ReadingTopic.course_id == course.id, ReadingTopic.is_active.is_(True))
            .order_by(ReadingTopic.display_order.asc(), ReadingTopic.title.asc())
            .all()
        )
        seen_topic_ids = {topic.id for topic in reading_topics}
        if linked_passages:
            for passage in linked_passages:
                topic = getattr(passage, "topic", None)
                if topic and topic.id not in seen_topic_ids:
                    reading_topics.append(topic)
                    seen_topic_ids.add(topic.id)
        if not reading_topics:
            reading_topics = _fallback_reading_topics_for_course(course)

        course_reading_topics[course.id] = reading_topics
        course_reading_counts[course.id] = max(len(linked_passages), len(reading_topics))

    return course_speaking_counts, course_reading_counts, course_speaking_topics, course_reading_passages, course_reading_topics


def _course_has_student_visible_content(course: Course, course_speaking_topics: dict[int, list[SpeakingTopic]] | None = None, course_reading_passages: dict[int, list[ReadingPassage]] | None = None) -> bool:
    if not bool(course.is_published):
        return False

    track = _course_skill_value(course)
    if track == "speaking":
        if course_speaking_topics is not None:
            return bool(course_speaking_topics.get(course.id))
        return bool(
            SpeakingTopic.query.filter(
                SpeakingTopic.course_id == course.id,
                SpeakingTopic.is_active.is_(True),
                SpeakingTopic.is_published.is_(True),
            ).first()
        )
    if track == "reading":
        if course_reading_passages is not None:
            return bool(course_reading_passages.get(course.id)) or bool(
                ReadingTopic.query.filter(
                    ReadingTopic.course_id == course.id,
                    ReadingTopic.is_active.is_(True),
                ).first()
            )
        return bool(
            ReadingPassage.query.filter(
                ReadingPassage.course_id == course.id,
                ReadingPassage.is_active.is_(True),
                ReadingPassage.is_published.is_(True),
                ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ).first()
        ) or bool(
            ReadingTopic.query.filter(
                ReadingTopic.course_id == course.id,
                ReadingTopic.is_active.is_(True),
            ).first()
        )
    return True


def _track_label(track_type: str | None) -> str:
    return ((track_type or "course").replace("_", " ").strip() or "course").title()


def _normalized_track_type(course: Course | None) -> str:
    raw = ((getattr(course, "track_type", "") or "").strip().lower())

    try:
        lesson_types = {
            ((getattr(lesson, "lesson_type", "") or "").strip().lower())
            for level in (getattr(course, "levels", []) or [])
            for lesson in (getattr(level, "lessons", []) or [])
            if (getattr(lesson, "lesson_type", "") or "").strip()
        }
        if "interview" in lesson_types:
            return "interview"
        if "listening" in lesson_types:
            return "listening"
        if "writing" in lesson_types:
            return "writing"
        if "reading" in lesson_types:
            return "reading"
        if "speaking" in lesson_types:
            return "speaking"
    except Exception:
        pass

    title = (getattr(course, "title", "") or "").strip().lower()
    if "interview" in title:
        return "interview"
    if raw in {"spoken", "topic"}:
        return "speaking"
    if raw in {"speaking", "reading", "writing", "listening", "interview"}:
        return raw
    return raw


def _first_available_reading_passage(course: Course) -> ReadingPassage | None:
    rows = (
        ReadingPassage.query
        .filter(
            ReadingPassage.course_id == course.id,
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
        )
        .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
        .all()
    )
    for passage in rows:
        has_questions = ReadingQuestion.query.filter_by(passage_id=passage.id, is_active=True, status=ReadingQuestion.STATUS_APPROVED).first()
        if has_questions:
            return passage
    return None


def _first_available_listening_lesson(course: Course) -> Lesson | None:
    lessons = []
    for level in sorted(course.levels, key=lambda row: ((row.sort_order or 0), row.id)):
        for lesson in sorted(level.lessons, key=lambda row: ((row.sort_order or 0), row.id)):
            if (lesson.lesson_type or '').strip().lower() != 'listening':
                continue
            if not bool(getattr(lesson, 'is_published', True)):
                continue
            workflow = (getattr(lesson, 'workflow_status', 'draft') or 'draft').strip().lower()
            if workflow not in {'approved', 'published', 'live'}:
                continue
            question_exists = False
            for chapter in lesson.chapters:
                for subsection in chapter.subsections:
                    for question in subsection.questions:
                        if getattr(question, 'is_active', True):
                            question_exists = True
                            break
                    if question_exists:
                        break
                if question_exists:
                    break
            if question_exists:
                lessons.append(lesson)
    return lessons[0] if lessons else None


def _ordered_course_lessons(course: Course, include_listening: bool = True) -> list[Lesson]:
    lessons: list[Lesson] = []
    for level in sorted(course.levels, key=lambda row: ((row.sort_order or 0), row.id)):
        for lesson in sorted(level.lessons, key=lambda row: ((row.sort_order or 0), row.id)):
            if not bool(getattr(lesson, 'is_published', True)):
                continue
            lesson_type = (getattr(lesson, 'lesson_type', '') or '').strip().lower()
            if not include_listening and lesson_type == 'listening':
                continue
            lessons.append(lesson)
    return lessons


def _first_incomplete_lesson(course: Course, student_id: int, include_listening: bool = True) -> Lesson | None:
    ordered_lessons = _ordered_course_lessons(course, include_listening=include_listening)
    if not ordered_lessons:
        return None

    for lesson in ordered_lessons:
        progress = LessonProgress.query.filter_by(student_id=student_id, lesson_id=lesson.id).first()
        if not progress or int(progress.completion_percent or 0) < 100:
            return lesson

    return ordered_lessons[0]


def _course_prefers_lesson_flow(course: Course) -> bool:
    track_type = _normalized_track_type(course)
    if track_type != 'speaking':
        return False
    return bool(_ordered_course_lessons(course, include_listening=False))


def _listening_lessons_for_course(course: Course) -> list[Lesson]:
    return [
        lesson for lesson in _ordered_course_lessons(course)
        if ((getattr(lesson, "lesson_type", "") or "").strip().lower()) == "listening"
    ]


def _latest_speaking_continue_url(course: Course) -> str:
    session_row = (
        SpeakingSession.query
        .filter_by(student_id=current_user.id, course_id=course.id)
        .order_by(SpeakingSession.updated_at.desc(), SpeakingSession.id.desc())
        .first()
    )
    if session_row:
        if (session_row.status or '').lower() == SpeakingSession.STATUS_COMPLETED:
            return url_for('student.course_speaking_result', course_id=course.id, session_id=session_row.id)
        return url_for('student.course_speaking_session', course_id=course.id, session_id=session_row.id)

    first_topic = next((topic for topic in (getattr(course, 'speaking_topics', []) or []) if bool(getattr(topic, 'is_active', False)) and bool(getattr(topic, 'is_published', False)) and int(getattr(topic, 'active_prompt_count', 0) or 0) > 0), None)
    if first_topic:
        return url_for('student.course_speaking_start', course_id=course.id, topic_id=first_topic.id)
    return url_for('student.course_speaking_home', course_id=course.id)


def _latest_reading_continue_url(course: Course) -> str:
    log = (
        ReadingSessionLog.query
        .filter_by(student_id=current_user.id, course_id=course.id)
        .order_by(ReadingSessionLog.submitted_at.desc(), ReadingSessionLog.id.desc())
        .first()
    )
    if log and getattr(log, 'passage_id', None):
        return url_for('student.course_reading_session', course_id=course.id, passage_id=log.passage_id)

    passage = _first_available_reading_passage(course)
    if passage:
        return url_for('student.course_reading_session', course_id=course.id, passage_id=passage.id)
    return url_for('student.course_reading_home', course_id=course.id)


def _latest_writing_continue_url(course: Course, student_id: int) -> str:
    latest_submission = (
        WritingSubmission.query
        .filter_by(student_id=student_id, course_id=course.id)
        .order_by(WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc())
        .first()
    )
    if latest_submission:
        if getattr(latest_submission, 'task_id', None):
            task = WritingTask.query.get(latest_submission.task_id)
            if task and task.course_id == course.id and bool(getattr(task, 'is_active', False)) and bool(getattr(task, 'is_published', False)) and bool((getattr(task, 'instructions', '') or '').strip()):
                return url_for('student.course_writing_task', course_id=course.id, task_id=task.id)
        if getattr(latest_submission, 'topic_id', None):
            topic = WritingTopic.query.get(latest_submission.topic_id)
            if topic and topic.course_id == course.id and bool(getattr(topic, 'is_active', False)) and bool(getattr(topic, 'is_published', False)):
                return url_for('student.course_writing_topic_workspace', course_id=course.id, topic_id=topic.id)

    return _first_writing_task_url(course, student_id)


def _latest_listening_continue_url(course: Course) -> str:
    lesson_ids = []
    for level in course.levels:
        for lesson in level.lessons:
            if (lesson.lesson_type or '').strip().lower() == 'listening':
                lesson_ids.append(lesson.id)

    if lesson_ids:
        progress_row = (
            LessonProgress.query
            .filter(LessonProgress.student_id == current_user.id, LessonProgress.lesson_id.in_(lesson_ids))
            .order_by(LessonProgress.last_activity_at.desc(), LessonProgress.id.desc())
            .first()
        )
        if progress_row and progress_row.lesson_id:
            return url_for('student.course_listening_session', course_id=course.id, lesson_id=progress_row.lesson_id)

        latest_attempt = (
            QuestionAttempt.query
            .filter(QuestionAttempt.student_id == current_user.id, QuestionAttempt.lesson_id.in_(lesson_ids))
            .order_by(QuestionAttempt.attempted_at.desc(), QuestionAttempt.id.desc())
            .first()
        )
        if latest_attempt and latest_attempt.lesson_id:
            return url_for('student.course_listening_session', course_id=course.id, lesson_id=latest_attempt.lesson_id)

    lesson = _first_available_listening_lesson(course)
    if lesson:
        return url_for('student.course_listening_session', course_id=course.id, lesson_id=lesson.id)
    return url_for('student.course_listening_home', course_id=course.id)


def _course_start_url(course: Course, student_id: int) -> str:
    track_type = _normalized_track_type(course)

    if track_type == 'interview':
        return url_for('student.course_interview_start', course_id=course.id)

    if track_type == 'speaking':
        if _is_spoken_english_course(course):
            return _spoken_english_daily_practice_url(course)

        first_lesson = _first_incomplete_lesson(course, student_id, include_listening=False)
        if first_lesson:
            return url_for('student.lesson_entry', lesson_id=first_lesson.id)

        first_topic = next(
            (
                topic for topic in (getattr(course, 'speaking_topics', []) or [])
                if bool(getattr(topic, 'is_active', False))
                and bool(getattr(topic, 'is_published', False))
                and int(getattr(topic, 'active_prompt_count', 0) or 0) > 0
            ),
            None,
        )
        if first_topic:
            return url_for('student.course_speaking_start', course_id=course.id, topic_id=first_topic.id)

        return url_for('student.course_speaking_home', course_id=course.id)

    if track_type == 'reading':
        passage = _first_available_reading_passage(course)
        if passage:
            return url_for('student.course_reading_session', course_id=course.id, passage_id=passage.id)
        return url_for('student.course_reading_home', course_id=course.id)

    if track_type == 'writing':
        return _latest_writing_continue_url(course, student_id)

    if track_type == 'listening':
        lesson = _first_available_listening_lesson(course)
        if lesson:
            return url_for('student.course_listening_session', course_id=course.id, lesson_id=lesson.id)
        return url_for('student.course_listening_home', course_id=course.id)

    return _course_target_url(course)


def _course_target_url(course: Course) -> str:
    track_type = _normalized_track_type(course)

    if track_type == 'interview':
        return url_for("student.course_interview_start", course_id=course.id)

    if track_type == "speaking":
        if _is_spoken_english_course(course):
            return _spoken_english_home_url(course)
        if _course_prefers_lesson_flow(course):
            return url_for("student.course_detail", course_id=course.id)
        return url_for("student.course_speaking_home", course_id=course.id)

    if track_type == "reading":
        return url_for("student.course_reading_home", course_id=course.id)

    if track_type == "writing":
        return url_for("student.course_writing_home", course_id=course.id)

    if track_type == "listening":
        return url_for("student.course_listening_home", course_id=course.id)

    return url_for("student.course_detail", course_id=course.id)


def _first_writing_task_url(course: Course, student_id: int) -> str:
    enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course.id, status="active").order_by(Enrollment.enrolled_at.desc()).first()
    writing_tasks = (
        WritingTask.query.filter(
            WritingTask.course_id == course.id,
            WritingTask.is_active.is_(True),
            WritingTask.is_published.is_(True),
        )
        .order_by(WritingTask.display_order.asc(), WritingTask.id.asc())
        .all()
    )
    for task in writing_tasks:
        level_number = getattr(task, "course_level_number", None)
        if not enrollment or enrollment.has_level_access(level_number):
            return url_for("student.course_writing_task", course_id=course.id, task_id=task.id)
    return url_for("student.course_writing_home", course_id=course.id)



def _course_continue_url(course: Course, student_id: int) -> str:
    track_type = _normalized_track_type(course)

    if track_type == "interview":
        # Interview module endpoints are not fully registered yet.
        # Use safe course detail until interview session routes are completed.
        return url_for("student.course_detail", course_id=course.id)

    if track_type == "speaking":
        if _is_spoken_english_course(course):
            daily_topic, daily_prompt = SpokenEnglishService.daily_prompt(course, student_id)
            resumable = SpeakingSessionService.get_resumable_session(student_id, course_id=course.id)
            if resumable:
                if (resumable.status or '').lower() == SpeakingSession.STATUS_COMPLETED:
                    return url_for('student.course_spoken_english_result', course_id=course.id, session_id=resumable.id)
                return url_for('student.course_spoken_english_session', course_id=course.id, session_id=resumable.id)
            if daily_topic:
                return _spoken_english_topic_practice_url(course, daily_topic.id)
            return _spoken_english_home_url(course)

        lesson = _first_incomplete_lesson(course, student_id, include_listening=False)
        if lesson:
            return url_for("student.lesson_entry", lesson_id=lesson.id)

        return _latest_speaking_continue_url(course)

    if track_type == "reading":
        return _latest_reading_continue_url(course)

    if track_type == "writing":
        return _latest_writing_continue_url(course, student_id)

    if track_type == "listening":
        return _latest_listening_continue_url(course)

    lesson = _first_incomplete_lesson(course, student_id)
    if not lesson:
        return _course_target_url(course)

    return url_for("student.lesson_entry", lesson_id=lesson.id)


def _course_entry_redirect(course_id: int, *, mode: str):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    enrollment = _active_enrollment(course.id)
    if not enrollment:
        flash("Please enroll in this course first.", "warning")
        return redirect(url_for("student.course_detail", course_id=course.id))

    if _course_welcome_required(enrollment):
        return redirect(url_for("student.course_welcome", course_id=course.id))

    if mode == "start":
        target_url = _course_start_url(course, current_user.id)
    else:
        target_url = _course_continue_url(course, current_user.id)
    return redirect(target_url)


@bp.get("/courses/<int:course_id>")
@login_required
def course_detail(course_id: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.filter(
        Course.id == course_id,
        Course.status != "archived",
        Course.is_published.is_(True),
    ).first_or_404()
    enrollment = _active_enrollment(course.id)
    if not enrollment:
        flash("Enroll in this course to open the workspace.", "info")
        return redirect(url_for("student.course_library", category=_course_category_key(course)))

    try:
        LMSService.sync_course_progress(current_user.id, course)
    except Exception as exc:
        current_app.logger.warning("Course progress sync failed: %s", exc)

    lesson_ids = _course_lesson_ids(course)
    lesson_progress_map = {}
    if lesson_ids:
        lesson_progress_map = {
            row.lesson_id: row
            for row in LessonProgress.query.filter(
                LessonProgress.student_id == current_user.id,
                LessonProgress.lesson_id.in_(lesson_ids),
            ).all()
        }

    try:
        course_breakdown = LMSService.course_progress_breakdown(current_user.id, course)
    except Exception as exc:
        current_app.logger.warning("Course breakdown failed: %s", exc)
        course_breakdown = None

    course_speaking_counts, course_reading_counts, course_speaking_topics, course_reading_passages, course_reading_topics = _course_library_content([course])
    writing_task_counts, listening_lesson_counts, writing_task_map, _enrollment_counts = _course_library_extra_content([course])
    normalized_track_type = _normalized_track_type(course)
    speaking_topics = course_speaking_topics.get(course.id, [])
    reading_passages = course_reading_passages.get(course.id, [])
    writing_tasks = writing_task_map.get(course.id, [])
    reward_overview = EconomyService.course_reward_overview(course)

    workspace_cards = []
    if speaking_topics or normalized_track_type in {"speaking", "interview"}:
        workspace_cards.append({
            "title": "Speaking",
            "headline": "Practice aloud",
            "description": "Open guided speaking practice for this course.",
            "count_label": f"{len(speaking_topics)} topic(s)",
            "href": url_for("student.course_interview_home" if normalized_track_type == "interview" else "student.course_speaking_home", course_id=course.id),
            "button_label": "Open",
            "button_class": "btn btn-primary btn-sm",
        })
    if reading_passages:
        workspace_cards.append({
            "title": "Reading",
            "headline": "Read and answer",
            "description": "Practice published reading sets linked to this course.",
            "count_label": f"{len(reading_passages)} passage(s)",
            "href": url_for("student.course_reading_home", course_id=course.id),
            "button_label": "Open",
            "button_class": "btn btn-primary btn-sm",
        })
    if writing_tasks:
        workspace_cards.append({
            "title": "Writing",
            "headline": "Write with structure",
            "description": "Complete writing tasks from this course.",
            "count_label": f"{len(writing_tasks)} task(s)",
            "href": url_for("student.course_writing_home", course_id=course.id),
            "button_label": "Open",
            "button_class": "btn btn-primary btn-sm",
        })
    if listening_lesson_counts.get(course.id):
        workspace_cards.append({
            "title": "Listening",
            "headline": "Listen and respond",
            "description": "Open listening practice lessons.",
            "count_label": f"{listening_lesson_counts.get(course.id, 0)} lesson(s)",
            "href": url_for("student.course_listening_home", course_id=course.id),
            "button_label": "Open",
            "button_class": "btn btn-primary btn-sm",
        })

    placement_result = _placement_test_result()
    course_fit = CourseRecommendationService.course_fit_for_card({
        "card_kind": "course",
        "course_id": course.id,
        "course_title": course.title,
        "difficulty": _course_level_value(course),
        "track_type": normalized_track_type,
        "is_enrolled": True,
        "is_premium": bool(getattr(course, "is_premium", False)),
    }, placement_result)

    return render_template(
        "student/course_detail.html",
        course=course,
        enrollment=enrollment,
        course_completion=_course_progress_percent(course),
        lesson_progress_map=lesson_progress_map,
        workspace_cards=workspace_cards,
        linked_speaking_topics=speaking_topics,
        linked_reading_passages=reading_passages,
        linked_writing_tasks=writing_tasks,
        normalized_track_type=normalized_track_type,
        placement_result=placement_result,
        course_fit=course_fit,
        reward_overview=reward_overview,
        course_breakdown=course_breakdown,
    )


@bp.get("/courses/<int:course_id>/start")
@login_required
def course_start(course_id: int):
    return _course_entry_redirect(course_id, mode="start")


@bp.get("/courses/<int:course_id>/continue")
@login_required
def course_continue(course_id: int):
    return _course_entry_redirect(course_id, mode="continue")


@bp.get("/courses/<int:course_id>/welcome")
@login_required
def course_welcome(course_id: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    enrollment = _active_enrollment(course.id)
    if not enrollment:
        flash("Please enroll in this course first.", "warning")
        return redirect(url_for("student.course_detail", course_id=course.id))

    return render_template(
        "student/course_welcome.html",
        course=course,
        enrollment=enrollment,
        welcome_points=_course_welcome_points(course),
        learning_outcomes=_course_learning_outcomes(course),
        welcome_message=_course_welcome_message(course),
    )


@bp.post("/courses/<int:course_id>/welcome/start")
@login_required
def course_welcome_start(course_id: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    enrollment = _active_enrollment(course.id)
    if not enrollment:
        flash("Please enroll in this course first.", "warning")
        return redirect(url_for("student.course_detail", course_id=course.id))

    enrollment.welcome_seen_at = datetime.utcnow()
    db.session.commit()
    return redirect(_course_start_url(course, current_user.id))


@bp.route("/courses/<int:course_id>/checkout", methods=["GET", "POST"])
@login_required
def course_checkout(course_id: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    enrollment = _active_enrollment(course.id)
    purchase_scope = (request.values.get("purchase_scope") or "full_course").strip().lower()
    selected_level = _normalize_course_level_number(course, request.values.get("level") or 1)
    coupon_code = (request.form.get("coupon_code") or "").strip()
    coupon = None
    coupon_error = ""
    discount_amount = 0

    if request.method == "POST" and (request.form.get("checkout_action") or "") == "start_payment":
        try:
            payment = PaymentService.create_checkout(
                current_user.id,
                course,
                coupon_code or None,
                purchase_scope=purchase_scope,
                level_number=selected_level,
            )
            flash("Checkout created. Payment gateway connection can be completed from the payment record.", "info")
            return redirect(url_for("student.course_checkout", course_id=course.id, purchase_scope=purchase_scope, level=selected_level, payment_id=payment.id))
        except Exception as exc:
            current_app.logger.exception("Checkout failed: %s", exc)
            coupon_error = "Checkout could not be started. Please try again."

    return render_template(
        "student/checkout.html",
        course=course,
        enrollment=enrollment,
        purchase_scope=purchase_scope,
        selected_level=selected_level,
        coupon_code=coupon_code,
        coupon=coupon,
        coupon_error=coupon_error,
        discount_amount=discount_amount,
        wallet_summary=EconomyService.wallet_summary(current_user.id),
        reward_overview=EconomyService.course_reward_overview(course),
    )


@bp.post("/courses/<int:course_id>/enroll")
@login_required
def enroll_free_course(course_id: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    try:
        enrollment = LMSService.self_enroll_free_course(current_user.id, course)
        flash("Course enrolled successfully.", "success")
        next_url = request.form.get("next") or url_for("student.course_detail", course_id=course.id)
        if _course_welcome_required(enrollment):
            return redirect(url_for("student.course_welcome", course_id=course.id))
        return redirect(next_url)
    except Exception as exc:
        current_app.logger.exception("Free course enrollment failed: %s", exc)
        flash("This course could not be enrolled directly.", "danger")
        return redirect(url_for("student.course_library", category=_course_category_key(course)))


@bp.post("/courses/<int:course_id>/levels/<int:level_number>/enroll")
@login_required
def enroll_free_level(course_id: int, level_number: int):
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    course = Course.query.get_or_404(course_id)
    try:
        enrollment = LMSService.self_enroll_free_level(current_user.id, course, level_number)
        flash(f"Level {level_number} unlocked.", "success")
        if _course_welcome_required(enrollment):
            return redirect(url_for("student.course_welcome", course_id=course.id))
        return redirect(url_for("student.course_detail", course_id=course.id))
    except Exception as exc:
        current_app.logger.exception("Free level enrollment failed: %s", exc)
        flash("This level could not be unlocked directly.", "danger")
        return redirect(url_for("student.course_checkout", course_id=course.id, purchase_scope="single_level", level=level_number))


def _card_matches_search(card: dict, query: str) -> bool:
    haystack = " ".join(
        str(card.get(field) or "")
        for field in (
            "card_title",
            "card_description",
            "course_title",
            "course_description",
            "meta_line",
            "card_kind",
            "skill_code",
            "parent_course_label",
        )
    ).lower()
    return query in haystack






def _my_course_enrollments(student_id: int) -> list[Enrollment]:
    """Return active enrollments in a stable order and keep access to the real
    enrollment rows so My Courses can reflect the true enrolled-course list.
    """
    return (
        Enrollment.query
        .join(Course, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == student_id, Enrollment.status == "active")
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .all()
    )


def _distinct_enrolled_courses(enrollments: list[Enrollment]) -> list[Course]:
    courses: list[Course] = []
    seen_course_ids: set[int] = set()

    for enrollment in enrollments:
        course = getattr(enrollment, "course", None)
        if not course or course.id in seen_course_ids:
            continue
        seen_course_ids.add(course.id)
        courses.append(course)

    return courses


def _best_student_interview_course(student_id: int) -> Course | None:
    enrollments = _my_course_enrollments(student_id)
    for enrollment in enrollments:
        course = getattr(enrollment, 'course', None)
        if course and _normalized_track_type(course) == 'interview':
            return course

    published_courses = (
        Course.query
        .filter(Course.status != 'archived', Course.is_published.is_(True))
        .order_by(Course.updated_at.desc(), Course.created_at.desc(), Course.id.desc())
        .all()
    )
    for course in published_courses:
        if _normalized_track_type(course) == 'interview':
            return course
    return None

def _build_my_course_cards(
    courses: list[Course],
    enrollment_map: dict[int, Enrollment],
    course_progress: dict[int, int],
    course_speaking_counts: dict[int, int],
    course_reading_counts: dict[int, int],
    course_speaking_topics: dict[int, list[SpeakingTopic]],
    course_reading_passages: dict[int, list[ReadingPassage]],
    course_reading_topics: dict[int, list[ReadingTopic]],
) -> tuple[list[dict], list[dict]]:
    course_cards: list[dict] = []
    continue_cards: list[dict] = []

    for course in courses:
        enrollment = enrollment_map.get(course.id)
        progress_value = int(course_progress.get(course.id, 0) or 0)
        speaking_count = int((course_speaking_counts or {}).get(course.id, 0) or 0)
        reading_count = int((course_reading_counts or {}).get(course.id, 0) or 0)
        speaking_topics = (course_speaking_topics or {}).get(course.id, []) or []
        reading_passages = (course_reading_passages or {}).get(course.id, []) or []
        reading_topics = (course_reading_topics or {}).get(course.id, []) or []

        ordered_levels = sorted(course.levels, key=lambda level: (level.sort_order or 0, level.id))
        first_level = ordered_levels[0] if ordered_levels else None
        ordered_lessons = []
        for level in ordered_levels:
            ordered_lessons.extend(sorted(level.lessons, key=lambda lesson: (lesson.sort_order or 0, lesson.id)))
        first_lesson = ordered_lessons[0] if ordered_lessons else None
        continue_url = _course_continue_url(course, current_user.id)

        course_cards.append({
            "course_id": course.id,
            "title": course.title,
            "description": (course.description or "Keep practicing regularly to improve your confidence and fluency.").strip(),
            "language_code": (course.language_code or "").upper(),
            "track_label": _track_label(course.track_type),
            "difficulty": (course.difficulty or "general").title(),
            "status": (course.status or "draft").title(),
            "progress_value": progress_value,
            "lesson_count": int(course.lesson_count or 0),
            "question_count": int(course.question_count or 0),
            "speaking_count": speaking_count,
            "reading_count": reading_count,
            "speaking_topics": speaking_topics[:3],
            "reading_topics": (reading_topics[:3] or reading_passages[:3]),
            "detail_url": url_for("student.course_detail", course_id=course.id),
            "continue_url": continue_url,
            "continue_label": "Continue" if (first_lesson or speaking_count or reading_count) else "Open Course",
            "reading_url": url_for("student.course_reading_home", course_id=course.id) if reading_count else None,
            "speaking_url": url_for("student.course_speaking_home", course_id=course.id) if speaking_count else None,
            "access_scope": getattr(enrollment, "access_scope", "full_course"),
            "level_summary": _enrollment_level_summary(enrollment),
        })

        continue_cards.append({
            "course_id": course.id,
            "kind": "course",
            "title": course.title,
            "label": "Main course flow",
            "meta": f"{(course.language_code or '').upper()} • {_track_label(course.track_type)}",
            "progress_value": progress_value,
            "target_url": continue_url,
            "cta_label": "Continue",
        })

        if speaking_count:
            continue_cards.append({
                "course_id": course.id,
                "kind": "speaking",
                "title": course.title,
                "label": "Speaking practice",
                "meta": f"{(course.language_code or '').upper()} • {speaking_count} active topic{'s' if speaking_count != 1 else ''}",
                "progress_value": progress_value,
                "target_url": url_for("student.course_speaking_home", course_id=course.id),
                "cta_label": "Open Speaking",
            })

        if reading_count:
            continue_cards.append({
                "course_id": course.id,
                "kind": "reading",
                "title": course.title,
                "label": "Reading practice",
                "meta": f"{(course.language_code or '').upper()} • {reading_count} active set{'s' if reading_count != 1 else ''}",
                "progress_value": progress_value,
                "target_url": url_for("student.course_reading_home", course_id=course.id),
                "cta_label": "Open Reading",
            })

    continue_cards.sort(key=lambda row: (row["course_id"], 0 if row["kind"] == "course" else 1 if row["kind"] == "speaking" else 2, row["title"].lower()))
    return course_cards, continue_cards
def _build_library_cards(
    courses: list[Course],
    enrollment_map: dict[int, Enrollment],
    course_progress: dict[int, int],
    course_speaking_topics: dict[int, list[SpeakingTopic]],
    course_reading_topics: dict[int, list[ReadingTopic]],
    course_reading_passages: dict[int, list[ReadingPassage]],
    writing_task_counts: dict[int, int] | None = None,
    listening_lesson_counts: dict[int, int] | None = None,
    writing_task_map: dict[int, list[WritingTask]] | None = None,
    enrollment_counts: dict[int, int] | None = None,
) -> list[dict]:
    cards: list[dict] = []
    writing_task_counts = writing_task_counts or {}
    listening_lesson_counts = listening_lesson_counts or {}
    writing_task_map = writing_task_map or {}
    enrollment_counts = enrollment_counts or {}

    for course in courses:
        course_enrollment = enrollment_map.get(course.id)
        course_is_enrolled = bool(course_enrollment)
        reward_overview = EconomyService.course_reward_overview(course)
        progress_value = max(0, min(int(course_progress.get(course.id, 0) or 0), 100))
        course_access_type = (getattr(course, "access_type", None) or ("paid" if course.is_premium and float(course.current_price or 0) > 0 else "free")).strip().lower()
        is_premium = course_access_type == "paid"
        access_label = "Premium" if is_premium else "Free"
        track_type = _course_skill_value(course)
        track_label = _track_label(track_type)
        difficulty = _course_level_value(course) or "general"
        level_rank = _level_rank(difficulty)
        max_level = max(int(getattr(course, "max_level", 1) or 1), 1)
        speaking_topics = course_speaking_topics.get(course.id, []) or []
        reading_topics = course_reading_topics.get(course.id, []) or []
        reading_passages = course_reading_passages.get(course.id, []) or []
        writing_tasks = writing_task_map.get(course.id, []) or []
        writing_count = int(writing_task_counts.get(course.id, 0) or len(writing_tasks) or 0)
        listening_count = int(listening_lesson_counts.get(course.id, 0) or 0)
        speaking_count = len(speaking_topics)
        reading_count = max(len(reading_topics), len(reading_passages))
        content_total = int(course.lesson_count or 0) + speaking_count + reading_count + writing_count
        popularity_score = int(enrollment_counts.get(course.id, 0) or 0)
        category_key = _course_category_key(course)
        category_label = _course_category_label(category_key)
        resume_url = _course_continue_url(course, current_user.id)
        course_target_url = resume_url if course_is_enrolled else url_for("student.course_detail", course_id=course.id)
        course_secondary_url = _course_start_url(course, current_user.id) if course_is_enrolled else url_for("student.course_detail", course_id=course.id)
        progress_label = _progress_label(progress_value)
        price_value = float(course.current_price or 0)
        price_label = f"₹{price_value:.0f}" if is_premium and price_value > 0 else "Free"

        def base_card(skill_code: str, skill_label: str, card_kind: str, card_title: str, card_description: str, item_count_label: str, content_badge_label: str, target_url: str, cta_label: str, secondary_label: str = "View Course", secondary_url: str | None = None):
            return {
                "course_id": course.id,
                "course_title": course.title,
                "language_code": (course.language_code or "").upper(),
                "language_filter_code": (course.language_code or "").strip().lower(),
                "difficulty": difficulty,
                "level_rank": level_rank,
                "price": price_value,
                "price_label": price_label,
                "is_premium": is_premium,
                "access_label": access_label,
                "progress_value": progress_value,
                "progress_label": progress_label,
                "lesson_count": int(course.lesson_count or 0),
                "question_count": int(course.question_count or 0),
                "content_total": content_total,
                "reward_band": reward_overview["band"],
                "reward_label": reward_overview["label"],
                "lesson_reward_base": reward_overview["lesson_base"],
                "lesson_reward_high": reward_overview["lesson_high"],
                "speaking_reward_min": reward_overview["speaking_min"],
                "speaking_reward_max": reward_overview["speaking_max"],
                "boss_reward": reward_overview["boss_reward"],
                "reward_summary": f"Lesson {reward_overview['lesson_base']}-{reward_overview['lesson_high']} coins • Boss {reward_overview['boss_reward']}+",
                "allow_coin_redemption": bool(getattr(course, "allow_coin_redemption", False)),
                "coin_redemption_price": int(getattr(course, "coin_redemption_price", 0) or 0),
                "track_type": skill_code,
                "track_label": skill_label,
                "skill_code": skill_code or "course",
                "course_description": card_description,
                "max_level": max_level,
                "level_range_label": f"Level 1–{max_level}",
                "level_group": difficulty,
                "status_label": "Enrolled" if course_is_enrolled else "Not Enrolled",
                "is_enrolled": course_is_enrolled,
                "cta_label": cta_label,
                "secondary_label": secondary_label,
                "target_url": target_url,
                "resume_url": resume_url,
                "secondary_url": secondary_url or url_for("student.course_detail", course_id=course.id),
                "sort_created_at": course.created_at,
                "parent_course_label": course.title,
                "allow_level_purchase": bool(getattr(course, "allow_level_purchase", False)),
                "level_access_label": (getattr(course, "level_access_type", "free") or "free").title(),
                "level_price": float(getattr(course, "current_level_price", 0) or 0),
                "level_checkout_url": _course_level_checkout_url(course, 1),
                "level_summary": _enrollment_level_summary(course_enrollment),
                "card_kind": card_kind,
                "card_title": card_title,
                "card_description": card_description,
                "meta_line": f"{(course.language_code or '').upper()} • {skill_label} • Level 1–{max_level} • {access_label}",
                "item_id": course.id,
                "item_count_label": item_count_label,
                "content_badge_label": content_badge_label,
                "category_key": category_key,
                "category_label": category_label,
                "popularity_score": popularity_score,
                "resume_label": "Resume" if course_is_enrolled and progress_value > 0 else "Start",
                "available_modules": {
                    "speaking": speaking_count,
                    "reading": reading_count,
                    "writing": writing_count,
                    "listening": listening_count,
                },
            }

        cards.append(base_card(
            track_type or "course",
            track_label,
            "course",
            course.title,
            course.description or "Structured language learning with lessons, tasks, and progress tracking.",
            f"{content_total} items" if content_total else "Course",
            f"{speaking_count} Speaking • {reading_count} Reading • {writing_count} Writing • {listening_count} Listening",
            course_target_url,
            "Continue" if course_is_enrolled else ("Buy Now" if is_premium else "Enroll Now"),
            "Open Course" if course_is_enrolled else "View Course",
            course_secondary_url,
        ))

    return cards


@bp.get("/interview")
@login_required
def interview_entry():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    try:
        course = _best_student_interview_course(current_user.id)
    except Exception as exc:
        current_app.logger.exception("Interview course lookup failed: %s", exc)
        course = None

    if course is None:
        flash("No published interview course is available right now.", "info")
        return redirect(url_for("student.course_library", category="interview"))

    active_enrollment = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course.id,
        status="active",
    ).first()

    if not active_enrollment:
        flash("Enroll in the interview course to start practicing.", "info")
        return redirect(url_for("student.course_library", category="interview"))

    return redirect(url_for("student.course_detail", course_id=course.id))


@bp.get("/my-courses")
@login_required
def my_courses():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    enrollments = _my_course_enrollments(current_user.id)
    courses = _distinct_enrolled_courses(enrollments)
    summary = dict(get_student_progress_summary(current_user.id) or {})
    course_progress = {course.id: _course_progress_percent(course) for course in courses}

    course_speaking_counts, course_reading_counts, course_speaking_topics, course_reading_passages, course_reading_topics = _course_library_content(courses)
    writing_task_counts, listening_lesson_counts, writing_task_map, enrollment_counts = _course_library_extra_content(courses)
    enrollment_map = {row.course_id: row for row in enrollments}

    enrolled_cards = [
        card for card in _build_library_cards(
            courses,
            enrollment_map,
            course_progress,
            course_speaking_topics,
            course_reading_topics,
            course_reading_passages,
            writing_task_counts,
            listening_lesson_counts,
            writing_task_map,
            enrollment_counts,
        )
        if card.get("is_enrolled")
    ]

    for card in enrolled_cards:
        card_course_id = card.get("course_id")
        if card.get("card_kind") == "course":
            card["speaking_total"] = len(course_speaking_topics.get(card_course_id, []) or [])
            card["reading_total"] = len(course_reading_topics.get(card_course_id, []) or course_reading_passages.get(card_course_id, []) or [])
        elif card.get("card_kind") == "speaking_topic":
            raw_count = str(card.get("item_count_label") or "0")
            raw_count = (
                raw_count
                .replace("Prompts:", "")
                .replace("Topics:", "")
                .replace("Topic •", "")
                .strip()
                .split()[0]
            )
            try:
                card["content_total"] = max(int(raw_count or 0), 0)
            except ValueError:
                card["content_total"] = 0
        elif card.get("card_kind") in {"reading_topic", "reading_passage"}:
            raw_count = str(card.get("item_count_label") or "0")
            raw_count = raw_count.replace("Passages:", "").replace("Passage •", "").strip().split()[0]
            try:
                card["content_total"] = max(int(raw_count or 0), 0)
            except ValueError:
                card["content_total"] = 0

    kind_order = {"course": 0, "speaking_topic": 1, "reading_topic": 2, "reading_passage": 3}
    enrolled_cards.sort(key=lambda card: (
        card.get("course_id", 0),
        kind_order.get(card.get("card_kind"), 99),
        str(card.get("card_title") or "").lower(),
    ))

    summary["active_courses"] = len(enrolled_cards)

    return render_template(
        "student/my_courses.html",
        enrollments=enrollments,
        courses=courses,
        summary=summary,
        course_progress=course_progress,
        course_speaking_counts=course_speaking_counts,
        course_reading_counts=course_reading_counts,
        course_speaking_topics=course_speaking_topics,
        course_reading_passages=course_reading_passages,
        course_reading_topics=course_reading_topics,
        enrolled_cards=enrolled_cards,
    )






def _special_pathway_bucket(card: dict) -> str | None:
    title = str(card.get("course_title") or card.get("card_title") or "").strip().lower()
    if not title:
        return None
    if "spoken english" in title:
        return "spoken_english"
    if "interview" in title:
        return "interview_preparation"
    if "super advanced" in title:
        return "english_super_advanced"
    return None


def _special_pathway_sections(cards: list[dict]) -> list[dict]:
    labels = {
        "spoken_english": ("Spoken English", "Conversation-first practice for daily life and confidence."),
        "interview_preparation": ("Interview Preparation", "Job-focused English with HR answers and mock speaking practice."),
        "english_super_advanced": ("English Super Advanced", "Premium advanced pathway for debate, vocabulary, and formal writing."),
    }
    grouped: dict[str, list[dict]] = {key: [] for key in labels}
    for card in cards:
        if (card.get("card_kind") or "") != "course":
            continue
        bucket = _special_pathway_bucket(card)
        if bucket:
            grouped[bucket].append(card)
    sections = []
    for key, (title, desc) in labels.items():
        if grouped[key]:
            sections.append({"key": key, "title": title, "description": desc, "cards": grouped[key][:3]})
    return sections

def _placement_test_result() -> dict | None:
    payload = session.get(PLACEMENT_TEST_SESSION_KEY) or {}

    def _normalize(raw: dict | None) -> dict | None:
        if not isinstance(raw, dict) or not raw:
            return None
        normalized = dict(raw)
        normalized.setdefault("recommended_tracks", [])
        normalized.setdefault("recommended_titles", [])
        normalized.setdefault("recommended_keywords", [])
        normalized.setdefault("strengths", [])
        normalized.setdefault("weak_areas", [])
        normalized.setdefault("next_steps", [])
        normalized.setdefault("learning_path", [])
        normalized.setdefault("summary", "")
        normalized.setdefault("fit_summary", "")
        return normalized

    payload = _normalize(payload)
    if payload:
        try:
            if getattr(current_user, "is_authenticated", False) and not payload.get("id"):
                saved = PlacementTestService.save_result(current_user.id, payload)
                payload = _normalize(saved.to_payload())
                session[PLACEMENT_TEST_SESSION_KEY] = payload
                session.modified = True
        except Exception:
            current_app.logger.exception("Placement session save failed for current user.")
        return payload

    if getattr(current_user, "is_authenticated", False):
        try:
            latest = PlacementTestService.latest_result_for_student(current_user.id)
            if latest:
                payload = _normalize(latest.to_payload())
                session[PLACEMENT_TEST_SESSION_KEY] = payload
                session.modified = True
                return payload
        except Exception:
            current_app.logger.exception("Latest placement result lookup failed for current user.")
            return None

    return None


def _placement_course_matches(card: dict, result: dict | None) -> bool:
    if not result:
        return False
    if not card or (card.get("card_kind") or "") != "course":
        return False

    target_level = (result.get("recommended_level") or result.get("level") or "").strip().lower()
    title = str(card.get("course_title") or card.get("card_title") or "").lower()
    difficulty = str(card.get("difficulty") or "").lower()
    track_type = str(card.get("track_type") or card.get("skill_code") or "").lower()
    language_code = str(card.get("language_filter_code") or "").lower()
    target_language = (result.get("target_language") or "english").strip().lower()
    recommended_tracks = {str(v).strip().lower() for v in (result.get("recommended_tracks") or []) if str(v).strip()}
    recommended_keywords = {str(v).strip().lower() for v in (result.get("recommended_keywords") or []) if str(v).strip()}

    level_match = not target_level or target_level in difficulty or target_level in title
    language_match = (
        not target_language
        or target_language in title
        or language_code.startswith(target_language[:2])
        or (target_language == "english" and language_code == "en")
    )
    track_match = not recommended_tracks or track_type in recommended_tracks
    keyword_match = not recommended_keywords or any(keyword in title for keyword in recommended_keywords if keyword)
    return language_match and (level_match or track_match or keyword_match)


def _placement_recommended_cards(all_cards: list[dict], result: dict | None, limit: int = 3) -> list[dict]:
    if not result:
        return []

    target_level = (result.get("recommended_level") or result.get("level") or "").strip().lower()
    preferred_tracks = {str(v).strip().lower() for v in (result.get("recommended_tracks") or []) if str(v).strip()}
    preferred_titles = {str(v).strip().lower() for v in (result.get("recommended_titles") or []) if str(v).strip()}
    preferred_keywords = {str(v).strip().lower() for v in (result.get("recommended_keywords") or []) if str(v).strip()}

    def _score(card: dict) -> tuple[int, int, int, float]:
        title = str(card.get("course_title") or card.get("card_title") or "").lower()
        track = str(card.get("track_type") or card.get("skill_code") or "").lower()
        difficulty = str(card.get("difficulty") or "").lower()
        score = 0
        if _placement_course_matches(card, result):
            score += 8
        if target_level and difficulty == target_level:
            score += 5
        if preferred_tracks and track in preferred_tracks:
            score += 4
        if preferred_titles and any(label in title for label in preferred_titles):
            score += 6
        if preferred_keywords and any(keyword in title for keyword in preferred_keywords):
            score += 4
        if not card.get("is_premium"):
            score += 1
        if card.get("is_enrolled"):
            score -= 3
        if card.get("progress_value"):
            score -= 1
        return (score, int(card.get("is_enrolled") or 0) * -1, int(card.get("course_id") or 0), -float(card.get("price") or 0))

    course_cards = [card for card in all_cards if (card.get("card_kind") or "") == "course"]
    course_cards = sorted(course_cards, key=_score, reverse=True)

    seen = set()
    picks = []
    for card in course_cards:
        cid = card.get("course_id")
        if cid in seen:
            continue
        seen.add(cid)
        picks.append(card)
        if len(picks) >= limit:
            break
    return picks


def _evaluate_placement_submission(form_data) -> dict:
    return PlacementTestService.evaluate_submission(form_data)


@bp.route("/placement-test", methods=["GET", "POST"])
@login_required
def placement_test():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    form_blueprint = PlacementTestService.form_blueprint()
    result = _placement_test_result()
    recommended_cards = []
    learning_path_payload = CourseRecommendationService.learning_path_payload(result, [])
    history_rows = []

    if request.method == "POST":
        try:
            result = _evaluate_placement_submission(request.form)
            saved = PlacementTestService.save_result(current_user.id, result)
            result = saved.to_payload()
            session[PLACEMENT_TEST_SESSION_KEY] = result
            session.modified = True
            flash(f"Placement test completed. Recommended level: {result['recommended_level'].title()}.", "success")
            return redirect(url_for("student.placement_test"))
        except Exception as exc:
            current_app.logger.exception("Placement test submit failed: %s", exc)
            flash("Placement test could not be saved. Please try again.", "danger")

    try:
        history_rows = [
            row.to_payload()
            for row in PlacementTestService.recent_history(current_user.id, limit=5)
        ]
    except Exception as exc:
        current_app.logger.warning("Placement history failed: %s", exc)

    try:
        courses = (
            Course.query
            .filter(Course.status != "archived", Course.is_published.is_(True))
            .order_by(Course.created_at.desc(), Course.id.desc())
            .limit(12)
            .all()
        )

        simple_cards = []
        enrolled_ids = set(_student_enrollment_map(current_user.id).keys())

        for course in courses:
            track = _normalized_track_type(course)
            simple_cards.append({
                "card_kind": "course",
                "course_id": course.id,
                "course_title": course.title,
                "card_title": course.title,
                "card_description": course.description or "Structured English learning course.",
                "track_type": track,
                "skill_code": track,
                "difficulty": (_course_level_value(course) or "basic").lower(),
                "is_enrolled": course.id in enrolled_ids,
                "is_premium": bool(getattr(course, "is_premium", False)),
                "target_url": url_for("student.course_detail", course_id=course.id),
            })

        recommended_cards = _placement_recommended_cards(simple_cards, result, limit=3)
        learning_path_payload = CourseRecommendationService.learning_path_payload(result, simple_cards)

    except Exception as exc:
        current_app.logger.exception("Placement recommendation load failed: %s", exc)
        recommended_cards = []
        learning_path_payload = CourseRecommendationService.learning_path_payload(result, [])

    return render_template(
        "student/placement_test.html",
        form_blueprint=form_blueprint,
        result=result,
        recommended_cards=recommended_cards,
        learning_path_payload=learning_path_payload,
        history_rows=history_rows,
        special_pathway_sections=[],
    )


@bp.get("/course-library")
@login_required
def course_library():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    q = (request.args.get("q") or "").strip().lower()
    category = (request.args.get("category") or "").strip().lower()
    difficulty = (request.args.get("difficulty") or "").strip().lower()
    access = (request.args.get("access") or "all").strip().lower()

    try:
        courses = (
            Course.query
            .filter(Course.status != "archived", Course.is_published.is_(True))
            .order_by(Course.created_at.desc(), Course.id.desc())
            .all()
        )
    except Exception as exc:
        current_app.logger.exception("Course library query failed: %s", exc)
        courses = []

    try:
        enrollments = Enrollment.query.filter_by(student_id=current_user.id, status="active").all()
        enrollment_map = {row.course_id: row for row in enrollments}
    except Exception:
        enrollment_map = {}
    enrolled_ids = set(enrollment_map.keys())

    def _course_category(course):
        track = _normalized_track_type(course)
        if track == "interview":
            return "interview"
        if track == "speaking":
            return "spoken_english"
        if track == "reading":
            return "reading_path"
        if track == "writing":
            return "writing_path"
        if track == "listening":
            return "listening_path"
        return "general"

    def _public_card(course):
        track = _normalized_track_type(course)
        is_enrolled = course.id in enrolled_ids
        price = float(getattr(course, "price", 0) or 0)
        is_premium = bool(price > 0 or getattr(course, "is_premium", False))
        try:
            target_url = _course_continue_url(course, current_user.id) if is_enrolled else url_for("student.course_detail", course_id=course.id)
        except Exception:
            target_url = url_for("student.course_detail", course_id=course.id)
        return {
            "card_kind": "course",
            "course_id": course.id,
            "course_title": getattr(course, "title", None) or "Untitled Course",
            "card_title": getattr(course, "title", None) or "Untitled Course",
            "course_description": getattr(course, "description", None) or "Structured learning path with guided practice.",
            "card_description": getattr(course, "description", None) or "Structured learning path with guided practice.",
            "track_type": track,
            "skill_code": track,
            "track_label": _track_label(track),
            "category_key": _course_category(course),
            "difficulty": (getattr(course, "difficulty", None) or getattr(course, "level", None) or "basic").lower(),
            "level_range_label": (getattr(course, "difficulty", None) or getattr(course, "level", None) or "Basic").title(),
            "language_code": (getattr(course, "language", None) or "English"),
            "language_filter_code": (getattr(course, "language", None) or "english").lower(),
            "price_label": "Free" if not is_premium else f"₹{int(price)}",
            "access_label": "Premium" if is_premium else "Free",
            "is_premium": is_premium,
            "is_enrolled": is_enrolled,
            "progress_value": _student_course_progress_map(current_user.id, {course.id}).get(course.id, 0) if is_enrolled else 0,
            "lesson_count": len(getattr(course, "lessons", []) or []),
            "question_count": 0,
            "content_total": len(getattr(course, "lessons", []) or []),
            "reward_label": "Standard",
            "reward_summary": "Practice, progress, and earn recognition.",
            "allow_coin_redemption": False,
            "coin_redemption_price": None,
            "target_url": target_url,
            "secondary_url": url_for("student.course_detail", course_id=course.id),
            "cta_label": "Continue" if is_enrolled else "View Course",
            "sort_created_at": getattr(course, "created_at", None),
        }

    cards = [_public_card(course) for course in courses]
    if q:
        cards = [card for card in cards if q in (card.get("card_title") or "").lower() or q in (card.get("card_description") or "").lower()]
    if category:
        cards = [card for card in cards if (card.get("category_key") or "") == category]
    if difficulty:
        cards = [card for card in cards if (card.get("difficulty") or "") == difficulty]
    if access == "free":
        cards = [card for card in cards if not card.get("is_premium")]
    elif access == "premium":
        cards = [card for card in cards if card.get("is_premium")]

    placement_result = _placement_test_result()
    cards = CourseRecommendationService.annotate_cards(cards, placement_result)
    recommended_cards = sorted(
        [card for card in cards if (card.get("recommendation_fit") or {}).get("score", 0)],
        key=lambda card: int((card.get("recommendation_fit") or {}).get("score") or 0),
        reverse=True,
    )[:3]
    learning_path_payload = CourseRecommendationService.learning_path_payload(placement_result, cards)

    category_options = [
        ("", "All categories"),
        ("spoken_english", "Spoken English"),
        ("interview", "Interview Prep"),
        ("reading_path", "Reading"),
        ("writing_path", "Writing"),
        ("listening_path", "Listening"),
        ("general", "General"),
    ]

    return render_template(
        "student/course_library.html",
        courses=courses,
        library_cards=cards,
        placement_result=placement_result,
        recommended_cards=recommended_cards,
        learning_path_payload=learning_path_payload,
        enrolled_ids=enrolled_ids,
        current_query=q,
        current_access=access,
        current_language="",
        current_skill="",
        current_difficulty=difficulty,
        current_category=category,
        current_status="all",
        current_sort="latest",
        language_options=[],
        skill_options=[("speaking", "Speaking"), ("interview", "Interview"), ("reading", "Reading"), ("writing", "Writing"), ("listening", "Listening")],
        category_options=category_options,
        level_sections=[],
        track_sections=[],
        special_pathway_sections=[],
        course_speaking_counts={},
        course_reading_counts={},
        course_speaking_topics={},
        course_reading_passages={},
        course_reading_topics={},
        course_progress={},
        enrollment_map=enrollment_map,
    )


@bp.get("/learning-path")
@login_required
def learning_path():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    try:
        placement_result = _placement_test_result()
        courses = (
            Course.query
            .filter(Course.status != "archived", Course.is_published.is_(True))
            .order_by(Course.updated_at.desc(), Course.created_at.desc(), Course.id.desc())
            .all()
        )
        enrollment_map = _student_enrollment_map(current_user.id)
        enrolled_ids = set(enrollment_map.keys())
        course_progress = _student_course_progress_map(current_user.id, enrolled_ids)
        course_speaking_counts, course_reading_counts, course_speaking_topics, course_reading_passages, course_reading_topics = _course_library_content(courses)
        writing_task_counts, listening_lesson_counts, writing_task_map, enrollment_counts = _course_library_extra_content(courses)
        all_library_cards = _build_library_cards(
            courses,
            enrollment_map,
            course_progress,
            course_speaking_topics,
            course_reading_topics,
            course_reading_passages,
            writing_task_counts,
            listening_lesson_counts,
            writing_task_map,
            enrollment_counts,
        )
        annotated_cards = CourseRecommendationService.annotate_cards(all_library_cards, placement_result)
        recommended_cards = [
            card for card in annotated_cards
            if (card.get("card_kind") or "") == "course"
        ]
        recommended_cards = sorted(
            recommended_cards,
            key=lambda card: int((card.get("recommendation_fit") or {}).get("score") or 0),
            reverse=True,
        )[:6]
        learning_path_payload = CourseRecommendationService.learning_path_payload(
            placement_result,
            annotated_cards,
        )
    except Exception as exc:
        current_app.logger.exception("Learning path render failed: %s", exc)
        placement_result = None
        recommended_cards = []
        learning_path_payload = CourseRecommendationService.learning_path_payload(None, [])

    return render_template(
        "student/learning_path.html",
        placement_result=placement_result,
        learning_path_payload=learning_path_payload,
        recommended_cards=recommended_cards,
    )



@bp.get("/certificates")
@login_required
def certificates():
    if not getattr(current_user, "is_student", False):
        flash("Student access required.", "warning")
        return redirect(url_for("main.home"))

    courses = get_student_active_courses(current_user.id)
    records = []
    for course in courses:
        cert = LMSService.ensure_certificate_placeholder(current_user.id, course)
        existing = cert or CertificateRecord.query.filter_by(
            student_id=current_user.id,
            course_id=course.id,
        ).first()
        records.append(
            {
                "course": course,
                "record": existing,
                "completion": _course_progress_percent(course),
            }
        )
    return render_template("student/certificates.html", records=records)
