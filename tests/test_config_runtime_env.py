from __future__ import annotations

from app.config import get_config


def test_get_config_reads_database_url_from_current_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///instance/runtime-a.db")
    first = get_config()

    monkeypatch.setenv("DATABASE_URL", "sqlite:///instance/runtime-b.db")
    second = get_config()

    assert first.SQLALCHEMY_DATABASE_URI.endswith("/instance/runtime-a.db")
    assert second.SQLALCHEMY_DATABASE_URI.endswith("/instance/runtime-b.db")
    assert first.SQLALCHEMY_DATABASE_URI != second.SQLALCHEMY_DATABASE_URI
