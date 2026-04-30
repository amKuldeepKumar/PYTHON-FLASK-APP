from __future__ import annotations

import json
import re

from flask import Response, abort, current_app, jsonify, render_template, request, url_for, redirect, send_from_directory, session, flash
from sqlalchemy import func
from flask_login import current_user

from . import bp
from ...models.lms import Course
from ...models.page import Page
from ...models.seo_settings import SeoSettings
from ...models.reading_passage import ReadingPassage
from ...models.reading_question import ReadingQuestion
from ...models.reading_topic import ReadingTopic
from ...services.economy_service import EconomyService
from ...services.cms_service import parse_json_list, resolve_page_content
from ...services.browser_notification_service import build_browser_notification_payload
from ...services.language_service import language_label
from ...services.placement_test_service import PlacementTestService
from ...services.whatsapp_service import WhatsAppService



PUBLIC_PLACEMENT_TEST_SESSION_KEY = "student_placement_test_result"


def _public_placement_result() -> dict | None:
    payload = session.get(PUBLIC_PLACEMENT_TEST_SESSION_KEY) or {}
    return payload if isinstance(payload, dict) and payload else None

def _slugify(value: str | None) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return text or "item"


def _normalized_html_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _should_use_fallback_page(slug: str, page, content, sections: list, faq_items: list) -> bool:
    if slug != "home" or not page or not content:
        return False

    hero_title = (getattr(content, "hero_title", None) or "").strip()
    hero_subtitle = (getattr(content, "hero_subtitle", None) or "").strip()
    hero_image = (getattr(content, "hero_image", None) or "").strip()
    subtitle = (getattr(content, "subtitle", None) or "").strip()
    body_text = _normalized_html_text(getattr(content, "body_html", None))

    default_hero_titles = {"home"}
    default_hero_subtitles = {"", "explore home with fluencify."}
    default_body_texts = {"", "welcome to home."}

    has_custom_hero = hero_title.lower() not in default_hero_titles or hero_subtitle.lower() not in default_hero_subtitles
    has_structured_content = bool(sections or faq_items or hero_image or subtitle or body_text not in default_body_texts)

    return not has_custom_hero and not has_structured_content


def _public_course_base_query():
    base_query = Course.query.filter(Course.status != "archived")

    published_count = base_query.filter(
        (Course.is_published.is_(True)) | (Course.status == "published")
    ).count()

    if published_count > 0:
        return base_query.filter(
            (Course.is_published.is_(True)) | (Course.status == "published")
        )

    return base_query


def _public_reading_base_query():
    return (
        ReadingPassage.query
        .join(ReadingTopic, ReadingTopic.id == ReadingPassage.topic_id)
        .filter(
            ReadingPassage.is_active.is_(True),
            ReadingPassage.is_published.is_(True),
            ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            ReadingTopic.is_active.is_(True),
        )
    )


def _passage_question_count(passage_id: int) -> int:
    return (
        ReadingQuestion.query
        .filter(
            ReadingQuestion.passage_id == passage_id,
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .count()
    )


def _reading_topic_json_ld(topic: ReadingTopic, passages: list[ReadingPassage]):
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': f'{topic.title} Reading Passages',
        'description': topic.description or f'Public reading practice on {topic.title} for {topic.level_label} learners.',
        'hasPart': [
            {
                '@type': 'Article',
                'headline': row.title,
                'wordCount': int(row.word_count or 0),
                'educationalLevel': row.level_label,
                'url': request.url_root.rstrip('/') + url_for('main.public_reading_passage', passage_id=row.id, slug=_slugify(row.title)),
            }
            for row in passages[:12]
        ],
    }, ensure_ascii=False)


def _reading_passage_json_ld(topic: ReadingTopic, passage: ReadingPassage, question_count: int):
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': passage.title,
        'description': passage.topic_title_snapshot or topic.title,
        'articleSection': topic.category_label,
        'educationalLevel': passage.level_label,
        'wordCount': int(passage.word_count or 0),
        'timeRequired': f'PT{max(1, int((passage.word_count or 120) / 80))}M',
        'isAccessibleForFree': True,
        'about': [topic.title, topic.category_label],
        'learningResourceType': 'Reading passage',
        'publisher': {'@type': 'Organization', 'name': 'Fluencify'},
        'mainEntityOfPage': request.url,
        'interactionStatistic': {
            '@type': 'InteractionCounter',
            'interactionType': 'https://schema.org/ReadAction',
            'userInteractionCount': question_count,
        },
    }, ensure_ascii=False)


