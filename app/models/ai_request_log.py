from __future__ import annotations

from datetime import datetime

from ..extensions import db


class AIRequestLog(db.Model):
    __tablename__ = "ai_request_logs"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(64), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    course_id = db.Column(db.Integer, nullable=True, index=True)
    lesson_id = db.Column(db.Integer, nullable=True, index=True)
    task_key = db.Column(db.String(64), nullable=False, index=True)
    provider_source = db.Column(db.String(32), nullable=True, index=True)
    provider_id = db.Column(db.Integer, nullable=True, index=True)
    provider_name = db.Column(db.String(120), nullable=True)
    provider_type = db.Column(db.String(64), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_hash = db.Column(db.String(64), nullable=True)
    response_hash = db.Column(db.String(64), nullable=True)
    redacted_prompt = db.Column(db.Text, nullable=True)
    redacted_response = db.Column(db.Text, nullable=True)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    estimated_cost = db.Column(db.Numeric(12, 6), nullable=True)
    cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    fallback_used = db.Column(db.Boolean, nullable=False, default=False)
    circuit_state = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="success", index=True)
    error_code = db.Column(db.String(80), nullable=True)
    error_message = db.Column(db.String(255), nullable=True)
    consent_snapshot = db.Column(db.Boolean, nullable=False, default=False)
    exportable_for_ml = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

