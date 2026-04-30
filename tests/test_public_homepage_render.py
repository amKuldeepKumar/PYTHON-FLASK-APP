from __future__ import annotations

from app.extensions import db
from app.models.page import Page, PageContent


def test_homepage_uses_fallback_template_when_cms_home_is_only_placeholder(client, app_ctx):
    page = Page(
        slug="home",
        title="Home",
        is_published=True,
        is_in_menu=True,
        menu_order=0,
    )
    db.session.add(page)
    db.session.flush()
    db.session.add(
        PageContent(
            page_id=page.id,
            lang_code="en",
            title="Home",
            subtitle="",
            body_html="<p>Welcome to Home.</p>",
            hero_title="Home",
            hero_subtitle="Explore home with Fluencify.",
            hero_cta_text="Get Started",
            hero_cta_url="/courses",
            meta_title="Home",
            meta_description="Home page of Fluencify.",
            og_title="Home",
            og_description="Home page of Fluencify.",
            twitter_card="summary_large_image",
        )
    )
    db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Know your" in html
    assert "English level" in html
    assert "Start Free Test" in html
    assert "Hall Of Champions" in html
    assert "dynamic sections" not in html