def _render_page(slug: str, fallback_template: str | None = None):
    page, content, lang_used = resolve_page_content(slug, preferred_lang=(request.args.get("lang") or None))
    weekly_leaders = EconomyService.leaderboard("weekly", limit=10) if slug == "home" else []
    monthly_leaders = EconomyService.leaderboard("monthly", limit=10) if slug == "home" else []
    sections = parse_json_list(getattr(content, "sections_json", None)) if content else []
    faq_items = parse_json_list(getattr(content, "faq_json", None)) if content else []

    if ((not page or not page.is_published or not content) or _should_use_fallback_page(slug, page, content, sections, faq_items)) and fallback_template:
        featured_courses = []
        if slug == "home":
            featured_courses = (
                _public_course_base_query()
                .order_by(Course.created_at.desc(), Course.id.desc())
                .limit(6)
                .all()
            )

        return render_template(
            fallback_template,
            featured_courses=featured_courses,
            meta_title=slug.title(),
            meta_description=f"{slug.title()} page",
            canonical_url=request.url,
            og_title=slug.title(),
            og_description=f"{slug.title()} page",
            og_image=None,
            twitter_card="summary_large_image",
            page_json_ld=None,
            weekly_leaders=weekly_leaders,
            monthly_leaders=monthly_leaders,
        )

    if not page or not page.is_published or not content:
        abort(404)

    meta_title = content.meta_title or content.og_title or content.title or page.title
    meta_description = content.meta_description or content.subtitle or ""
    canonical_url = content.canonical_url or request.url

    featured_courses = (
        _public_course_base_query()
        .order_by(Course.created_at.desc(), Course.id.desc())
        .limit(12)
        .all()
    )

    return render_template(
        "main/cms_page.html",
        page=page,
        content=content,
        lang_used=lang_used,
        sections=sections,
        faq_items=faq_items,
        redir_links=parse_json_list(content.links_json),
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        og_title=content.og_title or meta_title,
        og_description=content.og_description or meta_description,
        og_image=content.og_image,
        twitter_card=content.twitter_card or "summary_large_image",
        page_json_ld=content.json_ld,
        featured_courses=featured_courses,
        weekly_leaders=weekly_leaders,
        monthly_leaders=monthly_leaders,
    )


@bp.get("/")
def home():
    return _render_page("home", fallback_template="main/home.html")




@bp.get("/whatsapp")
def whatsapp_redirect():
    """Public WhatsApp lead redirect managed by SuperAdmin.

    The floating button calls this route so clicks can be logged before the
    visitor is sent to WhatsApp with the configured pre-filled message.
    Logged-in students should use the internal student chat instead, so this
    route sends them to the student dashboard.
    """
    if getattr(current_user, "is_authenticated", False):
        return redirect(url_for("student.dashboard"))

    settings = SeoSettings.singleton()
    if not WhatsAppService.is_public_widget_enabled(settings):
        flash("WhatsApp support is not available right now. Please use the contact page.", "info")
        return redirect(url_for("main.home"))

    source_path = request.args.get("source") or request.headers.get("Referer") or request.path
    WhatsAppService.log_click(settings, source_path=source_path)
    return redirect(WhatsAppService.build_wa_url(settings, source_path=source_path))


@bp.route("/test-yourself", methods=["GET", "POST"])
def test_yourself():
    form_blueprint = PlacementTestService.form_blueprint()
    result = _public_placement_result()

    if request.method == "POST":
        result = PlacementTestService.evaluate_submission(request.form)
        session[PUBLIC_PLACEMENT_TEST_SESSION_KEY] = result
        session.modified = True

        if getattr(current_user, "is_authenticated", False) and getattr(current_user, "is_student", False):
            saved = PlacementTestService.save_result(current_user.id, result)
            session[PUBLIC_PLACEMENT_TEST_SESSION_KEY] = saved.to_payload()
            session.modified = True
            flash(f"Placement test completed. Recommended level: {saved.recommended_level.title()}.", "success")
            return redirect(url_for("student.placement_test"))

        flash("Your free test is ready. Login to unlock your full student dashboard recommendation path.", "success")

    login_target = url_for("auth.login", next=url_for("student.placement_test"))
    register_target = url_for("auth.register", next=url_for("student.placement_test"))
    return render_template(
        "main/test_yourself.html",
        form_blueprint=form_blueprint,
        result=result,
        login_target=login_target,
        register_target=register_target,
    )


@bp.get("/about")
def about():
    return _render_page("about", fallback_template="main/about.html")


@bp.get("/contact")
def contact():
    return _render_page("contact", fallback_template="main/contact.html")


