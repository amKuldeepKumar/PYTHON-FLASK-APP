from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from flask_login import current_user
from sqlalchemy import desc

from ..audit import audit
from ..extensions import db
from ..models.audit import AuditLog
from ..models.lms import Lesson, Question
from ..models.reading_passage import ReadingPassage
from ..models.speaking_prompt import SpeakingPrompt
from ..models.speaking_topic import SpeakingTopic
from ..models.writing_task import WritingTask
from ..models.user import Role

REVIEW_AUDIT_ACTION = "publish_review_state"
REVIEW_NOTE_ACTION = "publish_review_note"


@dataclass
class ReviewItem:
    item_type: str
    item_id: int
    title: str
    course_id: Optional[int]
    course_title: Optional[str]
    module_label: str
    state: str
    is_published: bool
    is_ready: bool
    readiness_note: str
    edit_url: Optional[str] = None
    source_url: Optional[str] = None
    question_count: int = 0
    note: Optional[str] = None
    reviewed_by: Optional[str] = None


class PublishReviewService:
    ITEM_TYPES = ("speaking_topic", "reading_passage", "listening_lesson", "writing_task")

    @staticmethod
    def _audit_target(item_type: str, item_id: int) -> str:
        return f"{item_type}:{item_id}"

    @classmethod
    def _latest_review_audit(cls, item_type: str, item_id: int, action: str = REVIEW_AUDIT_ACTION) -> Optional[AuditLog]:
        return (
            AuditLog.query.filter_by(action=action, target=cls._audit_target(item_type, item_id))
            .order_by(desc(AuditLog.id))
            .first()
        )

    @classmethod
    def _latest_state_from_audit(cls, item_type: str, item_id: int) -> tuple[Optional[str], Optional[str], Optional[str]]:
        row = cls._latest_review_audit(item_type, item_id)
        if not row:
            return None, None, None
        try:
            payload = json.loads(row.meta or "{}")
        except Exception:
            payload = {}
        state = str(payload.get("state") or "").strip().lower() or None
        note = str(payload.get("note") or "").strip() or None
        reviewer = str(payload.get("reviewer_name") or "").strip() or None
        return state, note, reviewer

    @staticmethod
    def _speaking_ready(topic: SpeakingTopic) -> tuple[bool, str, int]:
        prompt_count = topic.prompts.filter_by(is_active=True).count()
        if not topic.course_id:
            return False, "Link topic to a course first.", prompt_count
        if prompt_count <= 0:
            return False, "At least one active prompt is required.", prompt_count
        if not bool(topic.is_active):
            return False, "Topic is inactive.", prompt_count
        return True, "Ready to publish.", prompt_count

    @staticmethod
    def _reading_ready(passage: ReadingPassage) -> tuple[bool, str, int]:
        question_count = passage.questions.count() if hasattr(passage.questions, 'count') else len(list(passage.questions))
        if not passage.course_id:
            return False, "Link passage to a course first.", question_count
        if not (passage.content or "").strip():
            return False, "Passage content is empty.", question_count
        if question_count <= 0:
            return False, "Add at least one question.", question_count
        if not bool(passage.is_active):
            return False, "Passage is inactive.", question_count
        return True, "Ready to publish.", question_count

    @staticmethod
    def _listening_ready(lesson: Lesson) -> tuple[bool, str, int]:
        question_count = 0
        for chapter in lesson.chapters:
            for subsection in chapter.subsections:
                question_count += len(subsection.questions)
        script = (lesson.explanation_tts_text or lesson.explanation_text or "").strip()
        if not lesson.course:
            return False, "Link lesson to a course first.", question_count
        if not script:
            return False, "Listening script is required.", question_count
        if question_count <= 0:
            return False, "Add at least one listening question.", question_count
        return True, "Ready to publish.", question_count

    @staticmethod
    def _writing_ready(task: WritingTask) -> tuple[bool, str, int]:
        if not task.course_id:
            return False, "Link task to a course first.", 0
        if not task.topic_id:
            return False, "Attach the task to a topic first.", 0
        if not (task.instructions or "").strip():
            return False, "Task instructions are missing.", 0
        if not bool(task.is_active):
            return False, "Task is inactive.", 0
        return True, "Ready to publish.", 0

    @classmethod
    def speaking_items(cls) -> list[ReviewItem]:
        rows: list[ReviewItem] = []
        for topic in SpeakingTopic.query.order_by(SpeakingTopic.updated_at.desc(), SpeakingTopic.id.desc()).all():
            ready, note, prompt_count = cls._speaking_ready(topic)
            audit_state, audit_note, reviewer = cls._latest_state_from_audit("speaking_topic", topic.id)
            state = audit_state or ("published" if topic.is_published else "draft")
            rows.append(ReviewItem(
                item_type="speaking_topic", item_id=topic.id, title=topic.title, course_id=topic.course_id,
                course_title=getattr(topic.course, 'title', None), module_label="Speaking", state=state,
                is_published=bool(topic.is_published), is_ready=ready, readiness_note=note,
                edit_url=f"/superadmin/speaking/topics/{topic.id}/edit", source_url=f"/superadmin/speaking/topics?course_id={topic.course_id or ''}",
                question_count=prompt_count, note=audit_note, reviewed_by=reviewer,
            ))
        return rows

    @classmethod
    def reading_items(cls) -> list[ReviewItem]:
        rows: list[ReviewItem] = []
        for passage in ReadingPassage.query.order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc()).all():
            ready, note, question_count = cls._reading_ready(passage)
            state = (passage.workflow_stage or "draft").strip().lower()
            reviewer = passage.reviewed_by.full_name if getattr(passage, 'reviewed_by', None) else None
            rows.append(ReviewItem(
                item_type="reading_passage", item_id=passage.id, title=passage.title, course_id=passage.course_id,
                course_title=getattr(passage.course, 'title', None), module_label="Reading", state=state,
                is_published=bool(passage.is_published), is_ready=ready, readiness_note=note,
                edit_url=f"/superadmin/reading/passages/{passage.id}/edit", source_url=f"/superadmin/reading/passages?course_id={passage.course_id or ''}",
                question_count=question_count, note=passage.review_notes, reviewed_by=reviewer,
            ))
        return rows

    @classmethod
    def listening_items(cls) -> list[ReviewItem]:
        rows: list[ReviewItem] = []
        query = Lesson.query.filter(Lesson.lesson_type == 'listening').order_by(Lesson.updated_at.desc(), Lesson.id.desc())
        for lesson in query.all():
            ready, note, question_count = cls._listening_ready(lesson)
            workflow = (lesson.workflow_status or 'draft').strip().lower()
            if lesson.is_published:
                state = 'published'
            elif workflow in {'review', 'pending'}:
                state = 'review'
            elif workflow in {'approved', 'live'}:
                state = 'approved'
            elif workflow == 'rejected':
                state = 'rejected'
            else:
                state = 'draft'
            audit_state, audit_note, reviewer = cls._latest_state_from_audit("listening_lesson", lesson.id)
            rows.append(ReviewItem(
                item_type="listening_lesson", item_id=lesson.id, title=lesson.title, course_id=getattr(lesson.course, 'id', None),
                course_title=getattr(lesson.course, 'title', None), module_label="Listening", state=audit_state or state,
                is_published=bool(lesson.is_published), is_ready=ready, readiness_note=note,
                edit_url=f"/superadmin/listening/topics/{lesson.id}/edit", source_url=f"/superadmin/listening/topics?course_id={getattr(lesson.course, 'id', '')}",
                question_count=question_count, note=audit_note, reviewed_by=reviewer,
            ))
        return rows

    @classmethod
    def writing_items(cls) -> list[ReviewItem]:
        rows: list[ReviewItem] = []
        for task in WritingTask.query.order_by(WritingTask.updated_at.desc(), WritingTask.id.desc()).all():
            ready, note, question_count = cls._writing_ready(task)
            audit_state, audit_note, reviewer = cls._latest_state_from_audit("writing_task", task.id)
            state = audit_state or ("published" if task.is_published else "draft")
            rows.append(ReviewItem(
                item_type="writing_task", item_id=task.id, title=task.title, course_id=task.course_id,
                course_title=getattr(task.course, 'title', None), module_label="Writing", state=state,
                is_published=bool(task.is_published), is_ready=ready, readiness_note=note,
                edit_url=f"/superadmin/writing/tasks/{task.id}/edit", source_url=f"/superadmin/writing/tasks?course_id={task.course_id or ''}",
                question_count=question_count, note=audit_note, reviewed_by=reviewer,
            ))
        return rows

    @classmethod
    def dashboard_rows(cls, module: str = "all", state: str = "all") -> list[ReviewItem]:
        builders = {
            "speaking": cls.speaking_items,
            "reading": cls.reading_items,
            "listening": cls.listening_items,
            "writing": cls.writing_items,
        }
        rows: list[ReviewItem] = []
        if module == "all":
            for builder in builders.values():
                rows.extend(builder())
        else:
            rows.extend(builders.get(module, lambda: [])())
        if state != "all":
            rows = [row for row in rows if row.state == state]
        rows.sort(key=lambda row: (0 if row.state == 'review' else 1 if row.state == 'draft' else 2, row.module_label, (row.course_title or ''), row.title.lower()))
        return rows

    @classmethod
    def dashboard_counts(cls) -> dict[str, int]:
        rows = cls.dashboard_rows()
        counts = {"all": len(rows), "review": 0, "draft": 0, "approved": 0, "published": 0, "rejected": 0, "not_ready": 0}
        for row in rows:
            counts[row.state] = counts.get(row.state, 0) + 1
            if not row.is_ready:
                counts["not_ready"] += 1
        return counts

    @classmethod
    def resolve_item(cls, item_type: str, item_id: int) -> Any | None:
        model_map = {
            "speaking_topic": SpeakingTopic,
            "reading_passage": ReadingPassage,
            "listening_lesson": Lesson,
            "writing_task": WritingTask,
        }
        model = model_map.get(item_type)
        return model.query.get(item_id) if model else None

    @classmethod
    def _record_state(cls, item_type: str, item_id: int, state: str, note: str | None = None) -> None:
        payload = json.dumps({
            "state": state,
            "note": (note or "").strip() or None,
            "reviewer_id": getattr(current_user, 'id', None),
            "reviewer_name": getattr(current_user, 'full_name', None),
            "reviewer_role": getattr(current_user, 'role_code', None),
        })
        audit(REVIEW_AUDIT_ACTION, target=cls._audit_target(item_type, item_id), meta=payload)

    @classmethod
    def apply_action(cls, item_type: str, item_id: int, action: str, note: str | None = None) -> tuple[bool, str]:
        obj = cls.resolve_item(item_type, item_id)
        if not obj:
            return False, "Item not found."
        action = (action or '').strip().lower()
        if action in {"approve", "publish", "reject", "submit_review", "unpublish"}:
            pass
        else:
            return False, "Unsupported action."

        if item_type == 'speaking_topic':
            ready, readiness_note, _ = cls._speaking_ready(obj)
            if action in {'approve', 'publish'} and not ready:
                return False, readiness_note
            if action == 'submit_review':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'review', note)
            elif action == 'approve':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'approved', note)
            elif action == 'publish':
                obj.is_active = True
                obj.is_published = True
                cls._record_state(item_type, item_id, 'published', note)
            elif action == 'reject':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'rejected', note)
            elif action == 'unpublish':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'draft', note)

        elif item_type == 'reading_passage':
            ready, readiness_note, _ = cls._reading_ready(obj)
            if action in {'approve', 'publish'} and not ready:
                return False, readiness_note
            if action == 'submit_review':
                obj.status = ReadingPassage.STATUS_REVIEW
                obj.is_published = False
                obj.review_notes = None
            elif action == 'approve':
                obj.status = ReadingPassage.STATUS_APPROVED
                obj.is_published = False
                obj.review_notes = (note or '').strip() or None
                obj.reviewed_at = db.func.now()
                obj.reviewed_by_id = getattr(current_user, 'id', None)
            elif action == 'publish':
                obj.status = ReadingPassage.STATUS_APPROVED
                obj.is_active = True
                obj.is_published = True
                obj.review_notes = (note or '').strip() or obj.review_notes
                obj.reviewed_at = db.func.now()
                obj.reviewed_by_id = getattr(current_user, 'id', None)
            elif action == 'reject':
                obj.status = ReadingPassage.STATUS_REJECTED
                obj.is_published = False
                obj.review_notes = (note or '').strip() or None
                obj.reviewed_at = db.func.now()
                obj.reviewed_by_id = getattr(current_user, 'id', None)
            elif action == 'unpublish':
                obj.is_published = False
            cls._record_state(item_type, item_id, 'published' if obj.is_published else (obj.workflow_stage or 'draft'), note)

        elif item_type == 'listening_lesson':
            ready, readiness_note, _ = cls._listening_ready(obj)
            if action in {'approve', 'publish'} and not ready:
                return False, readiness_note
            if action == 'submit_review':
                obj.workflow_status = 'review'
                obj.is_published = False
                cls._record_state(item_type, item_id, 'review', note)
            elif action == 'approve':
                obj.workflow_status = 'approved'
                obj.is_published = False
                cls._record_state(item_type, item_id, 'approved', note)
            elif action == 'publish':
                obj.workflow_status = 'published'
                obj.is_published = True
                cls._record_state(item_type, item_id, 'published', note)
            elif action == 'reject':
                obj.workflow_status = 'rejected'
                obj.is_published = False
                cls._record_state(item_type, item_id, 'rejected', note)
            elif action == 'unpublish':
                obj.is_published = False
                if obj.workflow_status == 'published':
                    obj.workflow_status = 'draft'
                cls._record_state(item_type, item_id, 'draft', note)

        elif item_type == 'writing_task':
            ready, readiness_note, _ = cls._writing_ready(obj)
            if action in {'approve', 'publish'} and not ready:
                return False, readiness_note
            if action == 'submit_review':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'review', note)
            elif action == 'approve':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'approved', note)
            elif action == 'publish':
                obj.is_active = True
                obj.is_published = True
                cls._record_state(item_type, item_id, 'published', note)
            elif action == 'reject':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'rejected', note)
            elif action == 'unpublish':
                obj.is_published = False
                cls._record_state(item_type, item_id, 'draft', note)

        db.session.commit()
        return True, f"{item_type.replace('_', ' ').title()} updated."
