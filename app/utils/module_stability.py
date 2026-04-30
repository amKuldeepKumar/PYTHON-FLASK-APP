from __future__ import annotations

from ..extensions import db
from ..models.lms import Course
from ..models.reading_passage import ReadingPassage
from ..models.reading_question import ReadingQuestion
from ..models.speaking_topic import SpeakingTopic
from ..models.writing_task import WritingTask
from ..models.writing_topic import WritingTopic
from ..services.course_runtime import course_track


LIVE_COURSE_STATES = {"published", "live", "approved"}
LIVE_WORKFLOW_STATES = {"published", "live", "approved"}


def normalize_track_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    aliases = {
        "spoken": "spoken_english",
        "spoken-english": "spoken_english",
        "spoken english": "spoken_english",
    }
    return aliases.get(raw, raw)


def course_is_live(course: Course | None) -> bool:
    if not course:
        return False
    if not bool(getattr(course, "is_published", False)):
        return False
    archived_at = getattr(course, "archived_at", None)
    if archived_at is not None:
        return False
    status = (getattr(course, "status", "") or "").strip().lower()
    workflow = (getattr(course, "workflow_status", "") or "").strip().lower()
    if status and status not in LIVE_COURSE_STATES:
        return False
    if workflow and workflow not in {"", *LIVE_WORKFLOW_STATES}:
        return False
    return True


def speaking_topic_is_startable(topic: SpeakingTopic | None) -> bool:
    if not topic:
        return False
    if not bool(getattr(topic, "is_active", False)) or not bool(getattr(topic, "is_published", False)):
        return False
    topic_kind = (getattr(topic, "topic_kind", "") or "").strip().lower()
    if topic_kind == "interview":
        return False
    return int(getattr(topic, "active_prompt_count", 0) or 0) > 0


def reading_passage_is_live(passage: ReadingPassage | None) -> bool:
    if not passage:
        return False
    if not bool(getattr(passage, "is_active", False)) or not bool(getattr(passage, "is_published", False)):
        return False
    if (getattr(passage, "status", "") or "").strip().lower() != ReadingPassage.STATUS_APPROVED:
        return False

    topic = getattr(passage, "topic", None)
    if not topic or not bool(getattr(topic, "is_active", False)):
        return False

    passage_course_id = getattr(passage, "course_id", None)
    topic_course_id = getattr(topic, "course_id", None)
    if passage_course_id is not None and topic_course_id is not None and passage_course_id != topic_course_id:
        return False

    approved_question_count = (
        ReadingQuestion.query
        .filter(
            ReadingQuestion.passage_id == passage.id,
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .count()
    )
    return approved_question_count > 0


def writing_topic_is_live(topic: WritingTopic | None) -> bool:
    if not topic:
        return False
    return bool(getattr(topic, "is_active", False)) and bool(getattr(topic, "is_published", False))


def writing_task_is_live(task: WritingTask | None) -> bool:
    if not task:
        return False
    if not bool(getattr(task, "is_active", False)) or not bool(getattr(task, "is_published", False)):
        return False
    topic = getattr(task, "topic", None)
    if not topic:
        return False
    topic_course_id = getattr(topic, "course_id", None)
    task_course_id = getattr(task, "course_id", None)
    if topic_course_id is not None and task_course_id is not None and topic_course_id != task_course_id:
        return False
    return writing_topic_is_live(topic)


def listening_course_is_live(course: Course | None) -> bool:
    if not course:
        return False
    if course_track(course) != "listening":
        return False
    if not course_is_live(course):
        return False
    return any(
        bool(getattr(lesson, "is_published", False))
        for level in getattr(course, "levels", [])
        for lesson in getattr(level, "lessons", [])
        if (getattr(lesson, "lesson_type", "") or "").strip().lower() == "listening"
    )


def course_module_is_live(course: Course | None, module_key: str) -> bool:
    if not course or not course_is_live(course):
        return False

    module_key = normalize_track_type(module_key)
    actual_track = course_track(course)
    if module_key and actual_track != module_key:
        return False

    if actual_track in {"speaking", "spoken_english"}:
        topics = getattr(course, "speaking_topics", []) or []
        return any(speaking_topic_is_startable(topic) for topic in topics)
    if actual_track == "reading":
        passages = getattr(course, "reading_passages", []) or []
        return any(reading_passage_is_live(passage) for passage in passages)
    if actual_track == "writing":
        tasks = getattr(course, "writing_tasks", []) or []
        return any(writing_task_is_live(task) for task in tasks)
    if actual_track == "listening":
        return listening_course_is_live(course)
    if actual_track == "interview":
        topics = getattr(course, "speaking_topics", []) or []
        return any(
            bool(getattr(topic, "is_active", False))
            and bool(getattr(topic, "is_published", False))
            and int(getattr(topic, "active_prompt_count", 0) or 0) > 0
            for topic in topics
            if (getattr(topic, "topic_kind", "") or "").strip().lower() == "interview"
        )
    return False


def course_has_startable_content(course: Course | None, module_key: str | None = None) -> bool:
    if not course:
        return False
    return course_module_is_live(course, module_key or course_track(course))


def student_can_open_course(course: Course | None, module_key: str | None = None) -> bool:
    if not course:
        return False
    return course_module_is_live(course, module_key or course_track(course))


def repair_module_relationships() -> dict[str, int]:
    stats = {
        "reading_passages_repaired": 0,
        "writing_tasks_repaired": 0,
        "speaking_topics_disabled": 0,
        "reading_passages_disabled": 0,
        "writing_tasks_disabled": 0,
    }

    for passage in ReadingPassage.query.all():
        topic = getattr(passage, "topic", None)
        if not topic:
            if passage.is_active:
                passage.is_active = False
                passage.is_published = False
                passage.status = ReadingPassage.STATUS_ARCHIVED
                stats["reading_passages_disabled"] += 1
            continue

        changed = False
        if getattr(passage, "course_id", None) != getattr(topic, "course_id", None):
            passage.course_id = getattr(topic, "course_id", None)
            changed = True
        if getattr(passage, "course_level_number", None) != getattr(topic, "course_level_number", None):
            passage.course_level_number = getattr(topic, "course_level_number", None)
            changed = True
        if changed:
            stats["reading_passages_repaired"] += 1

    for task in WritingTask.query.all():
        topic = getattr(task, "topic", None)
        if not topic:
            if task.is_active:
                task.is_active = False
                task.is_published = False
                stats["writing_tasks_disabled"] += 1
            continue

        changed = False
        if getattr(task, "course_id", None) != getattr(topic, "course_id", None):
            task.course_id = getattr(topic, "course_id", None)
            changed = True
        if getattr(task, "course_level_number", None) != getattr(topic, "course_level_number", None):
            task.course_level_number = getattr(topic, "course_level_number", None)
            changed = True
        if changed:
            stats["writing_tasks_repaired"] += 1

    for topic in SpeakingTopic.query.all():
        course = getattr(topic, "course", None)
        track = course_track(course) if course else ""
        if track not in {"speaking", "spoken_english", "interview"}:
            if topic.is_active or topic.is_published:
                topic.is_active = False
                topic.is_published = False
                stats["speaking_topics_disabled"] += 1

    if any(stats.values()):
        db.session.commit()
    return stats
