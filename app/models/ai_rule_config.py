from __future__ import annotations

from datetime import datetime

from ..extensions import db


class AIRuleConfig(db.Model):
    __tablename__ = 'ai_rule_configs'

    TRACK_SPEAKING = 'speaking'
    TRACK_WRITING = 'writing'
    TRACK_READING = 'reading'
    TRACK_LISTENING = 'listening'
    TRACK_CHOICES = [TRACK_SPEAKING, TRACK_WRITING, TRACK_READING, TRACK_LISTENING]

    id = db.Column(db.Integer, primary_key=True)
    track_key = db.Column(db.String(30), nullable=False, unique=True, index=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    rule_text = db.Column(db.Text, nullable=False, default='')
    guardrails_text = db.Column(db.Text, nullable=True)
    scoring_notes = db.Column(db.Text, nullable=True)
    output_format = db.Column(db.Text, nullable=True)
    strictness = db.Column(db.Integer, nullable=False, default=3)
    min_length = db.Column(db.Integer, nullable=False, default=0)
    require_explanations = db.Column(db.Boolean, nullable=False, default=True)
    off_topic_block = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    updated_by = db.relationship('User', lazy='joined')

    DEFAULTS = {
        TRACK_SPEAKING: {
            'rule_text': 'Evaluate only the spoken answer. Score pronunciation, fluency, grammar, sentence making, and relevance. Keep feedback learner-friendly.',
            'guardrails_text': 'Flag very short answers, repeated filler words, and clearly off-topic responses.',
            'scoring_notes': 'Explain the main mistake clearly and suggest the next retry action.',
            'output_format': 'Return strengths, mistakes, improvement tips, and a retry recommendation.',
            'strictness': 3,
            'min_length': 12,
            'require_explanations': True,
            'off_topic_block': True,
        },
        TRACK_WRITING: {
            'rule_text': 'Evaluate grammar, vocabulary, coherence, and task response. Respect task instructions and word-range guidance.',
            'guardrails_text': 'Penalize copied, extremely short, or clearly off-topic submissions.',
            'scoring_notes': 'Always explain why a line or sentence is weak and how to improve it.',
            'output_format': 'Return band-style scores, strengths, weaknesses, and line-level suggestions when possible.',
            'strictness': 3,
            'min_length': 40,
            'require_explanations': True,
            'off_topic_block': True,
        },
        TRACK_READING: {
            'rule_text': 'Check student answers against the question and expected answer. Prefer accuracy and simple explanations.',
            'guardrails_text': 'Avoid accepting unsupported answers. Keep explanations short and classroom-ready.',
            'scoring_notes': 'When the answer is wrong, explain the correct reason from the passage.',
            'output_format': 'Return correct or incorrect, score, and a short explanation.',
            'strictness': 2,
            'min_length': 0,
            'require_explanations': True,
            'off_topic_block': False,
        },
        TRACK_LISTENING: {
            'rule_text': 'Review listening content for clarity, answerability, caption quality, and lesson readiness.',
            'guardrails_text': 'Keep poor captions or unclear prompts in pending review.',
            'scoring_notes': 'Give one direct reason for approval, rejection, or pending.',
            'output_format': 'Return decision, confidence, and review reason.',
            'strictness': 3,
            'min_length': 0,
            'require_explanations': True,
            'off_topic_block': False,
        },
    }

    @classmethod
    def normalize_track(cls, value: str | None) -> str:
        normalized = (value or '').strip().lower()
        return normalized if normalized in cls.TRACK_CHOICES else cls.TRACK_SPEAKING

    @classmethod
    def ensure_defaults(cls) -> None:
        from ..extensions import db
        changed = False
        for track_key, payload in cls.DEFAULTS.items():
            row = cls.query.filter_by(track_key=track_key).first()
            if row:
                continue
            row = cls(track_key=track_key, **payload)
            db.session.add(row)
            changed = True
        if changed:
            db.session.commit()

    def to_prompt_block(self) -> str:
        if not self.is_enabled:
            return ''
        parts = [
            f"Track rules: {self.rule_text.strip()}" if (self.rule_text or '').strip() else '',
            f"Guardrails: {(self.guardrails_text or '').strip()}" if (self.guardrails_text or '').strip() else '',
            f"Scoring notes: {(self.scoring_notes or '').strip()}" if (self.scoring_notes or '').strip() else '',
            f"Output format: {(self.output_format or '').strip()}" if (self.output_format or '').strip() else '',
            f'Strictness: {int(self.strictness or 0)}/5',
            f'Minimum length: {int(self.min_length or 0)}',
            'Require explanations: yes' if self.require_explanations else 'Require explanations: no',
            'Block off-topic responses: yes' if self.off_topic_block else 'Block off-topic responses: no',
        ]
        return '\n'.join(part for part in parts if part).strip()
