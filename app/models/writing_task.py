from datetime import datetime

from ..extensions import db


class WritingTask(db.Model):
    __tablename__ = "writing_tasks"

    TASK_ESSAY = "essay"
    TASK_LETTER = "letter"
    TASK_STORY = "story"
    TASK_PARAGRAPH = "paragraph"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("writing_topics.id"), nullable=False, index=True)
    topic_title_snapshot = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    task_type = db.Column(db.String(30), nullable=False, default=TASK_ESSAY, index=True)
    level = db.Column(db.String(30), nullable=False, default="basic", index=True)
    min_words = db.Column(db.Integer, nullable=False, default=80)
    max_words = db.Column(db.Integer, nullable=True)
    language_code = db.Column(db.String(16), nullable=False, default="en", index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    course_level_number = db.Column(db.Integer, nullable=True, index=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    topic = db.relationship("WritingTopic", backref=db.backref("tasks", lazy="dynamic", cascade="all, delete-orphan"))
    course = db.relationship("Course", back_populates="writing_tasks", lazy="joined")

    @property
    def type_label(self) -> str:
        return (self.task_type or self.TASK_ESSAY).replace('_', ' ').title()

    @property
    def length_label(self) -> str:
        min_words = int(self.min_words or 0)
        max_words = int(self.max_words or 0)
        if min_words and max_words:
            return f"{min_words}-{max_words} words"
        if min_words:
            return f"At least {min_words} words"
        if max_words:
            return f"Up to {max_words} words"
        return "Flexible length"

    @property
    def length_guidance(self) -> str:
        min_words = int(self.min_words or 0)
        max_words = int(self.max_words or 0)
        if min_words and max_words:
            return f"Write between {min_words} and {max_words} words. Keep your answer controlled, complete, and within the target range."
        if min_words:
            return f"Write at least {min_words} words so your ideas are developed clearly."
        if max_words:
            return f"Keep your answer within {max_words} words and stay concise."
        return "Write a clear and complete answer."

    @property
    def ai_task_brief(self) -> str:
        base = (self.instructions or '').strip()
        guide = self.length_guidance
        if not base:
            return guide
        if guide.lower() in base.lower():
            return base
        return f"{base}\n\nLength target: {guide}"
