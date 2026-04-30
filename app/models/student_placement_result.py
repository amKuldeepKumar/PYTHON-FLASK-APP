from __future__ import annotations

import json
from datetime import datetime

from ..extensions import db


class StudentPlacementResult(db.Model):
    __tablename__ = "student_placement_results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    version = db.Column(db.String(32), nullable=False, default="phase-b-v1")
    target_language = db.Column(db.String(32), nullable=False, default="english")
    goal = db.Column(db.String(64), nullable=True)
    focus_skill = db.Column(db.String(32), nullable=True)
    comfort_level = db.Column(db.String(32), nullable=True)

    overall_score = db.Column(db.Integer, nullable=False, default=0)
    grammar_score = db.Column(db.Integer, nullable=False, default=0)
    vocabulary_score = db.Column(db.Integer, nullable=False, default=0)
    reading_score = db.Column(db.Integer, nullable=False, default=0)
    writing_score = db.Column(db.Integer, nullable=False, default=0)
    speaking_score = db.Column(db.Integer, nullable=False, default=0)
    listening_score = db.Column(db.Integer, nullable=False, default=0)
    confidence_score = db.Column(db.Integer, nullable=False, default=0)
    mcq_score = db.Column(db.Integer, nullable=False, default=0)
    mcq_total = db.Column(db.Integer, nullable=False, default=0)

    level = db.Column(db.String(32), nullable=False, default="basic")
    recommended_level = db.Column(db.String(32), nullable=False, default="basic")
    recommended_tracks_json = db.Column(db.Text, nullable=True)
    recommended_titles_json = db.Column(db.Text, nullable=True)
    recommended_keywords_json = db.Column(db.Text, nullable=True)
    strengths_json = db.Column(db.Text, nullable=True)
    weak_areas_json = db.Column(db.Text, nullable=True)
    next_steps_json = db.Column(db.Text, nullable=True)
    learning_path_json = db.Column(db.Text, nullable=True)
    answers_json = db.Column(db.Text, nullable=True)
    profile_answers_json = db.Column(db.Text, nullable=True)
    skill_scores_json = db.Column(db.Text, nullable=True)

    summary = db.Column(db.Text, nullable=True)
    fit_summary = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("User", backref=db.backref("placement_results", lazy="dynamic"))

    @staticmethod
    def _load_json(raw: str | None, fallback):
        text = (raw or "").strip()
        if not text:
            return fallback
        try:
            return json.loads(text)
        except Exception:
            return fallback

    @staticmethod
    def _dump_json(value) -> str | None:
        if value in (None, "", [], {}, ()):  # pragma: no cover - simple guard
            return None
        try:
            return json.dumps(value)
        except Exception:
            return None

    @property
    def recommended_tracks(self) -> list[str]:
        data = self._load_json(self.recommended_tracks_json, [])
        return [str(item).strip() for item in data if str(item).strip()]

    @recommended_tracks.setter
    def recommended_tracks(self, value):
        self.recommended_tracks_json = self._dump_json(list(value or []))

    @property
    def recommended_titles(self) -> list[str]:
        data = self._load_json(self.recommended_titles_json, [])
        return [str(item).strip() for item in data if str(item).strip()]

    @recommended_titles.setter
    def recommended_titles(self, value):
        self.recommended_titles_json = self._dump_json(list(value or []))

    @property
    def recommended_keywords(self) -> list[str]:
        data = self._load_json(self.recommended_keywords_json, [])
        return [str(item).strip() for item in data if str(item).strip()]

    @recommended_keywords.setter
    def recommended_keywords(self, value):
        self.recommended_keywords_json = self._dump_json(list(value or []))

    @property
    def strengths(self) -> list[dict]:
        data = self._load_json(self.strengths_json, [])
        return data if isinstance(data, list) else []

    @strengths.setter
    def strengths(self, value):
        self.strengths_json = self._dump_json(list(value or []))

    @property
    def weak_areas(self) -> list[dict]:
        data = self._load_json(self.weak_areas_json, [])
        return data if isinstance(data, list) else []

    @weak_areas.setter
    def weak_areas(self, value):
        self.weak_areas_json = self._dump_json(list(value or []))

    @property
    def next_steps(self) -> list[str]:
        data = self._load_json(self.next_steps_json, [])
        return [str(item).strip() for item in data if str(item).strip()]

    @next_steps.setter
    def next_steps(self, value):
        self.next_steps_json = self._dump_json(list(value or []))

    @property
    def learning_path(self) -> list[dict]:
        data = self._load_json(self.learning_path_json, [])
        return data if isinstance(data, list) else []

    @learning_path.setter
    def learning_path(self, value):
        self.learning_path_json = self._dump_json(list(value or []))

    @property
    def answers(self) -> list[dict]:
        data = self._load_json(self.answers_json, [])
        return data if isinstance(data, list) else []

    @answers.setter
    def answers(self, value):
        self.answers_json = self._dump_json(list(value or []))

    @property
    def profile_answers(self) -> dict:
        data = self._load_json(self.profile_answers_json, {})
        return data if isinstance(data, dict) else {}

    @profile_answers.setter
    def profile_answers(self, value):
        self.profile_answers_json = self._dump_json(dict(value or {}))

    @property
    def skill_scores(self) -> dict:
        data = self._load_json(self.skill_scores_json, {})
        return data if isinstance(data, dict) else {}

    @skill_scores.setter
    def skill_scores(self, value):
        self.skill_scores_json = self._dump_json(dict(value or {}))

    def to_payload(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "target_language": self.target_language,
            "goal": self.goal,
            "focus_skill": self.focus_skill,
            "comfort_level": self.comfort_level,
            "overall_score": int(self.overall_score or 0),
            "grammar_score": int(self.grammar_score or 0),
            "vocabulary_score": int(self.vocabulary_score or 0),
            "reading_score": int(self.reading_score or 0),
            "writing_score": int(self.writing_score or 0),
            "speaking_score": int(self.speaking_score or 0),
            "listening_score": int(self.listening_score or 0),
            "confidence_score": int(self.confidence_score or 0),
            "mcq_score": int(self.mcq_score or 0),
            "mcq_total": int(self.mcq_total or 0),
            "level": self.level,
            "recommended_level": self.recommended_level,
            "recommended_tracks": self.recommended_tracks,
            "recommended_titles": self.recommended_titles,
            "recommended_keywords": self.recommended_keywords,
            "strengths": self.strengths,
            "weak_areas": self.weak_areas,
            "next_steps": self.next_steps,
            "learning_path": self.learning_path,
            "answers": self.answers,
            "profile_answers": self.profile_answers,
            "skill_scores": self.skill_scores,
            "summary": self.summary,
            "fit_summary": self.fit_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
