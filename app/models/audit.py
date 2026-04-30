"""Phase 2: Audit log.

Stores immutable audit events for admin/staff actions.
"""

from datetime import datetime
from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    actor_role = db.Column(db.String(30), nullable=True)

    action = db.Column(db.String(80), nullable=False, index=True)
    target = db.Column(db.String(120), nullable=True)
    meta = db.Column(db.Text, nullable=True)

    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    prev_hash = db.Column(db.String(64), nullable=True, index=True)
    event_hash = db.Column(db.String(64), nullable=True, unique=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
