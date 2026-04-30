from datetime import datetime

from ..extensions import db


class ReadingPromptConfig(db.Model):
    __tablename__ = "reading_prompt_configs"

    TASK_PASSAGE = "passage"
    TASK_QUESTION = "question"
    TASK_TRANSLATION = "translation"
    TASK_EVALUATION = "evaluation"

    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(30), nullable=False, unique=True, index=True)
    title = db.Column(db.String(120), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
