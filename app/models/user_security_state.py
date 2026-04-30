from datetime import datetime
from ..extensions import db


class UserSecurityState(db.Model):
    __tablename__ = "user_security_states"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True, index=True)
    last_failed_at = db.Column(db.DateTime, nullable=True)
    last_ip = db.Column(db.String(64), nullable=True)
    last_device_hash = db.Column(db.String(128), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
