from __future__ import annotations

from ..extensions import db
from ..models.lms import Course

CANONICAL_TRACKS = {
    "speaking",
    "spoken_english",
    "interview",
    "reading",
    "writing",
    "listening",
}
SPEAKING_POWERED_TRACKS = {"speaking", "spoken_english"}
TRACK_ALIASES = {
    "spoken": "spoken_english",
    "spoken-english": "spoken_english",
    "spoken english": "spoken_english",
    "topic": "speaking",
    "conversation": "speaking",
}


def normalize_track_value(value: str | None) -> str:
    raw = (value or "").strip().lower()
    normalized = TRACK_ALIASES.get(raw, raw)
    return normalized if normalized in CANONICAL_TRACKS else ""


def _slug_value(course: Course | None) -> str:
    return (getattr(course, "slug", "") or "").strip().lower()


def _title_value(course: Course | None) -> str:
    return (getattr(course, "title", "") or "").strip().lower()


def is_spoken_english_course(course: Course | None) -> bool:
    if not course:
        return False
    return (
        _slug_value(course) == "spoken-english"
        or _title_value(course) == "spoken english"
        or normalize_track_value(getattr(course, "track_type", None)) == "spoken_english"
    )


def infer_course_track(course: Course | None) -> str:
    """
    Strict runtime track resolver.

    Priority:
    1. course.track_type when valid
    2. explicit known slug/title identities
    3. safe default = speaking

    Important: this intentionally avoids content-based guessing from lessons/topics,
    because that is one of the main causes of wrong redirects.
    """
    if not course:
        return "speaking"

    raw_track = normalize_track_value(getattr(course, "track_type", None))
    if raw_track:
        return raw_track

    slug = _slug_value(course)
    title = _title_value(course)

    if slug == "interview-preparation" or "interview" in title:
        return "interview"
    if slug == "spoken-english" or title == "spoken english":
        return "spoken_english"
    if "listening" in title:
        return "listening"
    if "reading" in title:
        return "reading"
    if "writing" in title:
        return "writing"

    return "speaking"


def course_track(course: Course | None) -> str:
    return infer_course_track(course)


def course_runtime_mode(course: Course | None) -> str:
    return course_track(course)


def course_is_track(course: Course | None, track: str) -> bool:
    return course_track(course) == normalize_track_value(track)


def is_interview_course(course: Course | None) -> bool:
    return course_track(course) == "interview"


def course_category_key(course: Course | None) -> str:
    if not course:
        return "general"
    slug = _slug_value(course)
    title = _title_value(course)
    track = course_track(course)
    if slug == "spoken-english" or track == "spoken_english":
        return "spoken_english"
    if slug == "interview-preparation" or track == "interview":
        return "interview"
    if slug == "english-super-advanced" or "super advanced" in title:
        return "super_advanced"
    if "ielts" in title or "exam" in title or "test prep" in title:
        return "exam_prep"
    return {
        "speaking": "speaking_path",
        "spoken_english": "spoken_english",
        "reading": "reading_path",
        "writing": "writing_path",
        "listening": "listening_path",
        "interview": "interview",
    }.get(track, "general")


def repair_course_catalog() -> int:
    changed = 0
    for course in Course.query.order_by(Course.id.asc()).all():
        inferred = infer_course_track(course)
        raw_value = normalize_track_value(getattr(course, "track_type", None))
        if inferred and raw_value != inferred:
            course.track_type = inferred
            changed += 1

        if inferred == "interview":
            for topic in (getattr(course, "speaking_topics", []) or []):
                if (getattr(topic, "topic_kind", "") or "").strip().lower() != "interview":
                    topic.topic_kind = "interview"
                    changed += 1
                if not getattr(topic, "interview_category", None):
                    topic.interview_category = "general_hr"
                    changed += 1
                prompts = topic.prompts.all() if hasattr(topic.prompts, 'all') else list(topic.prompts)
                for prompt in prompts:
                    if (getattr(prompt, "prompt_kind", "") or "").strip().lower() != "interview":
                        prompt.prompt_kind = "interview"
                        changed += 1

    if changed:
        db.session.commit()
    return changed
