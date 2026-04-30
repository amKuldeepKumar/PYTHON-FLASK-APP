from __future__ import annotations

from datetime import datetime

from ..extensions import db


class SpeakingPrompt(db.Model):
    __tablename__ = "speaking_prompts"

    id = db.Column(db.Integer, primary_key=True)
    owner_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("speaking_topics.id"), nullable=False, index=True)

    title = db.Column(db.String(140), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    instruction_text = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(30), nullable=False, default="basic", index=True)
    estimated_seconds = db.Column(db.Integer, nullable=False, default=60)
    target_duration_seconds = db.Column(db.Integer, nullable=True)
    min_duration_seconds = db.Column(db.Integer, nullable=True)
    max_duration_seconds = db.Column(db.Integer, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    prompt_kind = db.Column(db.String(30), nullable=False, default="general", index=True)
    interview_question_type = db.Column(db.String(60), nullable=True, index=True)
    answer_tips_text = db.Column(db.Text, nullable=True)
    sample_answer_text = db.Column(db.Text, nullable=True)
    followup_prompt_text = db.Column(db.Text, nullable=True)
    target_keywords_text = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    topic = db.relationship("SpeakingTopic", back_populates="prompts", lazy="joined")
    sessions = db.relationship("SpeakingSession", back_populates="prompt", lazy="dynamic")



    @property
    def effective_target_duration(self) -> int:
        value = int(self.target_duration_seconds or self.estimated_seconds or 60)
        return max(15, value)

    @property
    def effective_min_duration(self) -> int:
        raw = self.min_duration_seconds
        if raw is None:
            raw = max(10, int(round(self.effective_target_duration * 0.5)))
        return max(5, min(int(raw), self.effective_max_duration))

    @property
    def effective_max_duration(self) -> int:
        raw = self.max_duration_seconds
        if raw is None:
            raw = max(self.effective_target_duration, int(round(self.effective_target_duration * 1.5)))
        return max(self.effective_target_duration, int(raw))

    def __repr__(self) -> str:
        return f"<SpeakingPrompt {self.id}:{self.title}>"

    @property
    def is_interview_prompt(self) -> bool:
        return (self.prompt_kind or '').strip().lower() == 'interview' or bool(getattr(self.topic, 'is_interview_topic', False))

    @property
    def target_keywords_list(self) -> list[str]:
        raw = (self.target_keywords_text or '').replace('\n', ',')
        return [item.strip() for item in raw.split(',') if item.strip()]
