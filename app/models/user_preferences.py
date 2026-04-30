from __future__ import annotations

from datetime import datetime

from ..extensions import db


class UserPreferences(db.Model):
    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    ui_language_code = db.Column(db.String(20), nullable=False, default="en")
    learning_language_code = db.Column(db.String(20), nullable=False, default="en")
    translation_support_language_code = db.Column(db.String(20), nullable=False, default="en")
    use_native_language_support = db.Column(db.Boolean, nullable=False, default=True)
    accent = db.Column(db.String(20), nullable=False, default="en-IN")

    dark_mode = db.Column(db.Boolean, nullable=False, default=True)
    email_notifications = db.Column(db.Boolean, nullable=False, default=True)
    browser_notifications = db.Column(db.Boolean, nullable=False, default=True)
    marketing_opt_in = db.Column(db.Boolean, nullable=False, default=False)

    autoplay_voice = db.Column(db.Boolean, nullable=False, default=True)
    auto_play_question = db.Column(db.Boolean, nullable=False, default=True)
    auto_start_listening = db.Column(db.Boolean, nullable=False, default=True)
    question_beep_enabled = db.Column(db.Boolean, nullable=False, default=True)
    playback_speed = db.Column(db.Float, nullable=False, default=1.0)
    speaking_speed = db.Column(db.Float, nullable=False, default=1.0)
    voice_pitch = db.Column(db.Float, nullable=False, default=1.0)

    voice_gender = db.Column(db.String(20), nullable=False, default='female')
    voice_name = db.Column(db.String(80), nullable=True)
    preferred_study_time = db.Column(db.String(40), nullable=True)
    welcome_voice_mode = db.Column(db.String(20), nullable=False, default="once")

    notify_email = db.Column(db.Boolean, nullable=False, default=True)
    notify_push = db.Column(db.Boolean, nullable=False, default=False)
    allow_ml_training = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="preferences")