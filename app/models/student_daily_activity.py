from __future__ import annotations

from datetime import date, datetime

from ..extensions import db


class StudentDailyActivity(db.Model):
    __tablename__ = "student_daily_activity"
    __table_args__ = (
        db.UniqueConstraint("student_id", "activity_date", name="uq_student_daily_activity_student_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    activity_date = db.Column(db.Date, nullable=False, default=date.today, index=True)

    login_count = db.Column(db.Integer, nullable=False, default=0)
    first_login_at = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    questions_attempted = db.Column(db.Integer, nullable=False, default=0)
    questions_correct = db.Column(db.Integer, nullable=False, default=0)
    speaking_attempts = db.Column(db.Integer, nullable=False, default=0)
    lessons_completed = db.Column(db.Integer, nullable=False, default=0)
    practice_minutes = db.Column(db.Integer, nullable=False, default=0)
    speaking_completed_sessions = db.Column(db.Integer, nullable=False, default=0)
    coins_earned = db.Column(db.Integer, nullable=False, default=0)

    accuracy_total = db.Column(db.Float, nullable=False, default=0.0)
    accuracy_samples = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("User", back_populates="daily_activity_rows")

    @property
    def accuracy_percent(self) -> int:
        if not self.accuracy_samples:
            if not self.questions_attempted:
                return 0
            return int(round((self.questions_correct / max(1, self.questions_attempted)) * 100))
        return int(round((self.accuracy_total or 0.0) / max(1, self.accuracy_samples)))
