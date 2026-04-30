"""Phase Coverage:
- Phase 1: Centralized extension objects (db, migrate, login, csrf, limiter).

Why:
- Keeps create_app() clean and avoids circular imports.

Future:
- Phase 12+: add caching (Redis), background jobs (Celery/RQ), mail, sockets, etc.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)
