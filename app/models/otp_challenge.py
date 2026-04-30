from datetime import datetime
from ..extensions import db


class OtpChallenge(db.Model):
    __tablename__ = "otp_challenges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(32), nullable=False, default="RISK")
    sent_to = db.Column(db.String(255), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    device_hash = db.Column(db.String(128), nullable=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempts_left = db.Column(db.Integer, nullable=False, default=5)
    send_count = db.Column(db.Integer, nullable=False, default=1)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
