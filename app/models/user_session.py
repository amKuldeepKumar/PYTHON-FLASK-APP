from __future__ import annotations

from datetime import datetime

from ..extensions import db


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    session_key_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    device_hash = db.Column(db.String(128), nullable=True, index=True)
    ip_address = db.Column(db.String(64), nullable=True)
    browser = db.Column(db.String(120), nullable=True)
    os_name = db.Column(db.String(120), nullable=True)
    device_type = db.Column(db.String(40), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    country = db.Column(db.String(80), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    is_current = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship("User", backref=db.backref("session_rows", lazy="dynamic", cascade="all, delete-orphan"))

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @property
    def browser_display(self) -> str:
        browser = (self.browser or "").strip()
        os_name = (self.os_name or "").strip()
        if browser and os_name:
            return f"{browser} • {os_name}"
        return browser or os_name or "Unknown"

    @property
    def location_display(self) -> str:
        city = (self.city or "").strip()
        country = (self.country or "").strip()
        if city and country:
            return f"{city}, {country}"
        return city or country or "Unknown"
