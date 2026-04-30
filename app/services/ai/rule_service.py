from __future__ import annotations

from ...models.ai_rule_config import AIRuleConfig
from ...extensions import db


class AIRuleService:
    TASK_TO_TRACK = {
        'speaking_stt': AIRuleConfig.TRACK_SPEAKING,
        'speaking_evaluation': AIRuleConfig.TRACK_SPEAKING,
        'speaking_pronunciation': AIRuleConfig.TRACK_SPEAKING,
        'writing_evaluation': AIRuleConfig.TRACK_WRITING,
        'reading_passage': AIRuleConfig.TRACK_READING,
        'reading_question': AIRuleConfig.TRACK_READING,
        'reading_translation': AIRuleConfig.TRACK_READING,
        'reading_evaluation': AIRuleConfig.TRACK_READING,
        'listening_review': AIRuleConfig.TRACK_LISTENING,
    }

    TRACK_TO_TASKS = {
        AIRuleConfig.TRACK_SPEAKING: ['speaking_stt', 'speaking_pronunciation', 'speaking_evaluation'],
        AIRuleConfig.TRACK_WRITING: ['writing_evaluation'],
        AIRuleConfig.TRACK_READING: ['reading_passage', 'reading_question', 'reading_translation', 'reading_evaluation'],
        AIRuleConfig.TRACK_LISTENING: ['listening_review'],
    }

    @classmethod
    def ensure_defaults(cls) -> None:
        AIRuleConfig.ensure_defaults()

    @classmethod
    def track_for_task(cls, task_key: str) -> str | None:
        return cls.TASK_TO_TRACK.get((task_key or '').strip())

    @classmethod
    def get_rule(cls, track_key: str | None) -> AIRuleConfig | None:
        if not track_key:
            return None
        cls.ensure_defaults()
        return AIRuleConfig.query.filter_by(track_key=AIRuleConfig.normalize_track(track_key)).first()

    @classmethod
    def prompt_prefix_for_task(cls, task_key: str) -> str:
        track_key = cls.track_for_task(task_key)
        row = cls.get_rule(track_key)
        return row.to_prompt_block() if row else ''

    @classmethod
    def all_rules(cls) -> list[AIRuleConfig]:
        cls.ensure_defaults()
        rows = AIRuleConfig.query.order_by(AIRuleConfig.id.asc()).all()
        order = {key: idx for idx, key in enumerate(AIRuleConfig.TRACK_CHOICES)}
        return sorted(rows, key=lambda row: order.get(row.track_key, 99))


    @classmethod
    def tasks_for_track(cls, track_key: str | None) -> list[str]:
        normalized = AIRuleConfig.normalize_track(track_key)
        return list(cls.TRACK_TO_TASKS.get(normalized, []))

    @classmethod
    def as_metadata(cls, track_key: str | None) -> dict:
        row = cls.get_rule(track_key)
        if not row:
            return {
                'track_key': AIRuleConfig.normalize_track(track_key),
                'enabled': False,
                'strictness': 0,
                'min_length': 0,
                'require_explanations': False,
                'off_topic_block': False,
            }
        return {
            'track_key': row.track_key,
            'enabled': bool(row.is_enabled),
            'strictness': int(row.strictness or 0),
            'min_length': int(row.min_length or 0),
            'require_explanations': bool(row.require_explanations),
            'off_topic_block': bool(row.off_topic_block),
            'updated_at': row.updated_at.isoformat() if getattr(row, 'updated_at', None) else None,
        }

    @classmethod
    def apply_fallback_metadata(cls, output: dict | None, track_key: str | None, reason: str | None = None) -> dict:
        payload = dict(output or {})
        payload.setdefault('rule_track', AIRuleConfig.normalize_track(track_key))
        payload['rule_metadata'] = cls.as_metadata(track_key)
        if reason:
            payload['rule_fallback_reason'] = reason
        return payload

    @classmethod
    def update_rule(cls, *, track_key: str, form_data: dict, user_id: int | None = None) -> AIRuleConfig:
        cls.ensure_defaults()
        normalized = AIRuleConfig.normalize_track(track_key)
        row = AIRuleConfig.query.filter_by(track_key=normalized).first()
        if not row:
            row = AIRuleConfig(track_key=normalized)
            db.session.add(row)
        row.is_enabled = bool(form_data.get('is_enabled'))
        row.rule_text = (form_data.get('rule_text') or '').strip()
        row.guardrails_text = (form_data.get('guardrails_text') or '').strip() or None
        row.scoring_notes = (form_data.get('scoring_notes') or '').strip() or None
        row.output_format = (form_data.get('output_format') or '').strip() or None
        row.strictness = max(1, min(5, int(form_data.get('strictness') or 3)))
        row.min_length = max(0, int(form_data.get('min_length') or 0))
        row.require_explanations = bool(form_data.get('require_explanations'))
        row.off_topic_block = bool(form_data.get('off_topic_block'))
        row.status = 'active' if row.is_enabled else 'draft'
        row.updated_by_user_id = user_id
        db.session.add(row)
        db.session.commit()
        return row

    @classmethod
    def guard_learning_scope(cls, text: str | None) -> tuple[bool, str | None]:
        raw = (text or '').strip().lower()
        if not raw:
            return True, None
        blocked = ['politics', 'election', 'crypto', 'stock tip', 'medical diagnosis', 'dating advice', 'adult content']
        if any(term in raw for term in blocked):
            return False, 'This tutor is limited to learning support and cannot answer that request.'
        return True, None
