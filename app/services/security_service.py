from __future__ import annotations

import hashlib
import ipaddress
import json
import random
import re
from datetime import datetime, timedelta

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models.login_event import LoginEvent
from .student_activity_service import StudentActivityService
from ..models.otp_challenge import OtpChallenge
from ..models.security_policy import SecurityPolicy
from ..models.user_security_state import UserSecurityState

SAFE_HTML_TAGS = {"p", "b", "strong", "i", "em", "ul", "ol", "li", "br", "span", "div", "h1", "h2", "h3", "h4", "h5", "h6", "a"}


def get_policy() -> SecurityPolicy:
    return SecurityPolicy.singleton()


def get_client_ip() -> str:
    return (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()


def get_device_hash() -> str:
    raw = "|".join([
        request.headers.get("User-Agent", ""),
        request.headers.get("Accept-Language", ""),
        request.headers.get("Sec-CH-UA-Platform", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()


def _header_first(*names: str) -> str:
    for name in names:
        value = (request.headers.get(name) or "").strip()
        if value:
            return value
    return ""


def parse_client_environment() -> dict[str, str]:
    user_agent = request.headers.get("User-Agent") or ""
    browser = "Unknown"
    os_name = "Unknown"
    if "Chrome" in user_agent and "Edg" not in user_agent:
        browser = "Chrome"
    elif "Edg" in user_agent:
        browser = "Edge"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent and "Chrome" not in user_agent:
        browser = "Safari"
    if "Windows" in user_agent:
        os_name = "Windows"
    elif "Android" in user_agent:
        os_name = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        os_name = "iOS"
    elif "Mac OS X" in user_agent:
        os_name = "macOS"
    elif "Linux" in user_agent:
        os_name = "Linux"
    device_type = "Mobile" if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent else "Desktop"
    return {
        "user_agent": user_agent[:1000],
        "browser": browser,
        "os_name": os_name,
        "device_type": device_type,
    }


def resolve_request_location() -> dict[str, str | None]:
    ip = get_client_ip()
    try:
        parsed_ip = ipaddress.ip_address(ip)
        if parsed_ip.is_loopback:
            return {"country": "Local", "city": "Development"}
        if parsed_ip.is_private:
            return {"country": "Private Network", "city": None}
    except ValueError:
        pass

    country = _header_first(
        "CF-IPCountry",
        "CloudFront-Viewer-Country",
        "X-AppEngine-Country",
        "X-Geo-Country",
        "X-Country",
    )
    city = _header_first(
        "X-AppEngine-City",
        "X-Geo-City",
        "X-City",
        "CF-IPCity",
    )
    return {
        "country": country or None,
        "city": city or None,
    }


def get_user_state(user_id: int) -> UserSecurityState:
    row = UserSecurityState.query.filter_by(user_id=user_id).first()
    if row:
        return row
    row = UserSecurityState(user_id=user_id)
    db.session.add(row)
    db.session.commit()
    return row


def is_locked(user_id: int) -> tuple[bool, int]:
    state = get_user_state(user_id)
    if state.locked_until and state.locked_until > datetime.utcnow():
        remaining = int((state.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
        return True, max(1, remaining)
    return False, 0


def register_failure(user_id: int | None, ip: str, device_hash: str) -> tuple[bool, int]:
    if not user_id:
        return False, 0
    state = get_user_state(user_id)
    policy = get_policy()
    state.failed_attempts = int(state.failed_attempts or 0) + 1
    state.last_failed_at = datetime.utcnow()
    state.last_ip = ip
    state.last_device_hash = device_hash
    if state.failed_attempts >= int(policy.failed_login_threshold or 5):
        state.locked_until = datetime.utcnow() + timedelta(minutes=int(policy.lockout_minutes or 15))
    db.session.commit()
    locked, mins = is_locked(user_id)
    return locked, mins


def reset_failures(user_id: int) -> None:
    state = get_user_state(user_id)
    state.failed_attempts = 0
    state.locked_until = None
    db.session.commit()


def log_login_attempt(user_id: int | None, success: bool, reason: str | None = None) -> None:
    if user_id is None:
        return
    env = parse_client_environment()
    device_hash = get_device_hash()
    location = resolve_request_location()

    ev = LoginEvent(
        user_id=user_id,
        success=success,
        ip_address=get_client_ip(),
        device_hash=device_hash,
        browser=env["browser"],
        os_name=env["os_name"],
        device_type=env["device_type"],
        user_agent=env["user_agent"],
        country=location["country"],
        city=location["city"],
        reason=(reason or "")[:255] or None,
    )
    db.session.add(ev)
    if success:
        StudentActivityService.track_login(user_id, ev.created_at)
    db.session.commit()


def otp_mode_for_user(user) -> str:
    policy = get_policy()
    mode = (policy.otp_mode or "OFF").upper()
    if getattr(user, "role", "") == "ADMIN" and policy.otp_mode_admin:
        mode = policy.otp_mode_admin.upper()
    elif getattr(user, "role", "") == "STUDENT" and policy.otp_mode_student:
        mode = policy.otp_mode_student.upper()
    elif getattr(user, "role", "") in {"SUPERADMIN", "SEO", "SUPPORT", "ACCOUNTS", "SUB_ADMIN", "EDITOR", "TEACHER"} and policy.otp_mode_staff:
        mode = policy.otp_mode_staff.upper()
    return mode if mode in {"OFF", "RISK", "ALWAYS"} else "OFF"


def is_suspicious_login(user) -> bool:
    policy = get_policy()
    cutoff = datetime.utcnow() - timedelta(days=int(policy.suspicious_window_days or 45))
    ip = get_client_ip()
    current_user_agent = (request.headers.get("User-Agent") or "")[:120]
    recent_success = LoginEvent.query.filter(
        LoginEvent.user_id == user.id,
        LoginEvent.success.is_(True),
        LoginEvent.created_at >= cutoff,
    ).order_by(LoginEvent.created_at.desc()).limit(10).all()
    if not recent_success:
        return True
    for ev in recent_success:
        same_ip = (ev.ip_address or "") == ip
        same_ua = (ev.user_agent or "")[:120] == current_user_agent
        if same_ip and same_ua:
            return False
    return True


def should_require_otp(user) -> tuple[bool, str]:
    mode = otp_mode_for_user(user)
    if mode == "OFF":
        return False, "OFF"
    if mode == "ALWAYS":
        return True, "ALWAYS"
    suspicious = is_suspicious_login(user)
    return suspicious, "RISK" if suspicious else "RISK_OK"


def create_otp_challenge(user, reason: str = "RISK") -> str:
    policy = get_policy()
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    sends = OtpChallenge.query.filter(
        OtpChallenge.user_id == user.id,
        OtpChallenge.created_at >= one_hour_ago,
    ).count()
    if sends >= int(policy.otp_max_sends_per_hour or 5):
        raise ValueError("OTP send limit reached for this account. Please try again later.")

    OtpChallenge.query.filter(
        OtpChallenge.user_id == user.id,
        OtpChallenge.used_at.is_(None),
        OtpChallenge.expires_at >= now,
    ).update({"used_at": now})

    code = f"{random.randint(0, 999999):06d}"
    ch = OtpChallenge(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        reason=reason,
        sent_to=getattr(user, "email", None),
        ip=get_client_ip(),
        device_hash=get_device_hash(),
        expires_at=now + timedelta(minutes=int(policy.otp_ttl_minutes or 10)),
        attempts_left=int(policy.otp_max_verify_attempts or 5),
        send_count=sends + 1,
    )
    db.session.add(ch)
    db.session.commit()
    return code


def verify_otp(user_id: int, code: str) -> tuple[bool, str]:
    now = datetime.utcnow()
    ch = OtpChallenge.query.filter(
        OtpChallenge.user_id == user_id,
        OtpChallenge.used_at.is_(None),
    ).order_by(OtpChallenge.id.desc()).first()
    if not ch:
        return False, "No active OTP challenge found."
    if ch.expires_at < now:
        return False, "OTP expired. Please log in again."
    if ch.attempts_left <= 0:
        return False, "OTP verification attempts exceeded. Please log in again."
    if check_password_hash(ch.code_hash, (code or "").strip()):
        ch.used_at = now
        db.session.commit()
        mark_device_trusted(user_id)
        return True, "OTP verified."
    ch.attempts_left -= 1
    db.session.commit()
    return False, f"Invalid OTP. Attempts left: {max(0, ch.attempts_left)}"

def mark_device_trusted(user_id: int) -> None:
    """
    Mark current login device as trusted after successful OTP verification.
    """
    try:
        state = get_user_state(user_id)
        state.last_ip = get_client_ip()
        state.last_device_hash = get_device_hash()
        db.session.commit()
    except Exception:
        db.session.rollback()
        
def sanitize_html(raw: str | None) -> str:
    value = raw or ""
    value = re.sub(r"<\s*(script|iframe|object|embed|style)[^>]*>.*?<\s*/\s*\1\s*>", "", value, flags=re.I | re.S)
    value = re.sub(r'on[a-zA-Z]+\s*=\s*"[^"]*"', "", value, flags=re.I | re.S)
    value = re.sub(r"javascript:\s*", "", value, flags=re.I)
    value = re.sub(r'data:text/html[^"\']*', "", value, flags=re.I)
    return value


def sanitize_json_html_fields(raw_json: str | None) -> str:
    text = raw_json or "[]"
    try:
        data = json.loads(text)
    except Exception:
        return text

    def walk(obj):
        if isinstance(obj, dict):
            clean = {}
            for k, v in obj.items():
                if isinstance(v, str) and ("html" in k.lower() or k.lower() in {"title", "subtitle", "text", "content"}):
                    clean[k] = sanitize_html(v)
                else:
                    clean[k] = walk(v)
            return clean
        if isinstance(obj, list):
            return [walk(i) for i in obj]
        return obj

    return json.dumps(walk(data), ensure_ascii=False, indent=2)


def validate_upload(file_storage):
    policy = get_policy()
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No file selected.")
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {x.strip().lower() for x in (policy.allowed_upload_extensions or "").split(",") if x.strip()}
    if ext not in allowed:
        raise ValueError(f"Invalid file type: .{ext}")
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > int(policy.max_upload_mb or 5) * 1024 * 1024:
        raise ValueError(f"File too large. Max allowed is {int(policy.max_upload_mb or 5)} MB.")
    return filename, ext, size

def apply_security_policy_updates(policy, form):
    """
    Update SecurityPolicy model from SuperAdmin security form.
    """
    policy.otp_mode = form.otp_mode.data
    policy.otp_mode_student = form.otp_mode_student.data
    policy.otp_mode_admin = form.otp_mode_admin.data
    policy.otp_mode_staff = form.otp_mode_staff.data

    policy.otp_ttl_minutes = form.otp_ttl_minutes.data
    policy.otp_max_sends_per_hour = form.otp_max_sends_per_hour.data or form.otp_rate_limit.data or 5
    policy.otp_max_verify_attempts = form.otp_max_verify_attempts.data

    policy.failed_login_threshold = form.failed_login_threshold.data
    policy.lockout_minutes = form.lockout_minutes.data or form.failed_login_lock_minutes.data or 15

    policy.suspicious_window_days = form.suspicious_window_days.data
    policy.trust_device_days = form.trust_device_days.data
    policy.csp_report_only = form.csp_report_only.data
    policy.csp_report_uri = form.csp_report_uri.data

    policy.api_rate_limit = form.api_rate_limit.data
    policy.ai_rate_limit = form.ai_rate_limit.data
    policy.max_upload_mb = form.max_upload_mb.data
    policy.allowed_upload_extensions = (form.allowed_upload_extensions.data or "").strip().lower()

    # Keep alias fields in sync for templates or older handlers that still read them.
    form.otp_rate_limit.data = policy.otp_max_sends_per_hour
    form.failed_login_lock_minutes.data = policy.lockout_minutes

    db.session.add(policy)
    db.session.commit()