@bp.get("/courses")
def courses():
    q = (request.args.get("q") or "").strip().lower()
    category = (request.args.get("category") or "all").strip().lower()
    language = (request.args.get("language") or "").strip().lower()
    difficulty = (request.args.get("difficulty") or "").strip().lower()
    track = (request.args.get("track") or "").strip().lower()
    sort = (request.args.get("sort") or "latest").strip().lower()

    items = _public_course_base_query().all()

    if q:
        items = [
            c for c in items
            if q in (c.title or "").lower()
            or q in (c.description or "").lower()
            or q in (c.slug or "").lower()
        ]

    if category == "free":
        items = [c for c in items if (not c.is_premium) or float(c.current_price or 0) <= 0]
    elif category == "premium":
        items = [c for c in items if c.is_premium and float(c.current_price or 0) > 0]

    if language:
        items = [c for c in items if (c.language_code or "").strip().lower() == language]

    if difficulty:
        items = [c for c in items if (c.difficulty or "").strip().lower() == difficulty]

    if track:
        items = [c for c in items if (c.track_type or "").strip().lower() == track]

    if sort == "price_low":
        items = sorted(items, key=lambda c: float(c.current_price or 0))
    elif sort == "price_high":
        items = sorted(items, key=lambda c: float(c.current_price or 0), reverse=True)
    elif sort == "title":
        items = sorted(items, key=lambda c: (c.title or "").lower())
    else:
        items = sorted(
            items,
            key=lambda c: (c.created_at is not None, c.created_at, c.id),
            reverse=True,
        )

    visible_course_ids = [c.id for c in _public_course_base_query().all()]
    language_rows = []
    if visible_course_ids:
        language_rows = (
            Course.query.with_entities(Course.language_code)
            .filter(
                Course.id.in_(visible_course_ids),
                Course.language_code.isnot(None),
            )
            .distinct()
            .order_by(func.lower(Course.language_code).asc(), Course.language_code.asc())
            .all()
        )

    language_options = [
        {"code": code, "label": language_label(code, fallback=(code or "").upper())}
        for (code,) in language_rows if code
    ]

    visible_tracks = sorted(
        {
            (c.track_type or "").strip().lower()
            for c in _public_course_base_query().all()
            if (c.track_type or "").strip()
        }
    )
    track_options = [(code, code.title()) for code in visible_tracks]

    free_courses = [c for c in items if (not c.is_premium) or float(c.current_price or 0) <= 0]
    premium_courses = [c for c in items if c.is_premium and float(c.current_price or 0) > 0]

    return render_template(
        "main/courses.html",
        courses=items,
        all_courses=items,
        free_courses=free_courses,
        premium_courses=premium_courses,
        special_courses=[],
        active_category=category,
        enrolled_ids=set(),
        student_mode=False,
        current_query=q,
        current_language=language,
        current_difficulty=difficulty,
        current_track=track,
        current_sort=sort,
        language_options=language_options,
        track_options=track_options,
    )


@bp.get("/p/<slug>")

def page_by_slug(slug: str):
    slug = (slug or '').strip().lower()
    page = Page.query.filter_by(slug=slug).first()
    if not page:
        redirect_page = Page.query.filter(Page.redirect_from == '/' + slug, Page.deleted_at.is_(None)).first()
        if redirect_page and redirect_page.redirect_to:
            return redirect(redirect_page.redirect_to, code=int(redirect_page.redirect_code or 301))
    elif getattr(page, 'redirect_to', None) and getattr(page, 'redirect_from', None) == '/' + slug:
        return redirect(page.redirect_to, code=int(page.redirect_code or 301))
    return _render_page(slug)


