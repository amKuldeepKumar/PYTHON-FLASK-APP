"""Phase 2: RBAC enforcement decorators."""

from functools import wraps

from flask import abort
from flask_login import current_user

from .audit import audit


def _current_role_code() -> str:
    return (getattr(current_user, "role_code", None) or getattr(current_user, "role", "") or "").strip().upper()


def require_role(*role_codes: str):
    normalized_codes = {code.strip().upper() for code in role_codes}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if _current_role_code() not in normalized_codes:
                audit("access_denied", target=str(getattr(current_user, "id", None)), meta=f"require_role:{tuple(normalized_codes)}")
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_perm(perm_code: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not getattr(current_user, "has_perm", lambda _p: False)(perm_code):
                audit("access_denied", target=str(getattr(current_user, "id", None)), meta=f"require_perm:{perm_code}")
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator