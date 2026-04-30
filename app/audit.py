"""Audit logging helpers."""

import hashlib

from flask import request
from flask_login import current_user

from .extensions import db
from .models.audit import AuditLog
from typing import Optional


def audit(action: str, target: Optional[str] = None, meta: Optional[str] = None) -> None:
    """Best-effort audit logging with chained hashes for tamper evidence."""
    try:
        actor_id = getattr(current_user, "id", None) if current_user.is_authenticated else None
        actor_role = getattr(current_user, "role", None) if current_user.is_authenticated else None
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent")
        prev = AuditLog.query.order_by(AuditLog.id.desc()).first()
        prev_hash = getattr(prev, "event_hash", None) if prev else None
        payload = "|".join([
            str(actor_id or ""),
            str(actor_role or ""),
            str(action or ""),
            str(target or ""),
            str(meta or ""),
            str(ip or ""),
            str(ua or ""),
            str(prev_hash or ""),
        ])
        event_hash = hashlib.sha256(payload.encode("utf-8", "ignore")).hexdigest()
        row = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            target=target,
            meta=meta,
            ip=ip,
            user_agent=ua,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
