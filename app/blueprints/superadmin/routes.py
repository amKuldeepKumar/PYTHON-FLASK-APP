from __future__ import annotations

import csv
import io
import json
import os
from collections import defaultdict

from flask import Response, current_app, flash, redirect, render_template, request, url_for
from datetime import datetime, timedelta
from flask_login import current_user, login_required
from sqlalchemy import desc, func, or_
from werkzeug.utils import secure_filename

from . import bp
from .forms import (
    AdminCreateForm,
    AdminEditForm,
    AdminPasswordForm,
    AdminPermissionForm,
    StudentEditForm,
    StudentPasswordForm,
    PageForm,
    SecuritySettingsForm,
    SeoSettingsForm,
    CouponForm,
    LanguageForm,
    LanguageImportForm,
    TranslationProviderForm,
    TranslationTestForm,
    SpeakingProviderForm,
    SpeakingProviderTestForm,
    ReadingProviderForm,
    ReadingProviderTestForm,
    ReadingPromptConfigForm,
)
from ..admin.lms_forms import (
    ChapterForm,
    CourseForm,
    DeleteForm,
    LessonForm,
    ModuleForm,
    LevelForm,
    QuestionForm,
    QuestionUploadForm,
    SubsectionForm,
)
from ...extensions import db
from ...models.lms import Chapter, Course, Enrollment, Lesson, Level, Module, Question, QuestionAttempt, Subsection, ContentVersion, CourseProgress
from ...models.coupon import Coupon
from ...models.login_event import LoginEvent
from ...models.user_session import UserSession
from ...models.security_policy import SecurityPolicy
from ...models.page import Page
from ...models.seo_settings import SeoSettings
from ...models.whatsapp import WhatsAppInquiryLog
from ...models.theme import Theme
from ...models.language import Language
from ...models.translation_provider import TranslationProvider
from ...models.api_log import ApiCallLog
from ...models.ai_request_log import AIRequestLog
from ...models.ai_usage_counter import AIUsageCounter
from ...models.api_catalog_entry import ApiCatalogEntry
from ...models.payment import Payment
from ...models.speaking_provider import SpeakingProvider
from ...models.speaking_topic import SpeakingTopic
from ...models.reading_provider import ReadingProvider
from ...models.ai_rule_config import AIRuleConfig
from ...services.spoken_english_service import SpokenEnglishService
from ...models.reading_topic import ReadingTopic
from ...models.reading_passage import ReadingPassage
from ...models.reading_question import ReadingQuestion
from ...models.writing_topic import WritingTopic
from ...models.writing_task import WritingTask

from ...models.speaking_session import SpeakingSession
from ...models.interview_session import InterviewSession
from ...models.writing_submission import WritingSubmission
from ...services.cms_service import ensure_page_content, parse_json_list
from ...services.security_service import apply_security_policy_updates, get_policy, sanitize_html, sanitize_json_html_fields
from ...models.user import Role, User
from ...rbac import require_role
from ...services.lms_service import LMSService, slugify
from ...services.language_service import ensure_default_languages, language_choices
from ...services.translation_engine import get_primary_provider, translate_text
from ...services.tenancy_service import superadmin_chart_payload
from ...services.speaking.provider_registry_service import SpeakingProviderRegistryService
from ...services.reading.provider_registry_service import ReadingProviderRegistryService
from ...services.reading.passage_generation_service import ReadingPassageGenerationService
from ...services.reading.question_generation_service import ReadingQuestionGenerationService
from ...services.ai import AICentralProviderRegistry, AIPromptBuilder, AIRuleService
from ...services.ai.service_layer import AIServiceLayer
from ...services.ai.ml_export_service import AIMLExportService
from ...services.ai.tutor_service import TutorAIService
from ...services.ai_rule_logger import AIRuleLogger
from ...services.economy_service import EconomyService
from ...services.image_course_review_service import ImageCourseReviewService
from ...services.rbac_service import seed_default_rbac

try:
    from ...audit import audit
except Exception:
    def audit(*args, **kwargs):
        return None

READING_REVIEW_ROLE_CODES = (Role.SUPERADMIN.value, Role.EDITOR.value)

_API_WORKBENCH_GROUPS = (
    {
        "key": "core_language",
        "label": "Core Language",
        "description": "Foundational language APIs used across speaking, writing, reading, and multilingual workflows.",
        "services": (
            ("speech_to_text", "Speech-to-Text API"),
            ("text_to_speech", "Text-to-Speech API"),
            ("pronunciation_scoring", "Pronunciation Scoring API"),
            ("voice_activity_detection", "Voice Activity Detection API"),
            ("speaker_verification", "Speaker Verification API"),
            ("grammar_checking", "Grammar Checking API"),
            ("spelling_correction", "Spelling Correction API"),
            ("vocabulary_analysis", "Vocabulary Analysis API"),
            ("readability_analysis", "Readability Analysis API"),
            ("semantic_similarity", "Semantic Similarity API"),
            ("essay_scoring", "Essay Scoring API"),
            ("short_answer_evaluation", "Short Answer Evaluation API"),
            ("translation", "Translation API"),
            ("language_detection", "Language Detection API"),
            ("phoneme_analysis", "Phoneme Analysis API"),
            ("fluency_scoring", "Fluency Scoring API"),
            ("intonation_prosody", "Intonation / Prosody API"),
            ("confidence_analysis", "Confidence Analysis API"),
        ),
    },
    {
        "key": "ai_llm",
        "label": "AI / LLM",
        "description": "High-level reasoning, generation, scoring, orchestration, and adaptive intelligence services.",
        "services": (
            ("llm_chat_completion", "LLM Chat Completion API"),
            ("prompt_orchestration", "Prompt Orchestration API"),
            ("rubric_scoring", "Rubric Scoring API"),
            ("content_generation", "Content Generation API"),
            ("feedback_generation", "Feedback Generation API"),
            ("adaptive_learning", "Adaptive Learning API"),
            ("conversation_simulation", "Conversation Simulation API"),
            ("difficulty_adjustment", "Difficulty Adjustment API"),
        ),
    },
    {
        "key": "writing",
        "label": "Writing",
        "description": "Essay quality, structure, plagiarism, and coherence services for writing workflows.",
        "services": (
            ("essay_evaluation", "Essay Evaluation API"),
            ("coherence_cohesion", "Coherence & Cohesion API"),
            ("task_achievement", "Task Achievement API"),
            ("sentence_structure_analysis", "Sentence Structure Analysis API"),
            ("paraphrasing_detection", "Paraphrasing Detection API"),
            ("plagiarism_detection", "Plagiarism Detection API"),
            ("ai_written_content_detection", "AI-Written Content Detection API"),
        ),
    },
    {
        "key": "reading",
        "label": "Reading",
        "description": "Reading generation, comprehension checking, explanations, and passage analysis.",
        "services": (
            ("question_generation", "Question Generation API"),
            ("comprehension_checking", "Comprehension Checking API"),
            ("answer_explanation", "Answer Explanation API"),
            ("passage_difficulty_analysis", "Passage Difficulty Analysis API"),
            ("keyword_extraction", "Keyword Extraction API"),
        ),
    },
    {
        "key": "listening",
        "label": "Listening",
        "description": "Audio generation, playback behavior, caption sync, and listening evaluation.",
        "services": (
            ("tts_voice_synthesis", "TTS Voice Synthesis API"),
            ("audio_speed_control", "Audio Speed Control Engine"),
            ("subtitle_caption_sync", "Subtitle / Caption Sync API"),
            ("listening_answer_evaluation", "Listening Answer Evaluation API"),
            ("replay_tracking", "Replay Tracking / Listening Behavior API"),
        ),
    },
    {
        "key": "speaking",
        "label": "Speaking",
        "description": "Speaking performance analysis, timing, accent, relevance, and filler detection.",
        "services": (
            ("pronunciation_assessment", "Pronunciation Assessment API"),
            ("fluency_assessment", "Fluency Assessment API"),
            ("grammar_in_speech", "Grammar in Speech API"),
            ("speech_relevance_scoring", "Speech Relevance Scoring API"),
            ("response_timing", "Response Timing API"),
            ("pause_filler_word_detection", "Pause / Filler Word Detection API"),
            ("accent_analysis", "Accent Analysis API"),
            ("interview_evaluation", "Interview Evaluation API"),
        ),
    },
    {
        "key": "interview",
        "label": "Interview / Mock Test",
        "description": "Interview-specific question generation, follow-up logic, confidence, and scoring.",
        "services": (
            ("hr_interview_question", "HR Interview Question API"),
            ("role_based_interview_generator", "Role-Based Interview Generator API"),
            ("follow_up_question", "Follow-Up Question API"),
            ("mock_interview_scoring", "Mock Interview Scoring API"),
            ("body_language", "Body Language API"),
            ("confidence_clarity", "Confidence + Clarity API"),
        ),
    },
    {
        "key": "rewards",
        "label": "Rewards / Wallet / Fraud",
        "description": "Wallet movement, rewards intelligence, fraud, and certificate services.",
        "services": (
            ("wallet_ledger", "Wallet Ledger API"),
            ("reward_rules", "Reward Rules API"),
            ("xp_streak", "XP / Streak API"),
            ("fraud_detection", "Fraud Detection API"),
            ("risk_scoring", "Risk Scoring API"),
            ("transfer_validation", "Transfer Validation API"),
            ("certificate_generation", "Certificate Generation API"),
            ("certificate_verification", "Certificate Verification API"),
            ("rewards_analytics", "Rewards Analytics API"),
        ),
    },
    {
        "key": "platform",
        "label": "User / Platform",
        "description": "Authentication, enrollment, payments, notifications, storage, analytics, and core platform operations.",
        "services": (
            ("authentication", "Authentication API"),
            ("role_management", "Role Management API"),
            ("course_management", "Course Management API"),
            ("enrollment", "Enrollment API"),
            ("progress_tracking", "Progress Tracking API"),
            ("leaderboard", "Leaderboard API"),
            ("notification", "Notification API"),
            ("email", "Email API"),
            ("sms_otp", "SMS / OTP API"),
            ("payment_gateway", "Payment Gateway API"),
            ("storage", "Storage API"),
            ("cdn_media_delivery", "CDN / Media Delivery API"),
            ("analytics", "Analytics API"),
            ("audit_log", "Audit Log API"),
        ),
    },
    {
        "key": "control",
        "label": "Admin / SuperAdmin",
        "description": "Publishing, review, AI controls, themes, and dashboards for operations teams.",
        "services": (
            ("publish_workflow", "Publish Workflow API"),
            ("review_approval", "Review / Approval API"),
            ("ai_rule_panel", "AI Rule Panel API"),
            ("theme_control", "Theme Control API"),
            ("course_health_dashboard", "Course Health Dashboard API"),
            ("student_performance_dashboard", "Student Performance Dashboard API"),
            ("economy_dashboard", "Economy Dashboard API"),
        ),
    },
)

_API_WORKBENCH_GROUP_MAP = {group["key"]: group for group in _API_WORKBENCH_GROUPS}
_API_WORKBENCH_SERVICE_LOOKUP = {
    service_key: {
        "label": service_label,
        "category_key": group["key"],
        "category_label": group["label"],
    }
    for group in _API_WORKBENCH_GROUPS
    for service_key, service_label in group["services"]
}


def _api_workbench_tab(tab_key: str | None) -> str:
    value = (tab_key or "").strip().lower()
    return value if value in _API_WORKBENCH_GROUP_MAP else _API_WORKBENCH_GROUPS[0]["key"]


def _api_workbench_service_meta(service_key: str, custom_name: str | None = None, tab_key: str | None = None) -> tuple[str, str, str]:
    if service_key == "__custom__":
        title = (custom_name or "").strip()
        normalized_tab = _api_workbench_tab(tab_key)
        return normalized_tab, f"custom::{slugify(title)}", title

    meta = _API_WORKBENCH_SERVICE_LOOKUP.get(service_key)
    if not meta:
        normalized_tab = _api_workbench_tab(tab_key)
        title = (custom_name or service_key or "Custom API").strip()
        return normalized_tab, f"custom::{slugify(title)}", title
    return meta["category_key"], service_key, meta["label"]


def _api_workbench_registry_href(service_key: str) -> str:
    registry_map = {
        "speech_to_text": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_STT),
        "text_to_speech": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_TTS),
        "tts_voice_synthesis": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_TTS),
        "pronunciation_scoring": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_PRONUNCIATION),
        "phoneme_analysis": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_PRONUNCIATION),
        "pronunciation_assessment": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_PRONUNCIATION),
        "fluency_scoring": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_EVALUATION),
        "confidence_analysis": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_EVALUATION),
        "fluency_assessment": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_EVALUATION),
        "grammar_in_speech": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_EVALUATION),
        "interview_evaluation": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_EVALUATION),
        "translation": url_for("superadmin.api_registry"),
        "language_detection": url_for("superadmin.api_registry"),
        "question_generation": url_for("superadmin.reading_api_registry", kind=ReadingProvider.KIND_QUESTION),
        "answer_explanation": url_for("superadmin.reading_api_registry", kind=ReadingProvider.KIND_EVALUATION),
        "short_answer_evaluation": url_for("superadmin.reading_api_registry", kind=ReadingProvider.KIND_EVALUATION),
        "plagiarism_detection": url_for("superadmin.reading_api_registry", kind=ReadingProvider.KIND_PLAGIARISM),
    }
    return registry_map.get(service_key, url_for("superadmin.ai_central"))


def _api_workbench_rows_for_tab(tab_key: str) -> tuple[list[dict], list[ApiCatalogEntry]]:
    active_tab = _api_workbench_tab(tab_key)
    base_services = list(_API_WORKBENCH_GROUP_MAP[active_tab]["services"])
    entries = (
        ApiCatalogEntry.query
        .filter_by(category_key=active_tab)
        .order_by(ApiCatalogEntry.service_name.asc(), ApiCatalogEntry.is_selected.desc(), ApiCatalogEntry.provider_name.asc())
        .all()
    )

    service_map: dict[str, list[ApiCatalogEntry]] = defaultdict(list)
    custom_services: dict[str, str] = {}
    for entry in entries:
        service_map[entry.service_key].append(entry)
        if entry.service_key not in _API_WORKBENCH_SERVICE_LOOKUP:
            custom_services.setdefault(entry.service_key, entry.service_name)

    service_rows = []
    for service_key, service_label in base_services + list(custom_services.items()):
        service_entries = service_map.get(service_key, [])
        selected_entry = next((row for row in service_entries if row.is_selected), None)
        service_rows.append({
            "service_key": service_key,
            "service_name": service_label,
            "entry_count": len(service_entries),
            "selected_provider": selected_entry.provider_name if selected_entry else "Not selected yet",
            "recommended_provider": next((row.provider_name for row in service_entries if row.recommendation_level == ApiCatalogEntry.RECOMMENDATION_BEST), "Not marked"),
            "pricing_mix": ", ".join(sorted({row.pricing_label for row in service_entries})) or "Not mapped",
            "registry_href": _api_workbench_registry_href(service_key),
        })
    return service_rows, entries


def _ai_rule_preview_map() -> tuple[dict[str, str], dict[str, dict]]:
    task_map = {
        'speaking': 'speaking_evaluation',
        'writing': 'writing_evaluation',
        'reading': 'reading_evaluation',
        'listening': 'listening_review',
    }
    payloads = {
        'speaking_evaluation': {'prompt_text': 'Speak about your hometown.', 'transcript': 'My hometown is peaceful and friendly and I enjoy living there.', 'duration_seconds': 38},
        'writing_evaluation': {'submission_text': 'Countries should communicate and work together to avoid war and create peace for future generations.', 'task_title': 'World peace', 'task_instructions': 'Write 120 words.'},
        'reading_evaluation': {'question_text': 'What helps students build confidence?', 'student_answer': 'daily routine', 'correct_answer': 'daily routine', 'question_type': 'mcq'},
        'listening_review': {'topic_title': 'Daily Routine', 'prompt_text': 'Listen and answer.', 'caption_text': 'This is a clean caption sample.'},
    }
    return task_map, payloads


def _ai_rule_test_payload(track_key: str, form) -> dict:
    sample = (form.get('sample_input') or '').strip()
    if track_key == 'speaking':
        return {'prompt_text': form.get('sample_prompt') or 'Speak about your hometown.', 'transcript': sample or 'My hometown is calm and clean.', 'duration_seconds': int(form.get('sample_duration') or 35)}
    if track_key == 'writing':
        return {'submission_text': sample or 'Students learn better when they practice every day.', 'task_title': form.get('sample_prompt') or 'Writing task', 'task_instructions': 'Write 80 to 120 words.'}
    if track_key == 'reading':
        return {'question_text': form.get('sample_prompt') or 'What is the main idea?', 'student_answer': sample or 'daily practice', 'correct_answer': form.get('sample_expected') or 'daily practice', 'question_type': 'short'}
    return {'topic_title': form.get('sample_prompt') or 'Listening topic', 'prompt_text': form.get('sample_prompt') or 'Listen and answer.', 'caption_text': sample or 'This is a sample caption for review.'}


def _ai_rule_docs() -> list[dict[str, str]]:
    return [
        {'title': 'Strictness', 'body': '1 is lenient, 5 is strict. Use higher values when you want tighter scoring and less acceptance of weak answers.'},
        {'title': 'Minimum length', 'body': 'Blocks or penalizes answers that are too short for the task.'},
        {'title': 'Require explanations', 'body': 'Forces the AI to explain why the score or decision was given.'},
        {'title': 'Off-topic block', 'body': 'Rejects clearly unrelated answers instead of trying to score them normally.'},
    ]


def _count_enabled_speaking_providers(kind: str) -> int:
    return SpeakingProvider.query.filter_by(provider_kind=kind, is_enabled=True).count()


def _count_enabled_reading_providers(kind: str) -> int:
    return ReadingProvider.query.filter_by(provider_kind=kind, is_enabled=True).count()


def _superadmin_ai_capability_rows() -> list[dict[str, str]]:
    translation = get_primary_provider()
    translation_ready = bool(getattr(translation, "is_enabled", False))
    enabled_languages = Language.query.filter_by(is_enabled=True).count()
    writing_rule = AIRuleConfig.query.filter_by(track_key=AIRuleConfig.TRACK_WRITING).first()

    return [
        {
            "label": "Translation",
            "status": "ready" if translation_ready else "partial",
            "detail": f"{translation.name or translation.provider_label} is {'active' if translation_ready else 'saved but not enabled'} for multilingual content support.",
            "href": url_for("superadmin.api_registry"),
            "action": "Manage translation",
        },
        {
            "label": "Speech to Text",
            "status": "ready" if _count_enabled_speaking_providers(SpeakingProvider.KIND_STT) else "missing",
            "detail": "Controls microphone and audio-upload transcription for speaking and interview sessions.",
            "href": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_STT),
            "action": "Manage STT",
        },
        {
            "label": "Pronunciation",
            "status": "ready" if _count_enabled_speaking_providers(SpeakingProvider.KIND_PRONUNCIATION) else "partial",
            "detail": "Pronunciation providers can be configured, but you still need one enabled default for production scoring.",
            "href": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_PRONUNCIATION),
            "action": "Manage pronunciation",
        },
        {
            "label": "Text to Speech",
            "status": "ready" if _count_enabled_speaking_providers(SpeakingProvider.KIND_TTS) else "partial",
            "detail": "TTS providers now have a dedicated registry for lesson playback, multilingual narration, and welcome voice use-cases.",
            "href": url_for("superadmin.speaking_api_registry", kind=SpeakingProvider.KIND_TTS),
            "action": "Manage TTS",
        },
        {
            "label": "Grammar and Writing AI",
            "status": "ready" if writing_rule and writing_rule.is_enabled else "partial",
            "detail": "Writing evaluation and rule controls exist, but they still run mainly on internal heuristics instead of a dedicated external provider registry.",
            "href": url_for("superadmin.ai_rule_panel", track="writing"),
            "action": "Open writing AI rules",
        },
        {
            "label": "Reading AI",
            "status": "ready" if _count_enabled_reading_providers(ReadingProvider.KIND_PASSAGE) and _count_enabled_reading_providers(ReadingProvider.KIND_QUESTION) else "partial",
            "detail": "Reading generation, translation, and answer evaluation are configurable from the reading registry.",
            "href": url_for("superadmin.reading_api_registry"),
            "action": "Manage reading AI",
        },
        {
            "label": "Plagiarism Detection",
            "status": "ready" if _count_enabled_reading_providers(ReadingProvider.KIND_PLAGIARISM) else "partial",
            "detail": "Plagiarism providers can now be stored and tested from the reading/text registry for writing integrity workflows.",
            "href": url_for("superadmin.reading_api_registry", kind=ReadingProvider.KIND_PLAGIARISM),
            "action": "Manage plagiarism",
        },
        {
            "label": "Multilingual Coverage",
            "status": "ready" if translation_ready and enabled_languages > 1 else "partial",
            "detail": f"{enabled_languages} enabled language records are currently available across the platform.",
            "href": url_for("superadmin.languages_index"),
            "action": "Manage languages",
        },
        {
            "label": "Token and Cost Tracking",
            "status": "ready",
            "detail": "API call logs now store provider name, estimated token usage, and estimated cost for each logged provider event.",
            "href": url_for("superadmin.api_logs"),
            "action": "Open API logs",
        },
    ]


def _superadmin_ai_quick_links() -> list[dict[str, str]]:
    return [
        {
            "label": "AI Central",
            "detail": "One overview for translation, speech, reading, writing, and AI task mapping.",
            "href": url_for("superadmin.ai_central"),
        },
        {
            "label": "AI Rule Panel",
            "detail": "Control speaking, writing, reading, and listening rule behavior and prompt guardrails.",
            "href": url_for("superadmin.ai_rule_panel"),
        },
        {
            "label": "Speech Providers",
            "detail": "Manage STT, speaking evaluation, pronunciation, and TTS providers.",
            "href": url_for("superadmin.speaking_api_registry"),
        },
        {
            "label": "Reading and Integrity Providers",
            "detail": "Manage reading passage, question, translation, evaluation, and plagiarism engines.",
            "href": url_for("superadmin.reading_api_registry"),
        },
        {
            "label": "Translation Provider",
            "detail": "Configure multilingual translation, provider credits, and fallback behavior.",
            "href": url_for("superadmin.api_registry"),
        },
        {
            "label": "API Logs",
            "detail": "Inspect provider activity, failures, and rollout health from one place.",
            "href": url_for("superadmin.api_logs"),
        },
    ]


def _superadmin_ai_usage_snapshot() -> dict[str, int]:
    return {
        "total_logs": AIRequestLog.query.count(),
        "translation_logs": AIRequestLog.query.filter(AIRequestLog.task_key == "translation").count(),
        "reading_logs": AIRequestLog.query.filter(AIRequestLog.task_key.like("reading_%")).count(),
        "speaking_logs": AIRequestLog.query.filter(AIRequestLog.task_key.like("speaking_%")).count(),
        "tracked_tokens": int(db.session.query(func.coalesce(func.sum(AIRequestLog.total_tokens), 0)).scalar() or 0),
        "cache_hits": AIRequestLog.query.filter_by(cache_hit=True).count(),
        "fallback_runs": AIRequestLog.query.filter_by(fallback_used=True).count(),
        "error_logs": AIRequestLog.query.filter(AIRequestLog.status != "success").count(),
    }


def _user_scope_snapshot(user: User | None) -> dict[str, str]:
    if not user:
        return {
            "owner_label": "Unknown",
            "owner_name": "Unknown",
            "institute_name": "Not linked",
            "teacher_name": "Not assigned",
        }

    principal = user.organization or (User.query.get(user.admin_id) if user.admin_id else None)
    teacher = user.assigned_teacher if getattr(user, "assigned_teacher", None) else None
    manager = user.manager if getattr(user, "manager", None) else None
    institute_name = (
        user.organization_name
        or (principal.organization_name if principal else None)
        or (principal.full_name if principal else None)
        or "Independent learner"
    )
    owner_name = principal.full_name if principal else (manager.full_name if manager else "Independent / Direct")
    owner_label = "Institute / Admin" if principal else ("Manager" if manager else "Independent")
    return {
        "owner_label": owner_label,
        "owner_name": owner_name,
        "institute_name": institute_name,
        "teacher_name": teacher.full_name if teacher else "Not assigned",
    }


def _latest_login_rows_for_user_ids(user_ids: list[int]) -> dict[int, LoginEvent]:
    if not user_ids:
        return {}
    rows = (
        LoginEvent.query
        .filter(LoginEvent.user_id.in_(user_ids))
        .order_by(LoginEvent.created_at.desc())
        .all()
    )
    latest: dict[int, LoginEvent] = {}
    for row in rows:
        latest.setdefault(row.user_id, row)
    return latest


def _latest_session_rows_for_user_ids(user_ids: list[int]) -> dict[int, UserSession]:
    if not user_ids:
        return {}
    rows = (
        UserSession.query
        .filter(UserSession.user_id.in_(user_ids))
        .order_by(UserSession.last_seen_at.desc())
        .all()
    )
    latest: dict[int, UserSession] = {}
    for row in rows:
        latest.setdefault(row.user_id, row)
    return latest


def _country_flag(country: str | None) -> str:
    value = (country or "").strip()
    if not value:
        return "🌐"
    normalized = value.upper()
    if normalized in {"LOCAL", "DEVELOPMENT"}:
        return "🏠"
    if len(normalized) == 2 and normalized.isalpha():
        base = 127397
        return "".join(chr(base + ord(char)) for char in normalized)

    country_map = {
        "UNITED STATES": "US",
        "USA": "US",
        "UNITED KINGDOM": "GB",
        "UK": "GB",
        "INDIA": "IN",
        "PAKISTAN": "PK",
        "BANGLADESH": "BD",
        "CANADA": "CA",
        "AUSTRALIA": "AU",
        "NEW ZEALAND": "NZ",
        "GERMANY": "DE",
        "FRANCE": "FR",
        "ITALY": "IT",
        "SPAIN": "ES",
        "JAPAN": "JP",
        "CHINA": "CN",
        "UAE": "AE",
        "UNITED ARAB EMIRATES": "AE",
        "SAUDI ARABIA": "SA",
        "SINGAPORE": "SG",
        "NEPAL": "NP",
        "SRI LANKA": "LK",
    }
    code = country_map.get(normalized)
    if code:
        base = 127397
        return "".join(chr(base + ord(char)) for char in code)
    return "🌐"


def _location_with_flag(city: str | None, country: str | None) -> str:
    place = (city or "").strip()
    country_value = (country or "").strip()
    text = ", ".join(part for part in [place, country_value] if part) or "Unknown"
    return f"{_country_flag(country_value)} {text}"


def _course_visual_payload(course: Course | None) -> dict[str, str]:
    if not course:
        return {
            "initials": "NA",
            "track_label": "General",
            "accent_class": "student-course-art-general",
        }

    title = (course.title or "Course").strip()
    parts = [part[0] for part in title.split()[:2] if part]
    initials = "".join(parts).upper() or title[:2].upper()
    track = (course.track_type or "general").strip().lower()
    accent_map = {
        "speaking": "student-course-art-speaking",
        "reading": "student-course-art-reading",
        "writing": "student-course-art-writing",
        "listening": "student-course-art-listening",
    }
    return {
        "initials": initials,
        "track_label": track.replace("_", " ").title(),
        "accent_class": accent_map.get(track, "student-course-art-general"),
    }


def _student_access_detail(student: User | None) -> dict | None:
    if not student or student.role_code != Role.STUDENT.value:
        return None

    live_cutoff = datetime.utcnow() - timedelta(minutes=30)
    latest_login = (
        student.login_events
        .order_by(desc(LoginEvent.created_at))
        .first()
    )
    latest_session = (
        student.session_rows
        .order_by(UserSession.last_seen_at.desc())
        .first()
    )
    recent_sessions = (
        student.session_rows
        .order_by(UserSession.last_seen_at.desc())
        .limit(8)
        .all()
    )
    recent_logins = (
        student.login_events
        .order_by(desc(LoginEvent.created_at))
        .limit(8)
        .all()
    )
    enrollments = (
        Enrollment.query
        .filter_by(student_id=student.id)
        .order_by(Enrollment.enrolled_at.desc())
        .limit(6)
        .all()
    )
    course_ids = [row.course_id for row in enrollments if row.course_id]
    payment_map: dict[int, Payment] = {}
    if course_ids:
        payments = (
            Payment.query
            .filter(
                Payment.user_id == student.id,
                Payment.status == "paid",
                Payment.course_id.in_(course_ids),
            )
            .order_by(Payment.paid_at.desc(), Payment.created_at.desc())
            .all()
        )
        for payment in payments:
            payment_map.setdefault(payment.course_id, payment)

    course_access_rows = []
    for enrollment in enrollments:
        payment = payment_map.get(enrollment.course_id)
        course = enrollment.course
        course_access_rows.append({
            "course_title": course.title if course else "Unknown course",
            "track_type": (course.track_type or "general").replace("_", " ").title() if course else "General",
            "purchase_state": "Paid" if payment else "Enrolled",
            "purchase_scope": (payment.purchase_scope if payment else enrollment.access_scope or "full_course").replace("_", " ").title(),
            "amount": float(payment.final_amount or 0) if payment else 0.0,
            "currency_code": payment.currency_code if payment else (course.currency_code if course else "INR"),
            "enrolled_at": enrollment.enrolled_at,
            "is_active": enrollment.status == "active",
            "course_visual": _course_visual_payload(course),
        })

    access_rows = []
    for session in recent_sessions:
        access_rows.append({
            "browser_display": session.browser_display,
            "location_display": session.location_display,
            "location_flag": _country_flag(session.country),
            "location_with_flag": _location_with_flag(session.city, session.country),
            "ip_address": session.ip_address or "Unknown",
            "login_at": session.created_at,
            "last_seen_at": session.last_seen_at,
            "logout_at": session.revoked_at,
            "is_active": bool(session.revoked_at is None and session.last_seen_at and session.last_seen_at >= live_cutoff),
        })

    timeline_rows = []
    for login in recent_logins:
        timeline_rows.append({
            "kind": "login",
            "icon": "bi-box-arrow-in-right",
            "title": "Login accepted",
            "subtitle": f"{login.browser_display} • {_location_with_flag(login.city, login.country)}",
            "stamp": login.created_at,
            "badge": "Login",
            "badge_class": "student-chip-role",
            "meta": login.ip_address or "Unknown IP",
        })
    for session in recent_sessions:
        timeline_rows.append({
            "kind": "session",
            "icon": "bi-activity",
            "title": "Session heartbeat",
            "subtitle": f"{session.browser_display} • {_location_with_flag(session.city, session.country)}",
            "stamp": session.last_seen_at or session.created_at,
            "badge": "Active" if session.is_active else "Recent",
            "badge_class": "student-chip-live" if session.is_active else "student-chip-recent",
            "meta": session.ip_address or "Unknown IP",
        })
        if session.revoked_at:
            timeline_rows.append({
                "kind": "logout",
                "icon": "bi-box-arrow-right",
                "title": "Session revoked",
                "subtitle": f"{session.browser_display} • {_location_with_flag(session.city, session.country)}",
                "stamp": session.revoked_at,
                "badge": "Logout",
                "badge_class": "student-chip-soft",
                "meta": session.ip_address or "Unknown IP",
            })
    timeline_rows.sort(key=lambda row: row["stamp"] or datetime.min, reverse=True)

    return {
        "student": student,
        "scope": _user_scope_snapshot(student),
        "progress": LMSService.student_progress_report(student),
        "latest_login": latest_login,
        "latest_session": latest_session,
        "recent_logins": recent_logins,
        "course_access_rows": course_access_rows,
        "access_rows": access_rows,
        "timeline_rows": timeline_rows[:12],
        "latest_login_location": _location_with_flag(
            latest_login.city if latest_login else None,
            latest_login.country if latest_login else None,
        ),
        "latest_session_location": _location_with_flag(
            latest_session.city if latest_session else None,
            latest_session.country if latest_session else None,
        ),
    }


