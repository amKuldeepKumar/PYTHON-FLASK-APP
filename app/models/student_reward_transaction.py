from __future__ import annotations

from datetime import datetime

from ..extensions import db


class StudentRewardTransaction(db.Model):
    __tablename__ = "student_reward_transactions"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    speaking_session_id = db.Column(db.Integer, db.ForeignKey("speaking_sessions.id"), nullable=True, index=True)
    source_type = db.Column(db.String(40), nullable=False, default="speaking_completion", index=True)
    coins = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String(120), nullable=False, default="Speaking reward")
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("User", backref=db.backref("reward_transactions", lazy="dynamic", cascade="all, delete-orphan"), lazy="joined")
    speaking_session = db.relationship("SpeakingSession", lazy="joined")

    def __repr__(self) -> str:
        return f"<StudentRewardTransaction {self.id} student={self.student_id} coins={self.coins}>"
