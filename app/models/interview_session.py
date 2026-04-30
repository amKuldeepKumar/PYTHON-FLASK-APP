from __future__ import annotations

from datetime import datetime
import json

from ..extensions import db


class InterviewSession(db.Model):
    __tablename__ = 'interview_sessions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('interview_profiles.id'), nullable=False, index=True)

    status = db.Column(db.String(30), nullable=False, default='active', index=True)
    session_mode = db.Column(db.String(40), nullable=False, default='mock_interview')
    ai_persona = db.Column(db.String(60), nullable=False, default='recruiter')
    question_plan_json = db.Column(db.Text, nullable=True)
    current_turn_no = db.Column(db.Integer, nullable=False, default=1)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    total_duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    total_pause_count = db.Column(db.Integer, nullable=False, default=0)
    long_pause_count = db.Column(db.Integer, nullable=False, default=0)
    avg_response_latency = db.Column(db.Float, nullable=False, default=0)
    completion_percent = db.Column(db.Float, nullable=False, default=0)
    final_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course = db.relationship(
        'Course',
        lazy='joined',
        overlaps="interview_sessions"
    )
    profile = db.relationship('InterviewProfile', back_populates='sessions', lazy='joined')
    turns = db.relationship(
        'InterviewTurn',
        back_populates='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='InterviewTurn.turn_no.asc()',
    )
    feedback_rows = db.relationship(
        'InterviewFeedback',
        back_populates='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='desc(InterviewFeedback.created_at)',
    )

    @property
    def question_plan(self) -> list[dict]:
        raw = (self.question_plan_json or '').strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @property
    def latest_feedback(self):
        return self.feedback_rows.first()

    @property
    def is_completed(self) -> bool:
        return (self.status or '').lower() == 'completed'

    def __repr__(self) -> str:
        return f'<InterviewSession {self.id} student={self.student_id} status={self.status}>'
