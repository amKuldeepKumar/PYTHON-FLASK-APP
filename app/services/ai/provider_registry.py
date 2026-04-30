from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...models.translation_provider import TranslationProvider
from ...models.speaking_provider import SpeakingProvider
from ...models.reading_provider import ReadingProvider
from ..speaking.provider_registry_service import SpeakingProviderRegistryService
from ..reading.provider_registry_service import ReadingProviderRegistryService


@dataclass
class ProviderRow:
    source: str
    task_key: str
    name: str
    provider_type: str
    is_enabled: bool
    is_default: bool
    usage_scope: str | None
    provider_label: str
    kind_label: str
    model_name: str | None = None
    api_base_url: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'source': self.source,
            'task_key': self.task_key,
            'name': self.name,
            'provider_type': self.provider_type,
            'is_enabled': self.is_enabled,
            'is_default': self.is_default,
            'usage_scope': self.usage_scope,
            'provider_label': self.provider_label,
            'kind_label': self.kind_label,
            'model_name': self.model_name,
            'api_base_url': self.api_base_url,
            'notes': self.notes,
        }


class AICentralProviderRegistry:
    TASK_LABELS = {
        'translation': 'Translation',
        'speaking_stt': 'Speaking STT',
        'speaking_evaluation': 'Speaking Evaluation',
        'speaking_pronunciation': 'Speaking Pronunciation',
        'speaking_tts': 'Text to Speech',
        'reading_passage': 'Reading Passage Generation',
        'reading_question': 'Reading Question Generation',
        'reading_translation': 'Reading Word Support',
        'reading_evaluation': 'Reading Answer Evaluation',
        'writing_plagiarism': 'Plagiarism Detection',
        'writing_evaluation': 'Writing Evaluation',
        'listening_review': 'Listening Review',
    }

    @classmethod
    def ensure_defaults(cls) -> None:
        TranslationProvider.primary()
        SpeakingProviderRegistryService.ensure_defaults()
        ReadingProviderRegistryService.ensure_defaults()

    @classmethod
    def rows(cls) -> list[dict[str, Any]]:
        cls.ensure_defaults()
        rows: list[ProviderRow] = []

        translation = TranslationProvider.primary()
        rows.append(ProviderRow(
            source='translation',
            task_key='translation',
            name=translation.name,
            provider_type=translation.provider_type,
            is_enabled=bool(translation.is_enabled),
            is_default=True,
            usage_scope='runtime_translation',
            provider_label=translation.provider_label,
            kind_label='Translation',
            model_name=translation.model_name,
            api_base_url=translation.api_base_url,
            notes=translation.last_error,
        ))

        for provider in SpeakingProvider.query.order_by(SpeakingProvider.provider_kind.asc(), SpeakingProvider.is_default.desc(), SpeakingProvider.id.asc()).all():
            task_key = {
                SpeakingProvider.KIND_STT: 'speaking_stt',
                SpeakingProvider.KIND_EVALUATION: 'speaking_evaluation',
                SpeakingProvider.KIND_PRONUNCIATION: 'speaking_pronunciation',
                SpeakingProvider.KIND_TTS: 'speaking_tts',
            }.get(provider.provider_kind, f'speaking_{provider.provider_kind}')
            rows.append(ProviderRow(
                source='speaking',
                task_key=task_key,
                name=provider.name,
                provider_type=provider.provider_type,
                is_enabled=bool(provider.is_enabled),
                is_default=bool(provider.is_default),
                usage_scope=provider.usage_scope,
                provider_label=provider.provider_label,
                kind_label=provider.kind_label,
                model_name=provider.model_name,
                api_base_url=provider.api_base_url,
                notes=provider.last_test_message,
            ))

        for provider in ReadingProvider.query.order_by(ReadingProvider.provider_kind.asc(), ReadingProvider.is_default.desc(), ReadingProvider.id.asc()).all():
            task_key = {
                ReadingProvider.KIND_PASSAGE: 'reading_passage',
                ReadingProvider.KIND_QUESTION: 'reading_question',
                ReadingProvider.KIND_TRANSLATION: 'reading_translation',
                ReadingProvider.KIND_EVALUATION: 'reading_evaluation',
                ReadingProvider.KIND_PLAGIARISM: 'writing_plagiarism',
            }.get(provider.provider_kind, f'reading_{provider.provider_kind}')
            rows.append(ProviderRow(
                source='reading',
                task_key=task_key,
                name=provider.name,
                provider_type=provider.provider_type,
                is_enabled=bool(provider.is_enabled),
                is_default=bool(provider.is_default),
                usage_scope=provider.usage_scope,
                provider_label=provider.provider_label,
                kind_label=provider.kind_label,
                model_name=provider.model_name,
                api_base_url=provider.api_base_url,
                notes=provider.last_test_message,
            ))

        rows.append(ProviderRow(
            source='writing',
            task_key='writing_evaluation',
            name='Internal Writing Evaluation Engine',
            provider_type='internal_rules',
            is_enabled=True,
            is_default=True,
            usage_scope='writing_ai_feedback',
            provider_label='Internal Rules',
            kind_label='Writing Evaluation',
            notes='Central AI layer wraps the existing writing scoring heuristics.',
        ))
        rows.append(ProviderRow(
            source='listening',
            task_key='listening_review',
            name='Internal Listening Review Engine',
            provider_type='internal_rules',
            is_enabled=True,
            is_default=True,
            usage_scope='listening_admin_review',
            provider_label='Internal Rules',
            kind_label='Listening Review',
            notes='Central AI layer can standardize listening review decisions.',
        ))
        return [row.to_dict() for row in rows]

    @classmethod
    def grouped_rows(cls) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in cls.rows():
            task_key = row['task_key']
            group = grouped.setdefault(task_key, {
                'task_key': task_key,
                'task_label': cls.TASK_LABELS.get(task_key, task_key.replace('_', ' ').title()),
                'rows': [],
            })
            group['rows'].append(row)
        return [grouped[key] for key in sorted(grouped.keys())]

    @classmethod
    def default_provider_meta(cls, task_key: str) -> dict[str, Any]:
        cls.ensure_defaults()
        if task_key == 'translation':
            provider = TranslationProvider.primary()
            return {
                'id': provider.id,
                'name': provider.name,
                'kind': 'translation',
                'type': provider.provider_type,
                'source': 'translation',
            }
        if task_key.startswith('speaking_'):
            kind = {
                'speaking_stt': SpeakingProvider.KIND_STT,
                'speaking_evaluation': SpeakingProvider.KIND_EVALUATION,
                'speaking_pronunciation': SpeakingProvider.KIND_PRONUNCIATION,
                'speaking_tts': SpeakingProvider.KIND_TTS,
            }.get(task_key)
            provider = SpeakingProvider.query.filter_by(provider_kind=kind, is_default=True).first() if kind else None
            if provider:
                return {'id': provider.id, 'name': provider.name, 'kind': kind, 'type': provider.provider_type, 'source': 'speaking'}
        if task_key.startswith('reading_'):
            kind = {
                'reading_passage': ReadingProvider.KIND_PASSAGE,
                'reading_question': ReadingProvider.KIND_QUESTION,
                'reading_translation': ReadingProvider.KIND_TRANSLATION,
                'reading_evaluation': ReadingProvider.KIND_EVALUATION,
                'writing_plagiarism': ReadingProvider.KIND_PLAGIARISM,
            }.get(task_key)
            provider = ReadingProvider.query.filter_by(provider_kind=kind, is_default=True).first() if kind else None
            if provider:
                return {'id': provider.id, 'name': provider.name, 'kind': kind, 'type': provider.provider_type, 'source': 'reading'}
        if task_key == 'writing_evaluation':
            return {'id': 'internal-writing', 'name': 'Internal Writing Evaluation Engine', 'kind': 'evaluation', 'type': 'internal_rules', 'source': 'writing'}
        if task_key == 'listening_review':
            return {'id': 'internal-listening', 'name': 'Internal Listening Review Engine', 'kind': 'review', 'type': 'internal_rules', 'source': 'listening'}
        return {'id': None, 'name': 'Unconfigured', 'kind': task_key, 'type': None, 'source': None}

    @classmethod
    def health_summary(cls) -> dict[str, Any]:
        groups = cls.grouped_rows()
        total = sum(len(group['rows']) for group in groups)
        enabled = sum(1 for group in groups for row in group['rows'] if row['is_enabled'])
        default_count = sum(1 for group in groups for row in group['rows'] if row['is_default'])
        ready_tasks = sum(1 for group in groups if any(row['is_enabled'] or row['provider_type'] == 'internal_rules' for row in group['rows']))
        return {
            'total_providers': total,
            'enabled_providers': enabled,
            'default_mappings': default_count,
            'task_groups': len(groups),
            'ready_tasks': ready_tasks,
        }
