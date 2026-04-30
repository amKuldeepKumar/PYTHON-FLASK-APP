from __future__ import annotations

from datetime import datetime

from ..extensions import db


class RewardPolicy(db.Model):
    __tablename__ = "reward_policies"
    __table_args__ = (
        db.UniqueConstraint("difficulty_band", name="uq_reward_policies_difficulty_band"),
    )

    id = db.Column(db.Integer, primary_key=True)
    difficulty_band = db.Column(db.String(20), nullable=False, index=True)
    label = db.Column(db.String(40), nullable=False)

    speaking_base = db.Column(db.Integer, nullable=False, default=8)
    speaking_relevance_bonus = db.Column(db.Integer, nullable=False, default=2)
    speaking_progress_bonus = db.Column(db.Integer, nullable=False, default=2)
    speaking_good_bonus = db.Column(db.Integer, nullable=False, default=4)
    speaking_strong_bonus = db.Column(db.Integer, nullable=False, default=6)
    speaking_full_length_bonus = db.Column(db.Integer, nullable=False, default=2)
    speaking_first_try_bonus = db.Column(db.Integer, nullable=False, default=2)

    lesson_base = db.Column(db.Integer, nullable=False, default=20)
    lesson_accuracy_mid_bonus = db.Column(db.Integer, nullable=False, default=3)
    lesson_accuracy_high_bonus = db.Column(db.Integer, nullable=False, default=6)

    boss_suggested_reward = db.Column(db.Integer, nullable=False, default=40)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
