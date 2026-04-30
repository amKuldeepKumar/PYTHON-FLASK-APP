from datetime import datetime

from ..extensions import db


class ReadingQuestion(db.Model):
    __tablename__ = "reading_questions"

    TYPE_MCQ = "mcq"
    TYPE_FILL_BLANK = "fill_blank"
    TYPE_TRUE_FALSE = "true_false"

    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_PENDING = STATUS_REVIEW
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_ARCHIVED = "archived"

    id = db.Column(db.Integer, primary_key=True)
    passage_id = db.Column(db.Integer, db.ForeignKey("reading_passages.id"), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("reading_topics.id"), nullable=False, index=True)
    question_type = db.Column(db.String(30), nullable=False, index=True)
    level = db.Column(db.String(30), nullable=False, default="basic", index=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    prompt_snapshot = db.Column(db.Text, nullable=True)
    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=True)
    correct_answer = db.Column(db.Text, nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    source_sentence = db.Column(db.Text, nullable=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("reading_providers.id"), nullable=True, index=True)
    provider_name_snapshot = db.Column(db.String(160), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    review_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    confidence_score = db.Column(db.Float, nullable=True)
    auto_flag_reason = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    passage = db.relationship("ReadingPassage", backref=db.backref("questions", lazy="dynamic"))
    topic = db.relationship("ReadingTopic", lazy="joined")
    provider = db.relationship("ReadingProvider", lazy="joined")
    reviewed_by = db.relationship("User", lazy="joined")

    @property
    def type_label(self) -> str:
        return {
            self.TYPE_MCQ: "MCQ",
            self.TYPE_FILL_BLANK: "Fill in the Blank",
            self.TYPE_TRUE_FALSE: "True / False",
        }.get(self.question_type, (self.question_type or "Question").replace("_", " ").title())

    @property
    def level_label(self) -> str:
        return (self.level or "basic").replace("_", " ").title()

    @property
    def status_label(self) -> str:
        status = (self.status or self.STATUS_DRAFT).strip().lower()
        if status == self.STATUS_PENDING:
            status = self.STATUS_REVIEW
        return status.replace("_", " ").title()

    @property
    def workflow_stage(self) -> str:
        status = (self.status or self.STATUS_DRAFT).strip().lower()
        if status == self.STATUS_APPROVED:
            return "published"
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
