from __future__ import annotations

from datetime import datetime

from ..extensions import db


class SpeakingSession(db.Model):
    __tablename__ = 'speaking_sessions'

    STATUS_READY = 'ready'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    id = db.Column(db.Integer, primary_key=True)
    owner_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('speaking_topics.id'), nullable=False, index=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('speaking_prompts.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True, index=True)

    status = db.Column(db.String(30), nullable=False, default=STATUS_READY, index=True)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    submitted_from = db.Column(db.String(30), nullable=True, default='web')

    transcript_text = db.Column(db.Text, nullable=True)
    transcript_source = db.Column(db.String(30), nullable=True, default='manual')
    audio_file_path = db.Column(db.String(255), nullable=True)
    audio_original_name = db.Column(db.String(255), nullable=True)
    latest_word_count = db.Column(db.Integer, nullable=False, default=0)
    latest_char_count = db.Column(db.Integer, nullable=False, default=0)
    submit_count = db.Column(db.Integer, nullable=False, default=0)
    result_summary = db.Column(db.Text, nullable=True)
    last_submitted_at = db.Column(db.DateTime, nullable=True)

    evaluation_score = db.Column(db.Float, nullable=True)
    relevance_score = db.Column(db.Float, nullable=True)
    is_relevant = db.Column(db.Boolean, nullable=False, default=False)
    feedback_text = db.Column(db.Text, nullable=True)
    evaluation_json = db.Column(db.Text, nullable=True)
    recommended_next_step = db.Column(db.String(30), nullable=True, default='practice_more')
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    max_retry_count = db.Column(db.Integer, nullable=False, default=2)

    completion_tracked = db.Column(db.Boolean, nullable=False, default=False)
    coins_awarded = db.Column(db.Integer, nullable=False, default=0)
    is_fast_submit_flagged = db.Column(db.Boolean, nullable=False, default=False)
    fast_submit_reason = db.Column(db.String(255), nullable=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    topic = db.relationship('SpeakingTopic', back_populates='sessions', lazy='joined')
    course = db.relationship('Course', back_populates='speaking_sessions', lazy='joined')
    prompt = db.relationship('SpeakingPrompt', back_populates='sessions', lazy='joined')
    attempts = db.relationship(
        'SpeakingAttempt',
        back_populates='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='desc(SpeakingAttempt.created_at)',
    )

    @property
    def is_completed(self) -> bool:
        return (self.status or '').lower() == self.STATUS_COMPLETED

    @property
    def has_audio(self) -> bool:
        return bool((self.audio_file_path or '').strip())

    @property
    def transcript_preview(self) -> str:
        text = (self.transcript_text or '').strip()
        if not text:
            return ''
        return text if len(text) <= 180 else f'{text[:177]}...'

    @property
    def retries_left(self) -> int:
        return max(0, int(self.max_retry_count or 0) - int(self.retry_count or 0))

    @property
    def can_retry(self) -> bool:
        return self.retries_left > 0 and (self.recommended_next_step or '') == 'retry'

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
        return f'<SpeakingSession {self.id} student={self.student_id} status={self.status}>'
