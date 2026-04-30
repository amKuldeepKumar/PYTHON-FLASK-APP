from datetime import datetime
from ..extensions import db

class AdminPermissionOverride(db.Model):
    __tablename__ = "admin_permission_overrides"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False, index=True)

    # If True -> explicitly allowed; if False -> explicitly denied
    allowed = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_id", name="uq_admin_perm_override"),
    )
