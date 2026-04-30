from datetime import datetime

from ..extensions import db


class ReadingSessionLog(db.Model):
    __tablename__ = "reading_session_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True, index=True)
    passage_id = db.Column(db.Integer, db.ForeignKey("reading_passages.id"), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("reading_topics.id"), nullable=True, index=True)

    accuracy = db.Column(db.Float, nullable=False, default=0.0)
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    incorrect_count = db.Column(db.Integer, nullable=False, default=0)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    errors_count = db.Column(db.Integer, nullable=False, default=0)
    elapsed_seconds = db.Column(db.Integer, nullable=False, default=0)
    reading_speed_wpm = db.Column(db.Float, nullable=False, default=0.0)
    progress_percent = db.Column(db.Integer, nullable=False, default=100)

    answers_json = db.Column(db.Text, nullable=True)
    checked_rows_json = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = db.relationship("User", lazy="joined")
    course = db.relationship("Course", lazy="joined")
    passage = db.relationship("ReadingPassage", lazy="joined")
    topic = db.relationship("ReadingTopic", lazy="joined")
