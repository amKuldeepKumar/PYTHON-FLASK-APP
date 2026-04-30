from __future__ import annotations

from datetime import datetime

from app import db


class WhatsAppInquiryLog(db.Model):
    """Public WhatsApp button click log for SuperAdmin review."""

    __tablename__ = "whatsapp_inquiry_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    source_path = db.Column(db.String(500), default="")
    referer = db.Column(db.String(500), default="")
    ip_address = db.Column(db.String(80), default="")
    user_agent = db.Column(db.String(500), default="")
    category = db.Column(db.String(120), default="Course inquiry")
    number_snapshot = db.Column(db.String(40), default="")
    message_snapshot = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="clicked")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", lazy="joined")
