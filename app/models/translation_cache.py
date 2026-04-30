"""
Phase 3: Translation Cache (DB-based).

Goal:
- Store translations of UI strings/content to reduce repeated AI calls later.

This is intentionally provider-agnostic: later we can add AI provider registry and request logging.
"""

from datetime import datetime, timedelta
import hashlib

from ..extensions import db


def make_cache_key(source_text: str, src_lang: str, tgt_lang: str, context: str | None, version: str | None) -> str:
    raw = "\n".join([
        (src_lang or "").strip(),
        (tgt_lang or "").strip(),
        (context or "").strip(),
        (version or "").strip(),
        (source_text or "").strip(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TranslationCache(db.Model):
    __tablename__ = "translation_cache"

    id = db.Column(db.Integer, primary_key=True)

    cache_key = db.Column(db.String(64), unique=True, nullable=False, index=True)

    src_lang = db.Column(db.String(16), nullable=False, index=True)
    target_lang = db.Column(db.String(16), nullable=False, index=True)

    context = db.Column(db.String(120), nullable=True, index=True)  # e.g. "nav", "page:home"
    version = db.Column(db.String(40), nullable=True, index=True)  # page/content version, optional

    source_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)

    # TTL is optional. If null, treat as non-expiring cache.
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= datetime.utcnow()

    @staticmethod
    def compute_expiry(ttl_seconds: int | None) -> datetime | None:
        if not ttl_seconds:
            return None
        return datetime.utcnow() + timedelta(seconds=int(ttl_seconds))
