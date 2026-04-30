from __future__ import annotations

from sqlalchemy.exc import OperationalError


def test_tokens_css_falls_back_when_theme_query_breaks(client, app_ctx, monkeypatch):
    def _boom(*args, **kwargs):
        raise OperationalError("select", {}, Exception("no such table: themes"))

    monkeypatch.setattr("app.blueprints.theme.routes.Theme.query", type("BrokenQuery", (), {"filter_by": staticmethod(_boom)})())

    response = client.get("/theme/tokens.css")

    assert response.status_code == 200
    css = response.get_data(as_text=True)
    assert ":root" in css
    assert "--bg:#0b1220;" in css


def test_overrides_css_returns_empty_when_theme_query_breaks(client, app_ctx, monkeypatch):
    def _boom(*args, **kwargs):
        raise OperationalError("select", {}, Exception("no such table: themes"))

    monkeypatch.setattr("app.blueprints.theme.routes.Theme.query", type("BrokenQuery", (), {"filter_by": staticmethod(_boom)})())

    response = client.get("/theme/overrides.css")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == ""
