"""
Phase Coverage:
- Phase 1: Environment-based configuration (dev/stage/prod) using .env.

Future:
- Phase 4: security policies and OTP policies config
- Phase 12: provider registry config defaults, AI quotas, translation provider selection
- Phase 15: production loggers, Sentry, advanced CSP enforcement
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def _default_sqlite_uri() -> str:
    db_path = INSTANCE_DIR / "app.db"
    return f"sqlite:///{db_path.as_posix()}"


def _normalize_database_url(uri: str | None) -> str:
    """
    Make SQLite paths reliable on Windows and when running from CMD.

    Rules:
    - If DATABASE_URL is missing, use /instance/app.db
    - If sqlite path is relative, convert it to an absolute path
    - If sqlite path is absolute already, keep it
    """
    if not uri:
        return _default_sqlite_uri()

    if uri.startswith("sqlite:///"):
        raw_path = uri.replace("sqlite:///", "", 1).strip()

        if raw_path == ":memory:":
            return uri

        if os.path.isabs(raw_path):
            db_file = Path(raw_path)
        else:
            db_file = (BASE_DIR / raw_path).resolve()

        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file.as_posix()}"

    return uri


@dataclass(frozen=True)
class BaseConfig:
    ENV_NAME: str = "base"
    SECRET_KEY: str = _env("SECRET_KEY", "dev-secret-change-me") or "dev-secret-change-me"

    SQLALCHEMY_DATABASE_URI: str = _normalize_database_url(_env("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    WTF_CSRF_TIME_LIMIT = None

    FORCE_HTTPS: bool = (_env("FORCE_HTTPS", "0") == "1")

    RATELIMIT_ENABLED: bool = (_env("RATELIMIT_ENABLED", "1") == "1")
    RATELIMIT_DEFAULT: str = _env("RATELIMIT_DEFAULT", "200 per hour") or "200 per hour"

    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = _env("SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
    SESSION_COOKIE_SECURE: bool = (_env("SESSION_COOKIE_SECURE", "0") == "1")

    REMEMBER_COOKIE_HTTPONLY: bool = True
    REMEMBER_COOKIE_SAMESITE: str = _env("REMEMBER_COOKIE_SAMESITE", "Lax") or "Lax"
    REMEMBER_COOKIE_SECURE: bool = (_env("REMEMBER_COOKIE_SECURE", "0") == "1")

    OTP_DEV_MODE: bool = (_env("OTP_DEV_MODE", "1") == "1")
    MAX_CONTENT_LENGTH: int = int(_env("MAX_CONTENT_LENGTH_MB", "8") or "8") * 1024 * 1024


class DevConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True


class StageConfig(BaseConfig):
    ENV_NAME = "staging"
    DEBUG = False


class ProdConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False


def get_config():
    env = (_env("FLASK_ENV", "development") or "development").lower()

    def _runtime_config(base_cls):
        class RuntimeConfig(base_cls):
            SECRET_KEY = _env("SECRET_KEY", "dev-secret-change-me") or "dev-secret-change-me"
            SQLALCHEMY_DATABASE_URI = _normalize_database_url(_env("DATABASE_URL"))
            FORCE_HTTPS = (_env("FORCE_HTTPS", "0") == "1")
            RATELIMIT_ENABLED = (_env("RATELIMIT_ENABLED", "1") == "1")
            RATELIMIT_DEFAULT = _env("RATELIMIT_DEFAULT", "200 per hour") or "200 per hour"
            SESSION_COOKIE_SAMESITE = _env("SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
            SESSION_COOKIE_SECURE = (_env("SESSION_COOKIE_SECURE", "0") == "1")
            REMEMBER_COOKIE_SAMESITE = _env("REMEMBER_COOKIE_SAMESITE", "Lax") or "Lax"
            REMEMBER_COOKIE_SECURE = (_env("REMEMBER_COOKIE_SECURE", "0") == "1")
            OTP_DEV_MODE = (_env("OTP_DEV_MODE", "1") == "1")
            MAX_CONTENT_LENGTH = int(_env("MAX_CONTENT_LENGTH_MB", "8") or "8") * 1024 * 1024

        RuntimeConfig.__name__ = f"Runtime{base_cls.__name__}"
        return RuntimeConfig

    if env in ("prod", "production"):
        return _runtime_config(ProdConfig)
    if env in ("stage", "staging"):
        return _runtime_config(StageConfig)
    return _runtime_config(DevConfig)
