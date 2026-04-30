from __future__ import annotations

from datetime import datetime, timedelta
import json
from decimal import Decimal

from sqlalchemy.ext.hybrid import hybrid_property

from ..extensions import db


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    owner_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    welcome_intro_script = db.Column(db.Text, nullable=True)
    learning_outcomes_script = db.Column(db.Text, nullable=True)

    language_code = db.Column(db.String(20), nullable=False, default="en", index=True)
    track_type = db.Column(db.String(40), nullable=False, default="speaking", index=True)
    difficulty = db.Column(db.String(40), nullable=True, index=True)
    max_level = db.Column(db.Integer, nullable=False, default=1)
    access_type = db.Column(db.String(20), nullable=False, default="free", index=True)
    allow_level_purchase = db.Column(db.Boolean, nullable=False, default=False)
    level_access_type = db.Column(db.String(20), nullable=False, default="free", index=True)

    currency_code = db.Column(db.String(10), nullable=False, default="INR")
    level_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    level_sale_price = db.Column(db.Numeric(10, 2), nullable=True)
    base_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    sale_price = db.Column(db.Numeric(10, 2), nullable=True)
    allow_coin_redemption = db.Column(db.Boolean, nullable=False, default=False, index=True)
    coin_price = db.Column(db.Integer, nullable=True)
    community_enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    speaking_base_override = db.Column(db.Integer, nullable=True)
    speaking_relevance_bonus_override = db.Column(db.Integer, nullable=True)
    speaking_progress_bonus_override = db.Column(db.Integer, nullable=True)
    speaking_good_bonus_override = db.Column(db.Integer, nullable=True)
    speaking_strong_bonus_override = db.Column(db.Integer, nullable=True)
    speaking_full_length_bonus_override = db.Column(db.Integer, nullable=True)
    speaking_first_try_bonus_override = db.Column(db.Integer, nullable=True)
    lesson_base_override = db.Column(db.Integer, nullable=True)
    lesson_accuracy_mid_bonus_override = db.Column(db.Integer, nullable=True)
    lesson_accuracy_high_bonus_override = db.Column(db.Integer, nullable=True)
    boss_reward_override = db.Column(db.Integer, nullable=True)

    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_premium = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)

    sort_order = db.Column(db.Integer, nullable=False, default=0)
    archived_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    version_number = db.Column(db.Integer, nullable=False, default=1)
    workflow_status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    submitted_for_review_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)

    owner_admin = db.relationship("User", foreign_keys=[owner_admin_id], lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_id], lazy="joined")

    levels = db.relationship(
        "Level",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Level.sort_order.asc(), Level.id.asc()",
    )
    enrollments = db.relationship(
        "Enrollment",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Enrollment.enrolled_at.desc()",
    )
    course_progress_rows = db.relationship(
        "CourseProgress",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseProgress.updated_at.desc()",
    )
    speaking_topics = db.relationship(
        "SpeakingTopic",
        back_populates="course",
        lazy="select",
        order_by="SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc()",
    )
    speaking_sessions = db.relationship(
        "SpeakingSession",
        back_populates="course",
        lazy="select",
        order_by="SpeakingSession.created_at.desc(), SpeakingSession.id.desc()",
    )
    interview_profiles = db.relationship(
        "InterviewProfile",
        lazy="select",
        order_by="InterviewProfile.updated_at.desc(), InterviewProfile.id.desc()",
    )
    interview_sessions = db.relationship(
        "InterviewSession",
        lazy="select",
        order_by="InterviewSession.created_at.desc(), InterviewSession.id.desc()",
    )
    reading_topics = db.relationship(
        "ReadingTopic",
        back_populates="course",
        lazy="select",
        order_by="ReadingTopic.display_order.asc(), ReadingTopic.title.asc()",
    )
    reading_passages = db.relationship(
        "ReadingPassage",
        back_populates="course",
        lazy="select",
        order_by="ReadingPassage.created_at.desc(), ReadingPassage.id.desc()",
    )
    writing_topics = db.relationship(
        "WritingTopic",
        back_populates="course",
        lazy="select",
        order_by="WritingTopic.display_order.asc(), WritingTopic.title.asc()",
    )
    writing_tasks = db.relationship(
        "WritingTask",
        back_populates="course",
        lazy="select",
        order_by="WritingTask.display_order.asc(), WritingTask.title.asc()",
    )
    writing_submissions = db.relationship(
        "WritingSubmission",
        back_populates="course",
        lazy="select",
        order_by="WritingSubmission.submitted_at.desc(), WritingSubmission.id.desc()",
    )

    coupons = db.relationship(
        "Coupon",
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @hybrid_property
    def current_price(self):
        if self.sale_price is not None:
            return self.sale_price
        return self.base_price or Decimal("0.00")

    @hybrid_property
    def current_level_price(self):
        if self.level_sale_price is not None:
            return self.level_sale_price
        return self.level_price or Decimal("0.00")

    @property
    def coin_redemption_price(self) -> int:
        return max(0, int(self.coin_price or 0))

    @property
    def lesson_count(self) -> int:
        return sum(len(level.lessons) for level in self.levels)

    @property
    def question_count(self) -> int:
        total = 0
        for level in self.levels:
            for lesson in level.lessons:
                for chapter in lesson.chapters:
                    for subsection in chapter.subsections:
                        total += len(subsection.questions)
        return total


class Level(db.Model):
    __tablename__ = "levels"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship("Course", back_populates="levels")
    modules = db.relationship(
        "Module",
        back_populates="level",
        cascade="all, delete-orphan",
        order_by="Module.sort_order.asc(), Module.id.asc()",
    )
    lessons = db.relationship(
        "Lesson",
        back_populates="level",
        cascade="all, delete-orphan",
        order_by="Lesson.sort_order.asc(), Lesson.id.asc()",
    )


class Module(db.Model):
    __tablename__ = "modules"

    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"), nullable=False, index=True)

    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    level = db.relationship("Level", back_populates="modules")
    lessons = db.relationship(
        "Lesson",
        back_populates="module",
        order_by="Lesson.sort_order.asc(), Lesson.id.asc()",
    )


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=True, index=True)

    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), nullable=True, index=True)
    lesson_type = db.Column(db.String(40), nullable=False, default="guided", index=True)

    explanation_text = db.Column(db.Text, nullable=True)
    explanation_tts_text = db.Column(db.Text, nullable=True)
    estimated_minutes = db.Column(db.Integer, nullable=False, default=10)

    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    workflow_status = db.Column(db.String(30), nullable=False, default="draft", index=True)

    level = db.relationship("Level", back_populates="lessons")
    module = db.relationship("Module", back_populates="lessons")
    chapters = db.relationship(
        "Chapter",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Chapter.sort_order.asc(), Chapter.id.asc()",
    )
    progresses = db.relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")

    @property
    def course(self):
        return self.level.course if self.level else None

    @property
    def question_count(self) -> int:
        total = 0
        for chapter in self.chapters:
            for subsection in chapter.subsections:
                total += len(subsection.questions)
        return total


