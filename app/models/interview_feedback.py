from __future__ import annotations

from datetime import datetime
import json

from ..extensions import db


class InterviewFeedback(db.Model):
    __tablename__ = 'interview_feedback'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), nullable=False, index=True)
    overall_score = db.Column(db.Float, nullable=False, default=0)
    fluency_score = db.Column(db.Float, nullable=False, default=0)
    grammar_score = db.Column(db.Float, nullable=False, default=0)
    confidence_score = db.Column(db.Float, nullable=False, default=0)
    relevance_score = db.Column(db.Float, nullable=False, default=0)
    professional_tone_score = db.Column(db.Float, nullable=False, default=0)
    vocabulary_score = db.Column(db.Float, nullable=False, default=0)
    hesitation_score = db.Column(db.Float, nullable=False, default=0)
    role_fit_score = db.Column(db.Float, nullable=False, default=0)
    strengths_json = db.Column(db.Text, nullable=True)
    weaknesses_json = db.Column(db.Text, nullable=True)
    recommended_practice_json = db.Column(db.Text, nullable=True)
    best_answer_turn_id = db.Column(db.Integer, nullable=True)
    weakest_answer_turn_id = db.Column(db.Integer, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    coach_tips = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship('InterviewSession', back_populates='feedback_rows', lazy='joined')

    def _load_json_list(self, raw: str | None) -> list[str]:
        text = (raw or '').strip()
        if not text:
            return []
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @property
    def strengths(self) -> list[str]:
        return self._load_json_list(self.strengths_json)

    @property
    def weaknesses(self) -> list[str]:
        return self._load_json_list(self.weaknesses_json)

    @property
    def recommended_practice(self) -> list[str]:
        return self._load_json_list(self.recommended_practice_json)
