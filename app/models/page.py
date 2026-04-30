from __future__ import annotations

from datetime import datetime
import json

from ..extensions import db


class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(180), nullable=False, unique=True, index=True)
    title = db.Column(db.String(180), nullable=False)

    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_in_menu = db.Column(db.Boolean, nullable=False, default=False, index=True)
    menu_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    redirect_from = db.Column(db.String(255), nullable=True)
    redirect_to = db.Column(db.String(255), nullable=True)
    redirect_code = db.Column(db.Integer, nullable=False, default=301)

    contents = db.relationship(
        "PageContent",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="PageContent.lang_code.asc(), PageContent.id.asc()",
    )

    def content_for(self, lang_code: str):
        lang_code = (lang_code or "").strip().lower()
        for content in self.contents:
            if (content.lang_code or "").strip().lower() == lang_code:
                return content
        return None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        self.deleted_at = None

class PageContent(db.Model):
    __tablename__ = "page_contents"
    __table_args__ = (
        db.UniqueConstraint("page_id", "lang_code", name="uq_page_contents_page_lang"),
    )

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=False, index=True)

    lang_code = db.Column(db.String(20), nullable=False, default="en", index=True)

    title = db.Column(db.String(255), nullable=True)
    subtitle = db.Column(db.String(255), nullable=True)
    body_html = db.Column(db.Text, nullable=True)

    sections_json = db.Column(db.Text, nullable=True)
    faq_json = db.Column(db.Text, nullable=True)
    links_json = db.Column(db.Text, nullable=True)

    hero_title = db.Column(db.String(255), nullable=True)
    hero_subtitle = db.Column(db.Text, nullable=True)
    hero_cta_text = db.Column(db.String(120), nullable=True)
    hero_cta_url = db.Column(db.String(255), nullable=True)
    hero_image = db.Column(db.String(255), nullable=True)

    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.Text, nullable=True)
    canonical_url = db.Column(db.String(255), nullable=True)

    og_title = db.Column(db.String(255), nullable=True)
    og_description = db.Column(db.Text, nullable=True)
    og_image = db.Column(db.String(255), nullable=True)
    twitter_card = db.Column(db.String(40), nullable=True, default="summary_large_image")

    json_ld = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    redirect_from = db.Column(db.String(255), nullable=True)
    redirect_to = db.Column(db.String(255), nullable=True)
    redirect_code = db.Column(db.Integer, nullable=False, default=301)

    page = db.relationship("Page", back_populates="contents")

    def sections(self):
        try:
            return json.loads(self.sections_json) if self.sections_json else []
        except Exception:
            return []

    def faqs(self):
        try:
            return json.loads(self.faq_json) if self.faq_json else []
        except Exception:
            return []
