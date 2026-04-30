from __future__ import annotations

import json

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import (
    Language,
    Notification,
    OtpChallenge,
    Page,
    PageContent,
    Permission,
    RoleModel,
    RolePermission,
    SecurityPolicy,
    Theme,
    User,
    UserSecurityState,
)
from app.models.user import Role as UserRole


def _seed_rbac_data():
    roles = [
        ("SUPERADMIN", "Super Admin", "system"),
        ("ADMIN", "Admin", "tenant"),
        ("SEO", "SEO", "tenant"),
        ("ACCOUNTS", "Accounts", "tenant"),
        ("SUPPORT", "Support", "tenant"),
        ("STUDENT", "Student", "tenant"),
    ]

    perms = [
        ("superadmin.dashboard.view", "SuperAdmin dashboard", "System"),
        ("rbac.roles.manage", "Manage roles", "System"),
        ("rbac.permissions.manage", "Manage permissions", "System"),
        ("audit.view", "View audit logs", "System"),
        ("content.pages.manage", "Manage pages (CMS)", "Content"),
        ("seo.settings.manage", "Manage SEO settings", "SEO"),
        ("theme.manage", "Manage themes", "Appearance"),
        ("superadmin.admins.manage", "Manage admins", "System"),
        ("api.logs.view", "View API logs", "System"),
        ("notifications.view", "View notifications", "System"),
        ("admin.dashboard.view", "Admin dashboard", "Admin"),
        ("admin.students.view", "View students", "Admin"),
        ("admin.courses.view", "View courses", "Admin"),
        ("admin.support.view", "View support", "Admin"),
        ("student.dashboard.view", "Student dashboard", "Student"),
    ]

    for code, name, scope in roles:
        if not RoleModel.query.filter_by(code=code).first():
            db.session.add(RoleModel(code=code, name=name, scope=scope))

    for code, name, group in perms:
        if not Permission.query.filter_by(code=code).first():
            db.session.add(Permission(code=code, name=name, group=group))

    db.session.commit()

    super_role = RoleModel.query.filter_by(code="SUPERADMIN").first()
    admin_role = RoleModel.query.filter_by(code="ADMIN").first()
    sub_admin_role = RoleModel.query.filter_by(code="SUB_ADMIN").first()
    student_role = RoleModel.query.filter_by(code="STUDENT").first()
    seo_role = RoleModel.query.filter_by(code="SEO").first()
    support_role = RoleModel.query.filter_by(code="SUPPORT").first()
    accounts_role = RoleModel.query.filter_by(code="ACCOUNTS").first()
    perm_by_code = {p.code: p for p in Permission.query.all()}

    def give(role, codes):
        if not role:
            return
        for code in codes:
            perm = perm_by_code.get(code)
            if not perm:
                continue
            exists = RolePermission.query.filter_by(
                role_id=role.id,
                permission_id=perm.id,
            ).first()
            if not exists:
                db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    give(super_role, list(perm_by_code.keys()))
    give(
        admin_role,
        [
            "admin.dashboard.view",
            "admin.students.view",
            "admin.courses.view",
            "admin.support.view",
            "notifications.view",
        ],
    )
    give(sub_admin_role, ["admin.dashboard.view", "admin.students.view", "admin.support.view", "notifications.view"])
    give(
        seo_role,
        [
            "content.pages.manage",
            "seo.settings.manage",
            "theme.manage",
            "notifications.view",
        ],
    )
    give(
        support_role,
        [
            "admin.dashboard.view",
            "admin.support.view",
            "notifications.view",
        ],
    )
    give(accounts_role, ["notifications.view"])
    give(student_role, ["student.dashboard.view", "notifications.view"])

    db.session.commit()


def _seed_languages_minimal():
    from app.services.language_service import ensure_default_languages

    ensure_default_languages(enable_all=True)


