from datetime import datetime
from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(20), nullable=False, default="info")
    category = db.Column(db.String(32), nullable=False, default="system")
    link_path = db.Column(db.String(255), nullable=False, default="")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def has_internal_link(self) -> bool:
        return bool(self.link_path and self.link_path.startswith("/"))
