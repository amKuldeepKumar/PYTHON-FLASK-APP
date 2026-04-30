from __future__ import annotations

from datetime import datetime

from ..extensions import db


class LoginEvent(db.Model):
    __tablename__ = "login_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    success = db.Column(db.Boolean, nullable=False, default=True, index=True)

    ip_address = db.Column(db.String(64), nullable=True)
    device_hash = db.Column(db.String(128), nullable=True, index=True)
    device_type = db.Column(db.String(40), nullable=True)
    browser = db.Column(db.String(120), nullable=True)
    os_name = db.Column(db.String(120), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    country = db.Column(db.String(80), nullable=True)
    city = db.Column(db.String(80), nullable=True)

    reason = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="login_events")

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