def _seed_pages_data():
    defaults = [
        (
            "home",
            "/",
            "Home",
            True,
            [
                ("hero_title", "Welcome to Fluencify"),
                ("hero_subtitle", "Practice English smarter with guided AI learning."),
            ],
        ),
        (
            "about",
            "/about",
            "About",
            True,
            [
                ("body_title", "About Us"),
                ("body_html", "<p>Fluencify helps learners grow with guided practice.</p>"),
            ],
        ),
        (
            "contact",
            "/contact",
            "Contact",
            True,
            [
                ("body_title", "Contact Us"),
                ("body_html", "<p>Email: support@fluencify.local</p>"),
            ],
        ),
    ]

    for slug, route, title, published, contents in defaults:
        page = Page.query.filter_by(slug=slug).first()
        if not page:
            page = Page(slug=slug, route_path=route, title=title, is_published=published)
            db.session.add(page)
            db.session.commit()

        for key, value in contents:
            pc = PageContent.query.filter_by(page_id=page.id, field_key=key).first()
            if not pc:
                db.session.add(PageContent(page_id=page.id, field_key=key, field_value=value))

    db.session.commit()


def _seed_themes():
    theme = Theme.query.filter_by(slug="default").first()
    if theme:
        return

    default_tokens = {
        "primary": "#3b82f6",
        "secondary": "#6366f1",
        "accent": "#14b8a6",
        "background": "#f8fafc",
        "surface": "#ffffff",
        "text": "#0f172a",
        "muted": "#64748b",
        "success": "#10b981",
        "warning": "#f59e0b",
        "danger": "#ef4444",
    }

    theme = Theme(
        name="Default Theme",
        slug="default",
        description="System default theme",
        tokens_json=json.dumps(default_tokens, indent=2),
        css_overrides="",
        is_active=True,
    )
    db.session.add(theme)
    db.session.commit()


def _seed_curated_notifications():
    defaults = {
        UserRole.SUPERADMIN.value: [
            (
                "System ready",
                "Your Fluencify control center is ready. Review roles, themes, and dashboards.",
                "system",
                "/superadmin/dashboard",
            ),
            (
                "Security check",
                "Review security settings and ensure OTP policy matches your environment.",
                "security",
                "/superadmin/security",
            ),
        ],
        UserRole.ADMIN.value: [
            (
                "Welcome admin",
                "Start by reviewing courses, students, and lesson activity.",
                "system",
                "/admin/dashboard",
            ),
        ],
        UserRole.STUDENT.value: [
            (
                "Welcome to Fluencify",
                "Complete your profile and start your first lesson.",
                "system",
                "/student/dashboard",
            ),
        ],
    }

    users = User.query.all()
    for user in users:
        existing_titles = {n.title for n in Notification.query.filter_by(user_id=user.id).all()}
        for title, message, category, path in defaults.get(user.role, []):
            if title not in existing_titles:
                db.session.add(
                    Notification(
                        user_id=user.id,
                        title=title,
                        message=message,
                        category=category,
                        link_path=path,
                    )
                )
    db.session.commit()


@click.command("languages-import")
@with_appcontext
def languages_import_command():
    from app.services.language_service import ensure_default_languages

    total = ensure_default_languages(enable_all=True)
    click.echo(f"Imported/updated {total} languages.")


