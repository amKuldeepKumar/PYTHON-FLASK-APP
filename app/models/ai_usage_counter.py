from __future__ import annotations

from datetime import date, datetime

from ..extensions import db


class AIUsageCounter(db.Model):
    __tablename__ = "ai_usage_counters"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    usage_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    request_count = db.Column(db.Integer, nullable=False, default=0)
    token_count = db.Column(db.Integer, nullable=False, default=0)
    translation_count = db.Column(db.Integer, nullable=False, default=0)
    speech_seconds = db.Column(db.Integer, nullable=False, default=0)
    tts_characters = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("actor_user_id", "usage_date", name="uq_ai_usage_counters_user_day"),
    )
