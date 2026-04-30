from __future__ import annotations

from datetime import datetime
import json

from ..extensions import db


class InterviewTurn(db.Model):
    __tablename__ = 'interview_turns'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), nullable=False, index=True)
    turn_no = db.Column(db.Integer, nullable=False, index=True)
    question_type = db.Column(db.String(40), nullable=False, default='general')
    ai_question_text = db.Column(db.Text, nullable=False)
    ai_question_audio_path = db.Column(db.String(255), nullable=True)
    student_answer_text = db.Column(db.Text, nullable=True)
    student_audio_path = db.Column(db.String(255), nullable=True)
    live_transcript = db.Column(db.Text, nullable=True)
    response_started_at = db.Column(db.DateTime, nullable=True)
    response_ended_at = db.Column(db.DateTime, nullable=True)
    response_duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    pause_count = db.Column(db.Integer, nullable=False, default=0)
    long_pause_detected = db.Column(db.Boolean, nullable=False, default=False)
    nudge_count = db.Column(db.Integer, nullable=False, default=0)
    ai_nudge_text = db.Column(db.Text, nullable=True)
    ai_followup_text = db.Column(db.Text, nullable=True)
    grammar_score = db.Column(db.Float, nullable=True)
    fluency_score = db.Column(db.Float, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    relevance_score = db.Column(db.Float, nullable=True)
    vocabulary_score = db.Column(db.Float, nullable=True)
    professional_tone_score = db.Column(db.Float, nullable=True)
    clarity_score = db.Column(db.Float, nullable=True)
    turn_score = db.Column(db.Float, nullable=True)
    turn_feedback = db.Column(db.Text, nullable=True)
    improved_answer = db.Column(db.Text, nullable=True)
    metrics_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship('InterviewSession', back_populates='turns', lazy='joined')

    @property
    def metrics(self) -> dict:
        raw = (self.metrics_json or '').strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @property
    def is_answered(self) -> bool:
        return bool((self.student_answer_text or '').strip())

    def __repr__(self) -> str:
        return f'<InterviewTurn session={self.session_id} turn={self.turn_no}>'
