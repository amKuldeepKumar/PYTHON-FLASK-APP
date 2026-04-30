from __future__ import annotations

from datetime import datetime

from ..extensions import db


class DevicePreference(db.Model):
    __tablename__ = "device_preferences"

    id = db.Column(db.Integer, primary_key=True)
    device_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    ui_language_code = db.Column(db.String(20), nullable=False, default="en")
    learning_language_code = db.Column(db.String(20), nullable=False, default="en")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("device_preferences", lazy="dynamic"))