class Chapter(db.Model):
    __tablename__ = "chapters"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)

    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    lesson = db.relationship("Lesson", back_populates="chapters")
    subsections = db.relationship(
        "Subsection",
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Subsection.sort_order.asc(), Subsection.id.asc()",
    )


class Subsection(db.Model):
    __tablename__ = "subsections"

    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False, index=True)

    title = db.Column(db.String(180), nullable=False)
    grammar_formula = db.Column(db.String(180), nullable=True)
    grammar_tags = db.Column(db.String(500), nullable=True)
    hint_seed = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapter = db.relationship("Chapter", back_populates="subsections")
    questions = db.relationship(
        "Question",
        back_populates="subsection",
        cascade="all, delete-orphan",
        order_by="Question.sort_order.asc(), Question.id.asc()",
    )


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey("subsections.id"), nullable=False, index=True)

    prompt = db.Column(db.Text, nullable=False)
    prompt_type = db.Column(db.String(40), nullable=False, default="question", index=True)
    title = db.Column(db.String(180), nullable=True)
    image_url = db.Column(db.String(255), nullable=True)

    hint_text = db.Column(db.Text, nullable=True)
    model_answer = db.Column(db.Text, nullable=True)
    evaluation_rubric = db.Column(db.Text, nullable=True)
    expected_keywords = db.Column(db.Text, nullable=True)
    answer_patterns_text = db.Column(db.Text, nullable=True)
    answer_generation_status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    answer_generated_at = db.Column(db.DateTime, nullable=True)
    synonym_help_text = db.Column(db.Text, nullable=True)
    translation_help_text = db.Column(db.Text, nullable=True)

    language_code = db.Column(db.String(20), nullable=False, default="en", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    version_number = db.Column(db.Integer, nullable=False, default=1)

    @property
    def answer_patterns_list(self) -> list[str]:
        raw = (self.answer_patterns_text or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                return [str(item).strip() for item in data if str(item).strip()]
            except Exception:
                pass
        return [line.strip(" -•	") for line in raw.splitlines() if line.strip()]

    subsection = db.relationship("Subsection", back_populates="questions")
    attempts = db.relationship(
        "QuestionAttempt",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionAttempt.attempted_at.desc()",
    )


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    enrolled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    access_scope = db.Column(db.String(20), nullable=False, default="full_course", index=True)
    purchased_levels_json = db.Column(db.Text, nullable=True)
    enrolled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    welcome_seen_at = db.Column(db.DateTime, nullable=True)

    @property
    def purchased_levels(self) -> list[int]:
        raw = (self.purchased_levels_json or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            data = []
        levels = []
        for item in data or []:
            try:
                value = int(item)
            except Exception:
                continue
            if value > 0 and value not in levels:
                levels.append(value)
        return sorted(levels)

    @purchased_levels.setter
    def purchased_levels(self, values):
        clean = []
        for item in values or []:
            try:
                value = int(item)
            except Exception:
                continue
            if value > 0 and value not in clean:
                clean.append(value)
        self.purchased_levels_json = json.dumps(sorted(clean)) if clean else None

    def has_full_access(self) -> bool:
        return (self.access_scope or "full_course") == "full_course"

    def has_level_access(self, level_number: int | None) -> bool:
        if self.has_full_access() or level_number in (None, 0):
            return True
        try:
            target = int(level_number)
        except Exception:
            return False
        return target in self.purchased_levels

    def grant_level_access(self, level_number: int):
        levels = self.purchased_levels
        if level_number not in levels:
            levels.append(int(level_number))
        self.purchased_levels = levels
        if levels and not self.has_full_access():
            self.access_scope = "level_only"

    student = db.relationship("User", foreign_keys=[student_id], back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")
    enrolled_by = db.relationship("User", foreign_keys=[enrolled_by_id])


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        db.UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True, index=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey("subsections.id"), nullable=True, index=True)

    completed_questions = db.Column(db.Integer, nullable=False, default=0)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    completion_percent = db.Column(db.Integer, nullable=False, default=0)
    skipped_questions = db.Column(db.Integer, nullable=False, default=0)
    retry_questions = db.Column(db.Integer, nullable=False, default=0)
    support_tool_usage_count = db.Column(db.Integer, nullable=False, default=0)
    support_tool_penalty_points = db.Column(db.Float, nullable=False, default=0.0)

    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("User", back_populates="lesson_progress")
    lesson = db.relationship("Lesson", back_populates="progresses")
    chapter = db.relationship("Chapter")
    subsection = db.relationship("Subsection")


class CourseProgress(db.Model):
    __tablename__ = "course_progress"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_course_progress_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)

    completed_lessons = db.Column(db.Integer, nullable=False, default=0)
    total_lessons = db.Column(db.Integer, nullable=False, default=0)
    completed_questions = db.Column(db.Integer, nullable=False, default=0)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    completion_percent = db.Column(db.Integer, nullable=False, default=0)
    average_accuracy = db.Column(db.Float, nullable=False, default=0.0)

    first_started_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("User", back_populates="course_progress_rows")
    course = db.relationship("Course", back_populates="course_progress_rows")


class QuestionAttempt(db.Model):
    __tablename__ = "question_attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True, index=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey("subsections.id"), nullable=True, index=True)

    response_text = db.Column(db.Text, nullable=True)
    stt_transcript = db.Column(db.Text, nullable=True)
    response_mode = db.Column(db.String(30), nullable=False, default="typed", index=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    attempt_kind = db.Column(db.String(20), nullable=False, default="final", index=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    is_retry = db.Column(db.Boolean, nullable=False, default=False)

    hint_used = db.Column(db.Boolean, nullable=False, default=False)
    synonym_used = db.Column(db.Boolean, nullable=False, default=False)
    translation_used = db.Column(db.Boolean, nullable=False, default=False)
    skipped = db.Column(db.Boolean, nullable=False, default=False)
    returned_after_skip = db.Column(db.Boolean, nullable=False, default=False)
    skip_reason = db.Column(db.String(80), nullable=True)
    support_tools_json = db.Column(db.Text, nullable=True)
    support_tool_penalty_points = db.Column(db.Float, nullable=False, default=0.0)
    ml_consent_granted = db.Column(db.Boolean, nullable=False, default=False)

    accuracy_score = db.Column(db.Float, nullable=True)
    grammar_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    ai_feedback = db.Column(db.Text, nullable=True)
    ai_detected_grammar = db.Column(db.String(180), nullable=True)
    is_correctish = db.Column(db.Boolean, nullable=False, default=False)

    attempted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("User", back_populates="question_attempts")
    question = db.relationship("Question", back_populates="attempts")
    lesson = db.relationship("Lesson")
    chapter = db.relationship("Chapter")
    subsection = db.relationship("Subsection")


class CertificateRecord(db.Model):
    __tablename__ = "certificate_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    issued_at = db.Column(db.DateTime, nullable=True)
    certificate_code = db.Column(db.String(80), nullable=True, unique=True)
    storage_path = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PronunciationProfile(db.Model):
    __tablename__ = "pronunciation_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)

    ipa_summary = db.Column(db.Text, nullable=True)
    accent_notes = db.Column(db.Text, nullable=True)
    last_analyzed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class LearningAnalyticsSnapshot(db.Model):
    __tablename__ = "learning_analytics_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)

    lessons_completed = db.Column(db.Integer, nullable=False, default=0)
    speaking_accuracy = db.Column(db.Float, nullable=False, default=0.0)
    practice_minutes = db.Column(db.Integer, nullable=False, default=0)


class CourseBatch(db.Model):
    __tablename__ = "course_batches"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    admin = db.relationship("User", foreign_keys=[admin_id])
    course = db.relationship("Course")


class ContentVersion(db.Model):
    __tablename__ = "content_versions"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    change_summary = db.Column(db.String(255), nullable=True)
    snapshot_json = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by = db.relationship("User")


def spaced_repetition_weight(last_attempt_at: datetime | None, accuracy_score: float | None = None) -> float:
    score = float(accuracy_score or 0.0)
    if last_attempt_at is None:
        return 100.0 + max(0.0, 1.0 - score) * 50.0

    age_days = max(0.0, (datetime.utcnow() - last_attempt_at).total_seconds() / 86400.0)
    difficulty_bonus = max(0.0, 1.0 - score) * 70.0
    freshness_penalty = max(0.0, 10.0 - min(age_days, 10.0))
    return round(50.0 + difficulty_bonus + min(age_days, 30.0) - freshness_penalty, 2)


def should_repeat_question(last_attempt_at: datetime | None, cooldown_days: int = 7) -> bool:
    if last_attempt_at is None:
        return True
    if cooldown_days <= 0:
        return True
    return (datetime.utcnow() - last_attempt_at).days >= cooldown_days