@bp.get('/reading')
def public_reading_index():
    q = (request.args.get('q') or '').strip().lower()
    level = (request.args.get('level') or '').strip().lower()
    category = (request.args.get('category') or '').strip().lower()

    topics = (
        ReadingTopic.query
        .filter(ReadingTopic.is_active.is_(True))
        .order_by(func.lower(ReadingTopic.title).asc(), ReadingTopic.title.asc())
        .all()
    )

    topic_rows = []
    for topic in topics:
        passages = (
            _public_reading_base_query()
            .filter(ReadingPassage.topic_id == topic.id)
            .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
            .all()
        )
        if not passages:
            continue
        if q and q not in (topic.title or '').lower() and q not in (topic.description or '').lower() and not any(q in (p.title or '').lower() for p in passages):
            continue
        if level and (topic.level or '').lower() != level:
            continue
        if category and (topic.category or '').lower() != category:
            continue
        topic_rows.append({
            'topic': topic,
            'passage_count': len(passages),
            'latest_passage': passages[0],
            'topic_url': url_for('main.public_reading_topic', topic_id=topic.id, slug=_slugify(topic.title)),
        })

    categories = sorted({(row['topic'].category or 'General').strip() or 'General' for row in topic_rows}, key=str.lower)
    page_json_ld = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': 'Public Reading Practice',
        'description': 'Topic-based public reading pages for English learners.',
        'hasPart': [
            {
                '@type': 'Thing',
                'name': row['topic'].title,
                'url': request.url_root.rstrip('/') + row['topic_url'],
            }
            for row in topic_rows[:20]
        ],
    }, ensure_ascii=False)

    return render_template(
        'main/reading_public_index.html',
        topic_rows=topic_rows,
        current_query=q,
        current_level=level,
        current_category=category,
        category_options=categories,
        meta_title='Public Reading Practice Topics | Fluencify',
        meta_description='Browse public reading practice topics with SEO-friendly landing pages for basic, intermediate, and advanced learners.',
        canonical_url=request.base_url if not request.query_string else request.url,
        og_title='Public Reading Practice Topics | Fluencify',
        og_description='Explore topic-based public reading pages and improve reading skills with free practice passages.',
        twitter_card='summary_large_image',
        page_json_ld=page_json_ld,
    )


@bp.get('/reading/topic/<int:topic_id>-<slug>')
def public_reading_topic(topic_id: int, slug: str):
    topic = ReadingTopic.query.get_or_404(topic_id)
    if not topic.is_active:
        abort(404)
    passages = (
        _public_reading_base_query()
        .filter(ReadingPassage.topic_id == topic.id)
        .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
        .all()
    )
    if not passages:
        abort(404)

    canonical = url_for('main.public_reading_topic', topic_id=topic.id, slug=_slugify(topic.title), _external=True)
    if slug != _slugify(topic.title):
        return redirect(canonical, code=301)

    passage_rows = []
    for passage in passages:
        passage_rows.append({
            'passage': passage,
            'question_count': _passage_question_count(passage.id),
            'passage_url': url_for('main.public_reading_passage', passage_id=passage.id, slug=_slugify(passage.title)),
        })

    return render_template(
        'main/reading_topic_landing.html',
        topic=topic,
        passage_rows=passage_rows,
        canonical_url=canonical,
        meta_title=f'{topic.title} Reading Passages | Fluencify',
        meta_description=topic.description or f'Practice {topic.title} reading passages for {topic.level_label} learners.',
        og_title=f'{topic.title} Reading Passages | Fluencify',
        og_description=topic.description or f'Public reading pages about {topic.title} with clean practice passages and question previews.',
        twitter_card='summary_large_image',
        page_json_ld=_reading_topic_json_ld(topic, passages),
    )


@bp.get('/reading/passage/<int:passage_id>-<slug>')
def public_reading_passage(passage_id: int, slug: str):
    passage = _public_reading_base_query().filter(ReadingPassage.id == passage_id).first_or_404()
    topic = passage.topic
    canonical = url_for('main.public_reading_passage', passage_id=passage.id, slug=_slugify(passage.title), _external=True)
    if slug != _slugify(passage.title):
        return redirect(canonical, code=301)

    approved_questions = (
        ReadingQuestion.query
        .filter(
            ReadingQuestion.passage_id == passage.id,
            ReadingQuestion.is_active.is_(True),
            ReadingQuestion.status == ReadingQuestion.STATUS_APPROVED,
        )
        .order_by(ReadingQuestion.display_order.asc(), ReadingQuestion.id.asc())
        .all()
    )
    related_passages = (
        _public_reading_base_query()
        .filter(ReadingPassage.topic_id == topic.id, ReadingPassage.id != passage.id)
        .order_by(ReadingPassage.updated_at.desc(), ReadingPassage.id.desc())
        .limit(6)
        .all()
    )
    return render_template(
        'main/reading_passage_public.html',
        passage=passage,
        topic=topic,
        approved_questions=approved_questions,
        question_count=len(approved_questions),
        related_passages=related_passages,
        canonical_url=canonical,
        meta_title=f'{passage.title} | {topic.title} Reading Passage | Fluencify',
        meta_description=(passage.content or '')[:155].strip() or f'Practice {topic.title} reading with this {passage.level_label.lower()} passage.',
        og_title=f'{passage.title} | Fluencify',
        og_description=(passage.content or '')[:155].strip() or f'Free public reading passage on {topic.title}.',
        twitter_card='summary_large_image',
        page_json_ld=_reading_passage_json_ld(topic, passage, len(approved_questions)),
    )




