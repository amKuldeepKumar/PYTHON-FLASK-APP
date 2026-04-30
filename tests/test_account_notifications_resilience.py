from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import text


def test_notifications_page_recovers_when_notifications_table_is_missing(monkeypatch):
    tmp_dir = tempfile.mkdtemp(prefix="fluencify-notifications-resilience-")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + Path(tmp_dir, "app.db").as_posix())
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLUENCIFY_SKIP_DEV_BOOTSTRAP", "1")

    from app import create_app
    from app.extensions import db
    from app.models.user import Role, User
    from app.models.user_session import UserSession

    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()

        stamp = int(datetime.utcnow().timestamp() * 1000000)
        user = User(
            email=f"notifications-test-{stamp}@example.com",
            username=f"notifications-test-{stamp}",
            role=Role.STUDENT.value,
            password_hash="hashed",
        )
        db.session.add(user)
        db.session.commit()

        db.session.execute(text("DROP TABLE notifications"))
        db.session.commit()

        client = app.test_client()
        token = f"test-session-{user.id}"
        session_row = UserSession(
            user_id=user.id,
            session_key_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            device_hash="test-device",
            ip_address="127.0.0.1",
            browser="Chrome",
            os_name="Windows",
            device_type="desktop",
            user_agent="pytest",
            country="Local",
            city="Dev",
            is_current=True,
            last_seen_at=datetime.utcnow(),
        )
        db.session.add(session_row)
        db.session.commit()

        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
            session["auth_session_token"] = token

        response = client.get("/account/notifications")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Notifications" in html