def register_cli(app):
    @app.cli.command("seed-rbac")
    @with_appcontext
    def seed_rbac():
        _seed_rbac_data()
        click.echo("✅ RBAC seeded: roles + permissions + mappings.")

    @app.cli.command("seed-languages")
    @with_appcontext
    def seed_languages():
        _seed_languages_minimal()
        click.echo("✅ Languages seeded (minimal set).")

    @app.cli.command("seed-pages")
    @with_appcontext
    def seed_pages():
        _seed_languages_minimal()
        _seed_pages_data()
        click.echo("✅ Default pages and page content seeded.")

    @app.cli.command("seed-themes")
    @with_appcontext
    def seed_themes():
        _seed_themes()
        click.echo("✅ Default theme seeded.")

    @app.cli.command("seed-notifications")
    @with_appcontext
    def seed_notifications():
        _seed_curated_notifications()
        click.echo("✅ Curated notifications seeded.")

    @app.cli.command("create-superadmin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @with_appcontext
    def create_superadmin(username, email, password):
        _seed_rbac_data()
        _seed_themes()

        super_role = RoleModel.query.filter_by(code="SUPERADMIN").first()
        if not super_role:
            click.echo("❌ SUPERADMIN role missing. Run: flask seed-rbac")
            return

        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            click.echo("❌ User already exists.")
            return

        user = User(
            username=username,
            email=email,
            role=UserRole.SUPERADMIN.value,
            role_id=super_role.id,
            admin_id=None,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        _seed_curated_notifications()
        click.echo("✅ SuperAdmin created successfully.")

    @app.cli.command("reset-password")
    @click.argument("identifier")
    @click.option("--new", prompt=True, hide_input=True, confirmation_prompt=True)
    @with_appcontext
    def reset_password(identifier, new):
        ident = (identifier or "").strip().lower()
        user = User.query.filter(
            (User.email.ilike(ident)) | (User.username.ilike(ident))
        ).first()

        if not user:
            click.echo("❌ User not found.")
            return

        user.set_password(new)
        if hasattr(user, "is_active"):
            user.is_active = True
        db.session.commit()
        click.echo(f"✅ Password reset for: {user.username} ({user.email})")

    @app.cli.command("init-phase4-security")
    @with_appcontext
    def init_phase4_security():
        SecurityPolicy.__table__.create(bind=db.engine, checkfirst=True)
        OtpChallenge.__table__.create(bind=db.engine, checkfirst=True)
        UserSecurityState.__table__.create(bind=db.engine, checkfirst=True)
        SecurityPolicy.singleton()
        click.echo("✅ Phase 4 security tables initialized.")

    @app.cli.command("init-student-ai")
    @with_appcontext
    def init_student_ai():
        """Practical DB patch for new student AI fields on existing SQLite/dev DB."""
        from sqlalchemy import text

        conn = db.engine.connect()

        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        user_adds = {
            "gender": "ALTER TABLE users ADD COLUMN gender VARCHAR(20)",
            "date_of_birth": "ALTER TABLE users ADD COLUMN date_of_birth DATE",
            "target_exam": "ALTER TABLE users ADD COLUMN target_exam VARCHAR(40)",
            "current_level": "ALTER TABLE users ADD COLUMN current_level VARCHAR(40)",
            "target_score": "ALTER TABLE users ADD COLUMN target_score VARCHAR(40)",
            "native_language": "ALTER TABLE users ADD COLUMN native_language VARCHAR(40)",
            "bio": "ALTER TABLE users ADD COLUMN bio TEXT",
            "study_goal": "ALTER TABLE users ADD COLUMN study_goal TEXT",
            "preferred_study_time": "ALTER TABLE users ADD COLUMN preferred_study_time VARCHAR(40)",
            "profile_completed_at": "ALTER TABLE users ADD COLUMN profile_completed_at DATETIME",
        }
        for col, sql in user_adds.items():
            if col not in cols:
                conn.execute(text(sql))

        pcols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(user_preferences)")).fetchall()
        }
        pref_adds = {
            "voice_name": "ALTER TABLE user_preferences ADD COLUMN voice_name VARCHAR(80)",
            "preferred_study_time": "ALTER TABLE user_preferences ADD COLUMN preferred_study_time VARCHAR(40)",
            "welcome_voice_mode": (
                "ALTER TABLE user_preferences "
                "ADD COLUMN welcome_voice_mode VARCHAR(20) DEFAULT 'once' NOT NULL"
            ),
            "auto_play_question": "ALTER TABLE user_preferences ADD COLUMN auto_play_question BOOLEAN NOT NULL DEFAULT 1",
            "auto_start_listening": "ALTER TABLE user_preferences ADD COLUMN auto_start_listening BOOLEAN NOT NULL DEFAULT 1",
            "question_beep_enabled": "ALTER TABLE user_preferences ADD COLUMN question_beep_enabled BOOLEAN NOT NULL DEFAULT 1",
        }
        for col, sql in pref_adds.items():
            if col not in pcols:
                conn.execute(text(sql))

        conn.commit()
        db.create_all()
        click.echo("✅ Student AI profile patch applied.")

    @app.cli.command("db-reset")
    @click.confirmation_option(prompt="This will delete and recreate all tables. Continue?")
    @with_appcontext
    def db_reset():
        db.drop_all()
        db.create_all()
        _seed_rbac_data()
        _seed_languages_minimal()
        _seed_pages_data()
        _seed_themes()
        click.echo("✅ Database reset complete.")