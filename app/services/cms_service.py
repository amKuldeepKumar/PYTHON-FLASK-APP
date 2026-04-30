
from __future__ import annotations

import json

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..i18n import build_cached_content_proxy, get_ui_language_code, resolve_fallback_chain
from ..models.page import Page, PageContent


def parse_json_list(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return raw_value
    try:
        value = json.loads(raw_value)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def parse_json_dict(raw_value):
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    try:
        value = json.loads(raw_value)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_enabled_languages() -> list[tuple[str, str]]:
    defaults = [("en", "English"), ("hi", "Hindi"), ("pa", "Punjabi")]
    try:
        from ..models.language import Language

        items = Language.query.filter_by(is_enabled=True).order_by(Language.name.asc()).all()
        if items:
            return [(item.code, item.name) for item in items]
    except Exception:
        pass
    return defaults


def normalize_slug(value: str) -> str:
    value = (value or "").strip().lower()
    return value.strip("/")


def _content_version(content: PageContent) -> str:
    updated = getattr(content, "updated_at", None)
    return updated.isoformat() if updated else "v1"


def _recover_cms_schema() -> None:
    try:
        from ..schema_bootstrap import ensure_dev_sqlite_schema

        ensure_dev_sqlite_schema()
        seed_default_pages()
        db.session.remove()
    except Exception:
        pass


def resolve_page_content(slug: str, preferred_lang: str | None = None):
    slug = normalize_slug(slug)
    fallback_lang = (preferred_lang or "en").strip().lower() or "en"
    try:
        page = Page.query.filter_by(slug=slug).first()
    except SQLAlchemyError:
        _recover_cms_schema()
        try:
            page = Page.query.filter_by(slug=slug).first()
        except SQLAlchemyError:
            return None, None, fallback_lang

    if page and getattr(page, "deleted_at", None):
        return None, None, fallback_lang
    if not page:
        return None, None, fallback_lang

    preferred_lang = (preferred_lang or get_ui_language_code("en")).strip().lower()
    chain = resolve_fallback_chain(preferred_lang)

    for lang_code in chain:
        content = page.content_for(lang_code)
        if not content:
            continue
        if lang_code == preferred_lang:
            return page, content, preferred_lang
        proxy = build_cached_content_proxy(
            content,
            src_lang=lang_code,
            target_lang=preferred_lang,
            context_prefix=f"page:{page.slug}",
            version=_content_version(content),
        )
        return page, proxy, lang_code

    content = page.contents[0] if page.contents else None
    lang_used = getattr(content, "lang_code", None) if content else preferred_lang
    return page, content, lang_used


def ensure_page_content(page: Page, lang_code: str = "en") -> PageContent:
    lang_code = (lang_code or "en").strip().lower()
    existing = page.content_for(lang_code)
    if existing:
        return existing

    content = PageContent(
        page_id=page.id,
        lang_code=lang_code,
        title=page.title,
        subtitle=None,
        body_html="",
        hero_title=page.title,
        hero_subtitle="",
        meta_title=page.title,
        meta_description="",
        og_title=page.title,
        og_description="",
        twitter_card="summary_large_image",
    )
    return content


def seed_default_pages():
    defaults = [
        ("home", "Home", True, True, 0),
        ("courses", "Courses", True, True, 10),
        ("about", "About", True, True, 20),
        ("contact", "Contact", True, True, 30),
        ("speaking", "Speaking", True, True, 40),
        ("writing", "Writing", True, True, 50),
        ("listening", "Listening", True, True, 60),
        ("reading", "Reading", True, True, 70),
    ]

    from ..extensions import db

    for slug, title, is_published, is_in_menu, order in defaults:
        page = Page.query.filter_by(slug=slug).first()
        if page and getattr(page, "deleted_at", None):
            continue
        if not page:
            page = Page(
                slug=slug,
                title=title,
                is_published=is_published,
                is_in_menu=is_in_menu,
                menu_order=order,
            )
            db.session.add(page)
            db.session.flush()

        content = page.content_for("en")
        if not content:
            content = PageContent(
                page_id=page.id,
                lang_code="en",
                title=title,
                subtitle="",
                body_html=f"<p>Welcome to {title}.</p>",
                hero_title=title,
                hero_subtitle=f"Explore {title.lower()} with Fluencify.",
                hero_cta_text="Get Started",
                hero_cta_url="/courses",
                meta_title=title,
                meta_description=f"{title} page of Fluencify.",
                og_title=title,
                og_description=f"{title} page of Fluencify.",
                twitter_card="summary_large_image",
            )
            db.session.add(content)

    db.session.commit()
