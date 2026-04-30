from datetime import datetime

from ..extensions import db


class ReadingPassage(db.Model):
    __tablename__ = "reading_passages"

    LENGTH_SHORT = "short"
    LENGTH_MEDIUM = "medium"
    LENGTH_LONG = "long"

    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_PENDING = STATUS_REVIEW
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_ARCHIVED = "archived"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("reading_topics.id"), nullable=False, index=True)
    topic_title_snapshot = db.Column(db.String(160), nullable=False)
    level = db.Column(db.String(30), nullable=False, index=True)
    length_mode = db.Column(db.String(20), nullable=False, default=LENGTH_MEDIUM, index=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    prompt_snapshot = db.Column(db.Text, nullable=True)
    generation_notes = db.Column(db.Text, nullable=True)
    generation_source = db.Column(db.String(40), nullable=False, default="dynamic_api")
    provider_id = db.Column(db.Integer, db.ForeignKey("reading_providers.id"), nullable=True, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    course_level_number = db.Column(db.Integer, nullable=True, index=True)
    provider_name_snapshot = db.Column(db.String(160), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    review_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    confidence_score = db.Column(db.Float, nullable=True)
    auto_flag_reason = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    topic = db.relationship("ReadingTopic", backref=db.backref("passages", lazy="dynamic"))
    course = db.relationship("Course", back_populates="reading_passages")
    provider = db.relationship("ReadingProvider", lazy="joined")
    reviewed_by = db.relationship("User", lazy="joined")

    @property
    def level_label(self) -> str:
        return (self.level or "basic").replace("_", " ").title()

    @property
    def length_label(self) -> str:
        return (self.length_mode or self.LENGTH_MEDIUM).replace("_", " ").title()

    @property
    def status_label(self) -> str:
        status = (self.status or self.STATUS_DRAFT).strip().lower()
        if status == self.STATUS_PENDING:
            status = self.STATUS_REVIEW
        return status.replace("_", " ").title()

    @property
    def workflow_stage(self) -> str:
        status = (self.status or self.STATUS_DRAFT).strip().lower()
        if self.is_published:
            return "published"
        if status == self.STATUS_APPROVED:
            return "approved"
        if status in {self.STATUS_PENDING, self.STATUS_REVIEW}:
            return "review"
        if status == self.STATUS_REJECTED:
            return "rejected"
        if status == self.STATUS_ARCHIVED:
            return "archived"
        return "draft"

    @property
    def workflow_label(self) -> str:
        return self.workflow_stage.replace("_", " ").title()

    @property
    def publication_label(self) -> str:
        return "Published" if self.is_published else ("In Review" if self.workflow_stage == "review" else "Draft")
