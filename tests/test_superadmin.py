from __future__ import annotations

from app.core.config import settings


def test_superadmin_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")
    r = client.get("/superadmin/")
    assert r.status_code == 401


def test_superadmin_list_ok_with_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")
    r = client.get("/superadmin/", headers={"x-superadmin-secret": "secret123"})
    assert r.status_code == 200
    assert "Super Admin" in r.text

