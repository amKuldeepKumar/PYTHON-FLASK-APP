from __future__ import annotations

from dataclasses import dataclass, field

from flask import url_for
from flask_login import current_user

from .i18n import get_ui_language_code, resolve_fallback_chain
from .models.page import Page, PageContent


@dataclass(frozen=True)
class TopMenuItem:
    label: str
    href: str
    children: tuple["TopMenuItem", ...] = field(default_factory=tuple)
    languages: set[str] | None = None


@dataclass(frozen=True)
class SidebarItem:
    label: str
    href: str = "#"
    icon: str = "bi-circle"
    perm: str | None = None
    roles: tuple[str, ...] | None = None
    badge: str | None = None
    badge_class: str = "text-bg-secondary"
    disabled: bool = False
    children: tuple["SidebarItem", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SidebarSection:
    title: str
    items: tuple[SidebarItem, ...]


PHASE_BADGES = {
    "live": ("LIVE", "text-bg-success"),
    "p4": ("Phase 4", "text-bg-info"),
    "p5": ("Phase 5", "text-bg-warning"),
    "p6": ("Phase 6", "text-bg-primary"),
    "p7": ("Phase 7", "text-bg-primary"),
    "p8": ("Phase 8", "text-bg-primary"),
    "p9": ("Phase 9", "text-bg-primary"),
    "p10": ("Phase 10", "text-bg-secondary"),
    "p11": ("Phase 11", "text-bg-secondary"),
    "p12": ("Phase 12", "text-bg-secondary"),
    "p13": ("Phase 13", "text-bg-secondary"),
    "p14": ("Phase 14", "text-bg-secondary"),
}


def _safe_url(endpoint: str | None, endpoint_args: dict | None = None) -> str:
    if not endpoint:
        return "#"
    try:
        return url_for(endpoint, **(endpoint_args or {}))
    except Exception:
        return "#"


def _phase_item(
    label: str,
    endpoint: str,
    phase_key: str,
    icon: str,
    endpoint_args: dict | None = None,
    perm: str | None = None,
    roles: tuple[str, ...] | None = None,
) -> SidebarItem:
    badge, badge_class = PHASE_BADGES.get(phase_key, ("LIVE", "text-bg-success"))
    return SidebarItem(
        label=label,
        href=_safe_url(endpoint, endpoint_args),
        icon=icon,
        perm=perm,
        roles=roles,
        badge=badge,
        badge_class=badge_class,
    )


def _live_item(
    label: str,
    endpoint: str,
    icon: str,
    endpoint_args: dict | None = None,
    perm: str | None = None,
    roles: tuple[str, ...] | None = None,
) -> SidebarItem:
    badge, badge_class = PHASE_BADGES["live"]
    return SidebarItem(
        label=label,
        href=_safe_url(endpoint, endpoint_args),
        icon=icon,
        perm=perm,
        roles=roles,
        badge=badge,
        badge_class=badge_class,
    )


def _is_language_allowed(languages: set[str] | None) -> bool:
    if not languages:
        return True
    chain = resolve_fallback_chain(get_ui_language_code("en"))
    return any(code in languages for code in chain)


def _public_page_menu_items() -> list[TopMenuItem]:
    skill_slugs = ("speaking", "listening", "reading", "writing")
    skill_items: list[TopMenuItem] = []
    other_items: list[TopMenuItem] = []

    items: list[TopMenuItem] = [
        TopMenuItem(label="Home", href=_safe_url("main.home")),
        TopMenuItem(label="About Us", href=_safe_url("main.about")),
        TopMenuItem(
            label="Courses",
            href=_safe_url("main.courses"),
            children=(
                TopMenuItem(label="All Courses", href=_safe_url("main.courses")),
                TopMenuItem(label="Nursery Lessons", href=f"{_safe_url('main.courses')}?q=nursery"),
                TopMenuItem(label="Free Courses", href=f"{_safe_url('main.courses')}?category=free"),
                TopMenuItem(label="Premium Courses", href=f"{_safe_url('main.courses')}?category=premium"),
                TopMenuItem(label="Special Courses", href=f"{_safe_url('main.courses')}?category=special"),
            ),
        ),
        TopMenuItem(label="Test Yourself", href=_safe_url("main.test_yourself")),
    ]

    try:
        cms_pages = (
            Page.query.with_entities(Page.id, Page.slug, Page.title)
            .filter_by(is_published=True, is_in_menu=True)
            .filter(Page.deleted_at.is_(None))
            .filter(~Page.slug.in_(["home", "about", "contact", "courses"]))
            .order_by(Page.menu_order.asc(), Page.title.asc())
            .all()
        )
    except Exception:
        cms_pages = []

    lang_chain = resolve_fallback_chain(get_ui_language_code("en"))

    for page_id, slug, title in cms_pages:
        try:
            contents = PageContent.query.filter_by(page_id=page_id).all()
            langs = {c.lang_code for c in contents}
        except Exception:
            contents = []
            langs = set()

        label = title or slug.replace("-", " ").title()
        for code in lang_chain:
            content = next((item for item in contents if item.lang_code == code), None)
            if content and getattr(content, "title", None):
                label = content.title
                break

        item = TopMenuItem(
            label=label,
            href=_safe_url("main.page_by_slug", {"slug": slug}),
            languages=langs,
        )
        if _is_language_allowed(item.languages):
            if slug in skill_slugs:
                skill_items.append(item)
            else:
                other_items.append(item)

    if skill_items:
        ordered_skills = sorted(
            skill_items,
            key=lambda item: skill_slugs.index(item.href.rstrip("/").split("/")[-1]) if item.href.rstrip("/").split("/")[-1] in skill_slugs else len(skill_slugs),
        )
        items.append(
            TopMenuItem(
                label="Language Skills",
                href=_safe_url("main.courses"),
                children=tuple(ordered_skills),
            )
        )

    items.append(TopMenuItem(label="Contact", href=_safe_url("main.contact")))
    items.extend(other_items)

    return items


def build_menu() -> list[TopMenuItem]:
    return _public_page_menu_items()


def _current_role_code() -> str:
    return (getattr(current_user, "role_code", None) or getattr(current_user, "role", "") or "").strip().upper()


def _allowed(item: SidebarItem) -> bool:
    current_role = _current_role_code()

    if item.roles and current_role not in {r.strip().upper() for r in item.roles}:
        return False

    if item.perm and not getattr(current_user, "has_perm", lambda _p: False)(item.perm):
        return False

    return True


def _filter_sidebar_item(item: SidebarItem):
    if not _allowed(item):
        return None

    if item.children:
        children = tuple(filtered for child in item.children if (filtered := _filter_sidebar_item(child)))
        if not children:
            return None

        return SidebarItem(
            label=item.label,
            href=item.href,
            icon=item.icon,
            perm=item.perm,
            roles=item.roles,
            badge=item.badge,
            badge_class=item.badge_class,
            disabled=item.disabled,
            children=children,
        )

    return item


def _filter_section(section: SidebarSection):
    items = tuple(filtered for item in section.items if (filtered := _filter_sidebar_item(item)))
    if not items:
        return None
    return SidebarSection(title=section.title, items=items)


def _common_account_section() -> SidebarSection:
    return SidebarSection(
        title="Account",
        items=(
            _live_item("Profile", "account.profile", "bi-person-circle"),
            _live_item("Preferences", "account.preferences", "bi-sliders2"),
            _live_item("Security", "account.security", "bi-shield-lock"),
            _live_item("Login History", "account.login_history", "bi-clock-history"),
            _live_item("Sessions", "account.sessions", "bi-phone"),
        ),
    )


def _common_operations_section() -> SidebarSection:
    return SidebarSection(
        title="Operations",
        items=(
            _live_item("Notifications", "account.notifications", "bi-bell"),
        ),
    )


def _superadmin_sections() -> list[SidebarSection]:
    website_children = (
        _live_item("Front Pages", "superadmin.pages_list", "bi-window-stack"),
        _live_item("SEO Settings", "superadmin.seo_settings", "bi-search-heart"),
        _live_item("WhatsApp Leads", "superadmin.whatsapp_settings", "bi-whatsapp"),
        _live_item("Themes", "theme.manage_themes", "bi-palette2"),
        _live_item("Languages", "superadmin.languages_index", "bi-translate"),
        _live_item("Header Builder", "superadmin.header_builder", "bi-layout-text-sidebar-reverse") ,
        _live_item("Footer Builder", "superadmin.footer_builder", "bi-layout-text-window-reverse") ,
        _live_item("Media Library", "superadmin.media_library", "bi-images") ,
    )

    users_children = (
        _live_item("Admins", "superadmin.admins_list", "bi-people"),
        _live_item("Institutes", "superadmin.institutes_list", "bi-buildings"),
        _live_item("Teachers", "superadmin.teachers_list", "bi-person-workspace"),
        _live_item("Students", "superadmin.students", "bi-mortarboard"),
        _live_item("Search Directory", "superadmin.directory", "bi-search"),
    )

    roles_children = (
        _live_item("Roles", "superadmin.roles", "bi-person-badge"),
        _live_item("Permissions", "superadmin.permissions", "bi-key"),
    )

    academy_children = (
        _live_item("Courses", "superadmin.courses", "bi-journal-richtext"),
        _live_item("Nursery Studio", "superadmin.nursery_studio", "bi-balloon-heart"),
        _live_item("Coupons", "superadmin.coupons", "bi-ticket-perforated"),
        _live_item("Economy & Rewards", "superadmin.economy_dashboard", "bi-coin"),
        _live_item("Lessons", "superadmin.lessons_index", "bi-collection-play"),
        _live_item("Chapters", "superadmin.chapters_index", "bi-folder2-open"),
        _live_item("Questions", "superadmin.questions_index", "bi-patch-question"),
        _live_item("Bulk Upload", "superadmin.bulk_upload_index", "bi-cloud-arrow-up"),
        _live_item("Unified Review Dashboard", "superadmin.review_dashboard", "bi-clipboard-check"),
        _live_item("Publishing Review", "superadmin.publishing_review_dashboard", "bi-graph-up-arrow"),
        _live_item("Special English Pathways", "superadmin.course_pathways", "bi-stars"),
    )

    speaking_children = (
        _phase_item("Topics", "superadmin.speaking_topics", "p6", "bi-collection"),
        _phase_item("Prompts", "superadmin.speaking_prompts", "p6", "bi-chat-left-text"),
    )

    reading_children = (
        _phase_item("Topics", "superadmin.reading_topics", "p7", "bi-card-text"),
        _phase_item("Passages", "superadmin.reading_passages", "p7", "bi-file-earmark-text"),
        _phase_item("Questions", "superadmin.reading_questions", "p7", "bi-patch-question"),
        _phase_item("Review Queue", "superadmin.reading_review_queue", "p7", "bi-clipboard-check"),
    )

    writing_children = (
        _phase_item("Topics", "superadmin.writing_topics", "p9", "bi-pencil-square"),
        _phase_item("Tasks", "superadmin.writing_tasks", "p9", "bi-file-earmark-text"),
        _phase_item("Writing Courses", "superadmin.courses", "p9", "bi-journal-richtext"),
    )

    listening_children = (
        _phase_item("Topics", "superadmin.listening_topics", "p8", "bi-headphones"),
        _phase_item("Questions", "superadmin.listening_questions", "p8", "bi-patch-question"),
        _phase_item("Review Queue", "superadmin.listening_review_queue", "p8", "bi-clipboard-check"),
    )

    security_children = (
        _live_item("Security Settings", "superadmin.security_settings", "bi-shield-lock"),
        _phase_item("AI Central", "superadmin.ai_central", "p8", "bi-cpu"),
        _phase_item("AI Rule Panel", "superadmin.ai_rule_panel", "p14", "bi-sliders"),
        _live_item("API Workbench", "superadmin.api_workbench", "bi-diagram-3"),
        _live_item("Learner Ops", "superadmin.learner_ops", "bi-activity"),
        _live_item("Access Activity", "superadmin.access_activity", "bi-geo-alt"),
        _live_item("Chat Moderation", "superadmin.chat_moderation_queue", "bi-chat-square-text"),
        _live_item("API Logs", "superadmin.api_logs", "bi-box-arrow-in-right"),
        _live_item("Audit Logs", "superadmin.audit_logs", "bi-clipboard-data"),
    )

    return [
        SidebarSection(
            title="Overview",
            items=(
                _live_item("Overview", "superadmin.dashboard", "bi-grid-1x2-fill"),
            ),
        ),
        SidebarSection(
            title="Navigation",
            items=(
                SidebarItem(
                    label="Website",
                    icon="bi-window-sidebar",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=website_children,
                ),
                SidebarItem(
                    label="Users",
                    icon="bi-people",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=users_children,
                ),
                SidebarItem(
                    label="Roles & Access",
                    icon="bi-shield-check",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=roles_children,
                ),
                SidebarItem(
                    label="Academy",
                    icon="bi-journal-check",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=academy_children,
                ),
                SidebarItem(
                    label="Speaking",
                    icon="bi-mic-fill",
                    badge="Phase 6",
                    badge_class="text-bg-primary",
                    children=speaking_children,
                ),
                SidebarItem(
                    label="Reading",
                    icon="bi-book-half",
                    badge="Phase 7",
                    badge_class="text-bg-primary",
                    children=reading_children,
                ),
                SidebarItem(
                    label="Writing",
                    icon="bi-pencil-square",
                    badge="Phase 9",
                    badge_class="text-bg-primary",
                    children=writing_children,
                ),
                SidebarItem(
                    label="Listening",
                    icon="bi-headphones",
                    badge="Phase 8",
                    badge_class="text-bg-primary",
                    children=listening_children,
                ),
                SidebarItem(
                    label="Security & Audit",
                    icon="bi-shield-lock",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=security_children,
                ),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]


def _admin_sections() -> list[SidebarSection]:
    admin_children = (
        _live_item("Dashboard", "admin.dashboard", "bi-grid-1x2-fill"),
    )

    management_children = (
        _live_item("Team", "admin.team", "bi-people"),
        _live_item("Students", "admin.manage_students", "bi-mortarboard"),
        _phase_item("Speaking Analytics", "admin.speaking_analytics", "p6", "bi-graph-up-arrow"),
    )

    return [
        SidebarSection(
            title="Overview",
            items=(
                SidebarItem(
                    label="Admin",
                    icon="bi-speedometer2",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=admin_children,
                ),
            ),
        ),
        SidebarSection(
            title="Management",
            items=(
                SidebarItem(
                    label="Control",
                    icon="bi-diagram-3",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=management_children,
                ),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]


def _seo_sections() -> list[SidebarSection]:
    return [
        SidebarSection(
            title="Overview",
            items=(
                _live_item("Dashboard", "admin.dashboard", "bi-grid-1x2-fill"),
            ),
        ),
        SidebarSection(
            title="Website",
            items=(
                _live_item("Pages", "admin.pages_list", "bi-window-stack"),
                _live_item("Content Tools", "admin.coming_soon", "bi-stars", {"feature": "seo-content-tools"}),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]


def _support_sections() -> list[SidebarSection]:
    return [
        SidebarSection(
            title="Overview",
            items=(
                _live_item("Dashboard", "admin.dashboard", "bi-grid-1x2-fill"),
            ),
        ),
        SidebarSection(
            title="Support",
            items=(
                _live_item("Support Desk", "admin.support", "bi-life-preserver"),
                _live_item("Support Tools", "admin.coming_soon", "bi-tools", {"feature": "support-tools"}),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]


def _accounts_sections() -> list[SidebarSection]:
    return [
        SidebarSection(
            title="Overview",
            items=(
                _live_item("Dashboard", "admin.dashboard", "bi-grid-1x2-fill"),
            ),
        ),
        SidebarSection(
            title="Accounts",
            items=(
                _live_item("Billing Desk", "admin.coming_soon", "bi-receipt", {"feature": "accounts-billing"}),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]


def _student_sections() -> list[SidebarSection]:
    return [
        SidebarSection(
            title="Learning",
            items=(
                _live_item("Dashboard", "student.dashboard", "bi-grid-1x2-fill"),
                _live_item("Course Library", "student.course_library", "bi-collection-play"),
                _live_item("My Courses", "student.my_courses", "bi-journal-check"),
            ),
        ),
        SidebarSection(
            title="Rewards",
            items=(
                _live_item("Wallet", "student.wallet", "bi-wallet2"),
                _live_item("Rewards", "student.rewards", "bi-stars"),
                _live_item("Leaderboard", "student.leaderboard", "bi-trophy"),
            ),
        ),
        SidebarSection(
            title="Practice",
            items=(
                _live_item("Placement Test", "student.placement_test", "bi-clipboard-data"),
                _live_item("My Learning Path", "student.learning_path", "bi-signpost-split"),
                _live_item("AI Interview", "student.interview_entry", "bi-briefcase"),
                _live_item("Certificates", "student.certificates", "bi-award"),
                _live_item("Community Chat", "student.chat", "bi-chat-dots"),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]



def _editor_sections() -> list[SidebarSection]:
    review_children = (
        _phase_item("Review Queue", "superadmin.reading_review_queue", "p7", "bi-clipboard-check"),
    )

    return [
        SidebarSection(
            title="Reading Review",
            items=(
                SidebarItem(
                    label="Editor",
                    icon="bi-pencil-square",
                    badge="LIVE",
                    badge_class="text-bg-success",
                    children=review_children,
                ),
            ),
        ),
        _common_account_section(),
        _common_operations_section(),
    ]

def build_sidebar_sections() -> list[SidebarSection]:
    if not getattr(current_user, "is_authenticated", False):
        return []

    role = _current_role_code()

    if role == "SUPERADMIN":
        sections = _superadmin_sections()
    elif role in {"ADMIN", "SUB_ADMIN"}:
        sections = _admin_sections()
    elif role == "SEO":
        sections = _seo_sections()
    elif role == "SUPPORT":
        sections = _support_sections()
    elif role == "ACCOUNTS":
        sections = _accounts_sections()
    elif role == "EDITOR":
        sections = _editor_sections()
    else:
        sections = _student_sections()

    return [section for item in sections if (section := _filter_section(item))]
