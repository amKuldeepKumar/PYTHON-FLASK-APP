from __future__ import annotations

from datetime import datetime

from ..extensions import db


class SpeakingTopic(db.Model):
    __tablename__ = "speaking_topics"

    id = db.Column(db.Integer, primary_key=True)
    owner_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    course_level_number = db.Column(db.Integer, nullable=True, index=True)

    code = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    level = db.Column(db.String(30), nullable=False, default="basic", index=True)
    language_code = db.Column(db.String(16), nullable=False, default="en", index=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    topic_kind = db.Column(db.String(30), nullable=False, default="general", index=True)
    interview_category = db.Column(db.String(60), nullable=True, index=True)
    role_family = db.Column(db.String(80), nullable=True, index=True)
    role_name = db.Column(db.String(120), nullable=True)
    answer_framework = db.Column(db.Text, nullable=True)
    sample_answer = db.Column(db.Text, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)

    access_type = db.Column(db.String(20), nullable=False, default="free")
    price = db.Column(db.Float, nullable=False, default=0)
    discount_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=False, default="INR")

    coupon_enabled = db.Column(db.Boolean, nullable=False, default=False)
    coupon_code = db.Column(db.String(80), nullable=True)
    coupon_discount_type = db.Column(db.String(20), nullable=True)
    coupon_discount_value = db.Column(db.Float, nullable=True)
    coupon_valid_from = db.Column(db.String(40), nullable=True)
    coupon_valid_until = db.Column(db.String(40), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course = db.relationship("Course", back_populates="speaking_topics")

    prompts = db.relationship(
        "SpeakingPrompt",
        back_populates="topic",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    sessions = db.relationship(
        "SpeakingSession",
        back_populates="topic",
        lazy="dynamic",
    )

    @property
    def active_prompt_count(self) -> int:
        return self.prompts.filter_by(is_active=True).count()

    @property
    def student_visible_prompt_count(self) -> int:
        return self.prompts.filter_by(is_active=True).count()

    def __repr__(self) -> str:
        return f"<SpeakingTopic {self.code}:{self.title}>"