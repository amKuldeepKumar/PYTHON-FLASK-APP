from datetime import datetime
from ..extensions import db


class SecurityPolicy(db.Model):
    __tablename__ = "security_policies"

    id = db.Column(db.Integer, primary_key=True)

    # OFF by default while working offline
    otp_mode = db.Column(db.String(16), nullable=False, default="OFF")
    otp_mode_admin = db.Column(db.String(16), nullable=True)
    otp_mode_student = db.Column(db.String(16), nullable=True)
    otp_mode_staff = db.Column(db.String(16), nullable=True)

    otp_ttl_minutes = db.Column(db.Integer, nullable=False, default=10)
    otp_max_sends_per_hour = db.Column(db.Integer, nullable=False, default=5)
    otp_max_verify_attempts = db.Column(db.Integer, nullable=False, default=5)

    failed_login_threshold = db.Column(db.Integer, nullable=False, default=5)
    lockout_minutes = db.Column(db.Integer, nullable=False, default=15)

    suspicious_window_days = db.Column(db.Integer, nullable=False, default=45)
    trust_device_days = db.Column(db.Integer, nullable=False, default=45)

    api_rate_limit = db.Column(db.String(64), nullable=False, default="30 per minute")
    ai_rate_limit = db.Column(db.String(64), nullable=False, default="10 per minute")
    ai_daily_request_limit = db.Column(db.Integer, nullable=False, default=200)
    ai_daily_token_limit = db.Column(db.Integer, nullable=False, default=200000)
    translation_daily_limit = db.Column(db.Integer, nullable=False, default=100)
    tts_daily_character_limit = db.Column(db.Integer, nullable=False, default=50000)
    speech_daily_seconds_limit = db.Column(db.Integer, nullable=False, default=3600)
    ai_circuit_breaker_threshold = db.Column(db.Integer, nullable=False, default=3)
    ai_circuit_breaker_minutes = db.Column(db.Integer, nullable=False, default=10)
    translation_cache_ttl_seconds = db.Column(db.Integer, nullable=False, default=2592000)

    max_upload_mb = db.Column(db.Integer, nullable=False, default=5)
    allowed_upload_extensions = db.Column(db.String(255), nullable=False, default="jpg,jpeg,png,webp,pdf")

    csp_report_only = db.Column(db.Boolean, nullable=False, default=False)
    csp_report_uri = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def singleton(cls):
        row = cls.query.first()
        if row:
            return row
        row = cls()
        db.session.add(row)
        db.session.commit()
        return row
