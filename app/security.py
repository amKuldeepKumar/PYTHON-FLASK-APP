from flask import Flask
from flask_talisman import Talisman
from .extensions import limiter


def init_security(app: Flask):
    if app.config.get("RATELIMIT_ENABLED", True):
        limiter._default_limits = [app.config.get("RATELIMIT_DEFAULT", "200 per hour")]

    force_https = bool(app.config.get("FORCE_HTTPS", False))
    session_cookie_secure = bool(app.config.get("SESSION_COOKIE_SECURE", force_https))

    csp = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https:"],
        "style-src": ["'self'", "'unsafe-inline'", "https:"],
        "script-src": ["'self'", "'unsafe-inline'", "https:"],
        "font-src": ["'self'", "data:", "https:"],
        "connect-src": ["'self'", "https:"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }

    report_only = False
    report_uri = None
    try:
        from .models.security_policy import SecurityPolicy

        policy = SecurityPolicy.query.first()
        if policy:
            report_only = bool(policy.csp_report_only)
            report_uri = (policy.csp_report_uri or "").strip() or None
    except Exception:
        policy = None

    if report_uri:
        csp["report-uri"] = [report_uri]

    Talisman(
        app,
        force_https=force_https,
        content_security_policy=csp,
        content_security_policy_report_only=report_only,
        frame_options="DENY",
        strict_transport_security=force_https,
        session_cookie_secure=session_cookie_secure,
        session_cookie_http_only=True,
        session_cookie_samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
        referrer_policy="strict-origin-when-cross-origin",
    )
