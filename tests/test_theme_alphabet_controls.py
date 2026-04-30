from __future__ import annotations

import hashlib
from datetime import datetime

from app.extensions import db
from app.models.theme import Theme
from app.models.user import Role, User
from app.models.user_session import UserSession


def _login_superadmin(client) -> User:
    user = User(
        email=f"superadmin-{datetime.utcnow().timestamp()}@example.com",
        username=f"superadmin-{int(datetime.utcnow().timestamp() * 1000000)}",
        role=Role.SUPERADMIN.value,
        password_hash="hashed",
    )
    db.session.add(user)
    db.session.commit()

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

    return user


def test_theme_update_persists_new_alphabet_controls_and_tokens(client, app_ctx):
    _login_superadmin(client)
    theme = Theme.ensure_default()

    response = client.post(
        f"/theme/manage/{theme.id}/edit",
        data={
            "name": theme.name,
            "alphabet_background_enabled": "1",
            "alphabet_trails_enabled": "1",
            "alphabet_outline_only": "1",
            "alphabet_motion_mode": "drift",
            "alphabet_outline_color": "#5ac8fa",
            "alphabet_min_size": "28",
            "alphabet_max_size": "92",
            "alphabet_count": "48",
            "alphabet_direction_x": "-24",
            "alphabet_direction_y": "88",
            "alphabet_speed": "135",
            "alphabet_opacity": "61",
            "alphabet_trail_length": "9",
            "alphabet_tilt_x": "22",
            "alphabet_tilt_y": "17",
            "alphabet_tilt_z": "36",
            "alphabet_rotation_depth": "74",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    db.session.refresh(theme)
    assert theme.alphabet_outline_only is True
    assert theme.alphabet_outline_color == "#5ac8fa"
    assert theme.alphabet_tilt_x == 22
    assert theme.alphabet_tilt_y == 17
    assert theme.alphabet_tilt_z == 36
    assert theme.alphabet_motion_mode == "drift"
    assert theme.alphabet_min_size == 28
    assert theme.alphabet_max_size == 92

    css_response = client.get("/theme/tokens.css")
    css = css_response.get_data(as_text=True)

    assert css_response.status_code == 200
    assert "--alphabet-outline-only:1;" in css
    assert "--alphabet-outline-color:#5ac8fa;" in css
    assert "--alphabet-tilt-x:22;" in css
    assert "--alphabet-tilt-y:17;" in css
    assert "--alphabet-tilt-z:36;" in css


def test_duplicate_theme_copies_extended_alphabet_controls(client, app_ctx):
    _login_superadmin(client)

    source_theme = Theme(
        name="Source Theme",
        alphabet_background_enabled=True,
        alphabet_trails_enabled=False,
        alphabet_rotation_depth=66,
        alphabet_speed=142,
        alphabet_min_size=26,
        alphabet_max_size=88,
        alphabet_count=37,
        alphabet_motion_mode="shooting",
        alphabet_direction_x=12,
        alphabet_direction_y=72,
        alphabet_opacity=57,
        alphabet_trail_length=8,
        alphabet_tilt_x=20,
        alphabet_tilt_y=13,
        alphabet_tilt_z=31,
        alphabet_outline_only=True,
        alphabet_outline_color="#12d6a0",
    )
    db.session.add(source_theme)
    db.session.commit()

    response = client.post(
        f"/theme/manage/{source_theme.id}/duplicate",
        follow_redirects=True,
    )

    assert response.status_code == 200

    clone = Theme.query.filter_by(name="Source Theme Copy").first()
    assert clone is not None
    assert clone.alphabet_background_enabled is True
    assert clone.alphabet_trails_enabled is False
    assert clone.alphabet_motion_mode == "shooting"
    assert clone.alphabet_min_size == 26
    assert clone.alphabet_max_size == 88
    assert clone.alphabet_count == 37
    assert clone.alphabet_tilt_x == 20
    assert clone.alphabet_tilt_y == 13
    assert clone.alphabet_tilt_z == 31
    assert clone.alphabet_outline_only is True
    assert clone.alphabet_outline_color == "#12d6a0"
