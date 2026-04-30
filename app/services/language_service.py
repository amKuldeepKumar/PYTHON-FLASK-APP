from __future__ import annotations

from typing import Iterable

from ..extensions import db
from ..models.language import Language

DEFAULT_LANGUAGE_ROWS: list[dict[str, str]] = [
    {"code": "en", "name": "English", "native_name": "English", "direction": "ltr"},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "direction": "ltr"},
    {"code": "pa", "name": "Punjabi", "native_name": "ਪੰਜਾਬੀ", "direction": "ltr"},
    {"code": "ur", "name": "Urdu", "native_name": "اردو", "direction": "rtl"},
    {"code": "ar", "name": "Arabic", "native_name": "العربية", "direction": "rtl"},
    {"code": "bn", "name": "Bengali", "native_name": "বাংলা", "direction": "ltr"},
    {"code": "gu", "name": "Gujarati", "native_name": "ગુજરાતી", "direction": "ltr"},
    {"code": "mr", "name": "Marathi", "native_name": "मराठी", "direction": "ltr"},
    {"code": "ta", "name": "Tamil", "native_name": "தமிழ்", "direction": "ltr"},
    {"code": "te", "name": "Telugu", "native_name": "తెలుగు", "direction": "ltr"},
    {"code": "kn", "name": "Kannada", "native_name": "ಕನ್ನಡ", "direction": "ltr"},
    {"code": "ml", "name": "Malayalam", "native_name": "മലയാളം", "direction": "ltr"},
    {"code": "or", "name": "Odia", "native_name": "ଓଡ଼ିଆ", "direction": "ltr"},
    {"code": "as", "name": "Assamese", "native_name": "অসমীয়া", "direction": "ltr"},
    {"code": "ne", "name": "Nepali", "native_name": "नेपाली", "direction": "ltr"},
    {"code": "si", "name": "Sinhala", "native_name": "සිංහල", "direction": "ltr"},
    {"code": "es", "name": "Spanish", "native_name": "Español", "direction": "ltr"},
    {"code": "fr", "name": "French", "native_name": "Français", "direction": "ltr"},
    {"code": "de", "name": "German", "native_name": "Deutsch", "direction": "ltr"},
    {"code": "it", "name": "Italian", "native_name": "Italiano", "direction": "ltr"},
    {"code": "pt", "name": "Portuguese", "native_name": "Português", "direction": "ltr"},
    {"code": "ru", "name": "Russian", "native_name": "Русский", "direction": "ltr"},
    {"code": "tr", "name": "Turkish", "native_name": "Türkçe", "direction": "ltr"},
    {"code": "nl", "name": "Dutch", "native_name": "Nederlands", "direction": "ltr"},
    {"code": "pl", "name": "Polish", "native_name": "Polski", "direction": "ltr"},
    {"code": "sv", "name": "Swedish", "native_name": "Svenska", "direction": "ltr"},
    {"code": "no", "name": "Norwegian", "native_name": "Norsk", "direction": "ltr"},
    {"code": "da", "name": "Danish", "native_name": "Dansk", "direction": "ltr"},
    {"code": "fi", "name": "Finnish", "native_name": "Suomi", "direction": "ltr"},
    {"code": "el", "name": "Greek", "native_name": "Ελληνικά", "direction": "ltr"},
    {"code": "he", "name": "Hebrew", "native_name": "עברית", "direction": "rtl"},
    {"code": "fa", "name": "Persian", "native_name": "فارسی", "direction": "rtl"},
    {"code": "zh", "name": "Chinese", "native_name": "中文", "direction": "ltr"},
    {"code": "ja", "name": "Japanese", "native_name": "日本語", "direction": "ltr"},
    {"code": "ko", "name": "Korean", "native_name": "한국어", "direction": "ltr"},
    {"code": "th", "name": "Thai", "native_name": "ไทย", "direction": "ltr"},
    {"code": "vi", "name": "Vietnamese", "native_name": "Tiếng Việt", "direction": "ltr"},
    {"code": "id", "name": "Indonesian", "native_name": "Bahasa Indonesia", "direction": "ltr"},
    {"code": "ms", "name": "Malay", "native_name": "Bahasa Melayu", "direction": "ltr"},
    {"code": "tl", "name": "Filipino", "native_name": "Filipino", "direction": "ltr"},
    {"code": "uk", "name": "Ukrainian", "native_name": "Українська", "direction": "ltr"},
    {"code": "ro", "name": "Romanian", "native_name": "Română", "direction": "ltr"},
    {"code": "hu", "name": "Hungarian", "native_name": "Magyar", "direction": "ltr"},
    {"code": "cs", "name": "Czech", "native_name": "Čeština", "direction": "ltr"},
]

def ensure_default_languages(enable_all: bool = True) -> int:
    created_or_updated = 0
    for row in DEFAULT_LANGUAGE_ROWS:
        language = Language.query.filter_by(code=row["code"]).first()
        if not language:
            language = Language(code=row["code"])
            db.session.add(language)
        language.name = row["name"]
        language.native_name = row.get("native_name")
        language.direction = row.get("direction", "ltr")
        if enable_all:
            language.is_enabled = True
        created_or_updated += 1
    db.session.commit()
    return created_or_updated

def enabled_languages() -> list[Language]:
    return Language.query.filter_by(is_enabled=True).order_by(Language.name.asc()).all()

def all_languages() -> list[Language]:
    return Language.query.order_by(Language.name.asc(), Language.code.asc()).all()

def language_choices(enabled_only: bool = True, include_codes: bool = True) -> list[tuple[str, str]]:
    rows: Iterable[Language]
    rows = enabled_languages() if enabled_only else all_languages()
    choices = []
    for language in rows:
        label = language.name
        if include_codes:
            label = f"{language.name} ({language.code})"
        choices.append((language.code, label))
    if not choices:
        ensure_default_languages(enable_all=True)
        rows = enabled_languages() if enabled_only else all_languages()
        for language in rows:
            label = f"{language.name} ({language.code})" if include_codes else language.name
            choices.append((language.code, label))
    return choices


def resolve_language_code(value: str | None, default: str = "en") -> str:
    raw = (value or "").strip()
    if not raw:
        return default
    needle = raw.lower()
    rows = Language.query.all()
    for language in rows:
        if (language.code or "").lower() == needle:
            return language.code
    for language in rows:
        if (language.name or "").lower() == needle:
            return language.code
    for language in rows:
        if (language.native_name or "").lower() == needle:
            return language.code
    return default


def language_label(code: str | None, fallback: str = "English") -> str:
    resolved = resolve_language_code(code, default="en")
    language = Language.query.filter_by(code=resolved).first()
    if not language:
        return fallback
    if language.native_name and language.native_name != language.name:
        return f"{language.name} ({language.native_name})"
    return language.name
