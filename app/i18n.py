
"""
Phase 3: i18n helpers (language preferences + translation cache runtime integration).

This module now supports:
- user-level language preference
- device-level language preference
- fallback-chain resolution
- DB translation cache read/write helpers
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import request
from flask_login import current_user

from .extensions import db
from .models.translation_cache import TranslationCache, make_cache_key
from .services.language_service import language_label, resolve_language_code
from .services.session_service import get_device_preference
from typing import Optional


FALLBACK_CHAIN = {
    "pa": ["pa", "hi", "en"],
    "pa-IN": ["pa-IN", "pa", "hi", "en"],
    "hi": ["hi", "en"],
    "ar": ["ar", "en"],
    "ur": ["ur", "en"],
}


def resolve_fallback_chain(code: Optional[str]) -> list[str]:
    if not code:
        return ["en"]
    code = code.strip()
    if code in FALLBACK_CHAIN:
        return FALLBACK_CHAIN[code]
    base = code.split("-")[0]
    chain = [code]
    if base != code:
        chain.append(base)
    if "en" not in chain:
        chain.append("en")
    return chain


def _request_lang_arg() -> Optional[str]:
    try:
        value = (request.args.get("lang") or "").strip().lower()
        return value or None
    except Exception:
        return None


def get_ui_language_code(default: str = "en") -> str:
    explicit = _request_lang_arg()
    if explicit:
        return explicit
    try:
        device = get_device_preference(default_ui=default, default_learning=default)
        if device and device.ui_language_code:
            return device.ui_language_code
    except Exception:
        db.session.rollback()
        pass
    try:
        if current_user.is_authenticated and getattr(current_user, "preferences", None):
            return current_user.preferences.ui_language_code or default
    except Exception:
        pass
    return default


def get_learning_language_code(default: str = "en") -> str:
    explicit = _request_lang_arg()
    if explicit:
        return explicit
    try:
        device = get_device_preference(default_ui=default, default_learning=default)
        if device and device.learning_language_code:
            return device.learning_language_code
    except Exception:
        db.session.rollback()
        pass
    try:
        if current_user.is_authenticated and getattr(current_user, "preferences", None):
            return current_user.preferences.learning_language_code or default
    except Exception:
        pass
    return default


def get_cached_translation(source_text: str, src_lang: str, target_lang: str, context: Optional[str] = None, version: Optional[str] = None) -> Optional[str]:
    key = make_cache_key(source_text, src_lang, target_lang, context, version)
    row = TranslationCache.query.filter_by(cache_key=key).first()
    if not row:
        return None
    if row.is_expired():
        try:
            db.session.delete(row)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return None
    return row.translated_text


def set_cached_translation(source_text: str, translated_text: str, src_lang: str, target_lang: str, context: Optional[str] = None, version: Optional[str] = None, ttl_seconds: Optional[int] = None) -> TranslationCache:
    key = make_cache_key(source_text, src_lang, target_lang, context, version)
    row = TranslationCache.query.filter_by(cache_key=key).first()
    if row:
        row.translated_text = translated_text
        row.expires_at = TranslationCache.compute_expiry(ttl_seconds)
    else:
        row = TranslationCache(
            cache_key=key,
            src_lang=src_lang,
            target_lang=target_lang,
            context=context,
            version=version,
            source_text=source_text,
            translated_text=translated_text,
            expires_at=TranslationCache.compute_expiry(ttl_seconds),
        )
        db.session.add(row)
    db.session.commit()
    return row


def cache_text_for_runtime(source_text: Optional[str], src_lang: str, target_lang: str, context: str, version: Optional[str] = None, ttl_seconds: Optional[int] = 86400) -> Optional[str]:
    if source_text in (None, ""):
        return source_text
    if src_lang == target_lang:
        return source_text
    cached = get_cached_translation(source_text, src_lang, target_lang, context=context, version=version)
    if cached is not None:
        return cached
    # Provider hook ready: until AI translation is wired, cache the resolved fallback text.
    set_cached_translation(source_text, source_text, src_lang, target_lang, context=context, version=version, ttl_seconds=ttl_seconds)
    return source_text


def build_cached_content_proxy(content, src_lang: str, target_lang: str, context_prefix: str, version: Optional[str] = None):
    fields = [
        "title", "subtitle", "body_html", "sections_json", "faq_json", "links_json",
        "hero_title", "hero_subtitle", "hero_cta_text", "hero_cta_url", "hero_image",
        "meta_title", "meta_description", "canonical_url",
        "og_title", "og_description", "og_image", "twitter_card", "json_ld",
    ]
    payload = {}
    for field in fields:
        value = getattr(content, field, None)
        payload[field] = cache_text_for_runtime(
            value,
            src_lang=src_lang,
            target_lang=target_lang,
            context=f"{context_prefix}:{field}",
            version=version,
        )
    payload["lang_code"] = target_lang
    payload["source_lang_code"] = src_lang
    payload["updated_at"] = getattr(content, "updated_at", None)
    return SimpleNamespace(**payload)


def get_translation_language_code(default: str = "en") -> str:
    try:
        if current_user.is_authenticated:
            pref = getattr(current_user, "preferences", None)
            if pref and not getattr(pref, "use_native_language_support", True):
                return default
            if pref:
                selected = resolve_language_code(getattr(pref, "translation_support_language_code", None), default="")
                if selected:
                    return selected
            native = resolve_language_code(getattr(current_user, "native_language", None), default="")
            if native:
                return native
    except Exception:
        pass
    return default


def get_translation_language_name(default: str = "English") -> str:
    return language_label(get_translation_language_code(default="en"), fallback=default)
