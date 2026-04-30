from datetime import datetime

from ..extensions import db


class TranslationProvider(db.Model):
    __tablename__ = "translation_providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, default="Primary Translation Provider")
    provider_type = db.Column(db.String(40), nullable=False, default="mock")
    api_key = db.Column(db.Text, nullable=True)
    api_base_url = db.Column(db.String(255), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_default = db.Column(db.Boolean, nullable=False, default=True, index=True)
    fallback_provider_id = db.Column(db.Integer, db.ForeignKey("translation_providers.id"), nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=100, index=True)
    timeout_seconds = db.Column(db.Integer, nullable=False, default=30)
    requests_per_minute = db.Column(db.Integer, nullable=True)
    tokens_per_minute = db.Column(db.Integer, nullable=True)
    supports_live_credit_check = db.Column(db.Boolean, nullable=False, default=False)
    source_language_code = db.Column(db.String(16), nullable=False, default="en")
    credits_remaining = db.Column(db.Float, nullable=True)
    credit_unit = db.Column(db.String(30), nullable=False, default="credits")
    per_request_cost = db.Column(db.Float, nullable=False, default=1.0)
    cost_per_1k_input = db.Column(db.Float, nullable=False, default=0.0)
    cost_per_1k_output = db.Column(db.Float, nullable=False, default=0.0)
    total_requests = db.Column(db.Integer, nullable=False, default=0)
    total_failures = db.Column(db.Integer, nullable=False, default=0)
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    circuit_state = db.Column(db.String(20), nullable=False, default="closed")
    circuit_open_until = db.Column(db.DateTime, nullable=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    last_failure_at = db.Column(db.DateTime, nullable=True)
    last_credit_sync_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    fallback_provider = db.relationship("TranslationProvider", remote_side=[id], uselist=False)

    @classmethod
    def primary(cls):
        row = cls.query.order_by(cls.is_default.desc(), cls.priority.asc(), cls.id.asc()).first()
        if row:
            return row
        row = cls()
        db.session.add(row)
        db.session.commit()
        return row

    @property
    def provider_label(self) -> str:
        if self.provider_type == "openai_compatible":
            return "OpenAI Compatible"
        if self.provider_type == "mock":
            return "Mock / Manual"
        return (self.provider_type or "Unknown").replace("_", " ").title()

    def consume_credit(self, amount: float | None = None) -> None:
        if self.credits_remaining is None:
            return
        cost = float(amount if amount is not None else (self.per_request_cost or 0))
        self.credits_remaining = max(0.0, float(self.credits_remaining or 0) - cost)
        self.last_credit_sync_at = datetime.utcnow()
