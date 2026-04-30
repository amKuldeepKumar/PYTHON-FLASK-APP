from datetime import datetime

from ..extensions import db


class ReadingTopic(db.Model):
    __tablename__ = "reading_topics"

    LEVEL_BASIC = "basic"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(120), nullable=True, index=True)
    level = db.Column(db.String(30), nullable=False, default=LEVEL_BASIC, index=True)
    description = db.Column(db.Text, nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    course_level_number = db.Column(db.Integer, nullable=True, index=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def level_label(self) -> str:
        return (self.level or self.LEVEL_BASIC).replace('_', ' ').title()

    @property
    def category_label(self) -> str:
        return (self.category or 'General').strip() or 'General'

    @property
    def ai_generation_label(self) -> str:
        return f"{self.level_label} level generation ready"

    course = db.relationship("Course", back_populates="reading_topics", lazy="joined")


    @property
    def is_published(self) -> bool:
        return bool(self.is_active)

    @property
    def publication_label(self) -> str:
        return "Published" if self.is_active else "Draft"
