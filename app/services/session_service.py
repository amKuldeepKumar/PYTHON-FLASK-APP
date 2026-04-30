from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from flask import request, session
from flask_login import current_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models.device_preference import DevicePreference
from ..models.user_session import UserSession
from .security_service import get_client_ip, get_device_hash, parse_client_environment, resolve_request_location


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8", "ignore")).hexdigest()


def get_or_create_device_key() -> str:
    device_key = session.get("device_pref_key")
    if device_key:
        return device_key
    device_key = secrets.token_hex(24)
    session["device_pref_key"] = device_key
    session.permanent = True
    return device_key


def _recover_device_preference_schema() -> None:
    try:
        db.session.rollback()
        from ..schema_bootstrap import ensure_dev_sqlite_schema

        ensure_dev_sqlite_schema()
        db.session.remove()
    except Exception:
        db.session.rollback()


def get_device_preference(default_ui: str = "en", default_learning: str = "en") -> DevicePreference:
    device_key = get_or_create_device_key()
    try:
        row = DevicePreference.query.filter_by(device_key=device_key).first()
        if row:
            return row
        row = DevicePreference(
            device_key=device_key,
            user_id=getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
            ui_language_code=default_ui,
            learning_language_code=default_learning,
        )
        db.session.add(row)
        db.session.commit()
        return row
    except SQLAlchemyError:
        _recover_device_preference_schema()
        row = DevicePreference.query.filter_by(device_key=device_key).first()
        if row:
            return row
        row = DevicePreference(
            device_key=device_key,
            user_id=getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
            ui_language_code=default_ui,
            learning_language_code=default_learning,
        )
        db.session.add(row)
        db.session.commit()
        return row


def sync_device_preferences(ui_language_code: str, learning_language_code: str, user_id: int | None = None) -> DevicePreference:
    row = get_device_preference(default_ui=ui_language_code or "en", default_learning=learning_language_code or "en")
    row.ui_language_code = (ui_language_code or row.ui_language_code or "en").strip().lower()
    row.learning_language_code = (learning_language_code or row.learning_language_code or "en").strip().lower()
    if user_id:
        row.user_id = user_id
    db.session.commit()
    return row


def issue_session(user) -> UserSession:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    env = parse_client_environment()
    location = resolve_request_location()

    row = UserSession(
        user_id=user.id,
        session_key_hash=token_hash,
        device_hash=get_device_hash(),
        ip_address=get_client_ip(),
        browser=env["browser"],
        os_name=env["os_name"],
        device_type=env["device_type"],
        user_agent=env["user_agent"],
        country=location["country"],
        city=location["city"],
        is_current=True,
        last_seen_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()

    session["auth_session_token"] = token
    session.permanent = True
    if user:
        sync_device_preferences(
            getattr(getattr(user, "preferences", None), "ui_language_code", "en"),
            getattr(getattr(user, "preferences", None), "learning_language_code", "en"),
            user_id=user.id,
        )
    return row


def get_current_session_row() -> UserSession | None:
    token = session.get("auth_session_token")
    if not token or not getattr(current_user, "is_authenticated", False):
        return None
    return UserSession.query.filter_by(
        user_id=current_user.id,
        session_key_hash=_hash_token(token),
    ).first()


def touch_current_session() -> None:
    row = get_current_session_row()
    if not row or row.revoked_at is not None:
        return
    location = resolve_request_location()
    row.last_seen_at = datetime.utcnow()
    row.ip_address = get_client_ip()
    row.country = location["country"]
    row.city = location["city"]
    db.session.commit()


def revoke_current_session() -> None:
    row = get_current_session_row()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        row.is_current = False
        db.session.commit()
    session.pop("auth_session_token", None)


def revoke_other_sessions(user_id: int) -> int:
    token = session.get("auth_session_token")
    keep_hash = _hash_token(token) if token else None
    rows = UserSession.query.filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None)).all()
    count = 0
    for row in rows:
        if keep_hash and row.session_key_hash == keep_hash:
            continue
        row.revoked_at = datetime.utcnow()
        row.is_current = False
        count += 1
    db.session.commit()
    return count


def revoke_session_for_user(user_id: int, session_id: int) -> bool:
    row = UserSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not row or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.utcnow()
    row.is_current = False
    db.session.commit()
    return True


def enforce_session_guard() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return True
    row = get_current_session_row()
    if row is None or row.revoked_at is not None:
        logout_user()
        session.pop("auth_session_token", None)
        return False
    touch_current_session()
    return True
