from datetime import datetime
from urllib.parse import urlsplit

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import bp
from .forms import LoginForm, OtpForm, RegisterForm, ResetPasswordForm, ResetRequestForm
from ...audit import audit
from ...extensions import db, limiter
from ...models.user import Role, User
from ...models.user_preferences import UserPreferences
from ...services.ai_voice_service import login_voice_payload, registration_voice_payload
from ...services.dev_seed_service import local_dev_login_accounts
from ...services.session_service import issue_session, revoke_current_session
from ...services.security_service import (
    create_otp_challenge,
    get_client_ip,
    get_device_hash,
    is_locked,
    log_login_attempt,
    register_failure,
    reset_failures,
    should_require_otp,
    verify_otp,
)


def _role_dashboard_endpoint(user: User) -> str:
    role_code = getattr(user, "role_code", None)

    if role_code == Role.SUPERADMIN.value:
        return "superadmin.dashboard"

    if role_code in {
        Role.ADMIN.value,
        Role.SUB_ADMIN.value,
        Role.SEO.value,
        Role.ACCOUNTS.value,
        Role.SUPPORT.value,
        Role.TEACHER.value,
    }:
        return "admin.dashboard"

    if user.needs_student_onboarding():
        return "account.profile"

    return "student.dashboard"


def _redirect_after_login(user: User):
    next_url = session.pop("pending_redirect", None)
    if _is_safe_next_url(next_url):
        return redirect(next_url)

    endpoint = _role_dashboard_endpoint(user)

    if endpoint == "account.profile":
        return redirect(url_for(endpoint, onboarding="1"))

    return redirect(url_for(endpoint))


def _is_safe_next_url(target: str | None) -> bool:
    value = (target or "").strip()
    if not value:
        return False
    parsed = urlsplit(value)
    return not parsed.scheme and not parsed.netloc and value.startswith("/")


def _resolve_next_url() -> str | None:
    for candidate in (
        request.form.get("next"),
        request.args.get("next"),
        session.get("pending_redirect"),
    ):
        if _is_safe_next_url(candidate):
            return candidate
    return None


def _complete_login(user: User):
    login_user(user, remember=True)
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    reset_failures(user.id)
    log_login_attempt(user.id, True, reason="login_success")
    issue_session(user)

    accent = getattr(getattr(user, "preferences", None), "accent", None) or "en-IN"
    session["ai_voice_payload"] = login_voice_payload(
        username=user.first_name or user.username,
        accent=accent,
        last_activity=user.latest_learning_summary(),
        is_new=user.profile_completed_at is None,
    )

    session.pop("pending_auth_user_id", None)

    audit("login", target=str(user.id))
    flash("Welcome back!", "success")
    return _redirect_after_login(user)


@bp.get("/login")
@bp.post("/login")
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        next_url = request.args.get("next")
        if _is_safe_next_url(next_url):
            return redirect(next_url)
        return _redirect_after_login(current_user)

    form = LoginForm()
    voice_payload = session.pop("ai_voice_payload", None)
    dev_login_accounts = local_dev_login_accounts()
    next_url = _resolve_next_url()

    if form.validate_on_submit():
        ident_raw = form.username_or_email.data.strip()
        ident = ident_raw.lower()

        user = User.query.filter(
            db.or_(
                db.func.lower(User.email) == ident,
                db.func.lower(User.username) == ident,
            )
        ).first()

        if user:
            locked, mins = is_locked(user.id)
            if locked:
                flash(f"Account temporarily locked. Try again in about {mins} minute(s).", "danger")
                return render_template("auth/login.html", form=form, ai_voice_payload=voice_payload, dev_login_accounts=dev_login_accounts)

        if not user or not user.check_password(form.password.data):
            if user:
                locked, mins = register_failure(user.id, get_client_ip(), get_device_hash())
                log_login_attempt(user.id, False, reason="invalid_password")
                flash(
                    f"Too many failed attempts. Account locked for {mins} minute(s)." if locked else "Invalid credentials.",
                    "danger",
                )
            else:
                flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form, ai_voice_payload=voice_payload, dev_login_accounts=dev_login_accounts)

        if not user.is_active:
            flash("Account is disabled. Contact support.", "warning")
            return render_template("auth/login.html", form=form, ai_voice_payload=voice_payload, dev_login_accounts=dev_login_accounts)

        need_otp, reason = should_require_otp(user)
        if not need_otp:
            if next_url:
                session["pending_redirect"] = next_url
            return _complete_login(user)

        try:
            code = create_otp_challenge(user, reason=reason)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("auth/login.html", form=form, ai_voice_payload=voice_payload, dev_login_accounts=dev_login_accounts)

        session["pending_auth_user_id"] = user.id
        session["pending_redirect"] = next_url or url_for(_role_dashboard_endpoint(user))

        audit("otp_challenge_issued", target=str(user.id), meta=reason)
        flash(
            f"DEV OTP for {user.email}: {code}" if current_app.config.get("OTP_DEV_MODE", False) else "OTP sent to your registered contact.",
            "warning" if current_app.config.get("OTP_DEV_MODE", False) else "info",
        )
        return redirect(url_for("auth.otp_verify"))

    return render_template(
        "auth/login.html",
        form=form,
        ai_voice_payload=voice_payload,
        dev_login_accounts=dev_login_accounts,
        next_url=next_url,
    )


@bp.get("/otp")
@bp.post("/otp")
@limiter.limit("30 per hour")
def otp_verify():
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)

    pending_user_id = session.get("pending_auth_user_id")
    if not pending_user_id:
        flash("Your login session expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(pending_user_id)
    if not user:
        session.pop("pending_auth_user_id", None)
        session.pop("pending_redirect", None)
        flash("Account not found.", "danger")
        return redirect(url_for("auth.login"))

    form = OtpForm()
    if form.validate_on_submit():
        ok, message = verify_otp(user.id, form.code.data)
        if not ok:
            audit("otp_failed", target=str(user.id), meta=message)
            flash(message, "danger")
            return render_template("auth/otp.html", form=form, user=user)

        audit("otp_verified", target=str(user.id))
        return _complete_login(user)

    return render_template("auth/otp.html", form=form, user=user)


@bp.get("/register")
@bp.post("/register")
@limiter.limit("10 per minute")
def register():
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        username = form.username.data.strip()

        if User.query.filter(db.func.lower(User.email) == email).first():
            flash("Email already registered.", "warning")
            return render_template("auth/register.html", form=form)

        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            flash("Username already taken.", "warning")
            return render_template("auth/register.html", form=form)

        user = User(
            email=email,
            username=username,
            role=Role.STUDENT.value,
            is_active=True,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.flush()

        db.session.add(
            UserPreferences(
                user_id=user.id,
                ui_language_code="en",
                learning_language_code="en",
                accent="en-IN",
            )
        )
        db.session.commit()

        session["ai_voice_payload"] = registration_voice_payload(
            username=user.username,
            accent="en-IN",
        )
        audit("register", target=str(user.id), meta="student_self_signup")
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    audit("logout", target=str(current_user.id))
    revoke_current_session()
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@bp.get("/reset")
@bp.post("/reset")
@limiter.limit("10 per hour")
def reset_request():
    form = ResetRequestForm()
    if form.validate_on_submit():
        flash("Password reset flow is available in the next phase.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html", form=form)


@bp.get("/reset/<token>")
@bp.post("/reset/<token>")
@limiter.limit("10 per hour")
def reset_password(token):
    form = ResetPasswordForm()
    if form.validate_on_submit():
        flash("Password reset token flow is available in the next phase.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)