def _build_htaccess_content(settings: SeoSettings) -> str:
    lines = [
        'RewriteEngine On',
    ]
    if settings.htaccess_force_https:
        lines.extend([
            'RewriteCond %{HTTPS} !=on',
            'RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]',
        ])
    if settings.htaccess_force_www:
        lines.extend([
            r'RewriteCond %{HTTP_HOST} !^www\. [NC]',
            'RewriteRule ^ https://www.%{HTTP_HOST}%{REQUEST_URI} [L,R=301]',
        ])
    if settings.htaccess_enable_compression:
        lines.extend([
            '<IfModule mod_deflate.c>',
            '  AddOutputFilterByType DEFLATE text/plain text/html text/css application/javascript application/json image/svg+xml',
            '</IfModule>',
        ])
    if settings.htaccess_enable_browser_cache:
        lines.extend([
            '<IfModule mod_expires.c>',
            '  ExpiresActive On',
            '  ExpiresByType text/css "access plus 7 days"',
            '  ExpiresByType application/javascript "access plus 7 days"',
            '  ExpiresByType image/png "access plus 30 days"',
            '  ExpiresByType image/jpeg "access plus 30 days"',
            '  ExpiresByType image/webp "access plus 30 days"',
            '</IfModule>',
        ])
    custom = (settings.htaccess_custom_rules or '').strip()
    if custom:
        lines.extend(['', '# Custom rules', custom])
    return '\n'.join(lines).strip() + '\n'

@bp.get("/.htaccess")
def htaccess_preview():
    settings = SeoSettings.singleton()
    return Response(_build_htaccess_content(settings), mimetype="text/plain")


@bp.get("/robots.txt")
def robots():
    settings = SeoSettings.singleton()
    if not settings.robots_enabled:
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")
    lines = ["User-agent: *"]
    policy = (settings.robots_policy or 'index,follow').lower()
    if 'noindex' in policy or 'nofollow' in policy:
        lines.append('Disallow: /')
    else:
        lines.extend([
            'Disallow: /admin',
            'Disallow: /superadmin',
            'Disallow: /auth',
            'Allow: /',
        ])
    extra = (settings.extra_robots_lines or '').strip()
    if extra:
        lines.extend([line for line in extra.splitlines() if line.strip()])
    if settings.sitemap_enabled:
        lines.append(f"Sitemap: {request.url_root.rstrip('/')}/sitemap.xml")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    settings = SeoSettings.singleton()
    base = request.url_root.rstrip("/")
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    if settings.sitemap_include_pages:
        pages = Page.query.filter_by(is_published=True).filter(Page.deleted_at.is_(None)).all()
        for page in pages:
            if page.slug == "home":
                loc = base + url_for("main.home")
            elif page.slug in ("about", "contact", "courses"):
                loc = base + url_for(f"main.{page.slug}")
            else:
                loc = base + url_for("main.page_by_slug", slug=page.slug)
            xml.extend([
                "  <url>",
                f"    <loc>{loc}</loc>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ])

    if settings.sitemap_include_public_reading:
        xml.extend([
            "  <url>",
            f"    <loc>{base + url_for('main.public_reading_index')}</loc>",
            "    <changefreq>daily</changefreq>",
            "    <priority>0.8</priority>",
            "  </url>",
        ])
        public_topics = (
            ReadingTopic.query
            .join(ReadingPassage, ReadingPassage.topic_id == ReadingTopic.id)
            .filter(
                ReadingTopic.is_active.is_(True),
                ReadingPassage.is_active.is_(True),
                ReadingPassage.is_published.is_(True),
                ReadingPassage.status == ReadingPassage.STATUS_APPROVED,
            )
            .distinct()
            .all()
        )
        for topic in public_topics:
            xml.extend([
                "  <url>",
                f"    <loc>{base + url_for('main.public_reading_topic', topic_id=topic.id, slug=_slugify(topic.title))}</loc>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ])
        public_passages = _public_reading_base_query().all()
        for passage in public_passages:
            xml.extend([
                "  <url>",
                f"    <loc>{base + url_for('main.public_reading_passage', passage_id=passage.id, slug=_slugify(passage.title))}</loc>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.6</priority>",
                "  </url>",
            ])

    if settings.sitemap_include_courses:
        xml.extend([
            "  <url>",
            f"    <loc>{base + url_for('main.courses')}</loc>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>0.8</priority>",
            "  </url>",
        ])

    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")


@bp.get("/api/browser-notification")
def browser_notification_payload():
    response = jsonify(build_browser_notification_payload())
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@bp.get("/service-worker.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "service-worker.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return response