def _student_directory_context(
    *,
    q: str = "",
    admin_id: int = 0,
    teacher_id: int = 0,
    focus_student_id: int = 0,
    quick_filter: str = "all",
) -> dict:
    students = _student_query_for_superadmin(
        q=q or None,
        admin_id=admin_id or None,
        teacher_id=teacher_id or None,
    ).all()
    course_map = {
        student.id: Enrollment.query
        .filter_by(student_id=student.id, status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .first()
        for student in students
    }
    progress_map = {student.id: LMSService.student_progress_report(student) for student in students}
    latest_login_map = {
        student.id: student.login_events.order_by(desc(LoginEvent.created_at)).first()
        for student in students
    }
    latest_session_map = {
        student.id: student.session_rows.order_by(UserSession.last_seen_at.desc()).first()
        for student in students
    }
    student_ids = [student.id for student in students]
    latest_paid_payment_map: dict[int, Payment] = {}
    if student_ids:
        for payment in (
            Payment.query
            .filter(Payment.user_id.in_(student_ids), Payment.status == "paid")
            .order_by(Payment.paid_at.desc(), Payment.created_at.desc())
            .all()
        ):
            latest_paid_payment_map.setdefault(payment.user_id, payment)

    now = datetime.utcnow()
    live_cutoff = now - timedelta(minutes=30)
    student_rows = []
    for student in students:
        latest_login = latest_login_map.get(student.id)
        latest_session = latest_session_map.get(student.id)
        progress = progress_map.get(student.id, {})
        course_ref = course_map.get(student.id)
        is_live = bool(latest_session and latest_session.revoked_at is None and latest_session.last_seen_at and latest_session.last_seen_at >= live_cutoff)
        is_paid = student.id in latest_paid_payment_map
        is_independent = not bool(student.organization_id or student.admin_id or student.managed_by_user_id)
        location_text = (
            _location_with_flag(
                latest_session.city if latest_session else (latest_login.city if latest_login else None),
                latest_session.country if latest_session else (latest_login.country if latest_login else None),
            )
            if latest_session or latest_login
            else "🌐 Unknown"
        )
        recent_time = (
            latest_session.last_seen_at
            if latest_session and latest_session.last_seen_at
            else (latest_login.created_at if latest_login else None)
        )
        student_rows.append({
            "student": student,
            "course_ref": course_ref,
            "latest_login": latest_login,
            "latest_session": latest_session,
            "progress": progress,
            "is_live": is_live,
            "activity_label": "Live" if is_live else "Idle",
            "activity_chip_class": "student-chip-live" if is_live else "student-chip-recent",
            "is_paid": is_paid,
            "payment_label": "Paid" if is_paid else "Free / Direct",
            "payment_chip_class": "student-chip-live" if is_paid else "student-chip-soft",
            "is_independent": is_independent,
            "scope_label": "Independent" if is_independent else "Institute",
            "scope_chip_class": "student-chip-trend" if is_independent else "student-chip-role",
            "location_text": location_text,
            "recent_time": recent_time,
            "avatar_url": student.avatar_url or url_for("static", filename="shared/img/avatar-placeholder.svg"),
        })

    normalized_quick_filter = (quick_filter or "all").strip().lower()
    if normalized_quick_filter not in {"all", "live", "idle", "paid", "independent", "institute"}:
        normalized_quick_filter = "all"
    quick_filter_counts = {
        "all": len(student_rows),
        "live": sum(1 for row in student_rows if row["is_live"]),
        "idle": sum(1 for row in student_rows if not row["is_live"]),
        "paid": sum(1 for row in student_rows if row["is_paid"]),
        "independent": sum(1 for row in student_rows if row["is_independent"]),
        "institute": sum(1 for row in student_rows if not row["is_independent"]),
    }
    if normalized_quick_filter == "live":
        student_rows = [row for row in student_rows if row["is_live"]]
    elif normalized_quick_filter == "idle":
        student_rows = [row for row in student_rows if not row["is_live"]]
    elif normalized_quick_filter == "paid":
        student_rows = [row for row in student_rows if row["is_paid"]]
    elif normalized_quick_filter == "independent":
        student_rows = [row for row in student_rows if row["is_independent"]]
    elif normalized_quick_filter == "institute":
        student_rows = [row for row in student_rows if not row["is_independent"]]

    focused_student = None
    if focus_student_id:
        focused_student = User.query.filter_by(id=focus_student_id, role=Role.STUDENT.value).first()

    return {
        "students": students,
        "course_map": course_map,
        "progress_map": progress_map,
        "latest_login_map": latest_login_map,
        "latest_session_map": latest_session_map,
        "student_rows": student_rows,
        "focused_student_id": focus_student_id,
        "focused_student_detail": _student_access_detail(focused_student),
        "panel_role": "superadmin",
        "q": q,
        "selected_admin_id": admin_id,
        "selected_teacher_id": teacher_id,
        "current_quick_filter": normalized_quick_filter,
        "quick_filter_counts": quick_filter_counts,
        "admin_choices": _admin_scope_choices(include_none=True),
        "teacher_choices": _teacher_choices_for_superadmin(include_none=True),
    }


def _superadmin_live_workspace_snapshot() -> dict:
    now = datetime.utcnow()
    live_cutoff = now - timedelta(minutes=30)
    weekly_cutoff = now - timedelta(days=7)
    login_cutoff = now - timedelta(hours=24)

    paid_payments = (
        Payment.query
        .filter_by(status="paid")
        .order_by(Payment.paid_at.desc(), Payment.created_at.desc())
        .all()
    )
    active_enrollments = (
        Enrollment.query
        .filter_by(status="active")
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    recent_progress_rows = (
        CourseProgress.query
        .filter(CourseProgress.last_activity_at.isnot(None), CourseProgress.last_activity_at >= weekly_cutoff)
        .all()
    )
    recent_session_rows = (
        UserSession.query
        .join(User, User.id == UserSession.user_id)
        .filter(User.role == Role.STUDENT.value)
        .order_by(UserSession.last_seen_at.desc())
        .limit(8)
        .all()
    )

    payment_map: dict[tuple[int, int], Payment] = {}
    for row in paid_payments:
        payment_map.setdefault((row.user_id, row.course_id), row)

    recent_enrollment_rows = active_enrollments[:12]
    enrollment_user_ids = [row.student_id for row in recent_enrollment_rows]
    enrollment_login_map = _latest_login_rows_for_user_ids(enrollment_user_ids)
    enrollment_session_map = _latest_session_rows_for_user_ids(enrollment_user_ids)

    sales_rows = []
    for row in recent_enrollment_rows:
        student = row.student
        course = row.course
        scope = _user_scope_snapshot(student)
        payment = payment_map.get((row.student_id, row.course_id))
        latest_login = enrollment_login_map.get(row.student_id)
        latest_session = enrollment_session_map.get(row.student_id)
        sales_rows.append({
            "student_name": student.full_name,
            "student_email": student.email,
            "course_title": course.title if course else "Unknown course",
            "track_type": (course.track_type or "general").replace("_", " ").title() if course else "General",
            "purchase_state": "Paid" if payment else "Enrolled",
            "amount": float(payment.final_amount or 0) if payment else 0.0,
            "currency_code": payment.currency_code if payment else (course.currency_code if course else "INR"),
            "purchase_scope": (payment.purchase_scope if payment else row.access_scope or "full_course").replace("_", " ").title(),
            "purchased_at": payment.paid_at or payment.created_at if payment else row.enrolled_at,
            "is_live": bool(latest_session and latest_session.revoked_at is None and latest_session.last_seen_at and latest_session.last_seen_at >= live_cutoff),
            "browser_display": f"{latest_session.browser or 'Unknown'} • {latest_session.os_name or 'Unknown'}" if latest_session else (latest_login.browser_display if latest_login else "Unknown"),
            "location_display": latest_login.location_display if latest_login else "Unknown",
            "login_at": latest_session.created_at if latest_session else (latest_login.created_at if latest_login else None),
            "logout_at": latest_session.revoked_at if latest_session else None,
            "owner_label": scope["owner_label"],
            "owner_name": scope["owner_name"],
            "institute_name": scope["institute_name"],
            "teacher_name": scope["teacher_name"],
        })

    session_user_ids = [row.user_id for row in recent_session_rows]
    session_login_map = _latest_login_rows_for_user_ids(session_user_ids)
    current_enrollment_map: dict[int, Enrollment] = {}
    for row in (
        Enrollment.query
        .filter(Enrollment.student_id.in_(session_user_ids), Enrollment.status == "active")
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    ):
        current_enrollment_map.setdefault(row.student_id, row)

    access_rows = []
    for row in recent_session_rows:
        user = row.user
        latest_login = session_login_map.get(row.user_id)
        current_enrollment = current_enrollment_map.get(row.user_id)
        scope = _user_scope_snapshot(user)
        access_rows.append({
            "user_id": user.id,
            "user_name": user.full_name,
            "role_label": user.role.replace("_", " ").title(),
            "course_title": current_enrollment.course.title if current_enrollment and current_enrollment.course else ("—" if user.role_code != Role.STUDENT.value else "No active course"),
            "location_display": latest_login.location_display if latest_login else "Unknown",
            "ip_address": row.ip_address or (latest_login.ip_address if latest_login else "") or "Unknown",
            "browser_display": f"{row.browser or 'Unknown'} • {row.os_name or 'Unknown'}",
            "login_at": row.created_at,
            "last_seen_at": row.last_seen_at,
            "logout_at": row.revoked_at,
            "is_active": bool(row.revoked_at is None and row.last_seen_at and row.last_seen_at >= live_cutoff),
            "owner_name": scope["owner_name"],
            "institute_name": scope["institute_name"],
        })

    course_counters: dict[int, dict[str, int]] = defaultdict(lambda: {
        "paid_count": 0,
        "enrollment_count": 0,
        "active_learners": 0,
        "organization_count": 0,
        "independent_count": 0,
    })
    for row in paid_payments:
        course_counters[row.course_id]["paid_count"] += 1
    for row in active_enrollments:
        data = course_counters[row.course_id]
        data["enrollment_count"] += 1
        if row.student and row.student.admin_id:
            data["organization_count"] += 1
        else:
            data["independent_count"] += 1
    for row in recent_progress_rows:
        course_counters[row.course_id]["active_learners"] += 1

    course_map = {course.id: course for course in Course.query.filter(Course.status != "archived").all()}
    course_rows = []
    for course_id, data in course_counters.items():
        course = course_map.get(course_id)
        if not course:
            continue
        course_rows.append({
            "course_title": course.title,
            "track_type": (course.track_type or "general").replace("_", " ").title(),
            "paid_count": data["paid_count"],
            "enrollment_count": data["enrollment_count"],
            "active_learners": data["active_learners"],
            "organization_count": data["organization_count"],
            "independent_count": data["independent_count"],
        })
    course_rows.sort(key=lambda row: (row["paid_count"], row["active_learners"], row["enrollment_count"]), reverse=True)

    total_paid_revenue = float(sum(float(row.final_amount or 0) for row in paid_payments))
    recent_logins_24h = (
        LoginEvent.query
        .filter(LoginEvent.created_at >= login_cutoff, LoginEvent.success.is_(True))
        .count()
    )
    live_session_count = (
        UserSession.query
        .filter(UserSession.revoked_at.is_(None), UserSession.last_seen_at >= live_cutoff)
        .count()
    )

    return {
        "summary": {
            "paid_orders": len(paid_payments),
            "paid_revenue": total_paid_revenue,
            "live_sessions": live_session_count,
            "recent_logins_24h": recent_logins_24h,
        },
        "sales_rows": sales_rows,
        "access_rows": access_rows,
        "course_rows": course_rows[:8],
    }


def _parse_filter_datetime(raw: str | None, *, end_of_day: bool = False) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    if end_of_day:
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def _matches_filter(value: str | None, needle: str | None) -> bool:
    target = (needle or "").strip().lower()
    if not target:
        return True
    return target in ((value or "").strip().lower())


def _superadmin_learner_ops_report(
    *,
    q: str = "",
    role_filter: str = "ALL",
    course_id: int = 0,
    admin_id: int = 0,
    institute_query: str = "",
    city_query: str = "",
    browser_query: str = "",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    enrollment_query = (
        Enrollment.query
        .join(User, User.id == Enrollment.student_id)
        .join(Course, Course.id == Enrollment.course_id)
        .filter(User.role == Role.STUDENT.value)
    )
    session_query = (
        UserSession.query
        .join(User, User.id == UserSession.user_id)
    )

    if course_id:
        enrollment_query = enrollment_query.filter(Enrollment.course_id == course_id)

    if admin_id:
        enrollment_query = enrollment_query.filter(or_(User.admin_id == admin_id, User.organization_id == admin_id))
        session_query = session_query.filter(or_(User.admin_id == admin_id, User.organization_id == admin_id, User.id == admin_id))

    if role_filter != "ALL":
        session_query = session_query.filter(User.role == role_filter)

    if q:
        search = f"%{q}%"
        enrollment_query = enrollment_query.filter(
            or_(
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.username.ilike(search),
                User.email.ilike(search),
                Course.title.ilike(search),
            )
        )
        session_query = session_query.filter(
            or_(
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.username.ilike(search),
                User.email.ilike(search),
            )
        )

    enrollment_rows = enrollment_query.order_by(Enrollment.enrolled_at.desc()).all()
    student_ids = [row.student_id for row in enrollment_rows]
    course_ids = [row.course_id for row in enrollment_rows]
    login_map = _latest_login_rows_for_user_ids(student_ids)
    session_map = _latest_session_rows_for_user_ids(student_ids)

    payment_map: dict[tuple[int, int], Payment] = {}
    if student_ids and course_ids:
        payment_rows = (
            Payment.query
            .filter(
                Payment.user_id.in_(student_ids),
                Payment.course_id.in_(course_ids),
                Payment.status == "paid",
            )
            .order_by(Payment.paid_at.desc(), Payment.created_at.desc())
            .all()
        )
        for row in payment_rows:
            payment_map.setdefault((row.user_id, row.course_id), row)

    live_cutoff = datetime.utcnow() - timedelta(minutes=30)
    sales_rows = []
    for row in enrollment_rows:
        student = row.student
        course = row.course
        latest_login = login_map.get(row.student_id)
        latest_session = session_map.get(row.student_id)
        scope = _user_scope_snapshot(student)
        payment = payment_map.get((row.student_id, row.course_id))
        activity_at = payment.paid_at or payment.created_at if payment else row.enrolled_at

        sale_row = {
            "student_id": row.student_id,
            "student_name": student.full_name,
            "student_email": student.email,
            "course_id": row.course_id,
            "course_title": course.title if course else "Unknown course",
            "track_type": (course.track_type or "general").replace("_", " ").title() if course else "General",
            "purchase_state": "Paid" if payment else "Enrolled",
            "amount": float(payment.final_amount or 0) if payment else 0.0,
            "currency_code": payment.currency_code if payment else (course.currency_code if course else "INR"),
            "purchase_scope": (payment.purchase_scope if payment else row.access_scope or "full_course").replace("_", " ").title(),
            "activity_at": activity_at,
            "location_display": latest_login.location_display if latest_login else "Unknown",
            "city": latest_login.city if latest_login else "",
            "browser_display": f"{latest_session.browser or 'Unknown'} • {latest_session.os_name or 'Unknown'}" if latest_session else (latest_login.browser_display if latest_login else "Unknown"),
            "browser": latest_session.browser if latest_session else (latest_login.browser or ""),
            "login_at": latest_session.created_at if latest_session else (latest_login.created_at if latest_login else None),
            "last_seen_at": latest_session.last_seen_at if latest_session else None,
            "logout_at": latest_session.revoked_at if latest_session else None,
            "is_live": bool(latest_session and latest_session.revoked_at is None and latest_session.last_seen_at and latest_session.last_seen_at >= live_cutoff),
            "owner_label": scope["owner_label"],
            "owner_name": scope["owner_name"],
            "institute_name": scope["institute_name"],
            "teacher_name": scope["teacher_name"],
        }

        if date_from and (sale_row["activity_at"] is None or sale_row["activity_at"] < date_from):
            continue
        if date_to and (sale_row["activity_at"] is None or sale_row["activity_at"] > date_to):
            continue
        if not _matches_filter(sale_row["institute_name"], institute_query):
            continue
        if not _matches_filter(sale_row["city"], city_query):
            continue
        if not _matches_filter(sale_row["browser"], browser_query):
            continue
        if role_filter not in {"ALL", Role.STUDENT.value}:
            continue
        sales_rows.append(sale_row)

    raw_session_rows = session_query.order_by(UserSession.last_seen_at.desc()).all()
    session_user_ids = [row.user_id for row in raw_session_rows]
    session_login_map = _latest_login_rows_for_user_ids(session_user_ids)

    current_enrollment_map: dict[int, Enrollment] = {}
    if session_user_ids:
        for row in (
            Enrollment.query
            .filter(Enrollment.student_id.in_(session_user_ids), Enrollment.status == "active")
            .order_by(Enrollment.enrolled_at.desc())
            .all()
        ):
            current_enrollment_map.setdefault(row.student_id, row)

    access_rows = []
    for row in raw_session_rows:
        user = row.user
        latest_login = session_login_map.get(row.user_id)
        current_enrollment = current_enrollment_map.get(row.user_id)
        scope = _user_scope_snapshot(user)
        access_row = {
            "user_name": user.full_name,
            "user_email": user.email,
            "role_label": user.role.replace("_", " ").title(),
            "course_id": current_enrollment.course_id if current_enrollment else 0,
            "course_title": current_enrollment.course.title if current_enrollment and current_enrollment.course else ("—" if user.role_code != Role.STUDENT.value else "No active course"),
            "location_display": latest_login.location_display if latest_login else "Unknown",
            "city": latest_login.city if latest_login else "",
            "ip_address": row.ip_address or (latest_login.ip_address if latest_login else "") or "Unknown",
            "browser_display": f"{row.browser or 'Unknown'} • {row.os_name or 'Unknown'}",
            "browser": row.browser or "",
            "login_at": row.created_at,
            "last_seen_at": row.last_seen_at,
            "logout_at": row.revoked_at,
            "is_active": bool(row.revoked_at is None and row.last_seen_at and row.last_seen_at >= live_cutoff),
            "owner_name": scope["owner_name"],
            "institute_name": scope["institute_name"],
            "teacher_name": scope["teacher_name"],
        }

        if course_id and int(access_row["course_id"] or 0) != int(course_id):
            continue
        if date_from and (access_row["last_seen_at"] is None or access_row["last_seen_at"] < date_from):
            continue
        if date_to and (access_row["last_seen_at"] is None or access_row["last_seen_at"] > date_to):
            continue
        if not _matches_filter(access_row["institute_name"], institute_query):
            continue
        if not _matches_filter(access_row["city"], city_query):
            continue
        if not _matches_filter(access_row["browser"], browser_query):
            continue
        access_rows.append(access_row)

    course_stats: dict[int, dict] = defaultdict(lambda: {
        "course_title": "Unknown",
        "track_type": "General",
        "paid_count": 0,
        "enrollment_count": 0,
        "active_count": 0,
        "org_count": 0,
        "independent_count": 0,
    })
    for row in sales_rows:
        bucket = course_stats[row["course_id"]]
        bucket["course_title"] = row["course_title"]
        bucket["track_type"] = row["track_type"]
        bucket["enrollment_count"] += 1
        if row["purchase_state"] == "Paid":
            bucket["paid_count"] += 1
        if row["is_live"]:
            bucket["active_count"] += 1
        if row["owner_label"] == "Institute / Admin":
            bucket["org_count"] += 1
        else:
            bucket["independent_count"] += 1
    course_rows = sorted(course_stats.values(), key=lambda item: (item["paid_count"], item["active_count"], item["enrollment_count"]), reverse=True)

    cities_seen = len({(row["city"] or "").strip().lower() for row in sales_rows if (row["city"] or "").strip()})
    browsers_seen = len({(row["browser"] or "").strip().lower() for row in sales_rows if (row["browser"] or "").strip()})
    summary = {
        "sales_count": len(sales_rows),
        "paid_count": sum(1 for row in sales_rows if row["purchase_state"] == "Paid"),
        "paid_revenue": sum(row["amount"] for row in sales_rows),
        "live_students": sum(1 for row in sales_rows if row["is_live"]),
        "access_count": len(access_rows),
        "cities_seen": cities_seen,
        "browsers_seen": browsers_seen,
    }
    return {
        "summary": summary,
        "sales_rows": sales_rows[:250],
        "access_rows": access_rows[:250],
        "course_rows": course_rows[:50],
    }


def _split_name(full_name: str) -> tuple[str | None, str | None]:
    parts = (full_name or "").strip().split(None, 1)
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def _create_staff_user_from_form(form: AdminCreateForm) -> tuple[bool, str]:
    if User.query.filter_by(username=form.username.data.strip()).first():
        return False, "Username already exists."
    if User.query.filter_by(email=form.email.data.strip().lower()).first():
        return False, "Email already exists."

    first_name, last_name = _split_name(form.full_name.data)
    parent_admin = User.query.get(form.parent_admin_id.data) if form.parent_admin_id.data else None
    org_name = (form.organization_name.data or "").strip() or (parent_admin.organization_name if parent_admin else "")
    user = User(
        username=form.username.data.strip(),
        email=form.email.data.strip().lower(),
        first_name=first_name,
        last_name=last_name,
        role=form.role.data,
        is_active=bool(form.is_active.data),
        admin_id=parent_admin.id if parent_admin and form.role.data != Role.ADMIN.value else None,
        organization_id=parent_admin.id if parent_admin and form.role.data != Role.ADMIN.value else None,
        organization_name=org_name or None,
        managed_by_user_id=parent_admin.id if parent_admin and form.role.data in {Role.SUB_ADMIN.value, Role.TEACHER.value} else None,
    )
    user.set_password(form.password.data)
    db.session.add(user)
    db.session.commit()
    try:
        seed_default_rbac()
    except Exception:
        db.session.rollback()
    return True, "created"


def _admin_scope_choices(include_none: bool = True):
    rows = User.query.filter(User.role == Role.ADMIN.value).order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast(), User.created_at.desc()).all()
    choices = []
    if include_none:
        choices.append((0, "Standalone admin / direct owner"))
    for row in rows:
        label = row.organization_name or row.full_name
        choices.append((row.id, f"{label} ({row.full_name})" if row.organization_name else row.full_name))
    return choices


def _teacher_choices_for_superadmin(include_none: bool = True):
    rows = User.query.filter_by(role=Role.TEACHER.value).order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast(), User.created_at.desc()).all()
    choices = []
    if include_none:
        choices.append((0, "Not assigned yet"))
    for row in rows:
        org = row.organization_name or (row.organization.full_name if row.organization else None)
        label = f"{row.full_name} • {org}" if org else row.full_name
        choices.append((row.id, label))
    return choices


def _manager_choices_for_superadmin(include_none: bool = True):
    rows = User.query.filter(User.role.in_([Role.ADMIN.value, Role.SUB_ADMIN.value])).order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast()).all()
    choices = []
    if include_none:
        choices.append((0, "Auto / none"))
    for row in rows:
        label = row.organization_name or row.full_name
        choices.append((row.id, f"{label} ({row.role_code})"))
    return choices


def _apply_admin_management_choices(form):
    if hasattr(form, "parent_admin_id"):
        form.parent_admin_id.choices = _admin_scope_choices(include_none=True)
    if hasattr(form, "organization_id"):
        form.organization_id.choices = [(0, "Independent learner")] + _admin_scope_choices(include_none=False)
    if hasattr(form, "teacher_id"):
        form.teacher_id.choices = _teacher_choices_for_superadmin(include_none=True)
    if hasattr(form, "managed_by_user_id"):
        form.managed_by_user_id.choices = _manager_choices_for_superadmin(include_none=True)

def validate_student_linkage(selected_org_id: int | None, selected_teacher_id: int | None):
    selected_org_id = int(selected_org_id or 0)
    selected_teacher_id = int(selected_teacher_id or 0)

    teacher = None
    if selected_teacher_id:
        teacher = User.query.filter_by(id=selected_teacher_id, role=Role.TEACHER.value).first()
        if not teacher:
            return False, "Selected teacher was not found.", None

        teacher_org_id = int(teacher.organization_id or 0)
        if selected_org_id and teacher_org_id and teacher_org_id != selected_org_id:
            return False, "Selected teacher does not belong to the selected institute.", None

    return True, None, teacher


def apply_student_ownership(student, selected_org_id: int | None, selected_teacher_id: int | None, managed_by_user_id=None):
    selected_org_id = int(selected_org_id or 0)
    selected_teacher_id = int(selected_teacher_id or 0)
    managed_by_user_id = int(managed_by_user_id or 0)

    student.organization_id = selected_org_id or None
    student.admin_id = selected_org_id or None
    student.teacher_id = selected_teacher_id or None

    if managed_by_user_id:
        student.managed_by_user_id = managed_by_user_id
    elif selected_org_id:
        student.managed_by_user_id = selected_org_id
    else:
        student.managed_by_user_id = None

    if selected_org_id:
        admin_user = User.query.get(selected_org_id)
        if admin_user:
            student.organization_name = admin_user.organization_name or admin_user.full_name
    else:
        student.organization_name = None

        
def _institute_rows():
    mapped = []
    admins = (
        User.query
        .filter(User.role == Role.ADMIN.value)
        .order_by(User.organization_name.asc().nullslast(), User.first_name.asc().nullslast(), User.id.asc())
        .all()
    )
    for admin in admins:
        mapped.append({
            "organization_id": admin.id,
            "name": admin.organization_name or admin.full_name or "Unknown Institute",
            "admin_name": admin.full_name,
            "student_count": User.query.filter_by(role=Role.STUDENT.value, organization_id=admin.id).count(),
            "teacher_count": User.query.filter_by(role=Role.TEACHER.value, organization_id=admin.id).count(),
            "sub_admin_count": User.query.filter_by(role=Role.SUB_ADMIN.value, organization_id=admin.id).count(),
        })
    return mapped


def _staff_query_for_superadmin(filter_role: str | None = None, parent_admin_id: int | None = None, q: str | None = None):
    query = User.query.filter(User.role.in_([Role.ADMIN.value, Role.SUB_ADMIN.value, Role.TEACHER.value, Role.SEO.value, Role.ACCOUNTS.value, Role.SUPPORT.value, Role.EDITOR.value]))
    if filter_role:
        query = query.filter(User.role == filter_role)
    if parent_admin_id:
        query = query.filter(or_(User.id == parent_admin_id, User.admin_id == parent_admin_id, User.organization_id == parent_admin_id))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.first_name.ilike(like), User.last_name.ilike(like), User.username.ilike(like), User.email.ilike(like), User.organization_name.ilike(like)))
    return query.order_by(User.created_at.desc())


def _student_query_for_superadmin(q: str | None = None, admin_id: int | None = None, teacher_id: int | None = None):
    query = User.query.filter_by(role=Role.STUDENT.value)
    if admin_id:
        query = query.filter(or_(User.organization_id == admin_id, User.admin_id == admin_id, User.managed_by_user_id == admin_id))
    if teacher_id:
        query = query.filter(User.teacher_id == teacher_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.first_name.ilike(like), User.last_name.ilike(like), User.username.ilike(like), User.email.ilike(like), User.organization_name.ilike(like)))
    return query.order_by(User.created_at.desc())


def _apply_language_choices(*forms):
    choices = language_choices(enabled_only=True, include_codes=True)
    for form in forms:
        if not form:
            continue
        if hasattr(form, "lang_code"):
            form.lang_code.choices = choices
        if hasattr(form, "language_code"):
            form.language_code.choices = choices


