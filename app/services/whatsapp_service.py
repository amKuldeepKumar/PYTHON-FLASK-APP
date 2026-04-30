from __future__ import annotations

import re
from urllib.parse import quote_plus

from flask import request
from flask_login import current_user

from app import db
from app.models.seo_settings import SeoSettings
from app.models.whatsapp import WhatsAppInquiryLog


class WhatsAppService:
    """Builds and logs public WhatsApp lead links.

    Phase D1 intentionally uses WhatsApp click-to-chat with a SuperAdmin managed
    pre-filled automation message. Full WhatsApp Business API automation can be
    added later without changing the public button contract.
    """

    @staticmethod
    def clean_number(number: str | None) -> str:
        return re.sub(r"\D+", "", number or "")

    @classmethod
    def is_public_widget_enabled(cls, settings: SeoSettings | None) -> bool:
        if not settings:
            return False
        if not bool(getattr(settings, "whatsapp_enabled", False)):
            return False
        if not bool(getattr(settings, "whatsapp_show_on_public", True)):
            return False
        return bool(cls.clean_number(getattr(settings, "whatsapp_number", "")))

    @classmethod
    def build_message(cls, settings: SeoSettings, source_path: str | None = None) -> str:
        base = (getattr(settings, "whatsapp_message", None) or "Hi! I need help with Fluencify courses.").strip()
        category = (getattr(settings, "whatsapp_default_category", None) or "Course inquiry").strip()
        help_text = (getattr(settings, "whatsapp_help_text", None) or "").strip()
        parts = [base]
        if category:
            parts.append(f"Category: {category}")
        if help_text:
            parts.append(help_text)
        if source_path:
            parts.append(f"Page: {source_path}")
        return "\n".join(parts)

    @classmethod
    def build_wa_url(cls, settings: SeoSettings, source_path: str | None = None) -> str:
        number = cls.clean_number(getattr(settings, "whatsapp_number", ""))
        message = cls.build_message(settings, source_path=source_path)
        return f"https://wa.me/{number}?text={quote_plus(message)}"

    @classmethod
    def log_click(cls, settings: SeoSettings, source_path: str | None = None) -> None:
        if not bool(getattr(settings, "whatsapp_click_tracking_enabled", True)):
            return
        try:
            log = WhatsAppInquiryLog(
                user_id=getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
                source_path=(source_path or request.args.get("next") or request.path or "")[:500],
                referer=(request.headers.get("Referer") or "")[:500],
                ip_address=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:80],
                user_agent=(request.headers.get("User-Agent") or "")[:500],
                category=(getattr(settings, "whatsapp_default_category", None) or "Course inquiry")[:120],
                number_snapshot=cls.clean_number(getattr(settings, "whatsapp_number", ""))[:40],
                message_snapshot=cls.build_message(settings, source_path=source_path),
                status="clicked",
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
