from __future__ import annotations

import tempfile
from pathlib import Path


def test_ensure_local_dev_users_repairs_partial_local_database(monkeypatch):
    tmp_dir = tempfile.mkdtemp(prefix="fluencify-dev-seed-")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + Path(tmp_dir, "app.db").as_posix())
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLUENCIFY_SKIP_DEV_BOOTSTRAP", "1")

    from app import create_app
    from app.extensions import db
    from app.models.user import Role, User
    from app.services.dev_seed_service import ensure_local_dev_users

    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()

        user = User(
            email="superadmin@example.com",
            username="superadmin",
            role=Role.SUPERADMIN.value,
            is_active=True,
        )
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

        ensure_local_dev_users()

        repaired_superadmin = User.query.filter_by(username="superadmin").first()
        admin = User.query.filter_by(username="admin").first()
        student = User.query.filter_by(username="student").first()

        assert repaired_superadmin is not None
        assert repaired_superadmin.check_password("Admin@123") is True
        assert admin is not None
        assert admin.check_password("Admin@123") is True
        assert student is not None
        assert student.check_password("Student@123") is True
