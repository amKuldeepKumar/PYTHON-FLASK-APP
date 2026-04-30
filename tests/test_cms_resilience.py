from __future__ import annotations

from sqlalchemy.exc import OperationalError


def test_homepage_falls_back_when_pages_table_query_breaks(client, app_ctx, monkeypatch):
    def _boom(*args, **kwargs):
        raise OperationalError("select", {}, Exception("no such table: pages"))

    monkeypatch.setattr(
        "app.services.cms_service.Page.query",
        type("BrokenQuery", (), {"filter_by": staticmethod(_boom)})(),
    )

    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Know your" in html
    assert "English level" in html
    assert "Start Free Test" in html
