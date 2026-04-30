from __future__ import annotations

from datetime import datetime
from app import db


class SeoSettings(db.Model):
    __tablename__ = "seo_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Site-wide defaults
    site_name = db.Column(db.String(120), default="Fluencify")
    default_meta_title = db.Column(db.String(255), default="Fluencify")
    default_meta_description = db.Column(db.String(500), default="")
    default_og_image = db.Column(db.String(500), default="")
    favicon_url = db.Column(db.String(500), default="")
    site_logo_url = db.Column(db.String(500), default="")
    footer_logo_url = db.Column(db.String(500), default="")

    # Search engine verification
    google_site_verification = db.Column(db.String(255), default="")
    bing_site_verification = db.Column(db.String(255), default="")

    # Analytics / Tag Manager
    ga4_measurement_id = db.Column(db.String(64), default="")
    gtm_container_id = db.Column(db.String(64), default="")

    # Custom scripts (sanitized/controlled by perms)
    head_html = db.Column(db.Text, default="")
    body_start_html = db.Column(db.Text, default="")
    body_end_html = db.Column(db.Text, default="")
    custom_json_ld = db.Column(db.Text, default="")

    # Robots / sitemap
    robots_policy = db.Column(db.String(32), default="index,follow")
    extra_robots_lines = db.Column(db.Text, default="")
    sitemap_enabled = db.Column(db.Boolean, default=True)
    robots_enabled = db.Column(db.Boolean, default=True)
    sitemap_include_pages = db.Column(db.Boolean, default=True)
    sitemap_include_public_reading = db.Column(db.Boolean, default=True)
    sitemap_include_courses = db.Column(db.Boolean, default=True)

    # Apache .htaccess builder
    htaccess_enabled = db.Column(db.Boolean, default=False)
    htaccess_force_https = db.Column(db.Boolean, default=True)
    htaccess_force_www = db.Column(db.Boolean, default=False)
    htaccess_enable_compression = db.Column(db.Boolean, default=True)
    htaccess_enable_browser_cache = db.Column(db.Boolean, default=True)
    htaccess_custom_rules = db.Column(db.Text, default="")

    # Header / footer builder
    header_announcement_enabled = db.Column(db.Boolean, default=False)
    header_announcement_text = db.Column(db.String(255), default="")
    header_cta_text = db.Column(db.String(120), default="Get Started")
    header_cta_url = db.Column(db.String(255), default="/auth/register")
    header_links_json = db.Column(db.Text, default="[]")
    footer_columns = db.Column(db.Integer, default=4)
    footer_widgets_json = db.Column(db.Text, default="[]")
    footer_copyright = db.Column(db.String(255), default="© 2026 Fluencify AI")

    # WhatsApp lead widget (Phase D1)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    whatsapp_show_on_public = db.Column(db.Boolean, default=True)
    whatsapp_click_tracking_enabled = db.Column(db.Boolean, default=True)
    whatsapp_number = db.Column(db.String(32), default="")
    whatsapp_button_text = db.Column(db.String(80), default="Need Help? WhatsApp")
    whatsapp_help_text = db.Column(db.String(180), default="Ask us about courses, fees, or placement test help.")
    whatsapp_default_category = db.Column(db.String(120), default="Course inquiry")
    whatsapp_message = db.Column(db.String(500), default="Hi! I need help with Fluencify courses.")

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @staticmethod
    def singleton() -> "SeoSettings":
        row = SeoSettings.query.first()
        if not row:
            row = SeoSettings()
            db.session.add(row)
            db.session.commit()
        return row
