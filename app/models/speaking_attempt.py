from __future__ import annotations

from datetime import datetime

from ..extensions import db


class SpeakingAttempt(db.Model):
    __tablename__ = 'speaking_attempts'

    id = db.Column(db.Integer, primary_key=True)
    owner_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey('speaking_sessions.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('speaking_topics.id'), nullable=False, index=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('speaking_prompts.id'), nullable=False, index=True)

    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)

    audio_file_path = db.Column(db.String(255), nullable=True)
    audio_original_name = db.Column(db.String(255), nullable=True)
    audio_mime_type = db.Column(db.String(120), nullable=True)
    audio_file_size_bytes = db.Column(db.Integer, nullable=False, default=0)

    transcript_text = db.Column(db.Text, nullable=True)
    transcript_source = db.Column(db.String(30), nullable=True, default='manual')
    word_count = db.Column(db.Integer, nullable=False, default=0)
    char_count = db.Column(db.Integer, nullable=False, default=0)

    result_summary = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)
    relevance_score = db.Column(db.Float, nullable=True)
    is_relevant = db.Column(db.Boolean, nullable=False, default=False)
    feedback_text = db.Column(db.Text, nullable=True)
    evaluation_json = db.Column(db.Text, nullable=True)
    recommended_next_step = db.Column(db.String(30), nullable=True)
    retry_recommended = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship('SpeakingSession', back_populates='attempts', lazy='joined')
    topic = db.relationship('SpeakingTopic', lazy='joined')
    prompt = db.relationship('SpeakingPrompt', lazy='joined')

    @property
    def has_audio(self) -> bool:
        return bool((self.audio_file_path or '').strip())

    @property
    def evaluation_payload(self) -> dict:
        import json
        raw = (self.evaluation_json or '').strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f'<SpeakingAttempt {self.id} session={self.session_id} attempt={self.attempt_number}>'