def _build_course_tree(course: Course) -> dict:
    levels_payload = []
    for level in course.levels:
        lessons_payload = []
        for lesson in level.lessons:
            chapters_payload = []
            for chapter in lesson.chapters:
                subs_payload = []
                for subsection in chapter.subsections:
                    subs_payload.append({
                        "id": subsection.id,
                        "name": subsection.title,
                        "questions": len(subsection.questions),
                    })
                chapters_payload.append({
                    "id": chapter.id,
                    "name": chapter.title,
                    "subsections": subs_payload,
                    "questions": sum(s["questions"] for s in subs_payload),
                })
            lessons_payload.append({
                "id": lesson.id,
                "number": lesson.sort_order or lesson.id,
                "name": lesson.title,
                "chapters": chapters_payload,
                "questions": sum(ch["questions"] for ch in chapters_payload),
            })
        levels_payload.append({
            "id": level.id,
            "number": level.sort_order or level.id,
            "name": level.title,
            "lessons": lessons_payload,
            "questions": sum(ls["questions"] for ls in lessons_payload),
        })
    return {
        "id": course.id,
        "title": course.title,
        "levels": levels_payload,
        "question_count": course.question_count,
        "lesson_count": course.lesson_count,
    }


def _course_card_payload(course: Course) -> dict:
    metrics = LMSService.course_metrics(course.id)
    coupon_count = course.coupons.count() if hasattr(course.coupons, "count") else len(getattr(course, "coupons", []) or [])
    return {
        "id": course.id,
        "title": course.title,
        "slug": course.slug,
        "status": course.status,
        "difficulty": course.difficulty or "basic",
        "max_level": getattr(course, "max_level", 1) or 1,
        "access_type": (getattr(course, "access_type", None) or ("paid" if course.is_premium else "free")),
        "is_published": bool(course.is_published),
        "is_premium": bool(course.is_premium),
        "is_free": not bool(course.is_premium) or float(course.current_price or 0) <= 0,
        "current_price": float(course.current_price or 0),
        "base_price": float(course.base_price or 0),
        "sale_price": float(course.sale_price or 0) if course.sale_price is not None else None,
        "levels": len(course.levels),
        "lessons": metrics.get("lesson_count", 0),
        "questions": metrics.get("question_count", 0),
        "students": metrics.get("enrollments", 0),
        "coupons": coupon_count,
        "updated_at": course.updated_at,
    }


@bp.get("/dashboard")
@login_required
@require_role("SUPERADMIN")
def dashboard():
    staff_roles = [Role.ADMIN.value, Role.SUB_ADMIN.value, Role.SEO.value, Role.ACCOUNTS.value, Role.SUPPORT.value, Role.EDITOR.value, Role.TEACHER.value]
    paid_payments = Payment.query.filter_by(status="paid").all()
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    year_start = datetime(now.year, 1, 1)
    stats = {
        "admins": User.query.filter(User.role.in_(staff_roles)).count(),
        "students": User.query.filter_by(role=Role.STUDENT.value).count(),
        "courses": Course.query.count(),
        "enrollments": Enrollment.query.count(),
        "attempts": QuestionAttempt.query.count(),
        "total_students": User.query.filter_by(role=Role.STUDENT.value).count(),
        "total_admins": User.query.filter(User.role.in_(staff_roles)).count(),
        "live_students": User.query.filter_by(role=Role.STUDENT.value, is_active=True).count(),
        "published_pages": Page.query.filter_by(is_published=True).count(),
        "monthly_revenue": sum(float(row.final_amount or 0) for row in paid_payments if (row.paid_at or row.created_at) and (row.paid_at or row.created_at) >= month_start),
        "yearly_revenue": sum(float(row.final_amount or 0) for row in paid_payments if (row.paid_at or row.created_at) and (row.paid_at or row.created_at) >= year_start),
        "course_sales": len(paid_payments),
        "total_api_logs": ApiCallLog.query.count(),
        "enabled_languages": Language.query.filter_by(is_enabled=True).count(),
        "language_records": Language.query.count(),
        "organization_learners": User.query.filter(User.role == Role.STUDENT.value, User.admin_id.isnot(None)).count(),
        "independent_learners": User.query.filter(User.role == Role.STUDENT.value, User.admin_id.is_(None)).count(),
        "teacher_accounts": User.query.filter_by(role=Role.TEACHER.value).count(),
    }
    provider = get_primary_provider()
    stats["translation_provider_name"] = provider.name or provider.provider_label
    stats["translation_provider_type"] = provider.provider_label
    stats["translation_credits_left"] = provider.credits_remaining
    stats["translation_credit_unit"] = provider.credit_unit or "credits"
    stats["translation_provider_enabled"] = bool(provider.is_enabled)
    recent_courses = Course.query.order_by(Course.created_at.desc()).limit(8).all()
    recent_logins = LoginEvent.query.order_by(LoginEvent.created_at.desc()).limit(10).all()
    chart_data = superadmin_chart_payload()
    ai_capabilities = _superadmin_ai_capability_rows()
    ai_quick_links = _superadmin_ai_quick_links()
    ai_usage = _superadmin_ai_usage_snapshot()
    live_workspace = _superadmin_live_workspace_snapshot()
    phase18_status = [
        {
            "label": "UI inconsistency",
            "state": "partial",
            "detail": "Shared dashboard and public shells are in place, but some legacy pages still rely on older one-off layouts.",
        },
        {
            "label": "Color mismatch",
            "state": "partial",
            "detail": "Theme tokens are centralized, but overlapping override layers still create uneven color behavior on some pages.",
        },
        {
            "label": "Spacing issues",
            "state": "partial",
            "detail": "Phase 18 spacing polish exists, but older templates still use uneven container and card spacing.",
        },
        {
            "label": "Component inconsistency",
            "state": "partial",
            "detail": "Buttons, cards, pills, and forms are more aligned now, yet some feature pages still keep their own component styling.",
        },
        {
            "label": "Route cleanup",
            "state": "partial",
            "detail": "Major student routing cleanup is done, but fallback and legacy continue-flow logic still exists in a few places.",
        },
        {
            "label": "Error handling",
            "state": "ready",
            "detail": "Dedicated 404 and 500 recovery pages are active, though some flows still need more user-friendly inline handling.",
        },
        {
            "label": "Performance",
            "state": "partial",
            "detail": "The app is stable, but dashboard/public layouts still load a heavy CSS stack and some pages do more work than needed.",
        },
        {
            "label": "CSS structure",
            "state": "partial",
            "detail": "Theme and polish files are working, but the stack still contains multiple bridge/fix layers that should be consolidated.",
        },
        {
            "label": "Dark/light theme sync",
            "state": "partial",
            "detail": "Per-user theme mode is now wired to tokens, but a full page-by-page audit is still needed for perfect parity.",
        },
        {
            "label": "Final polish",
            "state": "partial",
            "detail": "The platform is much closer, but a final consistency pass is still needed for a fully premium professional finish.",
        },
    ]
    return render_template(
        "superadmin/dashboard.html",
        stats=stats,
        metrics=stats,
        recent_courses=recent_courses,
        recent_logins=recent_logins,
        chart_data=chart_data,
        ai_capabilities=ai_capabilities,
        ai_quick_links=ai_quick_links,
        ai_usage=ai_usage,
        live_workspace=live_workspace,
        phase18_status=phase18_status,
    )




def _normalize_course_track_type(value: str | None) -> str:
    raw = (value or '').strip().lower()
    alias_map = {
        'spoken': 'speaking',
        'topic': 'speaking',
        'grammar': 'writing',
    }
    normalized = alias_map.get(raw, raw)
    return normalized if normalized in {'speaking', 'interview', 'reading', 'writing', 'listening'} else 'speaking'
def _track_label(value: str | None) -> str:
    return _normalize_course_track_type(value).replace('_', ' ').title()


def _safe_ratio(part: int | float, whole: int | float) -> int:
    try:
        whole_value = float(whole or 0)
    except Exception:
        whole_value = 0.0
    if whole_value <= 0:
        return 0
    try:
        part_value = float(part or 0)
    except Exception:
        part_value = 0.0
    return int(round((part_value / whole_value) * 100))


def _course_content_snapshot(course: Course) -> dict:
    track = _normalize_course_track_type(course.track_type)
    payload = {
        'track': track,
        'ready': False,
        'label': 'Needs setup',
        'content_count': 0,
        'note': 'No content connected yet.',
    }

    if track == 'speaking':
        topics = [topic for topic in course.speaking_topics if getattr(topic, 'is_active', True)]
        prompt_count = sum(topic.prompts.filter_by(is_active=True).count() if hasattr(topic, 'prompts') else 0 for topic in topics)
        payload.update({
            'content_count': prompt_count or len(topics),
            'ready': bool(topics and prompt_count > 0),
            'label': 'Prompts ready' if topics and prompt_count > 0 else 'Prompts missing',
            'note': f'{len(topics)} topics • {prompt_count} active prompts',
        })
        return payload

    if track == 'interview':
        interview_lessons = [lesson for level in course.levels for lesson in level.lessons if (lesson.lesson_type or '').strip().lower() == 'interview']
        sessions_seeded = len(course.interview_profiles or [])
        payload.update({
            'content_count': len(interview_lessons),
            'ready': bool(interview_lessons),
            'label': 'Interview flow ready' if interview_lessons else 'Interview lesson missing',
            'note': f'{len(interview_lessons)} interview lessons • {sessions_seeded} profiles',
        })
        return payload

    if track == 'writing':
        tasks = [task for task in course.writing_tasks if getattr(task, 'is_active', True) and getattr(task, 'is_published', True)]
        payload.update({
            'content_count': len(tasks),
            'ready': bool(tasks),
            'label': 'Tasks ready' if tasks else 'Tasks missing',
            'note': f'{len(tasks)} published writing tasks',
        })
        return payload

    if track == 'reading':
        passages = [passage for passage in course.reading_passages if getattr(passage, 'is_published', False)]
        question_count = sum(passage.questions.count() for passage in passages)
        payload.update({
            'content_count': question_count or len(passages),
            'ready': bool(passages and question_count > 0),
            'label': 'Passages ready' if passages and question_count > 0 else 'Passages incomplete',
            'note': f'{len(passages)} published passages • {question_count} questions',
        })
        return payload

    listening_lessons = [lesson for level in course.levels for lesson in level.lessons if (lesson.lesson_type or '').strip().lower() == 'listening' and bool(getattr(lesson, 'is_published', False))]
    listening_questions = sum(lesson.question_count for lesson in listening_lessons)
    payload.update({
        'content_count': listening_questions or len(listening_lessons),
        'ready': bool(listening_lessons and listening_questions > 0),
        'label': 'Listening ready' if listening_lessons and listening_questions > 0 else 'Listening content incomplete',
        'note': f'{len(listening_lessons)} published lessons • {listening_questions} questions',
    })
    return payload


def _course_activity_snapshot(course: Course, active_since: datetime) -> dict:
    enrollment_rows = [row for row in course.enrollments if (row.status or 'active').lower() == 'active']
    enrolled_count = len(enrollment_rows)
    enrolled_students = {row.student_id for row in enrollment_rows}

    progress_rows = CourseProgress.query.filter_by(course_id=course.id).all()
    progress_map = {row.student_id: row for row in progress_rows}
    started_students = set(progress_map.keys())
    active_students = {row.student_id for row in progress_rows if row.last_activity_at and row.last_activity_at >= active_since}
    completion_values = [int(row.completion_percent or 0) for row in progress_rows]
    score_values = [float(row.average_accuracy or 0) for row in progress_rows if row.average_accuracy is not None]
    last_activity_values = [row.last_activity_at for row in progress_rows if row.last_activity_at]

    track = _normalize_course_track_type(course.track_type)

    if track == 'speaking':
        sessions = SpeakingSession.query.filter_by(course_id=course.id).all()
        started_students.update(session.student_id for session in sessions)
        active_students.update(session.student_id for session in sessions if max([value for value in [session.updated_at, session.last_submitted_at, session.ended_at, session.created_at] if value] or [None]) and max([value for value in [session.updated_at, session.last_submitted_at, session.ended_at, session.created_at] if value]) >= active_since)
        last_activity_values.extend(max([value for value in [session.updated_at, session.last_submitted_at, session.ended_at, session.created_at] if value]) for session in sessions if [value for value in [session.updated_at, session.last_submitted_at, session.ended_at, session.created_at] if value])
    elif track == 'interview':
        sessions = InterviewSession.query.filter_by(course_id=course.id).all()
        started_students.update(session.student_id for session in sessions)
        active_students.update(session.student_id for session in sessions if max([value for value in [session.updated_at, session.ended_at, session.started_at, session.created_at] if value] or [None]) and max([value for value in [session.updated_at, session.ended_at, session.started_at, session.created_at] if value]) >= active_since)
        score_values.extend(float(session.final_score or 0) for session in sessions if session.final_score is not None)
        completion_values.extend(int(round(float(session.completion_percent or 0))) for session in sessions if session.completion_percent is not None)
        last_activity_values.extend(max([value for value in [session.updated_at, session.ended_at, session.started_at, session.created_at] if value]) for session in sessions if [value for value in [session.updated_at, session.ended_at, session.started_at, session.created_at] if value])
    elif track == 'writing':
        submissions = WritingSubmission.query.filter_by(course_id=course.id).all()
        started_students.update(submission.student_id for submission in submissions)
        active_students.update(submission.student_id for submission in submissions if max([value for value in [submission.updated_at, submission.submitted_at, submission.created_at] if value] or [None]) and max([value for value in [submission.updated_at, submission.submitted_at, submission.created_at] if value]) >= active_since)
        score_values.extend(float(submission.score or 0) for submission in submissions if submission.score is not None)
        last_activity_values.extend(max([value for value in [submission.updated_at, submission.submitted_at, submission.created_at] if value]) for submission in submissions if [value for value in [submission.updated_at, submission.submitted_at, submission.created_at] if value])
    else:
        attempts = (
            QuestionAttempt.query
            .join(Lesson, Lesson.id == QuestionAttempt.lesson_id)
            .join(Level, Level.id == Lesson.level_id)
            .filter(Level.course_id == course.id)
            .all()
        )
        started_students.update(attempt.student_id for attempt in attempts)
        active_students.update(attempt.student_id for attempt in attempts if attempt.attempted_at and attempt.attempted_at >= active_since)
        score_values.extend(float(attempt.accuracy_score or 0) for attempt in attempts if attempt.accuracy_score is not None)
        last_activity_values.extend(attempt.attempted_at for attempt in attempts if attempt.attempted_at)

    started_count = len(started_students & (enrolled_students or started_students)) if enrolled_students else len(started_students)
    active_count = len(active_students & (enrolled_students or active_students)) if enrolled_students else len(active_students)
    inactive_count = max(enrolled_count - active_count, 0)
    average_completion = int(round(sum(completion_values) / len(completion_values))) if completion_values else 0
    average_score = round(sum(score_values) / len(score_values), 1) if score_values else 0.0
    last_activity_at = max(last_activity_values) if last_activity_values else None
    active_ratio = _safe_ratio(active_count, enrolled_count)

    if active_count == 0:
        engagement = 'No Activity'
        engagement_tone = 'danger' if enrolled_count else 'secondary'
    elif active_ratio >= 60:
        engagement = 'High'
        engagement_tone = 'success'
    elif active_ratio >= 25:
        engagement = 'Medium'
        engagement_tone = 'warning'
    else:
        engagement = 'Low'
        engagement_tone = 'danger'

    return {
        'enrolled_count': enrolled_count,
        'started_count': started_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'average_completion': average_completion,
        'average_score': average_score,
        'last_activity_at': last_activity_at,
        'engagement': engagement,
        'engagement_tone': engagement_tone,
        'active_ratio': active_ratio,
    }


def _course_publish_actor(course: Course):
    version_row = (
        ContentVersion.query
        .filter(ContentVersion.entity_type == 'course', ContentVersion.entity_id == course.id, ContentVersion.change_summary.ilike('%publish%'))
        .order_by(ContentVersion.created_at.desc(), ContentVersion.id.desc())
        .first()
    )
    if version_row and version_row.created_by:
        return version_row.created_by
    return course.created_by or course.owner_admin


def _course_health_label(content_ready: bool, enrolled_count: int, active_count: int, last_activity_at: datetime | None) -> tuple[str, str]:
    if not content_ready:
        return 'Broken', 'danger'
    if enrolled_count == 0:
        return 'Needs Attention', 'warning'
    if active_count == 0:
        return 'Dormant', 'secondary'
    if last_activity_at and last_activity_at < datetime.utcnow() - timedelta(days=14):
        return 'Dormant', 'secondary'
    if active_count < max(1, int(round(enrolled_count * 0.25))):
        return 'Needs Attention', 'warning'
    return 'Healthy', 'success'


