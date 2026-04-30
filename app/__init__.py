"""
Phase Coverage:
- Phase 1: Flask App Factory + extension initialization + blueprint registration + /health endpoint.
- Phase 2: Role-based dashboards & redirect rules (via blueprints + RBAC elsewhere)
- Phase 3: Language registry + user preferences blueprint (already registered below)

Future:
- Phase 4: OTP policy engine + stricter CSP + lockout
- Phase 12+: AI Provider registry, guardrails, request logging
"""

from __future__ import annotations

import os

from flask import Flask, flash, render_template, redirect, request, url_for

from .config import get_config
from .extensions import csrf, db, limiter, login_manager, migrate
from .security import init_security


def create_app() -> Flask:
    """Flask application factory."""
    app = Flask(__name__, instance_relative_config=True)

    cfg = get_config()
    app.config.from_object(cfg)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    try:
        limiter.init_app(app)
    except Exception:
        pass

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    init_security(app)

    from . import models as _models  # noqa: F401

    from .blueprints.main import bp as main_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.superadmin import bp as superadmin_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.student import bp as student_bp
    from .blueprints.account import bp as account_bp
    from .blueprints.theme import bp as theme_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(superadmin_bp, url_prefix="/superadmin")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(account_bp, url_prefix="/account")
    app.register_blueprint(theme_bp)

    with app.app_context():
        try:
            from .schema_bootstrap import ensure_dev_sqlite_schema
            from .services.cms_service import seed_default_pages
            from .services.dev_seed_service import ensure_local_dev_users

            ensure_dev_sqlite_schema()
            seed_default_pages()
            if os.getenv("FLUENCIFY_SKIP_DEV_BOOTSTRAP", "0") != "1":
                ensure_local_dev_users()
        except Exception as exc:
            app.logger.exception("Schema/bootstrap initialization failed: %s", exc)

    from .menu import build_menu, build_sidebar_sections

    @app.before_request
    def _enforce_active_session():
        try:
            from flask_login import current_user
            from .services.session_service import enforce_session_guard

            if getattr(current_user, "is_authenticated", False) and not enforce_session_guard():
                flash("Your session is no longer active on this device. Please sign in again.", "warning")
                return redirect(url_for("auth.login"))
        except Exception:
            return None

    @app.context_processor
    def inject_menu():
        # ------------------------------------------------------
        # PHASE 7 / PHASE 11
        # Global theme bridge for public, auth, admin, student,
        # and superadmin screens. We only inject presentation data
        # here so existing business logic stays untouched.
        # ------------------------------------------------------
        data = {
            "menu_items": build_menu(),
            "sidebar_sections": build_sidebar_sections(),
            "unread_notifications": 0,
            "seo_settings": None,
            "active_theme_mode": "dark",
            "student_chat_widget": None,
            "site_shell": {},
            "active_theme": None,
        }

        try:
            from flask_login import current_user
            from .models.notification import Notification
            from .models.seo_settings import SeoSettings
            from .models.theme import Theme

            def _safe_json_load(raw, fallback):
                try:
                    return json.loads(raw or '')
                except Exception:
                    return fallback

            import json

            def _hex_to_rgb(value: str):
                raw = (value or "").strip().lstrip("#")
                if len(raw) == 3:
                    raw = "".join(ch * 2 for ch in raw)
                if len(raw) != 6:
                    return None
                try:
                    return tuple(int(raw[i:i+2], 16) for i in (0, 2, 4))
                except ValueError:
                    return None

            def _pick_theme_mode(theme_obj) -> str:
                bg_value = getattr(theme_obj, "bg", "") or ""
                rgb = _hex_to_rgb(bg_value)
                if not rgb:
                    return "dark"
                luminance = (0.2126 * rgb[0]) + (0.7152 * rgb[1]) + (0.0722 * rgb[2])
                return "light" if luminance >= 186 else "dark"

            data["seo_settings"] = SeoSettings.singleton()
            active_theme = Theme.ensure_default()
            data["active_theme"] = active_theme
            data["active_theme_mode"] = _pick_theme_mode(active_theme)
            settings = data["seo_settings"]
            data["site_shell"] = {
                "header_links": _safe_json_load(getattr(settings, "header_links_json", "[]"), []),
                "footer_widgets": _safe_json_load(getattr(settings, "footer_widgets_json", "[]"), []),
                "footer_columns": max(1, min(6, int(getattr(settings, "footer_columns", 4) or 4))),
            }

            if getattr(current_user, "is_authenticated", False):
                data["unread_notifications"] = Notification.query.filter_by(
                    user_id=current_user.id,
                    is_read=False,
                ).count()
                user_prefs = getattr(current_user, "preferences", None)
                if user_prefs is not None and getattr(user_prefs, "dark_mode", None) is not None:
                    data["active_theme_mode"] = "dark" if bool(user_prefs.dark_mode) else "light"
                if getattr(current_user, "is_student", False):
                    from .models.lms import Lesson
                    from .services.economy_service import EconomyService

                    view_args = getattr(request, "view_args", {}) or {}
                    active_course_id = view_args.get("course_id")
                    lesson_id = view_args.get("lesson_id")
                    if active_course_id is None and lesson_id:
                        lesson = db.session.get(Lesson, int(lesson_id))
                        if lesson and lesson.level:
                            active_course_id = lesson.level.course_id
                    data["student_chat_widget"] = EconomyService.chat_payload(
                        current_user.id,
                        active_course_id,
                        limit=12,
                    )
        except Exception:
            data["unread_notifications"] = 0
            data["seo_settings"] = None
            data["active_theme_mode"] = "dark"
            data["student_chat_widget"] = None
            data["site_shell"] = {}
            data["active_theme"] = None

        return data

    from .cli import register_cli
    register_cli(app)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("main/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("main/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("main/500.html"), 500

    @app.get("/health")
    def health():
        return {"status": "ok", "env": app.config.get("ENV_NAME", "unknown")}, 200

    return app
