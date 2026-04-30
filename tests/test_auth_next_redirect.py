from __future__ import annotations

from app.extensions import db
from app.models.user import Role, User
from app.models.user_preferences import UserPreferences


def test_login_redirects_back_to_requested_theme_page(client, app_ctx, monkeypatch):
    monkeypatch.setattr("app.blueprints.auth.routes.should_require_otp", lambda user: (False, "OFF"))

    user = User(
        email="superadmin@example.com",
        username="superadmin",
        role=Role.SUPERADMIN.value,
        is_active=True,
    )
    user.set_password("secret123")
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

    response = client.post(
        "/auth/login?next=%2Ftheme%2Fmanage%2F1%2Fedit",
        data={
            "username_or_email": "superadmin",
            "password": "secret123",
            "next": "/theme/manage/1/edit",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/theme/manage/1/edit")