def _build_publishing_review_payload(filters: dict[str, str]) -> dict:
    now = datetime.utcnow()
    active_since = now - timedelta(days=7)
    recent_since = now - timedelta(days=7)
    stale_since = now - timedelta(days=14)

    query = Course.query.filter(Course.status != 'archived')
    if (filters.get('status') or 'published') == 'published':
        query = query.filter(Course.is_published.is_(True))
    elif filters.get('status') == 'draft':
        query = query.filter(Course.is_published.is_(False))

    course_rows = query.order_by(Course.published_at.desc().nullslast(), Course.updated_at.desc(), Course.id.desc()).all()

    rows = []
    alerts = []
    for course in course_rows:
        track = _normalize_course_track_type(course.track_type)
        if filters.get('track') and filters['track'] != 'all' and track != filters['track']:
            continue
        if filters.get('level') and filters['level'] != 'all':
            difficulty = (course.difficulty or '').strip().lower()
            if difficulty != filters['level']:
                continue
        if filters.get('access') and filters['access'] != 'all':
            if (course.access_type or 'free').strip().lower() != filters['access']:
                continue
        search = (filters.get('q') or '').strip().lower()
        if search and search not in (course.title or '').lower() and search not in (course.description or '').lower():
            continue

        content = _course_content_snapshot(course)
        activity = _course_activity_snapshot(course, active_since)
        health_label, health_tone = _course_health_label(content['ready'], activity['enrolled_count'], activity['active_count'], activity['last_activity_at'])
        publish_actor = _course_publish_actor(course)
        published_at = course.published_at or course.updated_at or course.created_at

        row = {
            'course': course,
            'course_id': course.id,
            'title': course.title,
            'track': track,
            'track_label': _track_label(track),
            'difficulty': (course.difficulty or 'General').replace('_', ' ').title(),
            'published_at': published_at,
            'published_by': publish_actor.full_name if publish_actor else 'System',
            'content': content,
            'activity': activity,
            'health_label': health_label,
            'health_tone': health_tone,
            'open_url': url_for('superadmin.course_detail', course_id=course.id),
            'review_url': url_for('superadmin.course_detail', course_id=course.id, tab='preview'),
        }

        engagement_filter = (filters.get('engagement') or 'all').strip().lower()
        if engagement_filter != 'all' and activity['engagement'].lower().replace(' ', '_') != engagement_filter:
            continue

        rows.append(row)

        if not content['ready']:
            alerts.append({'tone': 'danger', 'course_title': course.title, 'message': f"Published course is missing {content['track']} content.", 'open_url': row['review_url']})
        if activity['enrolled_count'] == 0:
            alerts.append({'tone': 'warning', 'course_title': course.title, 'message': 'Published but no students are enrolled yet.', 'open_url': row['open_url']})
        if activity['enrolled_count'] > 0 and activity['active_count'] == 0:
            alerts.append({'tone': 'secondary', 'course_title': course.title, 'message': 'Students enrolled but no recent activity in the last 7 days.', 'open_url': row['open_url']})
        if activity['average_completion'] < 10 and activity['started_count'] > 0:
            alerts.append({'tone': 'warning', 'course_title': course.title, 'message': 'Course has low completion even after students started.', 'open_url': row['open_url']})
        if activity['last_activity_at'] and activity['last_activity_at'] < stale_since:
            alerts.append({'tone': 'secondary', 'course_title': course.title, 'message': 'No meaningful student activity in the last 14 days.', 'open_url': row['open_url']})

    rows.sort(key=lambda item: ((item['published_at'] or datetime.min), item['course_id']), reverse=True)

    timeline_rows = []
    version_rows = (
        ContentVersion.query
        .filter(ContentVersion.entity_type == 'course')
        .order_by(ContentVersion.created_at.desc(), ContentVersion.id.desc())
        .limit(80)
        .all()
    )
    course_map = {row['course_id']: row for row in rows}
    for version in version_rows:
        summary = (version.change_summary or '').strip()
        if not summary:
            continue
        lower = summary.lower()
        if 'publish' not in lower and 'review' not in lower and 'archive' not in lower:
            continue
        if version.entity_id not in course_map:
            continue
        course_row = course_map[version.entity_id]
        timeline_rows.append({
            'timestamp': version.created_at,
            'course_title': course_row['title'],
            'track_label': course_row['track_label'],
            'action': summary,
            'actor_name': version.created_by.full_name if version.created_by else course_row['published_by'],
            'open_url': course_row['open_url'],
        })
        if len(timeline_rows) >= 12:
            break
    if not timeline_rows:
        for row in rows[:12]:
            timeline_rows.append({
                'timestamp': row['published_at'],
                'course_title': row['title'],
                'track_label': row['track_label'],
                'action': 'Published',
                'actor_name': row['published_by'],
                'open_url': row['open_url'],
            })

    summary = {
        'total_published': len(rows),
        'published_recent': sum(1 for row in rows if row['published_at'] and row['published_at'] >= recent_since),
        'total_enrolled': sum(row['activity']['enrolled_count'] for row in rows),
        'active_students': sum(row['activity']['active_count'] for row in rows),
        'low_engagement': sum(1 for row in rows if row['activity']['engagement'] in {'Low', 'No Activity'}),
        'zero_enrollment': sum(1 for row in rows if row['activity']['enrolled_count'] == 0),
    }

    return {
        'rows': rows,
        'alerts': alerts[:12],
        'timeline_rows': timeline_rows,
        'summary': summary,
        'filters': filters,
        'filter_options': {
            'tracks': [('all', 'All tracks'), ('speaking', 'Speaking'), ('writing', 'Writing'), ('reading', 'Reading'), ('listening', 'Listening'), ('interview', 'Interview')],
            'engagement': [('all', 'All engagement'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'), ('no_activity', 'No activity')],
            'access': [('all', 'Free + paid'), ('free', 'Free'), ('paid', 'Paid')],
            'statuses': [('published', 'Published'), ('draft', 'Draft / hidden')],
        },
    }


@bp.route("/publishing-review", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def publishing_review_dashboard():
    if request.method == 'POST':
        course_id = int(request.form.get('course_id') or 0)
        action = (request.form.get('action') or '').strip().lower()
        course = Course.query.get_or_404(course_id)
        if action == 'publish':
            LMSService.publish_course(course, current_user.id)
            flash('Course published.', 'success')
        elif action in {'unpublish', 'archive', 'restore'}:
            LMSService.set_course_status(course, action)
            flash(f'Course status updated: {action.replace("_", " ")}.', 'success')
        else:
            flash('Unsupported dashboard action.', 'warning')
        return redirect(url_for('superadmin.publishing_review_dashboard', **request.args.to_dict()))

    filters = {
        'track': (request.args.get('track') or 'all').strip().lower(),
        'level': (request.args.get('level') or 'all').strip().lower(),
        'engagement': (request.args.get('engagement') or 'all').strip().lower(),
        'access': (request.args.get('access') or 'all').strip().lower(),
        'status': (request.args.get('status') or 'published').strip().lower(),
        'q': (request.args.get('q') or '').strip(),
    }
    payload = _build_publishing_review_payload(filters)
    return render_template(
        'superadmin/publishing_review.html',
        rows=payload['rows'],
        alerts=payload['alerts'],
        timeline_rows=payload['timeline_rows'],
        summary=payload['summary'],
        filters=payload['filters'],
        filter_options=payload['filter_options'],
        panel_role='superadmin',
    )


@bp.route("/courses", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def courses():
    form = CourseForm()
    _apply_language_choices(form)

    if request.method == "POST":
        action = (request.form.get("action") or "create_course").strip().lower()
        if action == "create_nursery_starter":
            try:
                course, created = LMSService.create_nursery_image_starter_course(
                    owner_admin_id=current_user.id,
                    created_by_id=current_user.id,
                )
                flash(
                    "Nursery image practice course created successfully." if created else "Nursery image practice course already exists.",
                    "success",
                )
                return redirect(url_for("superadmin.course_detail", course_id=course.id))
            except Exception as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        elif form.validate_on_submit():
            try:
                course = LMSService.create_course(
                    title=form.title.data,
                    owner_admin_id=current_user.id,
                    created_by_id=current_user.id,
                    slug=form.slug.data,
                    description=form.description.data,
                    language_code=form.language_code.data,
                    track_type=form.track_type.data,
                    difficulty=form.difficulty.data,
                    currency_code=form.currency_code.data,
                    max_level=form.max_level.data,
                    access_type=form.access_type.data,
                    allow_level_purchase=form.allow_level_purchase.data,
                    level_access_type=form.level_access_type.data,
                    base_price=form.base_price.data,
                    sale_price=form.sale_price.data,
                    level_price=form.level_price.data,
                    level_sale_price=form.level_sale_price.data,
                    level_title=form.level_title.data,
                    lesson_title=form.lesson_title.data,
                    lesson_type=form.lesson_type.data,
                    explanation_text=form.explanation_text.data,
                    grammar_formula=form.grammar_formula.data,
                    badge_title=form.badge_title.data,
                    badge_subtitle=form.badge_subtitle.data,
                    badge_template=form.badge_template.data,
                    badge_animation=form.badge_animation.data,
                    is_published=form.is_published.data,
                    is_premium=form.is_premium.data,
                )
                audit("superadmin_course_create", target=str(course.id), meta=course.slug)
                flash("Course created successfully.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id, tab="settings", _anchor="course-settings"))
            except Exception as exc:
                flash(str(exc), "danger")
        else:
            flash("Please correct the highlighted course form errors.", "warning")

    q = (request.args.get("q") or "").strip().lower()
    sort = (request.args.get("sort") or "latest").strip().lower()
    status = (request.args.get("status") or "").strip().lower()

    items = Course.query.all()
    if q:
        items = [c for c in items if q in (c.title or "").lower() or q in (c.slug or "").lower()]
    if status:
        items = [c for c in items if (c.status or "").lower() == status]

    if sort == "title":
        items = sorted(items, key=lambda c: (c.title or "").lower())
    elif sort == "price_low":
        items = sorted(items, key=lambda c: float(c.current_price or 0))
    elif sort == "price_high":
        items = sorted(items, key=lambda c: float(c.current_price or 0), reverse=True)
    else:
        items = sorted(items, key=lambda c: c.created_at, reverse=True)

    course_cards = [_course_card_payload(c) for c in items]
    coupon_form = CouponForm()

    return render_template(
        "superadmin/courses.html",
        form=form,
        course_cards=course_cards,
        current_query=q,
        current_sort=sort,
        current_status=status,
        panel_role="superadmin",
        coupon_form=coupon_form,
    )


@bp.route("/coupons", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def coupons():
    form = CouponForm()
    form.course_id.choices = [(0, "All courses")] + [(c.id, c.title) for c in Course.query.order_by(Course.title.asc()).all()]

    if form.validate_on_submit():
        coupon = Coupon(
            code=(form.code.data or "").strip().upper(),
            title=form.title.data,
            description=form.description.data,
            discount_type=form.discount_type.data,
            discount_value=form.discount_value.data or 0,
            min_order_amount=form.min_order_amount.data or 0,
            usage_limit_total=form.usage_limit_total.data,
            usage_limit_per_user=form.usage_limit_per_user.data or 1,
            valid_from=datetime.combine(form.valid_from.data, datetime.min.time()) if form.valid_from.data else None,
            valid_until=datetime.combine(form.valid_until.data, datetime.max.time()) if form.valid_until.data else None,
            is_active=form.is_active.data,
            course_id=form.course_id.data or None,
            created_by_id=current_user.id,
        )
        db.session.add(coupon)
        db.session.commit()
        flash("Coupon created successfully.", "success")
        return redirect(url_for("superadmin.coupons"))

    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template("superadmin/coupons.html", form=form, coupons=coupons, panel_role="superadmin")


@bp.get("/lessons")
@login_required
@require_role("SUPERADMIN")
def lessons_index():
    lessons = Lesson.query.join(Level, Level.id == Lesson.level_id).join(Course, Course.id == Level.course_id).order_by(Course.title.asc(), Level.sort_order.asc(), Lesson.sort_order.asc()).all()
    return render_template("superadmin/lessons.html", lessons=lessons, panel_role="superadmin")


@bp.get("/questions/upload-template.csv")
@login_required
@require_role("SUPERADMIN")
def question_upload_template():
    return Response(
        LMSService.question_upload_template_csv(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fluencify-question-upload-template.csv"'},
    )




@bp.route("/lessons/<int:lesson_id>", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def lesson_detail(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course
    if not course:
        flash("Linked course was not found.", "warning")
        return redirect(url_for("superadmin.lessons_index"))

    lesson_form = LessonForm(prefix="lesson")
    upload_form = QuestionUploadForm(prefix="upload")
    delete_form = DeleteForm(prefix="delete")

    lesson_form.level_id.choices = [(lvl.id, lvl.title) for lvl in course.levels]
    upload_form.lesson_id.choices = [(lesson.id, f"{lesson.level.title} / {lesson.title}")]

    if request.method == "GET":
        lesson_form.level_id.data = lesson.level_id
        lesson_form.title.data = lesson.title
        lesson_form.slug.data = lesson.slug
        lesson_form.lesson_type.data = lesson.lesson_type
        lesson_form.explanation_text.data = lesson.explanation_text
        lesson_form.explanation_tts_text.data = lesson.explanation_tts_text
        lesson_form.estimated_minutes.data = lesson.estimated_minutes
        lesson_form.grammar_formula.data = next((s.grammar_formula for c in lesson.chapters for s in c.subsections if s.grammar_formula), "")
        lesson_form.is_published.data = lesson.is_published
        upload_form.lesson_id.data = lesson.id

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "save_lesson" and lesson_form.validate_on_submit():
                new_level_id = lesson_form.level_id.data or lesson.level_id
                if new_level_id != lesson.level_id:
                    target_level = Level.query.filter_by(id=new_level_id, course_id=course.id).first()
                    if not target_level:
                        raise ValueError("Selected level was not found for this course.")
                    lesson.level_id = target_level.id
                LMSService.update_lesson(
                    lesson,
                    title=lesson_form.title.data,
                    slug=lesson_form.slug.data,
                    lesson_type=lesson_form.lesson_type.data,
                    explanation_text=lesson_form.explanation_text.data,
                    explanation_tts_text=lesson_form.explanation_tts_text.data,
                    estimated_minutes=lesson_form.estimated_minutes.data,
                    is_published=lesson_form.is_published.data,
                )
                flash("Lesson updated successfully.", "success")
                return redirect(url_for("superadmin.lesson_detail", lesson_id=lesson.id))

            if action == "upload_questions" and upload_form.validate_on_submit():
                parsed = LMSService.parse_question_upload(upload_form.upload.data)
                if not parsed:
                    raise ValueError("The uploaded file did not contain any valid questions.")
                upload_issues = LMSService.validate_question_upload_rows(parsed)
                if upload_issues:
                    raise ValueError("Please fix the upload file first: " + " | ".join(upload_issues[:5]))
                count = LMSService.upload_questions_to_lesson(lesson, parsed, auto_split_size=upload_form.auto_split_size.data)
                flash(f"Uploaded {count} questions to this lesson.", "success")
                return redirect(url_for("superadmin.lesson_detail", lesson_id=lesson.id))

            if action == "delete_lesson":
                title = lesson.title
                LMSService.delete_lesson(lesson)
                flash(f'Lesson "{title}" deleted.', "success")
                return redirect(url_for("superadmin.lessons_index"))

            if action == "save_lesson":
                flash("Please correct the lesson form errors.", "warning")
            elif action == "upload_questions":
                flash("Please correct the upload form errors.", "warning")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")

    question_rows = (
        Question.query.join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .filter(Chapter.lesson_id == lesson.id)
        .order_by(Chapter.sort_order.asc(), Subsection.sort_order.asc(), Question.sort_order.asc())
        .all()
    )

    return render_template(
        "superadmin/lesson_detail.html",
        lesson=lesson,
        course=course,
        lesson_form=lesson_form,
        upload_form=upload_form,
        delete_form=delete_form,
        question_rows=question_rows,
        panel_role="superadmin",
    )


@bp.route("/chapters", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def chapters_index():
    delete_form = DeleteForm(prefix="delete")

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        if not delete_form.validate_on_submit():
            flash("Your session expired. Please try again.", "warning")
            return redirect(url_for("superadmin.chapters_index"))

        try:
            if action == "delete_chapter":
                chapter_id = int(request.form.get("chapter_id") or 0)
                chapter = Chapter.query.get(chapter_id)
                if not chapter:
                    raise ValueError("Chapter not found.")
                chapter_title = chapter.title
                LMSService.delete_chapter(chapter)
                flash(f'Chapter "{chapter_title}" deleted successfully.', "success")
                return redirect(url_for("superadmin.chapters_index"))

            flash("Unknown action.", "warning")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")
            return redirect(url_for("superadmin.chapters_index"))

    chapters = (
        Chapter.query
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .join(Course, Course.id == Level.course_id)
        .order_by(Course.title.asc(), Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc())
        .all()
    )
    return render_template("superadmin/chapters.html", chapters=chapters, delete_form=delete_form, panel_role="superadmin")


@bp.route("/chapters/<int:chapter_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def chapter_edit(chapter_id: int):
    chapter = (
        Chapter.query
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .join(Course, Course.id == Level.course_id)
        .filter(Chapter.id == chapter_id)
        .first_or_404()
    )

    form = ChapterForm(prefix="chapter")
    lessons = (
        Lesson.query
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == chapter.lesson.course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc())
        .all()
    )
    form.lesson_id.choices = [(lesson.id, f"{lesson.level.title} / {lesson.title}") for lesson in lessons]

    if request.method == "GET":
        form.lesson_id.data = chapter.lesson_id
        form.title.data = chapter.title
        form.description.data = chapter.description
        form.sort_order.data = chapter.sort_order

    if form.validate_on_submit():
        selected_lesson = next((lesson for lesson in lessons if lesson.id == form.lesson_id.data), None)
        if not selected_lesson:
            flash("Selected lesson was not found.", "warning")
            return redirect(url_for("superadmin.chapter_edit", chapter_id=chapter.id))

        chapter.lesson_id = selected_lesson.id
        chapter.title = (form.title.data or "").strip()
        chapter.description = (form.description.data or "").strip() or None
        chapter.sort_order = form.sort_order.data or 1
        db.session.commit()
        flash("Chapter updated successfully.", "success")
        return redirect(url_for("superadmin.chapters_index"))

    return render_template(
        "superadmin/chapter_edit.html",
        chapter=chapter,
        form=form,
        course=chapter.lesson.course,
        lesson=chapter.lesson,
        panel_role="superadmin",
    )


@bp.route("/questions", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def questions_index():
    delete_form = DeleteForm(prefix="bulk")

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        if not delete_form.validate_on_submit():
            flash("Your session expired. Please try again.", "warning")
            return redirect(url_for("superadmin.questions_index"))

        try:
            if action == "bulk_delete":
                raw_ids = request.form.getlist("question_ids")
                question_ids = [int(item) for item in raw_ids if str(item).isdigit()]
                if not question_ids:
                    raise ValueError("Select at least one question to delete.")

                questions = Question.query.filter(Question.id.in_(question_ids)).all()
                if not questions:
                    raise ValueError("Selected questions were not found.")

                deleted_count = 0
                for question in questions:
                    LMSService.delete_question(question)
                    deleted_count += 1

                flash(f"{deleted_count} question(s) deleted successfully.", "success")
                return redirect(url_for("superadmin.questions_index"))

            flash("Unknown action.", "warning")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")
            return redirect(url_for("superadmin.questions_index"))

    questions = (
        Question.query
        .join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .join(Course, Course.id == Level.course_id)
        .order_by(Course.title.asc(), Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc(), Question.sort_order.asc())
        .all()
    )
    return render_template("superadmin/questions.html", questions=questions, delete_form=delete_form, panel_role="superadmin")


@bp.route("/questions/<int:question_id>", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def question_detail(question_id: int):
    question = Question.query.get_or_404(question_id)
    question_form = QuestionForm(prefix="question")
    _apply_language_choices(question_form)
    delete_form = DeleteForm(prefix="delete")
    from_course_id = request.args.get("from_course_id", type=int)
    return_to = (request.args.get("return_to") or "").strip().lower()

    prev_question_id = None
    next_question_id = None

    question_scope = (
        Question.query
        .join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
    )

    if from_course_id:
        question_scope = question_scope.filter(Level.course_id == from_course_id)

    scoped_questions = question_scope.order_by(
        Level.sort_order.asc(),
        Lesson.sort_order.asc(),
        Chapter.sort_order.asc(),
        Subsection.sort_order.asc(),
        Question.sort_order.asc(),
        Question.id.asc(),
    ).all()

    scoped_ids = [item.id for item in scoped_questions]
    if question.id in scoped_ids:
        idx = scoped_ids.index(question.id)
        if idx > 0:
            prev_question_id = scoped_ids[idx - 1]
        if idx < len(scoped_ids) - 1:
            next_question_id = scoped_ids[idx + 1]

    subsections = (
        Subsection.query
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .join(Course, Course.id == Level.course_id)
        .order_by(
            Course.title.asc(),
            Level.sort_order.asc(),
            Lesson.sort_order.asc(),
            Chapter.sort_order.asc(),
            Subsection.sort_order.asc(),
        )
        .all()
    )
    question_form.subsection_id.choices = [
        (s.id, f"{s.chapter.lesson.course.title} / {s.chapter.lesson.title} / {s.chapter.title} / {s.title}")
        for s in subsections
    ]

    if request.method == "GET":
        question_form.subsection_id.data = question.subsection_id
        question_form.title.data = question.title
        question_form.prompt.data = question.prompt
        question_form.image_url.data = question.image_url
        question_form.prompt_type.data = question.prompt_type
        question_form.language_code.data = question.language_code
        question_form.hint_text.data = question.hint_text
        question_form.model_answer.data = question.model_answer
        question_form.evaluation_rubric.data = question.evaluation_rubric
        question_form.expected_keywords.data = question.expected_keywords
        question_form.is_active.data = question.is_active

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "save_question" and question_form.validate_on_submit():
                subsection = next((s for s in subsections if s.id == question_form.subsection_id.data), None)
                if not subsection:
                    raise ValueError("Selected subsection was not found.")
                question.subsection_id = subsection.id
                LMSService.update_question(
                    question,
                    title=question_form.title.data,
                    prompt=question_form.prompt.data,
                    image_url=question_form.image_url.data,
                    prompt_type=question_form.prompt_type.data,
                    language_code=question_form.language_code.data,
                    hint_text=question_form.hint_text.data,
                    model_answer=question_form.model_answer.data,
                    evaluation_rubric=question_form.evaluation_rubric.data,
                    expected_keywords=question_form.expected_keywords.data,
                    is_active=question_form.is_active.data,
                )
                flash("Question updated successfully.", "success")
                return redirect(url_for("superadmin.question_detail", question_id=question.id))

            if action == "delete_question":
                prompt_preview = (question.prompt or "Question").strip()[:60]
                LMSService.delete_question(question)
                flash(f'Question "{prompt_preview}" deleted.', "success")
                return redirect(url_for("superadmin.questions_index"))

            if action == "save_question":
                flash("Please correct the highlighted question form errors.", "warning")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")

    return render_template(
        "superadmin/question_detail.html",
        question=question,
        question_form=question_form,
        delete_form=delete_form,
        panel_role="superadmin",
        from_course_id=from_course_id,
        return_to=return_to,
        prev_question_id=prev_question_id,
        next_question_id=next_question_id,
    )


@bp.get("/bulk-upload")
@login_required
@require_role("SUPERADMIN")
def bulk_upload_index():
    courses = Course.query.order_by(Course.title.asc()).all()
    return render_template("superadmin/bulk_upload.html", courses=courses, panel_role="superadmin")


@bp.route("/nursery-studio", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def nursery_studio():
    course, created = LMSService.create_nursery_image_starter_course(
        owner_admin_id=current_user.id,
        created_by_id=current_user.id,
    )
    if created:
        flash("Nursery image practice course was created automatically for the studio.", "success")

    question_form = QuestionForm(prefix="question")
    upload_form = QuestionUploadForm(prefix="upload")
    _apply_language_choices(question_form)

    lessons = (
        Lesson.query.join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc())
        .all()
    )
    subsections = (
        Subsection.query.join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc())
        .all()
    )

    question_form.subsection_id.choices = [
        (s.id, f"{s.chapter.lesson.title} / {s.chapter.title} / {s.title}") for s in subsections
    ]
    upload_form.lesson_id.choices = [(lesson.id, f"{lesson.level.title} / {lesson.title}") for lesson in lessons]

    nursery_dir = os.path.join(current_app.root_path, "static", "uploads", "questions", "nursery")
    os.makedirs(nursery_dir, exist_ok=True)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "add_question" and question_form.validate_on_submit():
                subsection = next((s for s in subsections if s.id == question_form.subsection_id.data), None)
                if not subsection:
                    raise ValueError("Selected subsection was not found.")
                LMSService.add_question(
                    subsection=subsection,
                    title=question_form.title.data,
                    prompt=question_form.prompt.data,
                    image_url=question_form.image_url.data,
                    prompt_type=question_form.prompt_type.data,
                    language_code=question_form.language_code.data,
                    hint_text=question_form.hint_text.data,
                    model_answer=question_form.model_answer.data,
                    evaluation_rubric=question_form.evaluation_rubric.data,
                    expected_keywords=question_form.expected_keywords.data,
                    is_active=question_form.is_active.data,
                )
                flash("Nursery question added successfully.", "success")
                return redirect(url_for("superadmin.nursery_studio"))

            if action == "upload_questions" and upload_form.validate_on_submit():
                lesson = next((l for l in lessons if l.id == upload_form.lesson_id.data), None)
                if not lesson:
                    raise ValueError("Selected lesson was not found.")
                parsed = LMSService.parse_question_upload(upload_form.upload.data)
                upload_issues = LMSService.validate_question_upload_rows(parsed)
                if upload_issues:
                    raise ValueError("Please fix the upload file first: " + " | ".join(upload_issues[:5]))
                count = LMSService.upload_questions_to_lesson(
                    lesson,
                    parsed,
                    auto_split_size=upload_form.auto_split_size.data or 10,
                )
                flash(f"{count} nursery questions imported successfully.", "success")
                return redirect(url_for("superadmin.nursery_studio"))

            if action == "upload_images":
                files = request.files.getlist("images")
                if not files:
                    raise ValueError("Select at least one image to upload.")
                allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
                uploaded_count = 0
                for file in files:
                    original_name = (getattr(file, "filename", None) or "").strip()
                    if not original_name:
                        continue
                    safe_name = secure_filename(original_name)
                    _, ext = os.path.splitext(safe_name.lower())
                    if ext not in allowed_exts:
                        raise ValueError(f"Unsupported file type for {original_name}. Use PNG, JPG, JPEG, WEBP, or SVG.")
                    target_name = safe_name
                    target_path = os.path.join(nursery_dir, target_name)
                    if os.path.exists(target_path):
                        stem, ext = os.path.splitext(target_name)
                        target_name = f"{stem}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
                        target_path = os.path.join(nursery_dir, target_name)
                    file.save(target_path)
                    uploaded_count += 1
                if uploaded_count == 0:
                    raise ValueError("No valid image files were uploaded.")
                flash(f"{uploaded_count} nursery image(s) uploaded successfully.", "success")
                return redirect(url_for("superadmin.nursery_studio"))

            if action == "add_question":
                flash("Please correct the nursery question form errors.", "warning")
            elif action == "upload_questions":
                flash("Please correct the nursery upload form errors.", "warning")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")

    question_rows = (
        Question.query.join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc(), Question.sort_order.asc())
        .all()
    )

    image_assets = []
    for filename in sorted(os.listdir(nursery_dir)):
        file_path = os.path.join(nursery_dir, filename)
        if not os.path.isfile(file_path):
            continue
        db_path = f"/static/uploads/questions/nursery/{filename}"
        seo_meta = LMSService.image_asset_seo(db_path, course_title=course.title)
        image_assets.append(
            {
                "name": filename,
                "size_kb": max(1, round(os.path.getsize(file_path) / 1024)),
                "url": url_for("static", filename=f"uploads/questions/nursery/{filename}"),
                "db_path": db_path,
                "seo_alt": seo_meta["alt"],
                "seo_title": seo_meta["title"],
            }
        )

    return render_template(
        "superadmin/nursery_studio.html",
        course=course,
        lessons=lessons,
        subsections=subsections,
        question_rows=question_rows,
        image_assets=image_assets,
        question_form=question_form,
        upload_form=upload_form,
        nursery_static_path=nursery_dir,
        panel_role="superadmin",
    )


@bp.route("/courses/<int:course_id>/image-qa", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def course_image_qa(course_id: int):
    course = Course.query.get_or_404(course_id)
    bulk_validation = None

    def _qa_redirect():
        return redirect(
            url_for(
                "superadmin.course_image_qa",
                course_id=course.id,
                q=request.args.get("q") or request.form.get("q") or "",
                severity=request.args.get("severity") or request.form.get("severity") or "all",
                status=request.args.get("status") or request.form.get("status") or "all",
                page=request.args.get("page") or request.form.get("page") or 1,
            )
        )

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        if action == "validate_bulk_upload":
            upload = request.files.get("validation_upload")
            if not upload or not (getattr(upload, "filename", None) or "").strip():
                flash("Select a CSV or TXT file to validate.", "warning")
            else:
                try:
                    bulk_validation = ImageCourseReviewService.validate_bulk_upload(course, upload)
                    if bulk_validation["is_valid"]:
                        flash("Bulk upload validation passed. The file is ready to import.", "success")
                    else:
                        flash("Bulk upload validation found issues. Review the results below.", "warning")
                except Exception as exc:
                    flash(str(exc), "warning")
        question_id = request.form.get("question_id", type=int)
        if action in {"deactivate_question", "activate_question"}:
            question = db.session.get(Question, question_id) if question_id else None
            if not question:
                flash("Question was not found.", "warning")
                return _qa_redirect()

            try:
                if action == "deactivate_question":
                    question.is_active = False
                    db.session.commit()
                    flash("Question deactivated from the image QA dashboard.", "success")
                elif action == "activate_question":
                    question.is_active = True
                    db.session.commit()
                    flash("Question activated from the image QA dashboard.", "success")
            except Exception as exc:
                db.session.rollback()
                flash(str(exc), "warning")
            return _qa_redirect()

        if action in {"bulk_activate_questions", "bulk_deactivate_questions", "bulk_delete_questions"}:
            raw_ids = request.form.getlist("question_ids")
            question_ids = [int(item) for item in raw_ids if str(item).isdigit()]
            if not question_ids:
                flash("Select at least one question first.", "warning")
                return _qa_redirect()

            questions = (
                Question.query
                .join(Subsection, Subsection.id == Question.subsection_id)
                .join(Chapter, Chapter.id == Subsection.chapter_id)
                .join(Lesson, Lesson.id == Chapter.lesson_id)
                .join(Level, Level.id == Lesson.level_id)
                .filter(Level.course_id == course.id, Question.id.in_(question_ids))
                .all()
            )
            if not questions:
                flash("Selected questions were not found in this course.", "warning")
                return _qa_redirect()

            try:
                if action == "bulk_activate_questions":
                    for question in questions:
                        question.is_active = True
                    db.session.commit()
                    flash(f"{len(questions)} question(s) activated.", "success")
                elif action == "bulk_deactivate_questions":
                    for question in questions:
                        question.is_active = False
                    db.session.commit()
                    flash(f"{len(questions)} question(s) deactivated.", "success")
                elif action == "bulk_delete_questions":
                    deleted_count = 0
                    for question in questions:
                        LMSService.delete_question(question)
                        deleted_count += 1
                    flash(f"{deleted_count} question(s) deleted.", "success")
            except Exception as exc:
                db.session.rollback()
                flash(str(exc), "warning")
            return _qa_redirect()

    report = ImageCourseReviewService.build_report(course)
    q = (request.args.get("q") or "").strip().lower()
    severity = (request.args.get("severity") or "all").strip().lower()
    status = (request.args.get("status") or "all").strip().lower()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = 25

    filtered_issues = []
    for issue in report.get("issues", []):
        issue_status = "active" if issue.get("is_active") else "inactive"
        haystack = " ".join(
            str(issue.get(key) or "")
            for key in ("title", "detail", "question_title", "lesson_title", "chapter_title", "subsection_title", "image_url")
        ).lower()
        if q and q not in haystack:
            continue
        if severity != "all" and issue.get("severity") != severity:
            continue
        if status != "all" and issue_status != status:
            continue
        filtered_issues.append(issue)

    total_issue_count = len(filtered_issues)
    total_pages = max(1, (total_issue_count + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    paged_issues = filtered_issues[start:end]

    return render_template(
        "superadmin/image_course_qa.html",
        course=course,
        report=report,
        bulk_validation=bulk_validation,
        panel_role="superadmin",
        filtered_issues=paged_issues,
        issue_total=total_issue_count,
        issue_page=page,
        issue_total_pages=total_pages,
        q=q,
        severity=severity,
        status=status,
    )


@bp.get("/courses/<int:course_id>/image-qa/report.csv")
@login_required
@require_role("SUPERADMIN")
def course_image_qa_report_csv(course_id: int):
    course = Course.query.get_or_404(course_id)
    report = ImageCourseReviewService.build_report(course)
    csv_text = ImageCourseReviewService.report_csv_text(course, report)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="course-{course.id}-image-qa-report.csv"',
        },
    )


@bp.route("/courses/<int:course_id>", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def course_detail(course_id: int):
    course = Course.query.get_or_404(course_id)
    active_tab = (request.args.get('tab') or 'overview').strip().lower()
    tab_aliases = {'questions': 'questions-prompts', 'prompts': 'questions-prompts', 'question-prompts': 'questions-prompts', 'course-settings': 'settings'}
    active_tab = tab_aliases.get(active_tab, active_tab)
    allowed_tabs = {'overview', 'topics', 'ai-content', 'questions-prompts', 'settings', 'preview'}
    if active_tab not in allowed_tabs:
        active_tab = 'overview'

    course_form = CourseForm(prefix="course")
    delete_form = DeleteForm()
    upload_form = QuestionUploadForm(prefix="upload")
    level_form = LevelForm(prefix="level")
    module_form = ModuleForm(prefix="module")
    lesson_form = LessonForm(prefix="lesson")
    chapter_form = ChapterForm(prefix="chapter")
    subsection_form = SubsectionForm(prefix="subsection")
    question_form = QuestionForm(prefix="question")
    _apply_language_choices(question_form)

    lessons = (
        Lesson.query.join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc())
        .all()
    )
    modules = (
        Module.query.join(Level, Level.id == Module.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Module.sort_order.asc())
        .all()
    )
    chapters = (
        Chapter.query.join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc())
        .all()
    )
    subsections = (
        Subsection.query.join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Chapter.sort_order.asc(), Subsection.sort_order.asc())
        .all()
    )

    upload_form.lesson_id.choices = [(l.id, f"{l.level.title} / {l.title}") for l in lessons]
    lesson_form.level_id.choices = [(lvl.id, lvl.title) for lvl in course.levels]
    module_form.level_id.choices = [(lvl.id, lvl.title) for lvl in course.levels]
    lesson_form.module_id.choices = [(0, "No module (directly under level)")] + [(m.id, f"{m.level.title} / {m.title}") for m in modules]
    chapter_form.lesson_id.choices = [(l.id, f"{l.level.title} / {l.title}") for l in lessons]
    subsection_form.chapter_id.choices = [(c.id, f"{c.lesson.title} / {c.title}") for c in chapters]
    question_form.subsection_id.choices = [
        (s.id, f"{s.chapter.lesson.title} / {s.chapter.title} / {s.title}") for s in subsections
    ]

    if request.method == "GET":
        course_form.title.data = course.title
        course_form.slug.data = course.slug
        course_form.description.data = course.description
        course_form.welcome_intro_script.data = getattr(course, "welcome_intro_script", None)
        course_form.learning_outcomes_script.data = getattr(course, "learning_outcomes_script", None)
        course_form.language_code.data = course.language_code or "en"
        course_form.track_type.data = _normalize_course_track_type(course.track_type or "speaking")
        course_form.difficulty.data = course.difficulty or ""
        course_form.currency_code.data = course.currency_code or "INR"
        course_form.max_level.data = getattr(course, "max_level", 1) or 1
        course_form.access_type.data = (getattr(course, "access_type", None) or ("paid" if course.is_premium else "free"))
        course_form.allow_level_purchase.data = bool(getattr(course, "allow_level_purchase", False))
        course_form.level_access_type.data = getattr(course, "level_access_type", "free") or "free"
        course_form.level_price.data = getattr(course, "level_price", 0) or 0
        course_form.level_sale_price.data = getattr(course, "level_sale_price", None)
        course_form.base_price.data = course.base_price
        course_form.sale_price.data = course.sale_price
        course_form.level_title.data = course.levels[0].title if course.levels else "Level 1"
        course_form.lesson_title.data = lessons[0].title if lessons else "Lesson 1"
        course_form.lesson_type.data = lessons[0].lesson_type if lessons else "guided"
        course_form.explanation_text.data = lessons[0].explanation_text if lessons else ""
        course_form.grammar_formula.data = next((s.grammar_formula for s in subsections if s.grammar_formula), "")
        course_form.badge_title.data = ""
        course_form.badge_subtitle.data = ""
        course_form.badge_template.data = "gradient"
        course_form.badge_animation.data = "none"
        course_form.is_published.data = bool(course.is_published)
        course_form.is_premium.data = bool(course.is_premium)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "save_course" and course_form.validate_on_submit():
                LMSService.update_course(
                    course,
                    title=course_form.title.data,
                    slug=course_form.slug.data,
                    description=course_form.description.data,
                    welcome_intro_script=course_form.welcome_intro_script.data,
                    learning_outcomes_script=course_form.learning_outcomes_script.data,
                    language_code=course_form.language_code.data,
                    track_type=_normalize_course_track_type(course_form.track_type.data),
                    difficulty=course_form.difficulty.data,
                    currency_code=course_form.currency_code.data,
                    max_level=course_form.max_level.data,
                    access_type=course_form.access_type.data,
                    allow_level_purchase=course_form.allow_level_purchase.data,
                    level_access_type=course_form.level_access_type.data,
                    base_price=course_form.base_price.data,
                    sale_price=course_form.sale_price.data,
                    level_price=course_form.level_price.data,
                    level_sale_price=course_form.level_sale_price.data,
                    is_published=course_form.is_published.data,
                    is_premium=course_form.is_premium.data,
                )
                flash("Course updated successfully.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id, tab="settings", _anchor="course-settings"))

            if action == "submit_review":
                LMSService.submit_course_for_review(course, current_user.id)
                flash("Course submitted for review.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "approve_publish":
                LMSService.publish_course(course, current_user.id)
                flash("Course published.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action in {"publish", "unpublish", "disable", "archive", "restore"}:
                LMSService.set_course_status(course, action)
                flash("Course status updated.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_course":
                LMSService.delete_course(course)
                flash("Course deleted.", "success")
                return redirect(url_for("superadmin.courses"))

            if action == "add_level" and level_form.validate_on_submit():
                LMSService.add_level(
                    course=course,
                    title=level_form.title.data,
                    description=level_form.description.data,
                    sort_order=level_form.sort_order.data,
                )
                flash("Level added.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "add_module" and module_form.validate_on_submit():
                level = next((lvl for lvl in course.levels if lvl.id == module_form.level_id.data), None)
                if not level:
                    raise ValueError("Selected level was not found.")
                LMSService.add_module(level=level, title=module_form.title.data, description=module_form.description.data, sort_order=module_form.sort_order.data)
                flash("Module added.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "add_lesson" and lesson_form.validate_on_submit():
                LMSService.add_lesson(
                    course=course,
                    level_id=lesson_form.level_id.data,
                    module_id=(lesson_form.module_id.data or None),
                    title=lesson_form.title.data,
                    slug=lesson_form.slug.data,
                    lesson_type=lesson_form.lesson_type.data,
                    explanation_text=lesson_form.explanation_text.data,
                    explanation_tts_text=lesson_form.explanation_tts_text.data,
                    estimated_minutes=lesson_form.estimated_minutes.data,
                    grammar_formula=lesson_form.grammar_formula.data,
                    is_published=lesson_form.is_published.data,
                )
                flash("Lesson created.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "add_chapter" and chapter_form.validate_on_submit():
                lesson = next((l for l in lessons if l.id == chapter_form.lesson_id.data), None)
                if not lesson:
                    raise ValueError("Selected lesson was not found.")
                LMSService.add_chapter(
                    lesson=lesson,
                    title=chapter_form.title.data,
                    description=chapter_form.description.data,
                    sort_order=chapter_form.sort_order.data,
                )
                flash("Chapter added.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "add_subsection" and subsection_form.validate_on_submit():
                chapter = next((c for c in chapters if c.id == subsection_form.chapter_id.data), None)
                if not chapter:
                    raise ValueError("Selected chapter was not found.")
                LMSService.add_subsection(
                    chapter=chapter,
                    title=subsection_form.title.data,
                    grammar_formula=subsection_form.grammar_formula.data,
                    grammar_tags=subsection_form.grammar_tags.data,
                    hint_seed=subsection_form.hint_seed.data,
                    sort_order=subsection_form.sort_order.data,
                )
                flash("Subsection added.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "upload_questions" and upload_form.validate_on_submit():
                lesson = next((l for l in lessons if l.id == upload_form.lesson_id.data), None)
                if not lesson:
                    raise ValueError("Selected lesson was not found.")
                parsed = LMSService.parse_question_upload(upload_form.upload.data)
                upload_issues = LMSService.validate_question_upload_rows(parsed)
                if upload_issues:
                    raise ValueError("Please fix the upload file first: " + " | ".join(upload_issues[:5]))
                count = LMSService.upload_questions_to_lesson(
                    lesson,
                    parsed,
                    auto_split_size=upload_form.auto_split_size.data or 10,
                )
                flash(f"{count} questions imported.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "add_question" and question_form.validate_on_submit():
                subsection = next((s for s in subsections if s.id == question_form.subsection_id.data), None)
                if not subsection:
                    raise ValueError("Selected subsection was not found.")
                LMSService.add_question(
                    subsection=subsection,
                    title=question_form.title.data,
                    prompt=question_form.prompt.data,
                    image_url=question_form.image_url.data,
                    prompt_type=question_form.prompt_type.data,
                    language_code=question_form.language_code.data,
                    hint_text=question_form.hint_text.data,
                    model_answer=question_form.model_answer.data,
                    evaluation_rubric=question_form.evaluation_rubric.data,
                    expected_keywords=question_form.expected_keywords.data,
                    is_active=question_form.is_active.data,
                )
                flash("Question added.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_level":
                level_id = int(request.form.get("level_id") or 0)
                level = next((lvl for lvl in course.levels if lvl.id == level_id), None)
                if not level:
                    raise ValueError("Level not found.")
                LMSService.delete_level(level)
                flash("Level deleted.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_lesson":
                lesson_id = int(request.form.get("lesson_id") or 0)
                lesson = next((l for l in lessons if l.id == lesson_id), None)
                if not lesson:
                    raise ValueError("Lesson not found.")
                LMSService.delete_lesson(lesson)
                flash("Lesson deleted.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_chapter":
                chapter_id = int(request.form.get("chapter_id") or 0)
                chapter = next((c for c in chapters if c.id == chapter_id), None)
                if not chapter:
                    raise ValueError("Chapter not found.")
                LMSService.delete_chapter(chapter)
                flash("Chapter deleted.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_subsection":
                subsection_id = int(request.form.get("subsection_id") or 0)
                subsection = next((s for s in subsections if s.id == subsection_id), None)
                if not subsection:
                    raise ValueError("Subsection not found.")
                LMSService.delete_subsection(subsection)
                flash("Subsection deleted.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))

            if action == "delete_question":
                question_id = int(request.form.get("question_id") or 0)
                question = (
                    Question.query.join(Subsection, Subsection.id == Question.subsection_id)
                    .join(Chapter, Chapter.id == Subsection.chapter_id)
                    .join(Lesson, Lesson.id == Chapter.lesson_id)
                    .join(Level, Level.id == Lesson.level_id)
                    .filter(Level.course_id == course.id, Question.id == question_id)
                    .first()
                )
                if not question:
                    raise ValueError("Question not found.")
                LMSService.delete_question(question)
                flash("Question deleted.", "success")
                return redirect(url_for("superadmin.course_detail", course_id=course.id))
        except Exception as exc:
            flash(str(exc), "warning")

    question_rows = (
        Question.query.join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id)
        .order_by(
            Level.sort_order.asc(),
            Lesson.sort_order.asc(),
            Chapter.sort_order.asc(),
            Subsection.sort_order.asc(),
            Question.sort_order.asc(),
        )
        .all()
    )

    enrollments = Enrollment.query.filter_by(course_id=course.id).order_by(Enrollment.enrolled_at.desc()).all()
    linked_speaking_topics = SpeakingTopic.query.filter_by(course_id=course.id).order_by(SpeakingTopic.display_order.asc(), SpeakingTopic.title.asc()).all()
    linked_reading_topics = ReadingTopic.query.filter_by(course_id=course.id).order_by(ReadingTopic.display_order.asc(), ReadingTopic.title.asc()).all()
    linked_reading_passages = ReadingPassage.query.filter_by(course_id=course.id).order_by(ReadingPassage.created_at.desc(), ReadingPassage.id.desc()).all()
    linked_reading_question_count = ReadingQuestion.query.join(ReadingPassage, ReadingPassage.id == ReadingQuestion.passage_id).filter(ReadingPassage.course_id == course.id).count()
    linked_writing_topics = WritingTopic.query.filter_by(course_id=course.id).order_by(WritingTopic.display_order.asc(), WritingTopic.title.asc()).all()
    linked_writing_tasks = WritingTask.query.filter_by(course_id=course.id).order_by(WritingTask.display_order.asc(), WritingTask.title.asc()).all()
    linked_listening_lessons = (
        Lesson.query
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id, Lesson.lesson_type == 'listening')
        .order_by(Level.sort_order.asc(), Lesson.sort_order.asc(), Lesson.id.asc())
        .all()
    )
    linked_listening_question_count = (
        Question.query
        .join(Subsection, Subsection.id == Question.subsection_id)
        .join(Chapter, Chapter.id == Subsection.chapter_id)
        .join(Lesson, Lesson.id == Chapter.lesson_id)
        .join(Level, Level.id == Lesson.level_id)
        .filter(Level.course_id == course.id, Lesson.lesson_type == 'listening')
        .count()
    )
    reading_question_groups = {}
    if _normalize_course_track_type(course.track_type) == 'reading':
        reading_questions = (
            ReadingQuestion.query
            .join(ReadingPassage, ReadingPassage.id == ReadingQuestion.passage_id)
            .filter(ReadingPassage.course_id == course.id)
            .order_by(ReadingQuestion.passage_id.asc(), ReadingQuestion.display_order.asc(), ReadingQuestion.id.asc())
            .all()
        )
        for item in reading_questions:
            passage_id = item.passage_id or 0
            reading_question_groups.setdefault(passage_id, {'passage': item.passage, 'items': []})['items'].append(item)
    linked_topic_count = len(linked_speaking_topics) + len(linked_reading_topics) + len(linked_writing_topics) + len(linked_listening_lessons)
    total_prompt_like_items = len(question_rows) + linked_reading_question_count + linked_listening_question_count + sum(topic.active_prompt_count for topic in linked_speaking_topics) + len(linked_writing_tasks)

    track_status_cards = [
        {
            'key': 'speaking',
            'label': 'Speaking',
            'ready': len(linked_speaking_topics) > 0,
            'primary_count': len(linked_speaking_topics),
            'secondary_count': sum(int(getattr(topic, 'active_prompt_count', 0) or 0) for topic in linked_speaking_topics),
            'primary_label': 'Topics',
            'secondary_label': 'Prompts',
            'manager_url': url_for('superadmin.speaking_topics', course_id=course.id),
            'secondary_url': url_for('superadmin.course_speaking_prompts_manager', course_id=course.id),
            'secondary_cta': 'Prompts',
        },
        {
            'key': 'reading',
            'label': 'Reading',
            'ready': (len(linked_reading_topics) > 0 or len(linked_reading_passages) > 0),
            'primary_count': len(linked_reading_topics),
            'secondary_count': linked_reading_question_count,
            'primary_label': 'Topics',
            'secondary_label': 'Questions',
            'manager_url': url_for('superadmin.reading_topics', course_id=course.id),
            'secondary_url': url_for('superadmin.reading_questions', course_id=course.id),
            'secondary_cta': 'Questions',
        },
        {
            'key': 'writing',
            'label': 'Writing',
            'ready': (len(linked_writing_topics) > 0 or len(linked_writing_tasks) > 0),
            'primary_count': len(linked_writing_topics),
            'secondary_count': len(linked_writing_tasks),
            'primary_label': 'Topics',
            'secondary_label': 'Tasks',
            'manager_url': url_for('superadmin.writing_topics', course_id=course.id),
            'secondary_url': url_for('superadmin.writing_tasks', course_id=course.id),
            'secondary_cta': 'Tasks',
        },
        {
            'key': 'listening',
            'label': 'Listening',
            'ready': len(linked_listening_lessons) > 0,
            'primary_count': len(linked_listening_lessons),
            'secondary_count': linked_listening_question_count,
            'primary_label': 'Topics',
            'secondary_label': 'Questions',
            'manager_url': url_for('superadmin.listening_topics', course_id=course.id),
            'secondary_url': url_for('superadmin.listening_questions', course_id=course.id),
            'secondary_cta': 'Questions',
        },
    ]
    missing_content_alerts = [
        f"{item['label']} content is missing." for item in track_status_cards if not item['ready']
    ]
    ready_modules = sum(1 for item in track_status_cards if item['ready'])
    course_health = {
        'ready_modules': ready_modules,
        'total_modules': len(track_status_cards),
        'percent': int(round((ready_modules / max(len(track_status_cards), 1)) * 100)),
        'has_any_content': linked_topic_count > 0 or total_prompt_like_items > 0,
    }
    publish_readiness = {
        'ready': bool(course_health['has_any_content'] and course.is_published and ready_modules > 0),
        'summary': 'Ready to publish' if (course_health['has_any_content'] and ready_modules > 0) else 'Content missing before publish',
        'detail': 'At least one active module has content and the course can be reviewed.' if (course_health['has_any_content'] and ready_modules > 0) else 'Add course content first, then publish with confidence.',
    }
    quick_links = {
        'overview': url_for('superadmin.course_overview', course_id=course.id),
        'topics': url_for('superadmin.course_topics_manager', course_id=course.id),
        'ai_content': url_for('superadmin.course_ai_content_manager', course_id=course.id),
        'questions_prompts': url_for('superadmin.course_questions_prompts_manager', course_id=course.id),
        'settings': url_for('superadmin.course_settings_manager', course_id=course.id),
        'preview': url_for('superadmin.course_student_preview', course_id=course.id),
        'speaking': url_for('superadmin.speaking_topics', course_id=course.id),
        'reading': url_for('superadmin.reading_topics', course_id=course.id),
        'writing': url_for('superadmin.writing_topics', course_id=course.id),
        'listening': url_for('superadmin.listening_topics', course_id=course.id),
        'review_dashboard': url_for('superadmin.review_dashboard'),
    }
    preview_route = None
    try:
        preview_route = url_for('superadmin.course_student_preview', course_id=course.id)
    except Exception:
        preview_route = None
    LMSService.ensure_default_batch(course, current_user.id)
    batches = LMSService.course_batches_for_admin(current_user.id, course)
    version_rows = ContentVersion.query.filter_by(entity_type="course", entity_id=course.id).order_by(ContentVersion.created_at.desc()).limit(10).all()

    return render_template(
        "superadmin/course_detail.html",
        course=course,
        course_form=course_form,
        lessons=lessons,
        modules=modules,
        chapters=chapters,
        subsections=subsections,
        question_rows=question_rows,
        enrollments=enrollments,
        upload_form=upload_form,
        level_form=level_form,
        module_form=module_form,
        lesson_form=lesson_form,
        chapter_form=chapter_form,
        subsection_form=subsection_form,
        question_form=question_form,
        delete_form=delete_form,
        metrics=LMSService.course_metrics(course.id),
        course_tree=_build_course_tree(course),
        linked_speaking_topics=linked_speaking_topics,
        linked_reading_topics=linked_reading_topics,
        linked_reading_passages=linked_reading_passages,
        linked_reading_question_count=linked_reading_question_count,
        linked_writing_topics=linked_writing_topics,
        linked_writing_tasks=linked_writing_tasks,
        linked_listening_lessons=linked_listening_lessons,
        linked_listening_question_count=linked_listening_question_count,
        reading_question_groups=reading_question_groups,
        track_status_cards=track_status_cards,
        missing_content_alerts=missing_content_alerts,
        course_health=course_health,
        publish_readiness=publish_readiness,
        quick_links=quick_links,
        batches=batches,
        version_rows=version_rows,
        active_tab=active_tab,
        linked_topic_count=linked_topic_count,
        total_prompt_like_items=total_prompt_like_items,
        preview_route=preview_route,
        panel_role="superadmin",
    )



@bp.get("/courses/<int:course_id>/manager")
@login_required
@require_role("SUPERADMIN")
def course_manager_alias(course_id: int):
    return redirect(url_for("superadmin.course_detail", course_id=course_id))


@bp.get("/courses/<int:course_id>/content")
@login_required
@require_role("SUPERADMIN")
def course_content_alias(course_id: int):
    return redirect(url_for("superadmin.course_topics_manager", course_id=course_id))


@bp.get("/courses/<int:course_id>/review")
@login_required
@require_role("SUPERADMIN")
def course_review_alias(course_id: int):
    return redirect(url_for("superadmin.course_student_preview", course_id=course_id))


@bp.get("/courses/<int:course_id>/overview")
@login_required
@require_role("SUPERADMIN")
def course_overview(course_id: int):
    return redirect(url_for("superadmin.course_detail", course_id=course_id, tab="overview"))


@bp.get("/courses/<int:course_id>/topics")
@login_required
@require_role("SUPERADMIN")
def course_topics_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track = _normalize_course_track_type(course.track_type)
    if track == "speaking":
        return redirect(url_for("superadmin.speaking_topics", course_id=course.id))
    if track == "reading":
        return redirect(url_for("superadmin.reading_topics", course_id=course.id))
    if track == "writing":
        return redirect(url_for("superadmin.writing_topics", course_id=course.id))
    if track == "listening":
        return redirect(url_for("superadmin.listening_topics", course_id=course.id))
    return redirect(url_for("superadmin.course_detail", course_id=course.id, tab="topics"))


@bp.get("/courses/<int:course_id>/ai-content")
@login_required
@require_role("SUPERADMIN")
def course_ai_content_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track = _normalize_course_track_type(course.track_type)
    if track == "reading":
        return redirect(url_for("superadmin.reading_passages", course_id=course.id))
    if track == "writing":
        return redirect(url_for("superadmin.writing_tasks", course_id=course.id))
    if track == "listening":
        return redirect(url_for("superadmin.listening_topics", course_id=course.id))
    return redirect(url_for("superadmin.course_detail", course_id=course.id, tab="ai-content"))


@bp.get("/courses/<int:course_id>/questions-prompts")
@login_required
@require_role("SUPERADMIN")
def course_questions_prompts_manager(course_id: int):
    course = Course.query.get_or_404(course_id)
    track = _normalize_course_track_type(course.track_type)
    if track == "speaking":
        return redirect(url_for("superadmin.speaking_prompts", course_id=course.id))
    if track == "reading":
        return redirect(url_for("superadmin.reading_questions", course_id=course.id))
    if track == "writing":
        return redirect(url_for("superadmin.writing_tasks", course_id=course.id))
    if track == "listening":
        return redirect(url_for("superadmin.listening_questions", course_id=course.id))
    return redirect(url_for("superadmin.course_detail", course_id=course.id, tab="questions-prompts"))


@bp.get("/courses/<int:course_id>/settings")
@login_required
@require_role("SUPERADMIN")
def course_settings_manager(course_id: int):
    return redirect(url_for("superadmin.course_detail", course_id=course_id, tab="settings"))


@bp.get("/courses/<int:course_id>/preview")
@login_required
@require_role("SUPERADMIN")
def course_student_preview(course_id: int):
    course = Course.query.get_or_404(course_id)
    track = _normalize_course_track_type(course.track_type)
    if track == "speaking":
        return redirect(url_for("student.course_speaking_home", course_id=course.id))
    if track == "reading":
        return redirect(url_for("student.course_reading_home", course_id=course.id))
    if track == "writing":
        return redirect(url_for("student.course_writing_home", course_id=course.id))
    if track == "listening":
        return redirect(url_for("student.course_listening_home", course_id=course.id))
    return redirect(url_for("student.course_detail", course_id=course.id))




@bp.get("/students")
@login_required
@require_role("SUPERADMIN")
def students():
    q = (request.args.get("q") or "").strip()
    admin_id = int(request.args.get("admin_id") or 0) if str(request.args.get("admin_id") or "0").isdigit() else 0
    teacher_id = int(request.args.get("teacher_id") or 0) if str(request.args.get("teacher_id") or "0").isdigit() else 0
    focus_student_id = int(request.args.get("focus_student_id") or 0) if str(request.args.get("focus_student_id") or "0").isdigit() else 0
    quick_filter = (request.args.get("quick_filter") or "all").strip().lower()

    return render_template(
        "superadmin/students_manage.html",
        **_student_directory_context(
            q=q,
            admin_id=admin_id,
            teacher_id=teacher_id,
            focus_student_id=focus_student_id,
            quick_filter=quick_filter,
        ),
    )


@bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def students_edit(student_id: int):
    student = User.query.get_or_404(student_id)
    if student.role_code != Role.STUDENT.value:
        flash("Only student accounts can be edited here.", "warning")
        return redirect(url_for("superadmin.students"))

    form = StudentEditForm()
    _apply_admin_management_choices(form)
    if request.method == "GET":
        form.full_name.data = student.full_name
        form.username.data = student.username
        form.email.data = student.email
        form.current_level.data = student.current_level or ""
        form.target_exam.data = student.target_exam or ""
        form.organization_id.data = student.organization_id or 0
        form.teacher_id.data = student.teacher_id or 0
        form.managed_by_user_id.data = student.managed_by_user_id or (student.admin_id or 0)
        form.is_active.data = student.is_active

    if form.validate_on_submit():
        duplicate_username = User.query.filter(User.username == form.username.data.strip(), User.id != student.id).first()
        if duplicate_username:
            flash("Username already exists.", "warning")
            return redirect(url_for("superadmin.students_edit", student_id=student.id))

        duplicate_email = User.query.filter(User.email == form.email.data.strip().lower(), User.id != student.id).first()
        if duplicate_email:
            flash("Email already exists.", "warning")
            return redirect(url_for("superadmin.students_edit", student_id=student.id))

        first_name, last_name = _split_name(form.full_name.data)
        student.first_name = first_name
        student.last_name = last_name
        student.username = form.username.data.strip()
        student.email = form.email.data.strip().lower()
        student.current_level = form.current_level.data or None
        student.target_exam = form.target_exam.data or None
        selected_org_id = int(form.organization_id.data or 0)
        selected_teacher_id = int(form.teacher_id.data or 0)
        valid, error_message, _teacher = validate_student_linkage(selected_org_id, selected_teacher_id)
        if not valid:
            flash(error_message or "Invalid institute/teacher mapping.", "warning")
            return redirect(url_for("superadmin.students_edit", student_id=student.id))

        apply_student_ownership(
            student,
            selected_org_id,
            selected_teacher_id,
            managed_by_user_id=(form.managed_by_user_id.data or None),
        )
        student.is_active = bool(form.is_active.data)
        db.session.commit()
        flash("Student updated successfully.", "success")
        return redirect(url_for("superadmin.students"))

    return render_template(
        "superadmin/students_manage.html",
        editing_student=student,
        edit_form=form,
        **_student_directory_context(focus_student_id=student.id),
    )


@bp.route("/students/<int:student_id>/password", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def students_password(student_id: int):
    student = User.query.get_or_404(student_id)
    if student.role_code != Role.STUDENT.value:
        flash("Only student accounts can be changed here.", "warning")
        return redirect(url_for("superadmin.students"))

    form = StudentPasswordForm()
    if form.validate_on_submit():
        student.set_password(form.new_password.data)
        db.session.commit()
        flash("Student password changed successfully.", "success")
        return redirect(url_for("superadmin.students"))

    return render_template(
        "superadmin/students_manage.html",
        password_student=student,
        password_form=form,
        **_student_directory_context(focus_student_id=student.id),
    )


@bp.post("/students/<int:student_id>/delete")
@login_required
@require_role("SUPERADMIN")
def students_delete(student_id: int):
    student = User.query.get_or_404(student_id)
    if student.role_code != Role.STUDENT.value:
        flash("Only student accounts can be removed here.", "warning")
        return redirect(url_for("superadmin.students"))

    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "success")
    return redirect(url_for("superadmin.students"))


@bp.get("/students/export")
@login_required
@require_role("SUPERADMIN")
def students_export():
    students = User.query.filter_by(role=Role.STUDENT.value).order_by(User.created_at.asc()).all()
    rows = LMSService.export_students_csv_rows(students)

    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=list(rows[0].keys()) if rows else ["id", "name"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return Response(
        sio.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_export.csv"},
    )


@bp.get("/admins")
@login_required
@require_role("SUPERADMIN")
def admins_list():
    q = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("role") or "").strip().upper()
    parent_admin_id = int(request.args.get("parent_admin_id") or 0) if str(request.args.get("parent_admin_id") or "0").isdigit() else 0
    admins = _staff_query_for_superadmin(filter_role=role_filter or None, parent_admin_id=parent_admin_id or None, q=q or None).all()
    create_form = AdminCreateForm()
    _apply_admin_management_choices(create_form)
    return render_template(
        "superadmin/admins.html",
        admins=admins,
        create_form=create_form,
        q=q,
        role_filter=role_filter,
        parent_admin_id=parent_admin_id,
        parent_admin_choices=_admin_scope_choices(include_none=True),
    )


@bp.route("/admins/create", methods=["POST"])
@login_required
@require_role("SUPERADMIN")
def admins_create():
    form = AdminCreateForm()
    _apply_admin_management_choices(form)
    if form.validate_on_submit():
        ok, message = _create_staff_user_from_form(form)
        flash("Admin created successfully." if ok else message, "success" if ok else "warning")
    else:
        flash("Please correct the admin form errors.", "warning")
    return redirect(url_for("superadmin.admins_list"))


@bp.route("/admins/<int:admin_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def admins_edit(admin_id: int):
    admin = User.query.get_or_404(admin_id)
    form = AdminEditForm(obj=admin)
    _apply_admin_management_choices(form)

    if request.method == "GET":
        form.full_name.data = admin.full_name
        form.username.data = admin.username
        form.email.data = admin.email
        form.role.data = admin.role_code
        form.organization_name.data = admin.organization_name or ""
        form.parent_admin_id.data = admin.organization_id or admin.admin_id or 0
        form.is_active.data = admin.is_active

    if form.validate_on_submit():
        first_name, last_name = _split_name(form.full_name.data)
        parent_admin = User.query.get(form.parent_admin_id.data) if form.parent_admin_id.data else None
        admin.first_name = first_name
        admin.last_name = last_name
        admin.username = form.username.data.strip()
        admin.email = form.email.data.strip().lower()
        admin.role = form.role.data
        admin.organization_name = (form.organization_name.data or "").strip() or (parent_admin.organization_name if parent_admin else None)
        admin.admin_id = parent_admin.id if parent_admin and form.role.data != Role.ADMIN.value else None
        admin.organization_id = parent_admin.id if parent_admin and form.role.data != Role.ADMIN.value else None
        admin.managed_by_user_id = parent_admin.id if parent_admin and form.role.data in {Role.SUB_ADMIN.value, Role.TEACHER.value} else None
        admin.is_active = bool(form.is_active.data)
        db.session.commit()
        flash("Admin updated successfully.", "success")
        return redirect(url_for("superadmin.admins_list"))

    admins = _staff_query_for_superadmin().all()
    return render_template("superadmin/admins.html", admins=admins, edit_form=form, editing_admin=admin, q="", role_filter="", parent_admin_id=0, parent_admin_choices=_admin_scope_choices(include_none=True))


@bp.route("/admins/<int:admin_id>/password", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def admins_password(admin_id: int):
    admin = User.query.get_or_404(admin_id)
    form = AdminPasswordForm()

    if form.validate_on_submit():
        admin.set_password(form.new_password.data)
        db.session.commit()
        flash("Password changed successfully.", "success")
        return redirect(url_for("superadmin.admins_list"))

    admins = _staff_query_for_superadmin().all()
    return render_template("superadmin/admins.html", admins=admins, password_form=form, password_admin=admin, q="", role_filter="", parent_admin_id=0, parent_admin_choices=_admin_scope_choices(include_none=True))


@bp.post("/admins/<int:admin_id>/delete")
@login_required
@require_role("SUPERADMIN")
def admins_delete(admin_id: int):
    user = User.query.get_or_404(admin_id)
    if user.role_code == Role.SUPERADMIN.value:
        flash("SuperAdmin cannot be deleted from here.", "warning")
    else:
        db.session.delete(user)
        db.session.commit()
        flash("Admin deleted.", "success")
    return redirect(url_for("superadmin.admins_list"))


@bp.route("/admins/<int:admin_id>/permissions", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def admin_permissions(admin_id: int):
    admin = User.query.get_or_404(admin_id)
    form = AdminPermissionForm()

    permissions = []
    existing_codes = []
    try:
        seed_default_rbac()
        from ...models.rbac import Permission
        from ...models.admin_permission_override import AdminPermissionOverride

        permissions = Permission.query.order_by(Permission.code.asc()).all()
        form.permissions.choices = [(p.code, p.code) for p in permissions]

        overrides = AdminPermissionOverride.query.filter_by(user_id=admin.id).all()
        existing_codes = [o.permission.code for o in overrides if getattr(o, "allowed", True)]

        if request.method == "GET":
            form.permissions.data = existing_codes

        if form.validate_on_submit():
            AdminPermissionOverride.query.filter_by(user_id=admin.id).delete()
            for code in form.permissions.data or []:
                perm = next((p for p in permissions if p.code == code), None)
                if perm:
                    db.session.add(AdminPermissionOverride(user_id=admin.id, permission_id=perm.id, allowed=True))
            db.session.commit()
            flash("Permissions updated.", "success")
            return redirect(url_for("superadmin.admin_permissions", admin_id=admin.id))
    except Exception:
        if request.method == "POST":
            flash("Permission management models are not available in this build.", "warning")

    return render_template(
        "superadmin/admin_permissions.html",
        admin=admin,
        form=form,
        permission_keys=[p.code for p in permissions],
        selected_codes=existing_codes,
    )


@bp.get("/teachers")
@login_required
@require_role("SUPERADMIN")
def teachers_list():
    q = (request.args.get("q") or "").strip()
    parent_admin_id = int(request.args.get("parent_admin_id") or 0) if str(request.args.get("parent_admin_id") or "0").isdigit() else 0
    teachers = _staff_query_for_superadmin(filter_role=Role.TEACHER.value, parent_admin_id=parent_admin_id or None, q=q or None).all()
    create_form = AdminCreateForm()
    create_form.role.data = Role.TEACHER.value
    _apply_admin_management_choices(create_form)
    return render_template("superadmin/teachers.html", teachers=teachers, create_form=create_form, q=q, parent_admin_id=parent_admin_id, parent_admin_choices=_admin_scope_choices(include_none=True))


@bp.get("/institutes")
@login_required
@require_role("SUPERADMIN")
def institutes_list():
    q = (request.args.get("q") or "").strip().lower()
    institutes = _institute_rows()
    if q:
        institutes = [row for row in institutes if q in (row["name"] or "").lower() or q in (row["admin_name"] or "").lower()]
    create_form = AdminCreateForm()
    create_form.role.data = Role.ADMIN.value
    _apply_admin_management_choices(create_form)
    create_form.parent_admin_id.data = 0
    return render_template("superadmin/institutes.html", institutes=institutes, q=q, create_form=create_form)


@bp.post("/institutes/create")
@login_required
@require_role("SUPERADMIN")
def institutes_create():
    form = AdminCreateForm()
    _apply_admin_management_choices(form)
    form.role.data = Role.ADMIN.value
    form.parent_admin_id.data = 0
    if form.validate_on_submit() and (form.organization_name.data or "").strip():
        ok, message = _create_staff_user_from_form(form)
        flash("Institute created successfully." if ok else message, "success" if ok else "warning")
    else:
        flash("Please complete the institute and principal form correctly.", "warning")
    return redirect(url_for("superadmin.institutes_list"))


@bp.get("/directory")
@login_required
@require_role("SUPERADMIN")
def directory():
    q = (request.args.get("q") or "").strip()
    search_in = (request.args.get("search_in") or "all").strip().lower()
    staff_results = _staff_query_for_superadmin(q=q or None).all() if search_in in {"all", "admin", "teacher"} else []
    institute_results = _institute_rows() if search_in in {"all", "institute"} else []
    if q and institute_results:
        low=q.lower()
        institute_results = [row for row in institute_results if low in (row["name"] or "").lower() or low in (row["admin_name"] or "").lower()]
    student_results = _student_query_for_superadmin(q=q or None).all() if search_in in {"all", "student"} else []
    if search_in == "admin":
        staff_results = [row for row in staff_results if row.role_code in {Role.ADMIN.value, Role.SUB_ADMIN.value, Role.EDITOR.value}]
    if search_in == "teacher":
        staff_results = [row for row in staff_results if row.role_code == Role.TEACHER.value]
    return render_template("superadmin/directory.html", q=q, search_in=search_in, staff_results=staff_results, institute_results=institute_results, student_results=student_results)


@bp.get("/roles")
@login_required
@require_role("SUPERADMIN")
def roles():
    role_rows = []
    try:
        seed_default_rbac()
        from ...models.rbac import Permission, RoleModel, RolePermission

        perms = Permission.query.order_by(Permission.code.asc()).all()
        roles_q = RoleModel.query.order_by(RoleModel.code.asc()).all()

        for role in roles_q:
            role_perm_ids = {
                rp.permission_id
                for rp in RolePermission.query.filter_by(role_id=role.id).all()
            }
            role_rows.append(
                {
                    "role": role,
                    "permissions": [p.code for p in perms if p.id in role_perm_ids],
                }
            )
    except Exception:
        role_rows = [{"role": type("X", (), {"code": r.value})(), "permissions": []} for r in Role]

    return render_template("superadmin/roles.html", role_rows=role_rows)


@bp.get("/permissions")
@login_required
@require_role("SUPERADMIN")
def permissions():
    perms = []
    try:
        seed_default_rbac()
        from ...models.rbac import Permission

        perms = Permission.query.order_by(Permission.code.asc()).all()
    except Exception:
        perms = []
    return render_template("superadmin/permissions.html", perms=perms)


@bp.get("/pages")
@login_required
@require_role("SUPERADMIN")

def pages_list():
    include_deleted = request.args.get("view") == "trash"
    query = Page.query
    if include_deleted:
        query = query.filter(Page.deleted_at.is_not(None))
    else:
        query = query.filter(Page.deleted_at.is_(None))
    pages = query.order_by(Page.menu_order.asc(), Page.updated_at.desc()).all()
    return render_template("superadmin/pages_list.html", pages=pages, include_deleted=include_deleted, parse_json_list=parse_json_list)


@bp.route("/pages/create", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def pages_create():
    form = PageForm()
    _apply_language_choices(form)
    if form.validate_on_submit():
        page = Page(
            title=form.title.data.strip(),
            slug=form.slug.data.strip().lower(),
            is_published=bool(form.is_published.data),
            is_in_menu=bool(form.is_in_menu.data),
            menu_order=int(form.menu_order.data or 0),
            redirect_from=None,
            redirect_to=None,
            redirect_code=301,
        )
        db.session.add(page)
        db.session.flush()

        content = ensure_page_content(page, form.lang_code.data)
        content.title = form.content_title.data or form.title.data
        content.subtitle = form.subtitle.data or ""
        content.body_html = sanitize_html(form.body_html.data or "")
        content.hero_title = form.hero_title.data or form.title.data
        content.hero_subtitle = form.hero_subtitle.data or ""
        content.hero_cta_text = form.hero_cta_text.data or ""
        content.hero_cta_url = form.hero_cta_url.data or ""
        content.hero_image = form.hero_image.data or ""
        content.meta_title = form.meta_title.data or form.title.data
        content.meta_description = form.meta_description.data or ""
        content.canonical_url = form.canonical_url.data or ""
        content.og_title = form.og_title.data or form.title.data
        content.og_description = form.og_description.data or ""
        content.og_image = form.og_image.data or ""
        content.twitter_card = form.twitter_card.data or "summary_large_image"
        page.redirect_from = request.form.get("redirect_from") or None
        page.redirect_to = request.form.get("redirect_to") or None
        page.redirect_code = int(request.form.get("redirect_code") or 301)
        content.sections_json = sanitize_json_html_fields(form.sections_json.data or "")
        content.faq_json = sanitize_json_html_fields(form.faq_json.data or "")
        content.links_json = sanitize_json_html_fields(form.links_json.data or "")
        content.json_ld = sanitize_json_html_fields(form.json_ld.data or "")
        db.session.add(content)
        db.session.commit()

        flash("Page created successfully.", "success")
        return redirect(url_for("superadmin.pages_list"))

    return render_template("superadmin/pages_edit.html", form=form, page=None, content=None, mode="create", parse_json_list=parse_json_list)


@bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def pages_edit(page_id: int):
    page = Page.query.get_or_404(page_id)
    lang_code = (request.args.get("lang") or "en").strip().lower()
    content = ensure_page_content(page, lang_code)

    form = PageForm()
    _apply_language_choices(form)
    if request.method == "GET":
        form.title.data = page.title
        form.slug.data = page.slug
        form.is_published.data = page.is_published
        form.is_in_menu.data = page.is_in_menu
        form.menu_order.data = str(page.menu_order)
        form.lang_code.data = lang_code
        form.content_title.data = content.title or ""
        form.subtitle.data = content.subtitle or ""
        form.body_html.data = content.body_html or ""
        form.hero_title.data = content.hero_title or ""
        form.hero_subtitle.data = content.hero_subtitle or ""
        form.hero_cta_text.data = content.hero_cta_text or ""
        form.hero_cta_url.data = content.hero_cta_url or ""
        form.hero_image.data = content.hero_image or ""
        form.meta_title.data = content.meta_title or ""
        form.meta_description.data = content.meta_description or ""
        form.canonical_url.data = content.canonical_url or ""
        form.og_title.data = content.og_title or ""
        form.og_description.data = content.og_description or ""
        form.og_image.data = content.og_image or ""
        form.twitter_card.data = content.twitter_card or "summary_large_image"
        form.sections_json.data = content.sections_json or ""
        form.faq_json.data = content.faq_json or ""
        form.links_json.data = content.links_json or ""
        form.json_ld.data = content.json_ld or ""

    if form.validate_on_submit():
        page.title = form.title.data.strip()
        page.slug = form.slug.data.strip().lower()
        page.is_published = bool(form.is_published.data)
        page.is_in_menu = bool(form.is_in_menu.data)
        page.menu_order = int(form.menu_order.data or 0)

        content.lang_code = form.lang_code.data
        content.title = form.content_title.data or page.title
        content.subtitle = form.subtitle.data or ""
        content.body_html = sanitize_html(form.body_html.data or "")
        content.hero_title = form.hero_title.data or page.title
        content.hero_subtitle = form.hero_subtitle.data or ""
        content.hero_cta_text = form.hero_cta_text.data or ""
        content.hero_cta_url = form.hero_cta_url.data or ""
        content.hero_image = form.hero_image.data or ""
        content.meta_title = form.meta_title.data or page.title
        content.meta_description = form.meta_description.data or ""
        content.canonical_url = form.canonical_url.data or ""
        content.og_title = form.og_title.data or page.title
        content.og_description = form.og_description.data or ""
        content.og_image = form.og_image.data or ""
        content.twitter_card = form.twitter_card.data or "summary_large_image"
        page.redirect_from = request.form.get("redirect_from") or None
        page.redirect_to = request.form.get("redirect_to") or None
        page.redirect_code = int(request.form.get("redirect_code") or 301)
        content.sections_json = sanitize_json_html_fields(form.sections_json.data or "")
        content.faq_json = sanitize_json_html_fields(form.faq_json.data or "")
        content.links_json = sanitize_json_html_fields(form.links_json.data or "")
        content.json_ld = sanitize_json_html_fields(form.json_ld.data or "")

        db.session.add(content)
        db.session.commit()
        flash("Page updated successfully.", "success")
        return redirect(url_for("superadmin.pages_edit", page_id=page.id, lang=form.lang_code.data))

    return render_template("superadmin/pages_edit.html", form=form, page=page, content=content, mode="edit", parse_json_list=parse_json_list)


@bp.post("/pages/<int:page_id>/delete")
@login_required
@require_role("SUPERADMIN")

def pages_delete(page_id: int):
    page = Page.query.get_or_404(page_id)
    page.soft_delete()
    db.session.commit()
    flash("Page moved to trash.", "success")
    return redirect(url_for("superadmin.pages_list"))


@bp.post("/pages/<int:page_id>/restore")
@login_required
@require_role("SUPERADMIN")
def pages_restore(page_id: int):
    page = Page.query.get_or_404(page_id)
    page.restore()
    db.session.commit()
    flash("Page restored.", "success")
    return redirect(url_for("superadmin.pages_list", view="trash"))


@bp.post("/pages/<int:page_id>/publish")
@login_required
@require_role("SUPERADMIN")
def pages_publish(page_id: int):
    page = Page.query.get_or_404(page_id)
    page.is_published = True
    db.session.commit()
    flash("Page published.", "success")
    return redirect(url_for("superadmin.pages_list"))


@bp.post("/pages/<int:page_id>/unpublish")
@login_required
@require_role("SUPERADMIN")
def pages_unpublish(page_id: int):
    page = Page.query.get_or_404(page_id)
    page.is_published = False
    db.session.commit()
    flash("Page unpublished.", "success")
    return redirect(url_for("superadmin.pages_list"))




def _safe_json_string(raw: str | None, fallback: str) -> str:
    text = (raw or '').strip()
    if not text:
        return fallback
    try:
        json.loads(text)
        return text
    except Exception:
        return fallback


def _save_seo_form_to_settings(form, settings: SeoSettings) -> None:
    boolean_fields = {
        'sitemap_enabled', 'whatsapp_enabled', 'whatsapp_show_on_public', 'whatsapp_click_tracking_enabled', 'robots_enabled', 'sitemap_include_pages',
        'sitemap_include_public_reading', 'sitemap_include_courses', 'htaccess_enabled',
        'htaccess_force_https', 'htaccess_force_www', 'htaccess_enable_compression',
        'htaccess_enable_browser_cache', 'header_announcement_enabled',
    }
    json_fields = {'header_links_json', 'footer_widgets_json'}
    for field_name, field in form._fields.items():
        if field_name in {'csrf_token', 'submit'}:
            continue
        value = field.data
        if field_name in boolean_fields:
            value = bool(value)
        elif field_name in json_fields:
            value = _safe_json_string(value, '[]')
        elif field_name == 'footer_columns':
            value = int(value or 4)
        setattr(settings, field_name, value)


def _save_header_footer_theme_controls() -> None:
    theme = Theme.ensure_default()
    int_fields = {
        'alphabet_rotation_depth', 'alphabet_speed', 'alphabet_min_size', 'alphabet_max_size',
        'alphabet_count', 'alphabet_direction_x', 'alphabet_direction_y', 'alphabet_opacity',
        'alphabet_trail_length', 'alphabet_tilt_x', 'alphabet_tilt_y', 'alphabet_tilt_z',
    }
    bool_fields = {'alphabet_background_enabled', 'alphabet_trails_enabled', 'alphabet_outline_only', 'header_sticky_enabled', 'header_transparent_enabled'}
    str_fields = {'alphabet_motion_mode', 'alphabet_outline_color'}
    for name in int_fields:
        if name in request.form and hasattr(theme, name):
            try:
                setattr(theme, name, int(request.form.get(name) or 0))
            except Exception:
                pass
    for name in bool_fields:
        if hasattr(theme, name):
            setattr(theme, name, name in request.form)
    for name in str_fields:
        if name in request.form and hasattr(theme, name):
            setattr(theme, name, (request.form.get(name) or '').strip() or getattr(theme, name))
    db.session.commit()
@bp.route("/seo", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def seo_settings():
    settings = SeoSettings.singleton()
    form = SeoSettingsForm(obj=settings)
    if form.validate_on_submit():
        _save_seo_form_to_settings(form, settings)
        db.session.add(settings)
        db.session.commit()
        flash("SEO settings saved.", "success")
        return redirect(url_for("superadmin.seo_settings"))
    return render_template("superadmin/seo_settings.html", form=form, settings=settings)




@bp.route("/whatsapp-settings", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def whatsapp_settings():
    settings = SeoSettings.singleton()
    form = SeoSettingsForm(obj=settings)
    if form.validate_on_submit():
        for field_name in (
            "whatsapp_enabled",
            "whatsapp_show_on_public",
            "whatsapp_click_tracking_enabled",
            "whatsapp_number",
            "whatsapp_button_text",
            "whatsapp_help_text",
            "whatsapp_default_category",
            "whatsapp_message",
        ):
            if hasattr(form, field_name):
                field = getattr(form, field_name)
                value = bool(field.data) if field_name in {"whatsapp_enabled", "whatsapp_show_on_public", "whatsapp_click_tracking_enabled"} else field.data
                setattr(settings, field_name, value)
        db.session.add(settings)
        db.session.commit()
        flash("WhatsApp lead widget settings saved.", "success")
        return redirect(url_for("superadmin.whatsapp_settings"))

    logs = (
        WhatsAppInquiryLog.query
        .order_by(WhatsAppInquiryLog.created_at.desc(), WhatsAppInquiryLog.id.desc())
        .limit(50)
        .all()
    )
    return render_template("superadmin/whatsapp_settings.html", form=form, settings=settings, logs=logs)

@bp.route('/header-builder', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def header_builder():
    settings = SeoSettings.singleton()
    theme = Theme.ensure_default()
    form = SeoSettingsForm(obj=settings)
    if request.method == 'POST' and form.validate_on_submit():
        _save_seo_form_to_settings(form, settings)
        _save_header_footer_theme_controls()
        db.session.add(settings)
        db.session.commit()
        flash('Header Builder saved.', 'success')
        return redirect(url_for('superadmin.header_builder'))
    return render_template('superadmin/header_builder.html', form=form, settings=settings, theme=theme)


@bp.route('/footer-builder', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def footer_builder():
    settings = SeoSettings.singleton()
    form = SeoSettingsForm(obj=settings)
    if request.method == 'POST' and form.validate_on_submit():
        _save_seo_form_to_settings(form, settings)
        db.session.add(settings)
        db.session.commit()
        flash('Footer Builder saved.', 'success')
        return redirect(url_for('superadmin.footer_builder'))
    return render_template('superadmin/footer_builder.html', form=form, settings=settings)


@bp.route('/media-library', methods=['GET', 'POST'])
@login_required
@require_role('SUPERADMIN')
def media_library():
    settings = SeoSettings.singleton()
    form = SeoSettingsForm(obj=settings)
    if request.method == 'POST' and form.validate_on_submit():
        _save_seo_form_to_settings(form, settings)
        db.session.add(settings)
        db.session.commit()
        flash('Media assets saved.', 'success')
        return redirect(url_for('superadmin.media_library'))
    return render_template('superadmin/media_library.html', form=form, settings=settings)


@bp.route("/languages", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def languages_index():
    ensure_default_languages(enable_all=False)
    form = LanguageForm(prefix="language")
    import_form = LanguageImportForm(prefix="import")

    if import_form.submit.data and import_form.validate_on_submit():
        total = ensure_default_languages(enable_all=True)
        audit("languages_imported", target="registry", meta=f"count={total}")
        flash(f"Imported/updated {total} language records.", "success")
        return redirect(url_for("superadmin.languages_index"))

    if form.submit.data and form.validate_on_submit():
        code = (form.code.data or "").strip().lower()
        language = Language.query.filter_by(code=code).first()
        created = language is None
        if created:
            language = Language(code=code)
            db.session.add(language)
        language.name = (form.name.data or "").strip()
        language.native_name = (form.native_name.data or "").strip() or None
        language.direction = form.direction.data or "ltr"
        language.is_enabled = bool(form.is_enabled.data)
        db.session.commit()
        audit("language_saved", target=code, meta=f"enabled={language.is_enabled}")
        flash(f"Language {'created' if created else 'updated'} successfully.", "success")
        return redirect(url_for("superadmin.languages_index"))

    search_query = (request.args.get("q") or "").strip()
    all_languages = Language.query.order_by(Language.is_enabled.desc(), Language.name.asc()).all()
    if search_query:
        q = search_query.lower()
        languages = [
            language for language in all_languages
            if q in (language.code or "").lower()
            or q in (language.name or "").lower()
            or q in ((language.native_name or "").lower())
            or q in (language.direction or "").lower()
            or q in (("enabled" if language.is_enabled else "disabled"))
        ]
    else:
        languages = all_languages

    return render_template(
        "superadmin/languages.html",
        languages=languages,
        total_languages=len(all_languages),
        filtered_languages=len(languages),
        search_query=search_query,
        form=form,
        import_form=import_form,
    )


@bp.post("/languages/<int:language_id>/toggle")
@login_required
@require_role("SUPERADMIN")
def languages_toggle(language_id: int):
    language = Language.query.get_or_404(language_id)
    language.is_enabled = not bool(language.is_enabled)
    db.session.commit()
    audit("language_toggled", target=language.code, meta=f"enabled={language.is_enabled}")
    flash(f"{language.name} is now {'enabled' if language.is_enabled else 'disabled'}.", "success")
    return redirect(url_for("superadmin.languages_index"))


@bp.route("/security", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def security_settings():
    policy = get_policy()
    form = SecuritySettingsForm(obj=policy)
    if request.method == "GET":
        form.otp_rate_limit.data = policy.otp_max_sends_per_hour
        form.failed_login_lock_minutes.data = policy.lockout_minutes

    if form.validate_on_submit():
        try:
            apply_security_policy_updates(policy, form)
            audit("security_policy_updated", target=str(policy.id), meta=f"otp={policy.otp_mode}; student={policy.otp_mode_student or 'inherit'}")
            flash("Security policy updated successfully.", "success")
            return redirect(url_for("superadmin.security_settings"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("superadmin/security_settings.html", form=form, policy=policy)


@bp.route("/api-registry", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def api_registry():
    provider = get_primary_provider()
    form = TranslationProviderForm(obj=provider)
    test_form = TranslationTestForm()
    test_form.target_language_code.choices = language_choices(enabled_only=True, include_codes=True)

    if form.submit.data and form.validate_on_submit():
        provider.name = (form.name.data or "").strip() or "Primary Translation Provider"
        provider.provider_type = form.provider_type.data
        provider.api_base_url = (form.api_base_url.data or "").strip() or None
        if form.api_key.data:
            provider.api_key = form.api_key.data.strip()
        provider.model_name = (form.model_name.data or "").strip() or None
        provider.source_language_code = (form.source_language_code.data or "en").strip().lower() or "en"
        provider.credits_remaining = float(form.credits_remaining.data or 0) if form.credits_remaining.data is not None else None
        provider.credit_unit = (form.credit_unit.data or "credits").strip() or "credits"
        provider.per_request_cost = float(form.per_request_cost.data or 0)
        provider.supports_live_credit_check = bool(form.supports_live_credit_check.data)
        provider.is_enabled = bool(form.is_enabled.data)
        db.session.add(provider)
        db.session.commit()
        flash("Translation API settings saved.", "success")
        return redirect(url_for("superadmin.api_registry"))

    translated_text = None
    translated_from_cache = False
    if test_form.submit.data and test_form.validate_on_submit() and not form.submit.data:
        try:
            translated_text, translated_from_cache = translate_text(
                test_form.text.data,
                test_form.target_language_code.data,
                source_lang=provider.source_language_code or "en",
                context="superadmin:test",
            )
            flash("Translation test completed and cached.", "success")
        except Exception as exc:
            flash(str(exc), "danger")

    recent_logs = ApiCallLog.query.order_by(ApiCallLog.created_at.desc()).limit(12).all()
    cache_entries = 0
    try:
        from ...models.translation_cache import TranslationCache
        cache_entries = TranslationCache.query.count()
    except Exception:
        cache_entries = 0

    return render_template(
        "superadmin/api_registry.html",
        form=form,
        test_form=test_form,
        provider=provider,
        translated_text=translated_text,
        translated_from_cache=translated_from_cache,
        recent_logs=recent_logs,
        cache_entries=cache_entries,
    )


@bp.get("/api-logs")
@login_required
@require_role("SUPERADMIN")
def api_logs():
    rows = ApiCallLog.query.order_by(ApiCallLog.created_at.desc()).limit(200).all()
    summary = {
        "total_rows": len(rows),
        "ok_rows": sum(1 for row in rows if row.ok),
        "tracked_tokens": sum(int(row.total_tokens or 0) for row in rows),
        "estimated_cost": round(sum(float(row.estimated_cost or 0) for row in rows), 4),
    }
    return render_template("superadmin/api_logs.html", rows=rows, summary=summary)


@bp.route("/api-workbench", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def api_workbench():
    active_tab = _api_workbench_tab(request.values.get("tab"))

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        entry_id = request.form.get("entry_id", type=int) or 0
        entry = ApiCatalogEntry.query.get(entry_id) if entry_id else None

        if action == "save_entry":
            service_picker = (request.form.get("service_key") or "").strip()
            custom_service_name = (request.form.get("custom_service_name") or "").strip()
            category_key, service_key, service_name = _api_workbench_service_meta(service_picker, custom_service_name, active_tab)

            provider_name = (request.form.get("provider_name") or "").strip()
            if not provider_name:
                flash("Provider name is required.", "warning")
                redirect_id = f"&edit_id={entry_id}" if entry_id else ""
                return redirect(url_for("superadmin.api_workbench", tab=active_tab) + redirect_id)

            if service_picker == "__custom__" and not custom_service_name:
                flash("Please enter a custom service name when using the manual service option.", "warning")
                redirect_id = f"&edit_id={entry_id}" if entry_id else ""
                return redirect(url_for("superadmin.api_workbench", tab=active_tab) + redirect_id)

            if not entry:
                entry = ApiCatalogEntry()

            entry.category_key = category_key
            entry.service_key = service_key
            entry.service_name = service_name
            entry.provider_name = provider_name
            entry.provider_family = (request.form.get("provider_family") or "").strip() or None
            entry.pricing_tier = (request.form.get("pricing_tier") or ApiCatalogEntry.PRICING_PAID).strip().lower()
            entry.market_status = (request.form.get("market_status") or ApiCatalogEntry.MARKET_ESTABLISHED).strip().lower()
            entry.recommendation_level = (request.form.get("recommendation_level") or ApiCatalogEntry.RECOMMENDATION_RESEARCH).strip().lower()
            entry.official_url = (request.form.get("official_url") or "").strip() or None
            entry.api_base_url = (request.form.get("api_base_url") or "").strip() or None
            entry.advantage_summary = (request.form.get("advantage_summary") or "").strip() or None
            entry.best_for = (request.form.get("best_for") or "").strip() or None
            entry.notes = (request.form.get("notes") or "").strip() or None
            entry.is_selected = bool(request.form.get("is_selected"))
            entry.is_active_candidate = bool(request.form.get("is_active_candidate"))
            db.session.add(entry)
            db.session.flush()
            if entry.is_selected:
                (
                    ApiCatalogEntry.query
                    .filter(ApiCatalogEntry.service_key == entry.service_key, ApiCatalogEntry.id != entry.id)
                    .update({"is_selected": False}, synchronize_session=False)
                )
            db.session.commit()
            flash("API workbench entry saved.", "success")
            return redirect(url_for("superadmin.api_workbench", tab=entry.category_key))

        if not entry:
            flash("API workbench entry not found.", "warning")
            return redirect(url_for("superadmin.api_workbench", tab=active_tab))

        if action == "select_entry":
            (
                ApiCatalogEntry.query
                .filter(ApiCatalogEntry.service_key == entry.service_key)
                .update({"is_selected": False}, synchronize_session=False)
            )
            entry.is_selected = True
            db.session.commit()
            flash("Selected provider updated for that API service.", "success")
            return redirect(url_for("superadmin.api_workbench", tab=entry.category_key))

        if action == "toggle_active":
            entry.is_active_candidate = not entry.is_active_candidate
            db.session.commit()
            flash("Provider tracking status updated.", "success")
            return redirect(url_for("superadmin.api_workbench", tab=entry.category_key))

        if action == "delete_entry":
            target_tab = entry.category_key
            db.session.delete(entry)
            db.session.commit()
            flash("API workbench entry deleted.", "success")
            return redirect(url_for("superadmin.api_workbench", tab=target_tab))

    active_tab = _api_workbench_tab(request.args.get("tab"))
    edit_id = request.args.get("edit_id", type=int) or 0
    edit_entry = ApiCatalogEntry.query.get(edit_id) if edit_id else None
    if edit_entry and edit_entry.category_key in _API_WORKBENCH_GROUP_MAP:
        active_tab = edit_entry.category_key

    service_rows, entries = _api_workbench_rows_for_tab(active_tab)
    tab_cards = []
    for group in _API_WORKBENCH_GROUPS:
        rows, tab_entries = _api_workbench_rows_for_tab(group["key"])
        tab_cards.append({
            "key": group["key"],
            "label": group["label"],
            "description": group["description"],
            "service_count": len(rows),
            "entry_count": len(tab_entries),
            "selected_count": sum(1 for row in tab_entries if row.is_selected),
        })

    pricing_choices = [
        (ApiCatalogEntry.PRICING_FREE, "Free"),
        (ApiCatalogEntry.PRICING_FREEMIUM, "Freemium"),
        (ApiCatalogEntry.PRICING_PAID, "Paid"),
        (ApiCatalogEntry.PRICING_ENTERPRISE, "Enterprise"),
    ]
    market_choices = [
        (ApiCatalogEntry.MARKET_NEW, "New"),
        (ApiCatalogEntry.MARKET_EMERGING, "Emerging"),
        (ApiCatalogEntry.MARKET_ESTABLISHED, "Established"),
        (ApiCatalogEntry.MARKET_MATURE, "Mature"),
    ]
    recommendation_choices = [
        (ApiCatalogEntry.RECOMMENDATION_BEST, "Best Fit"),
        (ApiCatalogEntry.RECOMMENDATION_RECOMMENDED, "Recommended"),
        (ApiCatalogEntry.RECOMMENDATION_WATCH, "Watchlist"),
        (ApiCatalogEntry.RECOMMENDATION_RESEARCH, "Research"),
    ]
    active_group = _API_WORKBENCH_GROUP_MAP[active_tab]
    service_options = [("__custom__", "Custom / Manual API")] + list(active_group["services"])
    known_service_keys = {value for value, _label in service_options}
    edit_service_key = (
        edit_entry.service_key
        if edit_entry and edit_entry.service_key in known_service_keys
        else "__custom__"
    )

    summary = {
        "services_in_tab": len(service_rows),
        "tracked_entries": len(entries),
        "selected_entries": sum(1 for row in entries if row.is_selected),
        "best_fit_entries": sum(1 for row in entries if row.recommendation_level == ApiCatalogEntry.RECOMMENDATION_BEST),
        "free_entries": sum(1 for row in entries if row.pricing_tier == ApiCatalogEntry.PRICING_FREE),
        "freemium_entries": sum(1 for row in entries if row.pricing_tier == ApiCatalogEntry.PRICING_FREEMIUM),
    }

    return render_template(
        "superadmin/api_workbench.html",
        active_tab=active_tab,
        active_group=active_group,
        tab_cards=tab_cards,
        service_rows=service_rows,
        entries=entries,
        edit_entry=edit_entry,
        edit_service_key=edit_service_key,
        service_options=service_options,
        pricing_choices=pricing_choices,
        market_choices=market_choices,
        recommendation_choices=recommendation_choices,
        summary=summary,
    )


@bp.get("/learner-ops")
@login_required
@require_role("SUPERADMIN")
def learner_ops():
    q = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("role") or "ALL").strip().upper()
    course_id = request.args.get("course_id", type=int) or 0
    admin_id = request.args.get("admin_id", type=int) or 0
    institute_query = (request.args.get("institute") or "").strip()
    city_query = (request.args.get("city") or "").strip()
    browser_query = (request.args.get("browser") or "").strip()
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()

    valid_roles = {"ALL"} | {role.value for role in Role}
    if role_filter not in valid_roles:
        role_filter = "ALL"

    report = _superadmin_learner_ops_report(
        q=q,
        role_filter=role_filter,
        course_id=course_id,
        admin_id=admin_id,
        institute_query=institute_query,
        city_query=city_query,
        browser_query=browser_query,
        date_from=_parse_filter_datetime(date_from_raw),
        date_to=_parse_filter_datetime(date_to_raw, end_of_day=True),
    )

    role_choices = [("ALL", "All roles")] + [
        (role.value, role.value.replace("_", " ").title())
        for role in Role
    ]
    course_choices = [(0, "All courses")] + [
        (row.id, row.title or f"Course #{row.id}")
        for row in Course.query.order_by(Course.title.asc(), Course.created_at.desc()).all()
    ]
    admin_choices = [(0, "All admin / institute owners")] + _admin_scope_choices(include_none=False)

    return render_template(
        "superadmin/learner_ops.html",
        report=report,
        role_choices=role_choices,
        course_choices=course_choices,
        admin_choices=admin_choices,
        current_query=q,
        current_role=role_filter,
        current_course_id=course_id,
        current_admin_id=admin_id,
        current_institute=institute_query,
        current_city=city_query,
        current_browser=browser_query,
        current_date_from=date_from_raw,
        current_date_to=date_to_raw,
    )




@bp.get("/ai-ml-export")
@login_required
@require_role("SUPERADMIN")
def ai_ml_export():
    export_format = (request.args.get("format") or "csv").strip().lower()
    exportable_only = (request.args.get("all") or "0") != "1"
    if export_format == "jsonl":
        payload = AIMLExportService.export_jsonl(exportable_only=exportable_only)
        return Response(payload, mimetype="application/jsonl", headers={"Content-Disposition": "attachment; filename=ai_ml_export.jsonl"})
    payload = AIMLExportService.export_csv(exportable_only=exportable_only)
    return Response(payload, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=ai_ml_export.csv"})
@bp.get("/access-activity")
@login_required
@require_role("SUPERADMIN")
def access_activity():
    q = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("role") or "all").strip().upper()
    status_filter = (request.args.get("status") or "all").strip().lower()
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()
    date_from = _parse_filter_datetime(date_from_raw)
    date_to = _parse_filter_datetime(date_to_raw, end_of_day=True)
    valid_roles = {
        Role.SUPERADMIN.value,
        Role.ADMIN.value,
        Role.SUB_ADMIN.value,
        Role.SEO.value,
        Role.ACCOUNTS.value,
        Role.SUPPORT.value,
        Role.EDITOR.value,
        Role.TEACHER.value,
        Role.STUDENT.value,
        Role.PARENT.value,
    }
    if role_filter not in valid_roles:
        role_filter = "ALL"
    if status_filter not in {"all", "active", "revoked", "success", "failed"}:
        status_filter = "all"

    login_query = (
        LoginEvent.query
        .join(User, User.id == LoginEvent.user_id)
    )
    session_query = (
        UserSession.query
        .join(User, User.id == UserSession.user_id)
    )

    if role_filter != "ALL":
        login_query = login_query.filter(User.role == role_filter)
        session_query = session_query.filter(User.role == role_filter)

    if q:
        search = f"%{q}%"
        login_query = login_query.filter(
            or_(
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.username.ilike(search),
                User.email.ilike(search),
                LoginEvent.ip_address.ilike(search),
                LoginEvent.city.ilike(search),
                LoginEvent.country.ilike(search),
            )
        )
        session_query = session_query.filter(
            or_(
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.username.ilike(search),
                User.email.ilike(search),
                UserSession.ip_address.ilike(search),
                UserSession.city.ilike(search),
                UserSession.country.ilike(search),
                UserSession.browser.ilike(search),
                UserSession.os_name.ilike(search),
            )
        )

    if date_from:
        login_query = login_query.filter(LoginEvent.created_at >= date_from)
        session_query = session_query.filter(UserSession.last_seen_at >= date_from)
    if date_to:
        login_query = login_query.filter(LoginEvent.created_at <= date_to)
        session_query = session_query.filter(UserSession.last_seen_at <= date_to)

    if status_filter == "success":
        login_query = login_query.filter(LoginEvent.success.is_(True))
    elif status_filter == "failed":
        login_query = login_query.filter(LoginEvent.success.is_(False))
    elif status_filter == "active":
        session_query = session_query.filter(UserSession.revoked_at.is_(None))
    elif status_filter == "revoked":
        session_query = session_query.filter(UserSession.revoked_at.isnot(None))

    login_rows = login_query.order_by(LoginEvent.created_at.desc()).limit(250).all()
    session_rows = session_query.order_by(UserSession.last_seen_at.desc()).limit(250).all()
    live_cutoff = datetime.utcnow() - timedelta(minutes=30)

    summary = {
        "total_login_rows": len(login_rows),
        "successful_logins": sum(1 for row in login_rows if row.success),
        "failed_logins": sum(1 for row in login_rows if not row.success),
        "active_sessions": sum(1 for row in session_rows if row.is_active),
        "live_now": sum(
            1 for row in session_rows
            if row.revoked_at is None and row.last_seen_at and row.last_seen_at >= live_cutoff
        ),
    }
    role_choices = [("ALL", "All roles")] + [(role.value, role.value.replace("_", " ").title()) for role in Role]

    return render_template(
        "superadmin/access_activity.html",
        login_rows=login_rows,
        session_rows=session_rows,
        summary=summary,
        current_query=q,
        current_role=role_filter,
        current_status=status_filter,
        current_date_from=date_from_raw,
        current_date_to=date_to_raw,
        role_choices=role_choices,
    )


@bp.route("/chat-moderation", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def chat_moderation_queue():
    if request.method == "POST":
        event_id = request.form.get("event_id", type=int)
        status = (request.form.get("moderation_status") or "").strip().lower()
        notes = (request.form.get("moderator_notes") or "").strip()
        try:
            EconomyService.update_moderation_event(event_id, status, current_user.id, notes)
            db.session.commit()
            flash("Moderation event updated.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "warning")
        return redirect(url_for("superadmin.chat_moderation_queue"))

    rows = EconomyService.moderation_queue(limit=300)
    return render_template(
        "superadmin/chat_moderation.html",
        rows=rows,
        panel_role="superadmin",
    )


@bp.get("/audit")
@login_required
@require_role("SUPERADMIN")
def audit_logs():
    return render_template("superadmin/audit_logs.html", logs=[])


@bp.get("/coming-soon/<feature>")
@login_required
@require_role("SUPERADMIN")
def coming_soon(feature: str):
    return render_template(
        "superadmin/coming_soon.html",
        feature_title=feature.replace("-", " ").title(),
        phase="Roadmap",
        message="This feature is planned for a later phase.",
    )


def _reading_topic_query():
    return ReadingTopic.query.order_by(ReadingTopic.display_order.asc(), ReadingTopic.title.asc())


def _safe_int_value(value, default=0, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _normalize_reading_topic_code(raw: str | None, fallback_title: str | None = None) -> str:
    base = (raw or "").strip().lower()
    if not base and fallback_title:
        base = (fallback_title or "").strip().lower()
    cleaned = []
    last_dash = False
    for char in base:
        if char.isalnum():
            cleaned.append(char)
            last_dash = False
        elif char in {" ", "_", "-", "/"}:
            if not last_dash and cleaned:
                cleaned.append("-")
                last_dash = True
    result = "".join(cleaned).strip("-")
    return result[:80]




def _reading_course_rows():
    return (
        Course.query
        .filter(
            Course.status != "archived",
            func.lower(func.coalesce(Course.track_type, "")) == "reading",
        )
        .order_by(Course.title.asc())
        .all()
    )

def _parse_reading_topic_form(existing_topic: ReadingTopic | None = None):
    title = (request.form.get("title") or "").strip()
    code_source = request.form.get("code") if existing_topic is None else existing_topic.code
    code = _normalize_reading_topic_code(code_source, fallback_title=title)
    category = (request.form.get("category") or "").strip() or None
    level = (request.form.get("level") or ReadingTopic.LEVEL_BASIC).strip().lower()
    description = (request.form.get("description") or "").strip() or None
    display_order = _safe_int_value(request.form.get("display_order"), default=0, minimum=0)
    course_id = _safe_int_value(request.form.get("course_id") or request.args.get("course_id"), default=0, minimum=0) or None
    course_level_number = _safe_int_value(request.form.get("course_level_number"), default=0, minimum=0) or None
    is_active = bool(request.form.get("is_active"))

    errors: list[str] = []
    if not title:
        errors.append("Topic title is required.")
    if not code:
        errors.append("Topic code could not be generated. Please use a title with letters or numbers.")
    if level not in {ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED}:
        errors.append("Please select a valid level.")

    if not course_id:
        errors.append("Please open a reading course first. Reading topics now live only inside a course.")
    else:
        course = Course.query.get(course_id)
        track_type = ((getattr(course, "track_type", "") or "").strip().lower() if course else "")
        if not course or track_type != "reading":
            errors.append("Please link reading topics only to reading courses.")
        elif course_level_number and course_level_number > max(int(getattr(course, "max_level", 1) or 1), 1):
            errors.append("Course level number is higher than the selected reading course max level.")

    return {
        "code": code,
        "title": title,
        "category": category,
        "level": level,
        "description": description,
        "display_order": display_order,
        "course_id": course_id,
        "course_level_number": course_level_number,
        "is_active": is_active,
    }, errors


@bp.route("/reading/topics", methods=["GET", "POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_topics():
    selected_course_id = _safe_int_value(request.values.get("course_id"), default=0, minimum=0)
    selected_topic_id = _safe_int_value(request.values.get("topic_id"), default=0, minimum=0)
    selected_topic = ReadingTopic.query.get(selected_topic_id) if selected_topic_id else None
    if not selected_course_id and selected_topic and selected_topic.course_id:
        selected_course_id = selected_topic.course_id
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and ((selected_course.track_type or "").strip().lower() != "reading"):
        flash("Please open reading topics from a reading course only.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=selected_course.id))

    if request.method == "POST":
        payload, errors = _parse_reading_topic_form()
        existing = ReadingTopic.query.filter(ReadingTopic.code == payload["code"]).first()
        if existing:
            errors.append("A reading topic with this code already exists.")
        if errors:
            for message in errors:
                flash(message, "warning")
            if payload.get("course_id"):
                return redirect(url_for("superadmin.reading_topics", course_id=payload.get("course_id")))
            return redirect(url_for("superadmin.courses"))

        topic = ReadingTopic(**payload)
        db.session.add(topic)
        db.session.commit()
        flash("Reading topic created successfully.", "success")
        return redirect(url_for("superadmin.reading_topics", course_id=topic.course_id))

    topics = _reading_topic_query()
    if selected_course_id:
        topics = topics.filter(ReadingTopic.course_id == selected_course_id)
    topics = topics.all()
    return render_template(
        "superadmin/reading_topics.html",
        topics=topics,
        selected_course=selected_course,
        selected_course_id=selected_course_id,
        level_choices=(ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED),
        course_rows=_reading_course_rows(),
    )


@bp.route("/reading/topics/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_topic_edit(topic_id: int):
    topic = ReadingTopic.query.get_or_404(topic_id)
    if request.method == "POST":
        payload, errors = _parse_reading_topic_form(existing_topic=topic)
        duplicate = ReadingTopic.query.filter(ReadingTopic.code == payload["code"], ReadingTopic.id != topic.id).first()
        if duplicate:
            errors.append("Another reading topic already uses this code.")
        if errors:
            for message in errors:
                flash(message, "warning")
            return redirect(url_for("superadmin.reading_topic_edit", topic_id=topic.id))

        for key, value in payload.items():
            if key != "code":
                setattr(topic, key, value)
        db.session.commit()
        flash("Reading topic updated successfully.", "success")
        return redirect(url_for("superadmin.reading_topics", course_id=topic.course_id) if topic.course_id else url_for("superadmin.courses"))

    return render_template(
        "superadmin/reading_topic_edit.html",
        topic=topic,
        level_choices=(ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED),
        course_rows=_reading_course_rows(),
    )


@bp.route("/reading/topics/<int:topic_id>/toggle", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_topic_toggle(topic_id: int):
    topic = ReadingTopic.query.get_or_404(topic_id)
    topic.is_active = not bool(topic.is_active)
    db.session.commit()
    flash("Reading topic status updated.", "success")
    return redirect(url_for("superadmin.reading_topics", course_id=topic.course_id) if topic.course_id else url_for("superadmin.courses"))


@bp.route("/reading/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_topic_delete(topic_id: int):
    topic = ReadingTopic.query.get_or_404(topic_id)
    course_id = topic.course_id

    try:
        linked_passages = ReadingPassage.query.filter_by(topic_id=topic.id).all()
        for passage in linked_passages:
            linked_questions = ReadingQuestion.query.filter_by(passage_id=passage.id).all()
            for question in linked_questions:
                db.session.delete(question)
            db.session.delete(passage)

        db.session.delete(topic)
        db.session.commit()
        flash("Reading topic with linked passages and questions deleted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete reading topic: {exc}", "warning")

    return redirect(url_for("superadmin.reading_topics", course_id=course_id) if course_id else url_for("superadmin.courses"))




@bp.route("/reading/passages", methods=["GET", "POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passages():
    ReadingProviderRegistryService.ensure_defaults()
    selected_course_id = _safe_int_value(request.values.get("course_id"), default=0, minimum=0)
    selected_topic_id = _safe_int_value(request.values.get("topic_id"), default=0, minimum=0)
    selected_topic_for_course = ReadingTopic.query.get(selected_topic_id) if selected_topic_id else None
    if not selected_course_id and selected_topic_for_course and selected_topic_for_course.course_id:
        selected_course_id = selected_topic_for_course.course_id
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and _normalize_course_track_type(selected_course.track_type) != "reading":
        flash("Please open reading pages from a reading course only.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=selected_course.id))
    if request.method == "POST":
        topic_id = _safe_int_value(request.form.get("topic_id"), default=0, minimum=0)
        topic = ReadingTopic.query.get(topic_id) if topic_id else None
        level = (request.form.get("level") or "").strip().lower()
        length_mode = (request.form.get("length_mode") or ReadingPassage.LENGTH_MEDIUM).strip().lower()
        course_id = _safe_int_value(request.form.get("course_id") or request.args.get("course_id"), default=0, minimum=0) or None
        course_level_number = _safe_int_value(request.form.get("course_level_number"), default=0, minimum=0) or None

        if not topic:
            flash("Please select a valid reading topic.", "warning")
            return redirect(url_for("superadmin.reading_passages", course_id=selected_course_id) if selected_course_id else url_for("superadmin.reading_passages"))
        if level not in {ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED}:
            flash("Please select a valid student level.", "warning")
            return redirect(url_for("superadmin.reading_passages", topic_id=topic.id))
        if length_mode not in {ReadingPassage.LENGTH_SHORT, ReadingPassage.LENGTH_MEDIUM, ReadingPassage.LENGTH_LONG}:
            flash("Please select a valid passage length.", "warning")
            return redirect(url_for("superadmin.reading_passages", topic_id=topic.id))

        mode = (request.form.get("mode") or "ai").strip().lower()
        target_words = _safe_int_value(request.form.get("target_words"), default=0, minimum=0) or None
        if mode == "manual":
            manual_title = (request.form.get("manual_title") or "").strip() or f"{topic.title} • {level.title()} • Manual Passage"
            manual_content = (request.form.get("manual_content") or "").strip()
            if not manual_content:
                flash("Please enter manual passage content.", "warning")
                return redirect(url_for("superadmin.reading_passages", topic_id=topic.id, course_id=(course_id or topic.course_id or selected_course_id or None)))
            passage = ReadingPassage(
                topic_id=topic.id,
                topic_title_snapshot=topic.title,
                level=level,
                length_mode=length_mode,
                title=manual_title,
                content=manual_content,
                word_count=len([w for w in manual_content.split() if w.strip()]),
                generation_notes="Created manually by SuperAdmin.",
                generation_source="manual",
                course_id=course_id or topic.course_id,
                course_level_number=course_level_number or topic.course_level_number,
                status=ReadingPassage.STATUS_DRAFT,
                is_active=True,
                is_published=False,
            )
            db.session.add(passage)
            db.session.commit()
            flash("Manual reading passage created successfully.", "success")
            return redirect(url_for("superadmin.reading_passages", topic_id=topic.id, course_id=(course_id or topic.course_id or selected_course_id or None)))
        result = ReadingPassageGenerationService.generate_and_store(topic=topic, level=level, length_mode=length_mode, target_words=target_words)
        if result.ok and getattr(result, "passage", None):
            result.passage.course_id = course_id or topic.course_id
            result.passage.course_level_number = course_level_number or topic.course_level_number
            db.session.commit()
        flash(result.message, "success" if result.ok else "warning")
        return redirect(url_for("superadmin.reading_passages", topic_id=topic.id, course_id=(course_id or topic.course_id or selected_course_id or None)))

    selected_topic_id = _safe_int_value(request.args.get("topic_id"), default=0, minimum=0)
    topic_query = _reading_topic_query()
    if selected_course_id:
        topic_query = topic_query.filter(ReadingTopic.course_id == selected_course_id)
    topic_rows = topic_query.all()
    selected_topic = ReadingTopic.query.get(selected_topic_id) if selected_topic_id else None
    if not selected_course_id and selected_topic and selected_topic.course_id:
        selected_course_id = selected_topic.course_id
        selected_course = Course.query.get(selected_course_id)
        topic_query = _reading_topic_query().filter(ReadingTopic.course_id == selected_course_id)
        topic_rows = topic_query.all()

    query = ReadingPassage.query.order_by(ReadingPassage.created_at.desc(), ReadingPassage.id.desc())
    if selected_course_id:
        query = query.filter(ReadingPassage.course_id == selected_course_id)
    if selected_topic:
        query = query.filter(ReadingPassage.topic_id == selected_topic.id)
    passages = query.all()

    course_rows = _reading_course_rows()
    return render_template(
        "superadmin/reading_passages.html",
        topics=topic_rows,
        selected_topic=selected_topic,
        selected_course=selected_course,
        selected_course_id=selected_course_id,
        passages=passages,
        level_choices=(ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED),
        length_choices=(ReadingPassage.LENGTH_SHORT, ReadingPassage.LENGTH_MEDIUM, ReadingPassage.LENGTH_LONG),
        default_provider=ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_PASSAGE),
        course_rows=course_rows,
        review_counts={
            "draft_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_DRAFT).count(),
            "review_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_REVIEW).count(),
            "published_passages": ReadingPassage.query.filter_by(is_published=True).count(),
            "rejected_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_REJECTED).count(),
        },
    )


@bp.route("/reading/passages/<int:passage_id>/toggle", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passage_toggle(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    passage.is_active = not bool(passage.is_active)
    db.session.commit()
    flash("Reading passage status updated.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_passages", topic_id=passage.topic_id))


@bp.route("/reading/passages/<int:passage_id>/submit-review", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passage_submit_review(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    passage.status = ReadingPassage.STATUS_REVIEW
    passage.is_published = False
    passage.review_notes = None
    passage.reviewed_at = None
    passage.reviewed_by_id = None
    db.session.commit()
    flash("Reading passage moved to review.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_passages", topic_id=passage.topic_id, course_id=passage.course_id))


@bp.route("/reading/passages/<int:passage_id>/publish", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passage_publish(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if passage.status != ReadingPassage.STATUS_APPROVED and not passage.is_published:
        flash("Approve the passage first before publishing it for students.", "warning")
        return redirect(request.referrer or url_for("superadmin.reading_passages", topic_id=passage.topic_id, course_id=passage.course_id))
    passage.is_published = not bool(passage.is_published)
    if passage.is_published:
        passage.is_active = True
    db.session.commit()
    flash("Reading passage publication status updated.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_passages", topic_id=passage.topic_id))


@bp.route("/reading/passages/<int:passage_id>/approve", methods=["POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_passage_approve(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    passage.status = ReadingPassage.STATUS_APPROVED
    passage.is_active = True
    passage.review_notes = (request.form.get("review_notes") or "").strip() or None
    passage.reviewed_at = datetime.utcnow()
    passage.reviewed_by_id = current_user.id
    db.session.commit()
    flash("Reading passage approved.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_review_queue"))


@bp.route("/reading/passages/<int:passage_id>/reject", methods=["POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_passage_reject(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    passage.status = ReadingPassage.STATUS_REJECTED
    passage.is_published = False
    passage.review_notes = (request.form.get("review_notes") or "").strip() or None
    passage.reviewed_at = datetime.utcnow()
    passage.reviewed_by_id = current_user.id
    db.session.commit()
    flash("Reading passage rejected.", "warning")
    return redirect(request.referrer or url_for("superadmin.reading_review_queue"))


@bp.route("/reading/passages/<int:passage_id>/edit", methods=["GET", "POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_passage_edit(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    if request.method == "POST":
        passage.title = (request.form.get("title") or passage.title).strip()
        passage.content = (request.form.get("content") or passage.content).strip()
        passage.generation_notes = (request.form.get("generation_notes") or "").strip() or passage.generation_notes
        passage.course_id = _safe_int_value(request.form.get("course_id"), default=0, minimum=0) or None
        passage.word_count = len([w for w in passage.content.split() if w.strip()])
        passage.status = ReadingPassage.STATUS_DRAFT
        passage.is_published = False
        passage.review_notes = None
        passage.reviewed_at = None
        passage.reviewed_by_id = None
        db.session.commit()
        flash("Reading passage updated successfully.", "success")
        return redirect(url_for("superadmin.reading_passages", topic_id=passage.topic_id, course_id=passage.course_id))
    course_rows = _reading_course_rows()
    return render_template("superadmin/reading_passage_edit.html", passage=passage, course_rows=course_rows)


@bp.route("/reading/passages/<int:passage_id>/regenerate", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passage_regenerate(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    topic = passage.topic
    result = ReadingPassageGenerationService.generate_and_store(topic=topic, level=passage.level, length_mode=passage.length_mode)
    if result.ok:
        if getattr(result, 'passage', None):
            result.passage.course_id = passage.course_id or getattr(topic, 'course_id', None)
            result.passage.course_level_number = passage.course_level_number or getattr(topic, 'course_level_number', None)
        passage.is_active = False
        passage.is_published = False
        passage.status = ReadingPassage.STATUS_ARCHIVED
        db.session.commit()
    flash(result.message if result.ok else (result.message or "Reading passage regeneration failed."), "success" if result.ok else "warning")
    return redirect(request.referrer or url_for("superadmin.reading_passages", topic_id=passage.topic_id))


@bp.route("/reading/passages/<int:passage_id>/delete", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_passage_delete(passage_id: int):
    passage = ReadingPassage.query.get_or_404(passage_id)
    topic_id = passage.topic_id
    course_id = passage.course_id

    try:
        linked_questions = ReadingQuestion.query.filter_by(passage_id=passage.id).all()
        for question in linked_questions:
            db.session.delete(question)

        db.session.delete(passage)
        db.session.commit()
        flash("Reading passage and its linked questions deleted successfully.", "success")

    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete passage: {exc}", "warning")

    return redirect(
        request.referrer
        or url_for("superadmin.reading_passages", topic_id=topic_id, course_id=course_id)
    )


@bp.route("/reading/questions", methods=["GET", "POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_questions():
    ReadingProviderRegistryService.ensure_defaults()
    selected_course_id = _safe_int_value(request.values.get("course_id"), default=0, minimum=0)
    selected_passage_id = _safe_int_value(request.values.get("passage_id"), default=0, minimum=0)
    selected_passage_for_course = ReadingPassage.query.get(selected_passage_id) if selected_passage_id else None
    if not selected_course_id and selected_passage_for_course and selected_passage_for_course.course_id:
        selected_course_id = selected_passage_for_course.course_id
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    if selected_course and _normalize_course_track_type(selected_course.track_type) != "reading":
        flash("Please open reading pages from a reading course only.", "warning")
        return redirect(url_for("superadmin.course_detail", course_id=selected_course.id))
    if request.method == "POST":
        passage_id = _safe_int_value(request.form.get("passage_id"), default=0, minimum=0)
        passage = ReadingPassage.query.get(passage_id) if passage_id else None
        level = (request.form.get("level") or "").strip().lower()
        mcq_count = _safe_int_value(request.form.get("mcq_count"), default=3, minimum=0)
        fill_blank_count = _safe_int_value(request.form.get("fill_blank_count"), default=3, minimum=0)
        true_false_count = _safe_int_value(request.form.get("true_false_count"), default=3, minimum=0)
        replace_existing = bool(request.form.get("replace_existing"))

        if not passage:
            flash("Please select a valid passage.", "warning")
            return redirect(url_for("superadmin.reading_questions", course_id=selected_course_id) if selected_course_id else url_for("superadmin.reading_questions"))
        if selected_course_id and passage.course_id != selected_course_id:
            flash("Selected passage does not belong to the current reading course.", "warning")
            return redirect(url_for("superadmin.reading_questions", course_id=selected_course_id))
        if level not in {ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED}:
            flash("Please select a valid difficulty level.", "warning")
            return redirect(url_for("superadmin.reading_questions", passage_id=passage.id))
        if mcq_count + fill_blank_count + true_false_count <= 0:
            flash("Please request at least one question.", "warning")
            return redirect(url_for("superadmin.reading_questions", passage_id=passage.id))

        mode = (request.form.get("mode") or "ai").strip().lower()
        if mode == "manual":
            question_text = (request.form.get("manual_question_text") or "").strip()
            correct_answer = (request.form.get("manual_correct_answer") or "").strip()
            explanation = (request.form.get("manual_explanation") or "").strip() or None
            options_lines = [line.strip() for line in (request.form.get("manual_options") or "").splitlines() if line.strip()]
            question_type = (request.form.get("manual_question_type") or ReadingQuestion.TYPE_MCQ).strip().lower()
            if question_type not in {ReadingQuestion.TYPE_MCQ, ReadingQuestion.TYPE_FILL_BLANK, ReadingQuestion.TYPE_TRUE_FALSE}:
                question_type = ReadingQuestion.TYPE_MCQ
            if not question_text:
                flash("Please enter manual question text.", "warning")
                return redirect(url_for("superadmin.reading_questions", passage_id=passage.id, course_id=(passage.course_id or selected_course_id or None)))
            next_order = (db.session.query(func.max(ReadingQuestion.display_order)).filter(ReadingQuestion.passage_id == passage.id).scalar() or 0) + 1
            question = ReadingQuestion(
                passage_id=passage.id,
                topic_id=passage.topic_id,
                question_type=question_type,
                level=level,
                display_order=next_order,
                prompt_snapshot="Manual question entry",
                question_text=question_text,
                options_json=json.dumps(options_lines, ensure_ascii=False),
                correct_answer=correct_answer or None,
                explanation=explanation,
                source_sentence=None,
                provider_name_snapshot="Manual",
                status=ReadingQuestion.STATUS_DRAFT,
                is_active=True,
            )
            db.session.add(question)
            db.session.commit()
            flash("Manual reading question created successfully.", "success")
            return redirect(url_for("superadmin.reading_questions", passage_id=passage.id, course_id=(passage.course_id or selected_course_id or None)))
        result = ReadingQuestionGenerationService.generate_and_store(
            passage=passage,
            level=level,
            mcq_count=mcq_count,
            fill_blank_count=fill_blank_count,
            true_false_count=true_false_count,
            replace_existing=replace_existing,
        )
        flash(result.message, "success" if result.ok else "warning")
        return redirect(url_for("superadmin.reading_questions", passage_id=passage.id, course_id=(passage.course_id or selected_course_id or None)))

    selected_passage_id = _safe_int_value(request.args.get("passage_id"), default=0, minimum=0)
    selected_passage = ReadingPassage.query.get(selected_passage_id) if selected_passage_id else None
    if not selected_course_id and selected_passage and selected_passage.course_id:
        selected_course_id = selected_passage.course_id
        selected_course = Course.query.get(selected_course_id)
    passage_query = ReadingPassage.query.order_by(ReadingPassage.created_at.desc(), ReadingPassage.id.desc())
    if selected_course_id:
        passage_query = passage_query.filter(ReadingPassage.course_id == selected_course_id)
    passages = passage_query.all()

    query = ReadingQuestion.query.join(ReadingPassage, ReadingPassage.id == ReadingQuestion.passage_id).order_by(ReadingQuestion.passage_id.desc(), ReadingQuestion.display_order.asc(), ReadingQuestion.id.asc())
    if selected_course_id:
        query = query.filter(ReadingPassage.course_id == selected_course_id)
    if selected_passage:
        query = query.filter(ReadingQuestion.passage_id == selected_passage.id)
    questions = query.all()

    grouped_questions = {}
    for row in questions:
        grouped_questions.setdefault(row.passage_id, {"passage": row.passage, "items": []})["items"].append(row)

    return render_template(
        "superadmin/reading_questions.html",
        passages=passages,
        selected_passage=selected_passage,
        selected_course=selected_course,
        selected_course_id=selected_course_id,
        grouped_questions=grouped_questions,
        level_choices=(ReadingTopic.LEVEL_BASIC, ReadingTopic.LEVEL_INTERMEDIATE, ReadingTopic.LEVEL_ADVANCED),
        default_provider=ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_QUESTION),
    )

@bp.route("/reading/questions/<int:question_id>/approve", methods=["POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_question_approve(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    question.status = ReadingQuestion.STATUS_APPROVED
    question.review_notes = (request.form.get("review_notes") or "").strip() or None
    question.reviewed_at = datetime.utcnow()
    question.reviewed_by_id = current_user.id
    db.session.commit()
    flash("Reading question approved.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_review_queue"))


@bp.route("/reading/questions/<int:question_id>/reject", methods=["POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_question_reject(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    question.status = ReadingQuestion.STATUS_REJECTED
    question.review_notes = (request.form.get("review_notes") or "").strip() or None
    question.reviewed_at = datetime.utcnow()
    question.reviewed_by_id = current_user.id
    db.session.commit()
    flash("Reading question rejected.", "warning")
    return redirect(request.referrer or url_for("superadmin.reading_review_queue"))


@bp.route("/reading/questions/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_question_edit(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    if request.method == "POST":
        question.question_text = (request.form.get("question_text") or question.question_text).strip()
        question.correct_answer = (request.form.get("correct_answer") or question.correct_answer or "").strip() or None
        question.explanation = (request.form.get("explanation") or question.explanation or "").strip() or None
        question.options_json = (request.form.get("options_json") or question.options_json or "").strip() or None
        question.status = ReadingQuestion.STATUS_DRAFT
        question.review_notes = None
        question.reviewed_at = None
        question.reviewed_by_id = None
        db.session.commit()
        flash("Reading question updated successfully.", "success")
        return redirect(url_for("superadmin.reading_questions", passage_id=question.passage_id, course_id=getattr(question.passage, "course_id", None)))
    return render_template("superadmin/reading_question_edit.html", question=question)


@bp.route("/reading/questions/<int:question_id>/toggle", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_question_toggle(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    question.is_active = not bool(question.is_active)
    db.session.commit()
    flash("Reading question status updated.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_questions", passage_id=question.passage_id))


@bp.route("/reading/questions/<int:question_id>/submit-review", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_question_submit_review(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    question.status = ReadingQuestion.STATUS_REVIEW
    question.review_notes = None
    question.reviewed_at = None
    question.reviewed_by_id = None
    db.session.commit()
    flash("Reading question moved to review.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_questions", passage_id=question.passage_id, course_id=getattr(question.passage, "course_id", None)))


@bp.route("/reading/questions/<int:question_id>/delete", methods=["POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_question_delete(question_id: int):
    question = ReadingQuestion.query.get_or_404(question_id)
    passage_id = question.passage_id
    db.session.delete(question)
    db.session.commit()
    flash("Reading question deleted successfully.", "success")
    return redirect(request.referrer or url_for("superadmin.reading_questions", passage_id=passage_id))


@bp.get("/reading/review")
@login_required
@require_role(*READING_REVIEW_ROLE_CODES)
def reading_review_queue():
    passage_status = (request.args.get("passage_status") or ReadingPassage.STATUS_REVIEW).strip().lower()
    question_status = (request.args.get("question_status") or ReadingQuestion.STATUS_REVIEW).strip().lower()
    allowed_passage = {ReadingPassage.STATUS_DRAFT, ReadingPassage.STATUS_REVIEW, ReadingPassage.STATUS_APPROVED, ReadingPassage.STATUS_REJECTED}
    allowed_question = {ReadingQuestion.STATUS_DRAFT, ReadingQuestion.STATUS_REVIEW, ReadingQuestion.STATUS_APPROVED, ReadingQuestion.STATUS_REJECTED}
    if passage_status not in allowed_passage:
        passage_status = ReadingPassage.STATUS_REVIEW
    if question_status not in allowed_question:
        question_status = ReadingQuestion.STATUS_REVIEW

    passages = ReadingPassage.query.filter(ReadingPassage.status == passage_status).order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc()).all()
    questions = ReadingQuestion.query.filter(ReadingQuestion.status == question_status).order_by(ReadingQuestion.updated_at.desc(), ReadingQuestion.id.desc()).all()

    return render_template(
        "superadmin/reading_review_queue.html",
        passages=passages,
        questions=questions,
        passage_status=passage_status,
        question_status=question_status,
        passage_statuses=(ReadingPassage.STATUS_DRAFT, ReadingPassage.STATUS_REVIEW, ReadingPassage.STATUS_APPROVED, ReadingPassage.STATUS_REJECTED),
        question_statuses=(ReadingQuestion.STATUS_DRAFT, ReadingQuestion.STATUS_REVIEW, ReadingQuestion.STATUS_APPROVED, ReadingQuestion.STATUS_REJECTED),
        counts={
            "draft_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_DRAFT).count(),
            "review_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_REVIEW).count(),
            "approved_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_APPROVED).count(),
            "draft_questions": ReadingQuestion.query.filter_by(status=ReadingQuestion.STATUS_DRAFT).count(),
            "review_questions": ReadingQuestion.query.filter_by(status=ReadingQuestion.STATUS_REVIEW).count(),
            "approved_questions": ReadingQuestion.query.filter_by(status=ReadingQuestion.STATUS_APPROVED).count(),
            "rejected_passages": ReadingPassage.query.filter_by(status=ReadingPassage.STATUS_REJECTED).count(),
            "rejected_questions": ReadingQuestion.query.filter_by(status=ReadingQuestion.STATUS_REJECTED).count(),
        },
    )


@bp.route("/reading-api-registry", methods=["GET", "POST"])
@login_required
@require_role(Role.SUPERADMIN.value)
def reading_api_registry():
    ReadingProviderRegistryService.ensure_defaults()
    form = ReadingProviderForm(prefix="provider")
    test_form = ReadingProviderTestForm(prefix="test")
    prompt_form = ReadingPromptConfigForm(prefix="prompt")

    current_kind = (request.args.get("kind") or ReadingProvider.KIND_PASSAGE).strip().lower()
    allowed_kinds = {
        ReadingProvider.KIND_PASSAGE,
        ReadingProvider.KIND_QUESTION,
        ReadingProvider.KIND_TRANSLATION,
        ReadingProvider.KIND_EVALUATION,
        ReadingProvider.KIND_PLAGIARISM,
    }
    if current_kind not in allowed_kinds:
        current_kind = ReadingProvider.KIND_PASSAGE

    form.provider_kind.data = current_kind
    form.fallback_provider_id.choices = ReadingProviderRegistryService.choices_for_kind(current_kind, include_none=True)

    active_prompt_map = ReadingProviderRegistryService.active_prompt_map()
    current_prompt = active_prompt_map.get(current_kind)
    if current_prompt and request.method == "GET":
        prompt_form.task_type.data = current_prompt.task_type
        prompt_form.title.data = current_prompt.title
        prompt_form.prompt_text.data = current_prompt.prompt_text
        prompt_form.is_active.data = current_prompt.is_active

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        provider_id = int(request.form.get("provider_id") or 0)
        provider = ReadingProviderRegistryService.by_id(provider_id) if provider_id else None

        if action == "create":
            posted_kind = (request.form.get("provider_kind") or current_kind).strip().lower()
            if posted_kind not in allowed_kinds:
                posted_kind = ReadingProvider.KIND_PASSAGE
            ReadingProviderRegistryService.create_provider(posted_kind)
            flash("Reading provider row created.", "success")
            return redirect(url_for("superadmin.reading_api_registry", kind=posted_kind))

        if not provider and action in {"toggle", "make_default", "test"}:
            flash("Reading provider not found.", "warning")
            return redirect(url_for("superadmin.reading_api_registry", kind=current_kind))

        if action == "toggle" and provider:
            ReadingProviderRegistryService.toggle_enabled(provider)
            flash("Reading provider status updated.", "success")
            return redirect(url_for("superadmin.reading_api_registry", kind=provider.provider_kind))

        if action == "make_default" and provider:
            ReadingProviderRegistryService.set_default(provider)
            flash("Default reading provider updated.", "success")
            return redirect(url_for("superadmin.reading_api_registry", kind=provider.provider_kind))

        if action == "test" and provider:
            ok, message = ReadingProviderRegistryService.test_provider(provider)
            flash(message, "success" if ok else "warning")
            return redirect(url_for("superadmin.reading_api_registry", kind=provider.provider_kind))

        if action == "save_prompt" and prompt_form.validate_on_submit():
            ReadingProviderRegistryService.save_prompt(
                task_type=prompt_form.task_type.data,
                title=prompt_form.title.data,
                prompt_text=prompt_form.prompt_text.data,
                is_active=bool(prompt_form.is_active.data),
            )
            flash("Reading prompt config saved.", "success")
            return redirect(url_for("superadmin.reading_api_registry", kind=prompt_form.task_type.data))

        if action == "save_provider" and form.validate_on_submit():
            provider = ReadingProviderRegistryService.by_id(form.provider_id.data) if form.provider_id.data else None
            if not provider:
                provider = ReadingProvider(
                    provider_kind=form.provider_kind.data,
                    name=form.name.data.strip(),
                    provider_type=form.provider_type.data,
                )
            payload = {
                "name": (form.name.data or "").strip(),
                "provider_kind": form.provider_kind.data,
                "provider_type": form.provider_type.data,
                "official_website": (form.official_website.data or "").strip() or None,
                "usage_scope": (form.usage_scope.data or "").strip() or None,
                "pricing_note": (form.pricing_note.data or "").strip() or None,
                "notes": (form.notes.data or "").strip() or None,
                "fallback_provider_id": form.fallback_provider_id.data or 0,
                "api_base_url": (form.api_base_url.data or "").strip() or None,
                "api_key": (form.api_key.data or "").strip() or None,
                "model_name": (form.model_name.data or "").strip() or None,
                "config_json": (form.config_json.data or "").strip() or None,
                "is_enabled": bool(form.is_enabled.data),
                "supports_test": bool(form.supports_test.data),
            }
            ReadingProviderRegistryService.save_provider(provider, payload)
            flash("Reading provider saved.", "success")
            return redirect(url_for("superadmin.reading_api_registry", kind=form.provider_kind.data))

    grouped = ReadingProviderRegistryService.grouped_registry()
    registry_sections = [
        {
            "key": ReadingProvider.KIND_PASSAGE,
            "label": "Passage Provider Config",
            "description": "Controls topic to level-based reading passage generation.",
            "default": ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_PASSAGE),
            "rows": grouped.get(ReadingProvider.KIND_PASSAGE, []),
        },
        {
            "key": ReadingProvider.KIND_QUESTION,
            "label": "Question Provider Config",
            "description": "Controls MCQ, fill blanks, and true/false generation from the passage.",
            "default": ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_QUESTION),
            "rows": grouped.get(ReadingProvider.KIND_QUESTION, []),
        },
        {
            "key": ReadingProvider.KIND_TRANSLATION,
            "label": "Translation / Synonym Config",
            "description": "Controls vocabulary helper, word meaning, and translation support.",
            "default": ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_TRANSLATION),
            "rows": grouped.get(ReadingProvider.KIND_TRANSLATION, []),
        },
        {
            "key": ReadingProvider.KIND_EVALUATION,
            "label": "Answer Evaluation Config",
            "description": "Controls answer checking and wrong-answer explanation services.",
            "default": ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_EVALUATION),
            "rows": grouped.get(ReadingProvider.KIND_EVALUATION, []),
        },
        {
            "key": ReadingProvider.KIND_PLAGIARISM,
            "label": "Plagiarism Detection Config",
            "description": "Controls plagiarism and originality checks for premium writing and submission workflows.",
            "default": ReadingProviderRegistryService.default_provider(ReadingProvider.KIND_PLAGIARISM),
            "rows": grouped.get(ReadingProvider.KIND_PLAGIARISM, []),
        },
    ]

    section_map = {section["key"]: section for section in registry_sections}
    current_section = section_map.get(current_kind)
    recent_logs = (
        ApiCallLog.query.filter(ApiCallLog.system.like("reading:%")).order_by(ApiCallLog.created_at.desc()).limit(12).all()
    )
    provider_count = ReadingProvider.query.count()
    enabled_count = ReadingProvider.query.filter_by(is_enabled=True).count()

    return render_template(
        "superadmin/reading_api_registry.html",
        form=form,
        test_form=test_form,
        prompt_form=prompt_form,
        registry_sections=registry_sections,
        current_kind=current_kind,
        current_section=current_section,
        recommended_apis=ReadingProviderRegistryService.RECOMMENDED_APIS.get(current_kind, []),
        recent_logs=recent_logs,
        provider_count=provider_count,
        enabled_count=enabled_count,
        prompt_map=active_prompt_map,
        current_prompt=current_prompt,
    )




@bp.route('/ai-central', methods=['GET'])
@login_required
@require_role(Role.SUPERADMIN.value)
def ai_central():
    registry_groups = AICentralProviderRegistry.grouped_rows()
    health = AICentralProviderRegistry.health_summary()
    prompt_previews = AIPromptBuilder.preview_catalog()
    ai_capabilities = _superadmin_ai_capability_rows()
    ai_usage = _superadmin_ai_usage_snapshot()
    task_options = [group['task_key'] for group in registry_groups]
    selected_task = (request.args.get('task') or (task_options[0] if task_options else 'translation')).strip()
    if selected_task not in task_options:
        selected_task = task_options[0] if task_options else 'translation'

    sample_payloads = {
        'translation': {'source_text': 'How are you?', 'target_language': 'Punjabi', 'target_language_code': 'pa', 'source_language_code': 'en'},
        'speaking_stt': {'audio_name': 'sample.wav'},
        'speaking_evaluation': {'prompt_text': 'Speak about your hometown.', 'transcript': 'My hometown is peaceful and friendly.', 'duration_seconds': 40},
        'speaking_pronunciation': {'prompt_text': 'Speak about your hometown.', 'transcript': 'My hometown is peaceful and friendly.', 'duration_seconds': 40},
        'speaking_tts': {'text': 'Welcome to Fluencify. Your lesson is ready.', 'voice_name': 'Default voice'},
        'reading_passage': {'topic': 'World War', 'topic_description': 'A history topic for reading practice.', 'level': 'basic', 'length_mode': 'medium', 'target_words': 160},
        'reading_question': {'passage_content': 'Daily routine helps students build confidence. It keeps learning organized and clear.', 'mcq_count': 2, 'fill_blank_count': 1, 'true_false_count': 1},
        'reading_translation': {'word': 'confidence', 'sentence': 'Daily routine helps students build confidence.', 'target_language': 'English', 'target_language_code': 'en'},
        'reading_evaluation': {'question_text': 'What helps students build confidence?', 'student_answer': 'daily routine', 'correct_answer': 'daily routine', 'question_type': 'mcq'},
        'writing_plagiarism': {'submission_text': 'Daily practice builds confidence and progress.', 'reference_text': 'Daily practice helps students build confidence and steady progress.'},
        'writing_evaluation': {'submission_text': 'Countries should communicate and work together to avoid war.'},
        'listening_review': {'topic_title': 'Daily Routine', 'prompt_text': 'Listen and answer.', 'caption_text': 'This is a clean caption sample.'},
    }
    ai_preview = AIServiceLayer.execute(selected_task, sample_payloads.get(selected_task, {})).to_dict()
    tutor_preview = TutorAIService.respond(lesson_title='Sample Lesson', lesson_body='Daily routine helps students build confidence and learning discipline.', active_question='What helps students build confidence?', student_message='Explain the answer from this lesson only.', level='basic')

    category_meta = {
        'text_ai': {
            'label': 'Text AI',
            'description': 'One text provider family can support generation, evaluation, and feedback across reading, writing, listening, and speaking.',
            'editor_links': [
                {'label': 'Reading text tasks', 'href': url_for('superadmin.reading_api_registry')},
                {'label': 'Translation service', 'href': url_for('superadmin.api_registry')},
            ],
        },
        'speech': {
            'label': 'Speech Services',
            'description': 'Speech-to-text and pronunciation remain separate from text generation because they solve a different technical job.',
            'editor_links': [
                {'label': 'Speech provider editor', 'href': url_for('superadmin.speaking_api_registry')},
            ],
        },
        'translation': {
            'label': 'Translation',
            'description': 'Translation stays separate because caching, target languages, and runtime lookups behave differently from core text generation.',
            'editor_links': [
                {'label': 'Translation provider editor', 'href': url_for('superadmin.api_registry')},
            ],
        },
    }

    def _category_for_task(task_key: str) -> str:
        if task_key == 'translation':
            return 'translation'
        if task_key.startswith('speaking_stt') or task_key.startswith('speaking_pronunciation') or task_key.startswith('speaking_tts'):
            return 'speech'
        return 'text_ai'

    task_mapping_rows = []
    category_buckets = {key: {'key': key, **value, 'tasks': [], 'provider_count': 0, 'enabled_count': 0} for key, value in category_meta.items()}
    for group in registry_groups:
        category_key = _category_for_task(group['task_key'])
        manage_href = url_for('superadmin.ai_central')
        if group['task_key'] == 'translation':
            manage_href = url_for('superadmin.api_registry')
        elif group['task_key'] == 'writing_plagiarism':
            manage_href = url_for('superadmin.reading_api_registry', kind=ReadingProvider.KIND_PLAGIARISM)
        elif group['task_key'].startswith('reading_'):
            kind = group['task_key'].replace('reading_', '')
            manage_href = url_for('superadmin.reading_api_registry', kind=kind)
        elif group['task_key'].startswith('speaking_'):
            kind = group['task_key'].replace('speaking_', '')
            manage_href = url_for('superadmin.speaking_api_registry', kind=kind)

        default_row = next((row for row in group['rows'] if row.get('is_default')), None)
        enabled_rows = [row for row in group['rows'] if row.get('is_enabled')]
        mapping_row = {
            'task_key': group['task_key'],
            'task_label': group['task_label'],
            'category_key': category_key,
            'category_label': category_meta[category_key]['label'],
            'provider_count': len(group['rows']),
            'enabled_count': len(enabled_rows),
            'default_name': (default_row or {}).get('name') or 'Not set',
            'default_type': (default_row or {}).get('provider_label') or '—',
            'manage_href': manage_href,
            'rows': group['rows'],
        }
        task_mapping_rows.append(mapping_row)
        category_buckets[category_key]['tasks'].append(mapping_row)
        category_buckets[category_key]['provider_count'] += len(group['rows'])
        category_buckets[category_key]['enabled_count'] += len(enabled_rows)

    category_sections = [bucket for bucket in category_buckets.values() if bucket['tasks']]

    recent_logs = AIRequestLog.query.order_by(AIRequestLog.created_at.desc()).limit(12).all()

    return render_template(
        'superadmin/ai_central.html',
        registry_groups=registry_groups,
        health=health,
        prompt_previews=prompt_previews,
        ai_preview=ai_preview,
        task_options=task_options,
        selected_task=selected_task,
        recent_logs=recent_logs,
        category_sections=category_sections,
        task_mapping_rows=task_mapping_rows,
        ai_capabilities=ai_capabilities,
        ai_usage=ai_usage,
        tutor_preview=tutor_preview,
    )






@bp.route('/course-pathways', methods=['GET', 'POST'])
@login_required
@require_role(Role.SUPERADMIN.value)
def course_pathways():
    if request.method == 'POST':
        results = SpokenEnglishService.sync_special_pathways(getattr(current_user, 'id', None), getattr(current_user, 'id', None))
        created_count = sum(1 for row in results if row.created)
        flash(f'Special English pathways synced successfully. Created {created_count} new course(s).', 'success')
        return redirect(url_for('superadmin.course_pathways'))

    pathway_courses = (
        Course.query
        .filter(Course.slug.in_(['spoken-english', 'interview-preparation', 'english-super-advanced']))
        .order_by(Course.created_at.desc())
        .all()
    )
    advanced_course = next((course for course in pathway_courses if (getattr(course, 'slug', '') or '').strip().lower() == 'english-super-advanced'), None)
    advanced_topics = []
    advanced_tasks_count = 0
    advanced_sessions_count = 0

    if advanced_course:
        advanced_topics = (
            WritingTopic.query
            .filter(WritingTopic.course_id == advanced_course.id)
            .order_by(WritingTopic.display_order.asc(), WritingTopic.id.asc())
            .all()
        )
        advanced_tasks_count = WritingTask.query.filter(WritingTask.course_id == advanced_course.id).count()
        advanced_sessions_count = WritingSubmission.query.filter(WritingSubmission.course_id == advanced_course.id).count()

    topic_labels = {
        ((getattr(topic, 'title', '') or '') + ' ' + (getattr(topic, 'category', '') or '')).strip().lower()
        for topic in advanced_topics
    }
    has_debate = any('debate' in label for label in topic_labels)
    has_vocabulary = any('vocabulary' in label for label in topic_labels)
    has_formal_writing = any('formal writing' in label for label in topic_labels)
    has_premium_pricing = bool(
        advanced_course
        and getattr(advanced_course, 'is_premium', False)
        and (
            float(getattr(advanced_course, 'sale_price', 0) or 0) > 0
            or float(getattr(advanced_course, 'base_price', 0) or 0) > 0
        )
    )
    phase17_status = [
        {
            'label': 'Premium course',
            'state': 'ready' if advanced_course else 'missing',
            'detail': advanced_course.title if advanced_course else 'English Super Advanced course not created yet.',
        },
        {
            'label': 'Advanced topics',
            'state': 'ready' if len(advanced_topics) >= 3 else ('partial' if advanced_topics else 'missing'),
            'detail': f'{len(advanced_topics)} structured topic(s) linked.' if advanced_topics else 'No advanced writing topics linked yet.',
        },
        {
            'label': 'High-level content',
            'state': 'ready' if advanced_tasks_count >= 4 else ('partial' if advanced_tasks_count else 'missing'),
            'detail': f'{advanced_tasks_count} writing task(s) available.' if advanced_tasks_count else 'No premium high-level tasks available yet.',
        },
        {
            'label': 'Debate system',
            'state': 'ready' if has_debate else 'missing',
            'detail': 'Debate topic available in the premium pathway.' if has_debate else 'No debate-focused topic found.',
        },
        {
            'label': 'Professional writing',
            'state': 'ready' if has_formal_writing else 'missing',
            'detail': 'Formal writing topic is present.' if has_formal_writing else 'Formal writing topic is not configured.',
        },
        {
            'label': 'Vocabulary system',
            'state': 'ready' if has_vocabulary else 'missing',
            'detail': 'Advanced vocabulary topic is present.' if has_vocabulary else 'No advanced vocabulary topic found.',
        },
        {
            'label': 'Course structure',
            'state': 'ready' if advanced_course and (advanced_topics or getattr(advanced_course, 'lesson_title', None)) else 'missing',
            'detail': 'Course shell, lesson title, and topic structure are defined.' if advanced_course and (advanced_topics or getattr(advanced_course, 'lesson_title', None)) else 'Structure is not defined yet.',
        },
        {
            'label': 'Pricing logic',
            'state': 'ready' if has_premium_pricing else 'missing',
            'detail': 'Premium pricing is configured.' if has_premium_pricing else 'Base/sale premium pricing is still missing.',
        },
        {
            'label': 'Analytics linkage',
            'state': 'partial' if advanced_course else 'missing',
            'detail': f'{advanced_sessions_count} submission(s) recorded for analytics.' if advanced_course and advanced_sessions_count else 'Course exists, but premium analytics is still generic or has no submissions yet.' if advanced_course else 'No course available to attach analytics.',
        },
        {
            'label': 'UI differentiation',
            'state': 'partial' if advanced_course else 'missing',
            'detail': f"Badge style: {getattr(advanced_course, 'badge_template', 'default')} / {getattr(advanced_course, 'badge_animation', 'none')}." if advanced_course else 'No premium UI styling can be applied before the course exists.',
        },
    ]
    return render_template('superadmin/course_pathways.html', pathway_courses=pathway_courses, phase17_status=phase17_status)


@bp.route('/ai-rule-panel', methods=['GET', 'POST'])
@login_required
@require_role(Role.SUPERADMIN.value)
def ai_rule_panel():
    AIRuleService.ensure_defaults()
    selected_track = AIRuleConfig.normalize_track(request.args.get('track') or request.form.get('track_key') or AIRuleConfig.TRACK_SPEAKING)
    task_map, preview_payloads = _ai_rule_preview_map()

    if request.method == 'POST':
        action = (request.form.get('action') or 'save').strip().lower()
        track_key = AIRuleConfig.normalize_track(request.form.get('track_key'))
        if action == 'reset':
            defaults = AIRuleConfig.DEFAULTS.get(track_key, {})
            AIRuleService.update_rule(track_key=track_key, form_data={
                'is_enabled': True,
                'rule_text': defaults.get('rule_text', ''),
                'guardrails_text': defaults.get('guardrails_text', ''),
                'scoring_notes': defaults.get('scoring_notes', ''),
                'output_format': defaults.get('output_format', ''),
                'strictness': defaults.get('strictness', 3),
                'min_length': defaults.get('min_length', 0),
                'require_explanations': defaults.get('require_explanations', True),
                'off_topic_block': defaults.get('off_topic_block', False),
            }, user_id=current_user.id)
            flash(f'{track_key.title()} AI rules reset to default.', 'success')
            return redirect(url_for('superadmin.ai_rule_panel', track=track_key))
        if action == 'save':
            AIRuleService.update_rule(track_key=track_key, form_data={
                'is_enabled': request.form.get('is_enabled') == 'on',
                'rule_text': request.form.get('rule_text'),
                'guardrails_text': request.form.get('guardrails_text'),
                'scoring_notes': request.form.get('scoring_notes'),
                'output_format': request.form.get('output_format'),
                'strictness': request.form.get('strictness'),
                'min_length': request.form.get('min_length'),
                'require_explanations': request.form.get('require_explanations') == 'on',
                'off_topic_block': request.form.get('off_topic_block') == 'on',
            }, user_id=current_user.id)
            flash(f'{track_key.title()} AI rules updated.', 'success')
            return redirect(url_for('superadmin.ai_rule_panel', track=track_key))
        if action == 'test':
            selected_track = track_key

    rules = AIRuleService.all_rules()
    rule_map = {row.track_key: row for row in rules}
    current_rule = rule_map.get(selected_track)
    preview_task = task_map.get(selected_track, 'speaking_evaluation')
    preview_result = AIServiceLayer.execute(preview_task, preview_payloads.get(preview_task, {})).to_dict()
    test_payload = _ai_rule_test_payload(selected_track, request.form if request.method == 'POST' else {})
    test_result = AIServiceLayer.execute(preview_task, test_payload).to_dict() if request.method == 'POST' and (request.form.get('action') or '').strip().lower() == 'test' else None
    rule_usage_logs = AIRuleLogger.tail(10)
    task_rows = [
        {'task_key': task_key, 'track_key': AIRuleService.track_for_task(task_key) or 'general'}
        for task_key in AIRuleService.tasks_for_track(selected_track)
    ]
    return render_template(
        'superadmin/ai_rule_panel.html',
        rules=rules,
        selected_track=selected_track,
        current_rule=current_rule,
        preview_task=preview_task,
        preview_result=preview_result,
        test_result=test_result,
        test_payload=test_payload,
        task_rows=task_rows,
        rule_usage_logs=rule_usage_logs,
        docs_cards=_ai_rule_docs(),
    )


@bp.route("/speaking-api-registry", methods=["GET", "POST"])
@login_required
@require_role("SUPERADMIN")
def speaking_api_registry():
    SpeakingProviderRegistryService.ensure_defaults()
    form = SpeakingProviderForm(prefix="provider")
    test_form = SpeakingProviderTestForm(prefix="test")

    current_kind = (request.args.get("kind") or SpeakingProvider.KIND_STT).strip().lower()
    valid_kinds = {
        SpeakingProvider.KIND_STT,
        SpeakingProvider.KIND_EVALUATION,
        SpeakingProvider.KIND_PRONUNCIATION,
        SpeakingProvider.KIND_TTS,
    }
    if current_kind not in valid_kinds:
        current_kind = SpeakingProvider.KIND_STT
    form.provider_kind.data = current_kind
    form.fallback_provider_id.choices = SpeakingProviderRegistryService.fallback_choices(current_kind, form.provider_id.data if form.provider_id.data else None)

    if request.method == "POST":
        action = request.form.get("action", "save")
        provider_id = request.form.get("provider_id", type=int) or request.form.get("test-provider_id", type=int)
        provider = SpeakingProviderRegistryService.by_id(provider_id) if provider_id else None

        posted_kind = (request.form.get("provider_kind") or current_kind).strip().lower()
        if posted_kind not in valid_kinds:
            posted_kind = SpeakingProvider.KIND_STT

        if action == "create":
            SpeakingProviderRegistryService.create_provider(posted_kind)
            flash(f"New {posted_kind.title()} provider row created.", "success")
            return redirect(url_for("superadmin.speaking_api_registry", kind=posted_kind))

        if action == "toggle" and provider:
            SpeakingProviderRegistryService.toggle_enabled(provider)
            flash("Provider status updated.", "success")
            return redirect(url_for("superadmin.speaking_api_registry", kind=provider.provider_kind))

        if action == "make_default" and provider:
            SpeakingProviderRegistryService.set_default(provider)
            flash("Default provider updated.", "success")
            return redirect(url_for("superadmin.speaking_api_registry", kind=provider.provider_kind))

        if action == "test" and provider:
            ok, message = SpeakingProviderRegistryService.test_provider(provider)
            flash(message, "success" if ok else "warning")
            return redirect(url_for("superadmin.speaking_api_registry", kind=provider.provider_kind))

        if action == "save" and form.validate_on_submit():
            provider = SpeakingProviderRegistryService.by_id(form.provider_id.data) if form.provider_id.data else None
            if not provider:
                provider = SpeakingProvider(
                    provider_kind=form.provider_kind.data,
                    name=form.name.data,
                    provider_type=form.provider_type.data,
                )

            payload = {
                "name": (form.name.data or "").strip(),
                "provider_kind": form.provider_kind.data,
                "provider_type": form.provider_type.data,
                "official_website": (form.official_website.data or "").strip() or None,
                "api_base_url": (form.api_base_url.data or "").strip() or None,
                "api_key": (form.api_key.data or "").strip() or None,
                "model_name": (form.model_name.data or "").strip() or None,
                "usage_scope": (form.usage_scope.data or "").strip() or None,
                "pricing_note": (form.pricing_note.data or "").strip() or None,
                "notes": (form.notes.data or "").strip() or None,
                "fallback_provider_id": form.fallback_provider_id.data or 0,
                "config_json": (form.config_json.data or "").strip() or None,
                "is_enabled": bool(form.is_enabled.data),
                "supports_test": bool(form.supports_test.data),
            }
            SpeakingProviderRegistryService.save_provider(provider, payload)
            flash("Speaking provider saved.", "success")
            return redirect(url_for("superadmin.speaking_api_registry", kind=form.provider_kind.data))

    grouped = SpeakingProviderRegistryService.grouped_registry()
    registry_sections = [
        {
            "key": SpeakingProvider.KIND_STT,
            "label": "STT Provider Config",
            "description": "Controls future speech-to-text engines for browser microphone capture and transcript generation.",
            "default": SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_STT),
            "rows": grouped.get(SpeakingProvider.KIND_STT, []),
        },
        {
            "key": SpeakingProvider.KIND_EVALUATION,
            "label": "Evaluation Provider Config",
            "description": "Controls scoring and content-feedback engines for speaking answers.",
            "default": SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_EVALUATION),
            "rows": grouped.get(SpeakingProvider.KIND_EVALUATION, []),
        },
        {
            "key": SpeakingProvider.KIND_PRONUNCIATION,
            "label": "Pronunciation Provider Config",
            "description": "Controls future pronunciation and phoneme quality engines.",
            "default": SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_PRONUNCIATION),
            "rows": grouped.get(SpeakingProvider.KIND_PRONUNCIATION, []),
        },
        {
            "key": SpeakingProvider.KIND_TTS,
            "label": "TTS Provider Config",
            "description": "Controls text-to-speech engines for lesson playback, onboarding voice, and multilingual narration.",
            "default": SpeakingProviderRegistryService.default_provider(SpeakingProvider.KIND_TTS),
            "rows": grouped.get(SpeakingProvider.KIND_TTS, []),
        },
    ]

    section_map = {section["key"]: section for section in registry_sections}
    current_section = section_map.get(current_kind)

    recommended_catalog = {
        SpeakingProvider.KIND_STT: [
            {
                "name": "Deepgram",
                "link": "https://deepgram.com",
                "plan": "Usage-based / trial available",
                "best_for": "Real-time speech to text",
                "placement": "Mic input to transcript",
            },
            {
                "name": "Google Speech-to-Text",
                "link": "https://cloud.google.com/speech-to-text",
                "plan": "Usage-based",
                "best_for": "Reliable cloud STT",
                "placement": "Browser speech transcript",
            },
            {
                "name": "Azure Speech",
                "link": "https://azure.microsoft.com/en-us/products/ai-services/ai-speech",
                "plan": "Usage-based",
                "best_for": "Enterprise speech stack",
                "placement": "STT + pronunciation ecosystem",
            },
            {
                "name": "OpenAI Whisper",
                "link": "https://platform.openai.com/docs",
                "plan": "Usage-based",
                "best_for": "General transcription",
                "placement": "Speech upload to text",
            },
        ],
        SpeakingProvider.KIND_EVALUATION: [
            {
                "name": "OpenAI",
                "link": "https://platform.openai.com/docs",
                "plan": "Usage-based",
                "best_for": "Answer evaluation and feedback",
                "placement": "Speaking score + AI comments",
            },
            {
                "name": "Azure OpenAI",
                "link": "https://azure.microsoft.com/en-us/products/ai-services/openai-service",
                "plan": "Usage-based / enterprise",
                "best_for": "Enterprise evaluation layer",
                "placement": "Scoring + moderation + feedback",
            },
            {
                "name": "Anthropic",
                "link": "https://www.anthropic.com/api",
                "plan": "Usage-based",
                "best_for": "Rubric-style evaluation",
                "placement": "Fluency/content review",
            },
        ],
        SpeakingProvider.KIND_PRONUNCIATION: [
            {
                "name": "Speechace",
                "link": "https://www.speechace.com",
                "plan": "Custom / contact sales",
                "best_for": "Pronunciation scoring",
                "placement": "Pronunciation and fluency analysis",
            },
            {
                "name": "Azure Speech Pronunciation Assessment",
                "link": "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-pronunciation-assessment",
                "plan": "Usage-based",
                "best_for": "Pronunciation assessment",
                "placement": "Accent, fluency, pronunciation score",
            },
            {
                "name": "Google Speech",
                "link": "https://cloud.google.com/speech-to-text",
                "plan": "Usage-based",
                "best_for": "Support signal with STT",
                "placement": "Pronunciation support with transcript",
            },
        ],
    }

    recent_logs = (
        ApiCallLog.query
        .filter(ApiCallLog.system.like("speaking:%"))
        .order_by(ApiCallLog.created_at.desc())
        .limit(12)
        .all()
    )
    provider_count = SpeakingProvider.query.count()
    enabled_count = SpeakingProvider.query.filter_by(is_enabled=True).count()

    return render_template(
        "superadmin/speaking_api_registry.html",
        form=form,
        test_form=test_form,
        registry_sections=registry_sections,
        current_kind=current_kind,
        current_section=current_section,
        recommended_apis=recommended_catalog.get(current_kind, []),
        recent_logs=recent_logs,
        provider_count=provider_count,
        enabled_count=enabled_count,
    )



@bp.get('/listening/review')
@login_required
@require_role('SUPERADMIN')
def listening_review_queue():
    status = (request.args.get('status') or 'pending').strip().lower()
    allowed = {'pending', 'approved', 'rejected', 'draft'}
    if status not in allowed:
        status = 'pending'
    lessons = (
        Lesson.query.join(Level, Lesson.level_id == Level.id).join(Course, Level.course_id == Course.id)
        .filter(Course.track_type == 'listening', Lesson.lesson_type == 'listening', Lesson.workflow_status == status)
        .order_by(Lesson.updated_at.desc(), Lesson.id.desc())
        .all()
    )
    counts = {key: (Lesson.query.join(Level, Lesson.level_id == Level.id).join(Course, Level.course_id == Course.id)
        .filter(Course.track_type == 'listening', Lesson.lesson_type == 'listening', Lesson.workflow_status == key).count()) for key in allowed}
    return render_template('superadmin/listening_review_queue.html', lessons=lessons, status=status, counts=counts)


@bp.post('/listening/review/<int:lesson_id>/<action>')
@login_required
@require_role('SUPERADMIN')
def listening_review_action(lesson_id: int, action: str):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course
    if not course or (course.track_type or '').strip().lower() != 'listening' or (lesson.lesson_type or '').strip().lower() != 'listening':
        flash('Listening lesson not found for review.', 'warning')
        return redirect(url_for('superadmin.listening_review_queue'))
    action = (action or '').strip().lower()
    if action == 'approve':
        lesson.workflow_status = 'approved'
        lesson.is_published = True
        flash('Listening lesson approved.', 'success')
    elif action == 'reject':
        lesson.workflow_status = 'rejected'
        flash('Listening lesson rejected.', 'warning')
    elif action == 'reset':
        lesson.workflow_status = 'pending'
        flash('Listening lesson moved back to pending.', 'success')
    else:
        flash('Unknown review action.', 'warning')
        return redirect(url_for('superadmin.listening_review_queue'))
    lesson.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(request.referrer or url_for('superadmin.listening_review_queue'))
