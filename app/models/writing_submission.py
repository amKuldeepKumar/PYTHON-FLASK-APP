from datetime import datetime

from ..extensions import db


class WritingSubmission(db.Model):
    __tablename__ = "writing_submissions"

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("writing_topics.id"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("writing_tasks.id"), nullable=True, index=True)

    submission_text = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    char_count = db.Column(db.Integer, nullable=False, default=0)
    paragraph_count = db.Column(db.Integer, nullable=False, default=0)
    sentence_count = db.Column(db.Integer, nullable=False, default=0)

    score = db.Column(db.Float, nullable=True)
    feedback_text = db.Column(db.Text, nullable=True)
    evaluation_summary = db.Column(db.Text, nullable=True)
    evaluation_payload = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_SUBMITTED, index=True)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = db.relationship("User", lazy="joined")
    course = db.relationship("Course", back_populates="writing_submissions", lazy="joined")
    topic = db.relationship("WritingTopic", lazy="joined")
    task = db.relationship("WritingTask", lazy="joined")

    @property
    def evaluation_data(self):
        import json
        if not self.evaluation_payload:
            return {}
        try:
            return json.loads(self.evaluation_payload)
        except Exception:
            return {}
